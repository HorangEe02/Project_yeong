"""Optional NAVER Cloud CLOVA OCR fallback provider."""

from __future__ import annotations

import base64
import time
from collections.abc import Mapping
from typing import Any, Protocol
from uuid import uuid4

import httpx

from src.config import Settings
from src.ocr.base import (
    OCRAdapter,
    OCRBlock,
    OCRBoundingPoly,
    OCRError,
    OCRImageInput,
    OCRPage,
    OCRParagraph,
    OCRResult,
    OCRVertex,
    OCRWord,
)

CLOVA_OCR_PROVIDER = "clova_ocr"
HTTP_ERROR_STATUS_MIN = 400


class ClovaHTTPResponse(Protocol):
    """Protocol for the HTTP response fields used by the CLOVA adapter."""

    status_code: int

    def json(self) -> Any:
        """Return parsed JSON response.

        Returns:
            Parsed JSON payload.
        """
        ...


class ClovaHTTPClient(Protocol):
    """Protocol for the async HTTP client used by the CLOVA adapter."""

    async def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> ClovaHTTPResponse:
        """Post a CLOVA OCR request.

        Args:
            url: Request URL.
            json: Request payload.
            headers: Request headers.
            timeout: Request timeout.

        Returns:
            HTTP response.
        """
        ...


class ClovaOCRAdapter(OCRAdapter):
    """External CLOVA OCR adapter used only as an explicit fallback.

    The adapter sends image bytes to NAVER Cloud CLOVA OCR, so callers must keep
    ``ALLOW_EXTERNAL_OCR`` and external OCR consent gates enforced before use.
    """

    def __init__(self, settings: Settings, client: ClovaHTTPClient | None = None) -> None:
        """Initialize the adapter.

        Args:
            settings: Runtime settings.
            client: Optional injected HTTP client for tests.
        """
        self._settings = settings
        self._client = client

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Extract text with NAVER Cloud CLOVA OCR.

        Args:
            image: Validated OCR image input.

        Returns:
            OCR result with joined text and averaged confidence when available.

        Raises:
            OCRError: If external OCR is disabled, credentials are missing, or
                CLOVA returns an invalid response.
        """
        _validate_clova_settings(self._settings)
        payload = _build_clova_payload(image)
        headers = _build_clova_headers(self._settings)
        response_payload = await self._post(payload=payload, headers=headers)
        return _parse_clova_response(response_payload)

    async def _post(
        self,
        *,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Post a CLOVA OCR request.

        Args:
            payload: Request payload.
            headers: Request headers.

        Returns:
            Parsed JSON object.

        Raises:
            OCRError: If transport or response parsing fails.
        """
        try:
            if self._client is not None:
                response = await self._client.post(
                    self._settings.clova_ocr_api_url or "",
                    json=payload,
                    headers=headers,
                    timeout=self._settings.google_vision_timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self._settings.google_vision_timeout_seconds
                ) as client:
                    response = await client.post(
                        self._settings.clova_ocr_api_url or "",
                        json=payload,
                        headers=headers,
                    )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise OCRError("CLOVA OCR transport failure.") from exc

        if response.status_code >= HTTP_ERROR_STATUS_MIN:
            raise OCRError(f"CLOVA OCR request failed: status {response.status_code}.")
        try:
            parsed = response.json()
        except ValueError as exc:
            raise OCRError("CLOVA OCR returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise OCRError("CLOVA OCR returned an invalid response shape.")
        return parsed


def _validate_clova_settings(settings: Settings) -> None:
    """Validate CLOVA OCR settings before sending image bytes.

    Args:
        settings: Runtime settings.

    Raises:
        OCRError: If required external OCR settings are missing.
    """
    if not settings.enable_clova_ocr:
        raise OCRError("ENABLE_CLOVA_OCR=true is required for CLOVA fallback.")
    if not settings.allow_external_ocr:
        raise OCRError("ALLOW_EXTERNAL_OCR=true is required for CLOVA OCR.")
    if not settings.clova_ocr_api_url:
        raise OCRError("CLOVA_OCR_API_URL is required for CLOVA OCR.")
    if settings.clova_ocr_secret is None:
        raise OCRError("CLOVA_OCR_SECRET is required for CLOVA OCR.")


def _build_clova_headers(settings: Settings) -> dict[str, str]:
    """Build CLOVA request headers without logging secrets.

    Args:
        settings: Runtime settings.

    Returns:
        Request headers.
    """
    secret = settings.clova_ocr_secret
    if secret is None:
        raise OCRError("CLOVA_OCR_SECRET is required for CLOVA OCR.")
    return {
        "Content-Type": "application/json",
        "X-OCR-SECRET": secret.get_secret_value(),
    }


def _build_clova_payload(image: OCRImageInput) -> dict[str, object]:
    """Build a CLOVA OCR JSON request payload.

    Args:
        image: Validated OCR image input.

    Returns:
        JSON payload.
    """
    return {
        "version": "V2",
        "requestId": str(uuid4()),
        "timestamp": int(time.time() * 1000),
        "images": [
            {
                "format": _clova_format_for_mime_type(image.mime_type),
                "name": "supplement_label",
                "data": base64.b64encode(image.image_bytes).decode("ascii"),
            }
        ],
    }


def _clova_format_for_mime_type(mime_type: str) -> str:
    """Return CLOVA image format token for a MIME type.

    Args:
        mime_type: Validated image MIME type.

    Returns:
        CLOVA image format.
    """
    if mime_type == "image/jpeg":
        return "jpg"
    if mime_type == "image/webp":
        return "png"
    return "png"


def _parse_clova_response(payload: dict[str, Any]) -> OCRResult:
    """Normalize CLOVA OCR response JSON.

    Args:
        payload: Parsed CLOVA response.

    Returns:
        OCR result.

    Raises:
        OCRError: If no successful text fields are present.
    """
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise OCRError("CLOVA OCR response is missing images.")
    first_image = images[0]
    if not isinstance(first_image, dict):
        raise OCRError("CLOVA OCR response image shape is invalid.")

    infer_result = first_image.get("inferResult")
    if isinstance(infer_result, str) and infer_result not in {"SUCCESS", ""}:
        raise OCRError(f"CLOVA OCR inference failed: {infer_result}.")

    fields = first_image.get("fields")
    if not isinstance(fields, list):
        raise OCRError("CLOVA OCR response is missing fields.")

    fragments: list[str] = []
    confidences: list[float] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        text = field.get("inferText")
        if isinstance(text, str) and text.strip():
            fragments.append(text.strip())
        confidence = field.get("inferConfidence")
        if isinstance(confidence, int | float) and 0 <= confidence <= 1:
            confidences.append(float(confidence))

    if not fragments:
        raise OCRError("CLOVA OCR returned no readable text.")
    return OCRResult(
        text="\n".join(_dedupe_preserve_order(fragments)),
        provider=CLOVA_OCR_PROVIDER,
        confidence=_average(confidences),
        pages=_extract_layout_pages(first_image),
    )


def _extract_layout_pages(image_payload: dict[str, Any]) -> tuple[OCRPage, ...]:
    """Normalize CLOVA OCR fields into the OCR layout contract.

    Args:
        image_payload: One CLOVA image response object.

    Returns:
        One OCR page with line-level blocks, or an empty tuple when no fields are usable.
    """
    fields = image_payload.get("fields")
    if not isinstance(fields, list):
        return ()
    blocks = tuple(
        _layout_block(
            text=text,
            confidence=confidence,
            bounding_box=bounding_box,
            index=index,
        )
        for index, (text, confidence, bounding_box) in enumerate(_layout_lines(fields))
    )
    if not blocks:
        return ()
    image_info = image_payload.get("convertedImageInfo")
    if not isinstance(image_info, dict):
        image_info = {}
    return (
        OCRPage(
            width=_optional_int(image_info.get("width")),
            height=_optional_int(image_info.get("height")),
            confidence=_average(
                [block.confidence for block in blocks if block.confidence is not None]
            ),
            blocks=blocks,
        ),
    )


def _layout_lines(
    fields: list[object],
) -> list[tuple[str, float | None, OCRBoundingPoly | None]]:
    """Return line-level CLOVA OCR fields in provider order.

    Args:
        fields: CLOVA ``fields`` response array.

    Returns:
        Text, confidence, and optional bounding polygon tuples.
    """
    lines: list[tuple[str, float | None, OCRBoundingPoly | None]] = []
    seen: set[tuple[str, tuple[tuple[float, float], ...]]] = set()
    for field in fields:
        if not isinstance(field, dict):
            continue
        _append_layout_line(field, lines=lines, seen=seen)
        sub_fields = field.get("subFields")
        if isinstance(sub_fields, list):
            for sub_field in sub_fields:
                if isinstance(sub_field, dict):
                    _append_layout_line(sub_field, lines=lines, seen=seen)
    return lines


def _append_layout_line(
    field: dict[object, object],
    *,
    lines: list[tuple[str, float | None, OCRBoundingPoly | None]],
    seen: set[tuple[str, tuple[tuple[float, float], ...]]],
) -> None:
    """Append one sanitized CLOVA layout line when text is present."""
    text = field.get("inferText")
    if not isinstance(text, str) or not text.strip():
        return
    stripped = text.strip()
    bounding_box = _parse_bounding_poly(field.get("boundingPoly"))
    fingerprint = (stripped, _poly_fingerprint(bounding_box))
    if fingerprint in seen:
        return
    seen.add(fingerprint)
    lines.append(
        (
            stripped,
            _optional_confidence(field.get("inferConfidence")),
            bounding_box,
        )
    )


def _layout_block(
    *,
    text: str,
    confidence: float | None,
    bounding_box: OCRBoundingPoly | None,
    index: int,
) -> OCRBlock:
    """Build a line-level OCR block from one CLOVA field."""
    word = OCRWord(
        text=text,
        confidence=confidence,
        bounding_box=bounding_box,
        block_index=index,
        paragraph_index=0,
        word_index=0,
    )
    paragraph = OCRParagraph(
        text=text,
        confidence=confidence,
        bounding_box=bounding_box,
        words=(word,),
    )
    return OCRBlock(
        text=text,
        confidence=confidence,
        bounding_box=bounding_box,
        block_type="TEXT",
        paragraphs=(paragraph,),
    )


def _parse_bounding_poly(value: object) -> OCRBoundingPoly | None:
    """Parse CLOVA ``boundingPoly.vertices`` into provider-neutral vertices."""
    if not isinstance(value, dict):
        return None
    raw_vertices = value.get("vertices")
    if not isinstance(raw_vertices, list):
        return None
    vertices: list[OCRVertex] = []
    for raw_vertex in raw_vertices:
        if not isinstance(raw_vertex, dict):
            continue
        x = _optional_float(raw_vertex.get("x"))
        y = _optional_float(raw_vertex.get("y"))
        if x is not None and y is not None:
            vertices.append(OCRVertex(x=x, y=y))
    if not vertices:
        return None
    return OCRBoundingPoly(vertices=tuple(vertices))


def _poly_fingerprint(poly: OCRBoundingPoly | None) -> tuple[tuple[float, float], ...]:
    """Return a stable fingerprint for layout-line deduplication."""
    if poly is None:
        return ()
    return tuple((vertex.x, vertex.y) for vertex in poly.vertices)


def _optional_confidence(value: object) -> float | None:
    """Return a bounded confidence value when present."""
    if isinstance(value, int | float) and 0 <= value <= 1:
        return float(value)
    return None


def _optional_int(value: object) -> int | None:
    """Return a non-negative integer value when present."""
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _optional_float(value: object) -> float | None:
    """Return a numeric value when present."""
    if isinstance(value, int | float):
        return float(value)
    return None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Deduplicate values while preserving first-seen order.

    Args:
        values: Raw values.

    Returns:
        Deduplicated values.
    """
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped


def _average(values: list[float]) -> float | None:
    """Average values when present.

    Args:
        values: Confidence values.

    Returns:
        Average confidence or None.
    """
    if not values:
        return None
    return sum(values) / len(values)
