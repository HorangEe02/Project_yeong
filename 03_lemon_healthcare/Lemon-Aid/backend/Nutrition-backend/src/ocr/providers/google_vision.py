"""Google Cloud Vision OCR provider for supplement label images."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any, Literal

import httpx

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
from src.ocr.providers.google_vision_auth import (
    GoogleVisionAuthError,
    GoogleVisionAuthHeadersProvider,
)

GOOGLE_VISION_PROVIDER = "google_vision_document"
GOOGLE_VISION_GLOBAL_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
GOOGLE_VISION_FEATURE_TYPES = {"document_text_detection": "DOCUMENT_TEXT_DETECTION"}
HTTP_ERROR_STATUS_MIN = 400
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
GoogleVisionLocation = Literal["global", "us", "eu"]
GoogleVisionFeature = Literal["document_text_detection"]


class GoogleVisionOCRAdapter(OCRAdapter):
    """OCR adapter that calls Google Cloud Vision document text detection."""

    def __init__(
        self,
        *,
        auth_headers: GoogleVisionAuthHeadersProvider,
        endpoint: str = GOOGLE_VISION_GLOBAL_ENDPOINT,
        feature: GoogleVisionFeature = "document_text_detection",
        language_hints: Sequence[str] = (),
        timeout_seconds: int = 15,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Google Vision OCR adapter.

        Args:
            auth_headers: Provider for API-key or ADC bearer headers.
            endpoint: Google Vision REST endpoint.
            feature: OCR feature selector. MVP supports document text detection.
            language_hints: Optional OCR language hints.
            timeout_seconds: Per-request timeout.
            max_retries: Retries for transient provider failures.
            client: Optional injected HTTP client for tests.
        """
        self._auth_headers = auth_headers
        self._endpoint = endpoint
        self._feature = feature
        self._language_hints = tuple(language_hints)
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = client

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Extract dense label text with Google Vision.

        Args:
            image: Validated supplement label image payload.

        Returns:
            OCR text, provider label, and optional confidence.

        Raises:
            OCRError: If Google Vision authentication, transport, or response parsing fails.
        """
        payload = self._build_payload(image)
        headers = await self._build_headers()
        response_payload = await self._post_with_retries(payload=payload, headers=headers)
        return _parse_google_vision_response(response_payload)

    async def _build_headers(self) -> dict[str, str]:
        """Build sanitized request headers for Google Vision.

        Returns:
            Request headers.

        Raises:
            OCRError: If authentication headers cannot be built.
        """
        try:
            headers = await self._auth_headers.build_headers()
        except GoogleVisionAuthError as exc:
            raise OCRError("Google Vision authentication is not available.") from exc
        return {"Content-Type": "application/json; charset=utf-8", **headers}

    def _build_payload(self, image: OCRImageInput) -> dict[str, object]:
        """Build a Google Vision annotate request payload.

        Args:
            image: Validated image payload.

        Returns:
            JSON request payload.
        """
        request: dict[str, object] = {
            "image": {"content": base64.b64encode(image.image_bytes).decode("ascii")},
            "features": [{"type": GOOGLE_VISION_FEATURE_TYPES[self._feature]}],
        }
        if self._language_hints:
            request["imageContext"] = {"languageHints": list(self._language_hints)}
        return {"requests": [request]}

    async def _post_with_retries(
        self,
        *,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Post to Google Vision with bounded transient retries.

        Args:
            payload: JSON request payload.
            headers: Sanitized request headers.

        Returns:
            Parsed JSON response.

        Raises:
            OCRError: If all attempts fail or a non-retryable response is returned.
        """
        attempts = self._max_retries + 1
        last_error: OCRError | None = None
        for attempt_index in range(attempts):
            try:
                response = await self._post_once(payload=payload, headers=headers)
                if response.status_code in TRANSIENT_STATUS_CODES and attempt_index < attempts - 1:
                    last_error = OCRError(
                        f"Google Vision OCR transient failure: status {response.status_code}."
                    )
                    continue
                return _parse_response_json(response)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = OCRError("Google Vision OCR transport failure.")
                if attempt_index >= attempts - 1:
                    raise last_error from exc
        if last_error is not None:
            raise last_error
        raise OCRError("Google Vision OCR request failed.")

    async def _post_once(
        self,
        *,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> httpx.Response:
        """Execute one HTTP request.

        Args:
            payload: JSON request payload.
            headers: Sanitized request headers.

        Returns:
            HTTP response.
        """
        if self._client is not None:
            return await self._client.post(self._endpoint, json=payload, headers=headers)
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            return await client.post(self._endpoint, json=payload, headers=headers)


def build_google_vision_endpoint(
    *,
    project_id: str | None,
    location: GoogleVisionLocation,
) -> str:
    """Build the REST endpoint for a Google Vision OCR location.

    Args:
        project_id: Google Cloud project for regional OCR endpoints.
        location: OCR processing location.

    Returns:
        Google Vision REST endpoint.

    Raises:
        ValueError: If a regional endpoint is requested without a project.
    """
    if location == "global":
        return GOOGLE_VISION_GLOBAL_ENDPOINT
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT is required for regional Google Vision OCR.")
    return (
        f"https://{location}-vision.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/images:annotate"
    )


def _parse_response_json(response: httpx.Response) -> dict[str, Any]:
    """Parse and validate a Google Vision HTTP response.

    Args:
        response: HTTP response.

    Returns:
        JSON object response.

    Raises:
        OCRError: If the response is an error or not a JSON object.
    """
    if response.status_code >= HTTP_ERROR_STATUS_MIN:
        raise OCRError(f"Google Vision OCR request failed: status {response.status_code}.")
    try:
        parsed = response.json()
    except ValueError as exc:
        raise OCRError("Google Vision OCR returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise OCRError("Google Vision OCR returned an invalid response shape.")
    return parsed


def _parse_google_vision_response(payload: dict[str, Any]) -> OCRResult:
    """Normalize a Google Vision annotate response.

    Args:
        payload: Parsed Google Vision JSON response.

    Returns:
        Normalized OCR result.

    Raises:
        OCRError: If the response contains a provider error or invalid shape.
    """
    raw_responses = payload.get("responses")
    if not isinstance(raw_responses, list) or not raw_responses:
        raise OCRError("Google Vision OCR response is missing responses.")
    first_response = raw_responses[0]
    if not isinstance(first_response, dict):
        raise OCRError("Google Vision OCR response is invalid.")

    provider_error = first_response.get("error")
    if isinstance(provider_error, dict):
        message = _safe_provider_error_message(provider_error)
        raise OCRError(f"Google Vision OCR provider error: {message}")

    text = _extract_text(first_response)
    confidence = _average_confidence(first_response)
    pages = _extract_pages(first_response)
    return OCRResult(
        text=text,
        provider=GOOGLE_VISION_PROVIDER,
        confidence=confidence,
        pages=pages,
    )


def _extract_text(response: dict[str, Any]) -> str:
    """Extract OCR text from a Google Vision response object.

    Args:
        response: One Google Vision annotate response.

    Returns:
        Extracted text or an empty string.
    """
    full_text_annotation = response.get("fullTextAnnotation")
    if isinstance(full_text_annotation, dict):
        text = full_text_annotation.get("text")
        if isinstance(text, str):
            return text

    text_annotations = response.get("textAnnotations")
    if isinstance(text_annotations, list) and text_annotations:
        first_annotation = text_annotations[0]
        if isinstance(first_annotation, dict):
            description = first_annotation.get("description")
            if isinstance(description, str):
                return description
    return ""


def _average_confidence(response: dict[str, Any]) -> float | None:
    """Average confidence values present in the Google Vision response.

    Args:
        response: One Google Vision annotate response.

    Returns:
        Average confidence or None when Google did not return confidence values.
    """
    values = list(_confidence_values(response))
    if not values:
        return None
    return sum(values) / len(values)


def _extract_pages(response: dict[str, Any]) -> tuple[OCRPage, ...]:
    """Normalize Google Vision full-text pages into the OCR layout contract.

    Args:
        response: One Google Vision annotate response.

    Returns:
        OCR pages with block, paragraph, and word hierarchy.
    """
    full_text_annotation = response.get("fullTextAnnotation")
    if not isinstance(full_text_annotation, dict):
        return ()
    raw_pages = full_text_annotation.get("pages")
    if not isinstance(raw_pages, list):
        return ()
    pages: list[OCRPage] = []
    for raw_page in raw_pages:
        if isinstance(raw_page, dict):
            pages.append(_parse_page(raw_page))
    return tuple(pages)


def _parse_page(raw_page: dict[str, Any]) -> OCRPage:
    """Parse one Google Vision page object."""
    raw_blocks = raw_page.get("blocks")
    blocks = (
        tuple(
            _parse_block(raw_block, block_index)
            for block_index, raw_block in enumerate(raw_blocks)
            if isinstance(raw_block, dict)
        )
        if isinstance(raw_blocks, list)
        else ()
    )
    return OCRPage(
        width=_optional_int(raw_page.get("width")),
        height=_optional_int(raw_page.get("height")),
        confidence=_optional_confidence(raw_page.get("confidence")),
        blocks=blocks,
    )


def _parse_block(raw_block: dict[str, Any], block_index: int) -> OCRBlock:
    """Parse one Google Vision block object."""
    raw_paragraphs = raw_block.get("paragraphs")
    paragraphs = (
        tuple(
            _parse_paragraph(raw_paragraph, block_index, paragraph_index)
            for paragraph_index, raw_paragraph in enumerate(raw_paragraphs)
            if isinstance(raw_paragraph, dict)
        )
        if isinstance(raw_paragraphs, list)
        else ()
    )
    return OCRBlock(
        text="\n".join(paragraph.text for paragraph in paragraphs if paragraph.text),
        confidence=_optional_confidence(raw_block.get("confidence")),
        bounding_box=_parse_bounding_poly(raw_block.get("boundingBox")),
        block_type=_optional_string(raw_block.get("blockType")),
        paragraphs=paragraphs,
    )


def _parse_paragraph(
    raw_paragraph: dict[str, Any],
    block_index: int,
    paragraph_index: int,
) -> OCRParagraph:
    """Parse one Google Vision paragraph object."""
    raw_words = raw_paragraph.get("words")
    words = (
        tuple(
            _parse_word(raw_word, block_index, paragraph_index, word_index)
            for word_index, raw_word in enumerate(raw_words)
            if isinstance(raw_word, dict)
        )
        if isinstance(raw_words, list)
        else ()
    )
    return OCRParagraph(
        text=" ".join(word.text for word in words if word.text),
        confidence=_optional_confidence(raw_paragraph.get("confidence")),
        bounding_box=_parse_bounding_poly(raw_paragraph.get("boundingBox")),
        words=words,
    )


def _parse_word(
    raw_word: dict[str, Any],
    block_index: int,
    paragraph_index: int,
    word_index: int,
) -> OCRWord:
    """Parse one Google Vision word object without retaining provider payload."""
    return OCRWord(
        text=_word_text(raw_word),
        confidence=_optional_confidence(raw_word.get("confidence")),
        bounding_box=_parse_bounding_poly(raw_word.get("boundingBox")),
        block_index=block_index,
        paragraph_index=paragraph_index,
        word_index=word_index,
    )


def _word_text(raw_word: dict[str, Any]) -> str:
    """Assemble a Google Vision word from child symbols."""
    raw_symbols = raw_word.get("symbols")
    if not isinstance(raw_symbols, list):
        return ""
    parts: list[str] = []
    for raw_symbol in raw_symbols:
        if isinstance(raw_symbol, dict):
            text = raw_symbol.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _parse_bounding_poly(value: object) -> OCRBoundingPoly | None:
    """Parse Google Vision bounding polygons into provider-neutral vertices."""
    if not isinstance(value, dict):
        return None
    raw_vertices = value.get("vertices")
    if not isinstance(raw_vertices, list):
        raw_vertices = value.get("normalizedVertices")
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


def _optional_string(value: object) -> str | None:
    """Return a string value when present."""
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    """Return a non-negative integer when present."""
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _optional_float(value: object) -> float | None:
    """Return a numeric value when present."""
    if isinstance(value, int | float):
        return float(value)
    return None


def _optional_confidence(value: object) -> float | None:
    """Return a bounded confidence value when present."""
    if isinstance(value, int | float) and 0 <= value <= 1:
        return float(value)
    return None


def _confidence_values(value: object) -> list[float]:
    """Collect bounded confidence values from a nested JSON-like object.

    Args:
        value: Candidate JSON value.

    Returns:
        Confidence values in the inclusive range 0.0 to 1.0.
    """
    values: list[float] = []
    if isinstance(value, dict):
        confidence = value.get("confidence")
        if isinstance(confidence, int | float) and 0 <= confidence <= 1:
            values.append(float(confidence))
        for nested_value in value.values():
            values.extend(_confidence_values(nested_value))
    elif isinstance(value, list):
        for item in value:
            values.extend(_confidence_values(item))
    return values


def _safe_provider_error_message(error: dict[str, Any]) -> str:
    """Return a bounded non-secret provider error message.

    Args:
        error: Provider error object.

    Returns:
        Sanitized error status or message.
    """
    status = error.get("status")
    if isinstance(status, str) and status:
        return status[:80]
    message = error.get("message")
    if isinstance(message, str) and message:
        return message[:80]
    return "unknown"
