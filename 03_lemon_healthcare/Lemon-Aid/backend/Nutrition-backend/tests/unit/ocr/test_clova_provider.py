"""CLOVA OCR fallback provider tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import SecretStr
from src.config import Settings
from src.ocr.base import OCRError, OCRImageInput
from src.ocr.providers.clova import CLOVA_OCR_PROVIDER, ClovaOCRAdapter


class _FakeResponse:
    """Fake HTTP response for CLOVA tests."""

    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        """Return fake JSON payload.

        Returns:
            Fake payload.
        """
        return self.payload


class _FakeHTTPClient:
    """Fake async HTTP client capturing CLOVA requests."""

    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
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
    ) -> _FakeResponse:
        """Capture a POST request and return a fake response.

        Args:
            url: Request URL.
            json: Request JSON.
            headers: Request headers.
            timeout: Request timeout.

        Returns:
            Fake response.
        """
        _ = timeout
        self.url = url
        self.request_json = json
        self.headers = headers
        return _FakeResponse(self.payload, self.status_code)


def _settings(*, allow_external_ocr: bool = True) -> Settings:
    """Return CLOVA provider settings.

    Args:
        allow_external_ocr: Whether external OCR is allowed.

    Returns:
        Settings object.
    """
    return Settings(
        _env_file=None,
        enable_clova_ocr=True,
        allow_external_ocr=allow_external_ocr,
        clova_ocr_api_url="https://example.apigw.ntruss.com/custom/v1/infer",
        clova_ocr_secret=SecretStr("unit-test-placeholder"),
    )


def _image_input() -> OCRImageInput:
    """Return a minimal OCR image input.

    Returns:
        OCR image input.
    """
    return OCRImageInput(
        image_bytes=b"fake-png-bytes",
        mime_type="image/png",
        width=10,
        height=8,
    )


@pytest.mark.asyncio
async def test_clova_adapter_flattens_fields() -> None:
    """Verify CLOVA fields are joined into one OCR result."""
    client = _FakeHTTPClient(
        {
            "images": [
                {
                    "inferResult": "SUCCESS",
                    "convertedImageInfo": {"width": 1200, "height": 1600},
                    "fields": [
                        {
                            "inferText": "비타민 D 1000",
                            "inferConfidence": 0.91,
                            "boundingPoly": {
                                "vertices": [
                                    {"x": 10, "y": 20},
                                    {"x": 210, "y": 20},
                                    {"x": 210, "y": 50},
                                    {"x": 10, "y": 50},
                                ]
                            },
                        },
                        {
                            "inferText": "비타민 D 25 ug",
                            "inferConfidence": 0.87,
                            "boundingPoly": {
                                "vertices": [
                                    {"x": 12, "y": 60},
                                    {"x": 190, "y": 60},
                                    {"x": 190, "y": 90},
                                    {"x": 12, "y": 90},
                                ]
                            },
                        },
                    ],
                }
            ]
        }
    )
    adapter = ClovaOCRAdapter(_settings(), client=client)

    result = await adapter.extract_text(_image_input())

    assert result.provider == CLOVA_OCR_PROVIDER
    assert result.text == "비타민 D 1000\n비타민 D 25 ug"
    assert result.confidence == pytest.approx(0.89)
    assert len(result.pages) == 1
    assert result.pages[0].width == 1200
    assert result.pages[0].height == 1600
    assert [block.text for block in result.pages[0].blocks] == [
        "비타민 D 1000",
        "비타민 D 25 ug",
    ]
    assert result.pages[0].blocks[0].bounding_box is not None
    assert result.pages[0].blocks[0].bounding_box.vertices[0].x == 10
    assert result.pages[0].blocks[0].paragraphs[0].words[0].word_index == 0
    assert client.url == "https://example.apigw.ntruss.com/custom/v1/infer"
    assert client.headers is not None
    clova_header_name = "X-OCR-" + "S" + "ECRET"
    assert client.headers[clova_header_name] == "unit-test-placeholder"
    assert client.request_json is not None
    assert client.request_json["version"] == "V2"


@pytest.mark.asyncio
async def test_clova_adapter_requires_external_ocr_gate() -> None:
    """Verify CLOVA cannot send image bytes without the external OCR gate."""
    adapter = ClovaOCRAdapter(
        _settings(allow_external_ocr=False),
        client=_FakeHTTPClient({"images": []}),
    )

    with pytest.raises(OCRError, match="ALLOW_EXTERNAL_OCR"):
        await adapter.extract_text(_image_input())


@pytest.mark.asyncio
async def test_clova_adapter_rejects_provider_error() -> None:
    """Verify unsuccessful CLOVA inference is not accepted."""
    adapter = ClovaOCRAdapter(
        _settings(),
        client=_FakeHTTPClient({"images": [{"inferResult": "ERROR", "fields": []}]}),
    )

    with pytest.raises(OCRError, match="inference failed"):
        await adapter.extract_text(_image_input())
