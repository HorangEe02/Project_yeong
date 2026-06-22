"""Ensemble OCR merge wiring integration test.

Wires the real adapter factory plus real Clova/Paddle provider adapters (with
fake transports, no network) and asserts that an ``always`` secondary-merge
policy produces a line-union merged result whose provider label joins both
providers. This pins the config-gated ensemble seam end-to-end without touching
external services.
"""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any

from PIL import Image
from pydantic import SecretStr
from src.config import Settings
from src.ocr.base import OCRImageInput
from src.ocr.factory import build_supplement_image_analysis_adapters
from src.ocr.providers.clova import ClovaOCRAdapter
from src.ocr.providers.paddle import PaddleOCRAdapter
from src.services.supplement_image_analysis import (
    _supplement_ensemble_ocr_if_allowed,
)
from src.services.supplement_intake import ValidatedSupplementImage


class _FakeClovaResponse:
    """Minimal fake CLOVA HTTP response."""

    def __init__(self, payload: Any) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> Any:
        """Return the canned payload.

        Returns:
            Canned JSON payload.
        """
        return self._payload


class _FakeClovaClient:
    """Fake async CLOVA HTTP client returning a canned payload."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.url: str | None = None
        self.request_json: Mapping[str, Any] | None = None
        self.headers: Mapping[str, str] | None = None

    async def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> _FakeClovaResponse:
        """Capture the request and return the canned CLOVA response.

        Args:
            url: Request URL.
            json: Request payload.
            headers: Request headers.
            timeout: Optional timeout.

        Returns:
            Fake CLOVA response.
        """
        self.url = url
        self.request_json = json
        self.headers = headers
        _ = timeout
        return _FakeClovaResponse(self._payload)


class _FakePaddlePredictor:
    """Fake PaddleOCR predictor returning a canned prediction."""

    def __init__(self, prediction: object) -> None:
        self._prediction = prediction
        self.received_path: str | None = None
        self.received_kwargs: dict[str, object] = {}

    def predict(self, image_path: str, **kwargs: object) -> object:
        """Capture the call and return the canned prediction.

        Args:
            image_path: Temporary image path.
            **kwargs: Predict-time tuning parameters.

        Returns:
            Canned prediction payload.
        """
        self.received_path = image_path
        self.received_kwargs = dict(kwargs)
        return self._prediction


def _settings() -> Settings:
    """Return ensemble-enabled settings with CLOVA primary wiring.

    Returns:
        Settings instance for the wiring test.
    """
    return Settings(
        _env_file=None,
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        ocr_primary_provider="clova",
        allow_external_ocr=True,
        enable_clova_ocr=True,
        clova_ocr_api_url="https://example.apigw.ntruss.com/custom/v1/infer",
        clova_ocr_secret=SecretStr("unit-test-placeholder"),
        enable_local_ocr=True,
        local_ocr_preprocess_mode="none",
        ocr_secondary_merge_policy="always",
    )


def _png_bytes() -> bytes:
    """Return a tiny in-memory PNG image.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (4, 3), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _clova_payload() -> dict[str, Any]:
    """Return a canned CLOVA success payload.

    Returns:
        CLOVA inference payload with two fields.
    """
    return {
        "images": [
            {
                "inferResult": "SUCCESS",
                "convertedImageInfo": {"width": 1200, "height": 1600},
                "fields": [
                    {"inferText": "비타민 D 1000", "inferConfidence": 0.91},
                    {"inferText": "60 capsules", "inferConfidence": 0.89},
                ],
            }
        ]
    }


def _image_metadata() -> ValidatedSupplementImage:
    """Return validated image metadata for the stage call.

    Returns:
        Validated supplement image metadata.
    """
    return ValidatedSupplementImage(
        mime_type="image/png",
        width=1200,
        height=1600,
        size_bytes=64,
        sha256="c" * 64,
    )


def test_factory_wires_paddle_secondary_merge_for_clova_primary() -> None:
    """Verify the real factory wires a PaddleOCR secondary-merge adapter."""
    adapters = build_supplement_image_analysis_adapters(_settings())

    assert isinstance(adapters.ocr, ClovaOCRAdapter)
    assert isinstance(adapters.secondary_merge_ocr, PaddleOCRAdapter)


async def test_ensemble_stage_merges_real_clova_and_paddle() -> None:
    """Verify the real Clova+Paddle adapters merge into one cross-provider result."""
    settings = _settings()
    clova_adapter = ClovaOCRAdapter(settings, client=_FakeClovaClient(_clova_payload()))
    paddle_adapter = PaddleOCRAdapter(
        settings,
        predictor=_FakePaddlePredictor(
            [{"rec_texts": ["60 capsules", "마그네슘 400mg"], "rec_scores": [0.88, 0.86]}]
        ),
    )
    image_bytes = _png_bytes()
    primary_result = await clova_adapter.extract_text(
        OCRImageInput(
            image_bytes=image_bytes,
            mime_type="image/png",
            width=1200,
            height=1600,
        )
    )

    merged = await _supplement_ensemble_ocr_if_allowed(
        image_bytes=image_bytes,
        image_metadata=_image_metadata(),
        label_region=None,
        ocr_result=primary_result,
        secondary_merge_adapter=paddle_adapter,
        settings=settings,
    )

    assert merged is not None
    assert merged.provider == "clova_ocr+paddleocr_local"
    assert "비타민 D 1000" in merged.text
    assert "마그네슘 400mg" in merged.text
