"""Ollama vision assist adapter tests."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from io import BytesIO
from typing import Any, Literal

import httpx
import pytest
from PIL import Image
from src.config import Settings
from src.llm.ollama import (
    OllamaChatClient,
    OllamaClientError,
    OllamaConfigurationError,
    OllamaStructuredOutputError,
)
from src.llm.ollama_vision import (
    OLLAMA_VISION_ASSIST_PROVIDER,
    OllamaVisionAssistAdapter,
    OllamaVisionStructuredExtractionResult,
    check_ollama_vision_readiness,
)
from src.ocr.base import OCRImageInput
from src.vision.base import BoundingBox

OcrAssistPolicy = Literal["disabled", "ocr_empty_only", "low_confidence"]


class _FakeResponse:
    """Fake HTTP response for Ollama vision tests."""

    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Raise an HTTP status error when configured.

        Returns:
            None.
        """
        if self.status_code < 400:
            return
        request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("Fake Ollama status error.", request=request, response=response)

    def json(self) -> Any:
        """Return the configured fake payload.

        Returns:
            Fake JSON payload.
        """
        return self.payload


class _FakeHTTPClient:
    """Fake async HTTP client that captures Ollama requests."""

    def __init__(
        self,
        post_payload: Any = None,
        *,
        get_payload: Any | None = None,
        post_status_code: int = 200,
        get_status_code: int = 200,
    ) -> None:
        self.post_payload = post_payload
        self.get_payload = get_payload if get_payload is not None else {"models": []}
        self.post_status_code = post_status_code
        self.get_status_code = get_status_code
        self.request_json: Mapping[str, Any] | None = None
        self.post_url: str | None = None
        self.get_url: str | None = None

    async def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        timeout: float,
    ) -> _FakeResponse:
        """Capture a fake POST request.

        Args:
            url: Request URL.
            json: Request payload.
            timeout: Request timeout.

        Returns:
            Fake response.
        """
        _ = timeout
        self.post_url = url
        self.request_json = json
        return _FakeResponse(self.post_payload, self.post_status_code)

    async def get(
        self,
        url: str,
        *,
        timeout: float,
    ) -> _FakeResponse:
        """Capture a fake GET request.

        Args:
            url: Request URL.
            timeout: Request timeout.

        Returns:
            Fake response.
        """
        _ = timeout
        self.get_url = url
        return _FakeResponse(self.get_payload, self.get_status_code)


def _settings(
    *,
    enable_multimodal_llm: bool = True,
    multimodal_ocr_assist_policy: OcrAssistPolicy = "ocr_empty_only",
    ollama_base_url: str = "http://127.0.0.1:11434",
    ollama_vision_model: str | None = "gemma4:e4b",
    environment: str = "development",
) -> Settings:
    """Return settings for Ollama vision tests.

    Args:
        enable_multimodal_llm: Whether the gated multimodal channel is enabled.
        multimodal_ocr_assist_policy: Runtime policy for vision assist calls.
        ollama_base_url: Ollama base URL used by the fake client assertions.
        ollama_vision_model: Local vision model tag to check in readiness tests.
        environment: Runtime environment for local-host policy checks.

    Returns:
        Settings object.
    """
    return Settings(
        enable_multimodal_llm=enable_multimodal_llm,
        multimodal_ocr_assist_policy=multimodal_ocr_assist_policy,
        ollama_base_url=ollama_base_url,
        ollama_vision_model=ollama_vision_model,
        environment=environment,
        auth_mode="jwt" if environment != "development" else "disabled",
        allowed_hosts=["localhost"] if environment != "development" else [],
    )


def _png_bytes(width: int = 10, height: int = 8) -> bytes:
    """Return a PNG fixture.

    Args:
        width: Image width.
        height: Image height.

    Returns:
        Encoded PNG bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _ocr_image_input(label_region: BoundingBox | None = None) -> OCRImageInput:
    """Return a validated OCR image input fixture.

    Args:
        label_region: Optional ROI.

    Returns:
        OCR image input.
    """
    return OCRImageInput(
        image_bytes=_png_bytes(),
        mime_type="image/png",
        width=10,
        height=8,
        label_region=label_region,
    )


def _response_content() -> str:
    """Return a schema-valid vision assist response body.

    Returns:
        JSON response content.
    """
    return json.dumps(
        {
            "visible_text_fragments": ["비타민 D 1000", "비타민 D 25 ug"],
            "possible_product_name": "비타민 D 1000",
            "source_region": "yolo_roi",
            "low_confidence_fields": ["serving_size"],
            "warnings": ["라벨 일부가 흐립니다."],
        },
        ensure_ascii=False,
    )


def _verification_response_content(
    *,
    status: str = "partial",
    missing_critical_sections: list[str] | None = None,
) -> str:
    """Return a schema-valid vision verification response body.

    Args:
        status: Verification status emitted by the fake local model.
        missing_critical_sections: Required sections reported as absent.

    Returns:
        JSON response content.
    """
    return json.dumps(
        {
            "verification_status": status,
            "confidence": 0.77,
            "source_region": "yolo_roi",
            "matched_fragments": ["비타민 D 25 ug"],
            "missing_fragments": ["주의사항"],
            "missing_critical_sections": missing_critical_sections or ["precautions"],
            "warnings": ["주의사항 영역을 확인하지 못했습니다."],
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_ollama_vision_assist_posts_base64_image_and_schema() -> None:
    """Verify the adapter sends a local structured vision request."""
    fake_client = _FakeHTTPClient({"message": {"content": _response_content()}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)
    adapter = OllamaVisionAssistAdapter(_settings(), client=chat_client)

    result = await adapter.extract_text(
        _ocr_image_input(
            BoundingBox(x=2, y=1, width=4, height=3, confidence=0.9, label="supplement_label")
        )
    )

    assert result.provider == OLLAMA_VISION_ASSIST_PROVIDER
    assert result.confidence is None
    assert result.text == "비타민 D 1000\n비타민 D 25 ug"
    assert fake_client.post_url == "http://127.0.0.1:11434/api/chat"
    assert fake_client.request_json is not None
    assert fake_client.request_json["model"] == "gemma4:e4b"
    assert fake_client.request_json["stream"] is False
    assert fake_client.request_json["think"] is False
    assert fake_client.request_json["format"]["type"] == "object"
    user_message = fake_client.request_json["messages"][1]
    assert "images" in user_message
    decoded = base64.b64decode(user_message["images"][0])
    with Image.open(BytesIO(decoded)) as image:
        assert image.size == (4, 3)


@pytest.mark.asyncio
async def test_ollama_vision_assist_verifies_ocr_text_with_schema() -> None:
    """Verify the adapter sends OCR text for local structured vision verification."""
    fake_client = _FakeHTTPClient({"message": {"content": _verification_response_content()}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)
    adapter = OllamaVisionAssistAdapter(_settings(), client=chat_client)

    result = await adapter.verify_text(
        _ocr_image_input(
            BoundingBox(x=2, y=1, width=4, height=3, confidence=0.9, label="precautions")
        ),
        "비타민 D 25 ug\n주의사항",
    )

    assert result.verification_status == "partial"
    assert result.missing_critical_sections == ["precautions"]
    assert result.source_region == "yolo_roi"
    assert fake_client.request_json is not None
    assert fake_client.request_json["model"] == "gemma4:e4b"
    assert fake_client.request_json["format"]["type"] == "object"
    user_message = fake_client.request_json["messages"][1]
    assert "OCR text to verify" in user_message["content"]
    assert "비타민 D 25 ug" in user_message["content"]
    assert "medical advice" not in user_message["content"].casefold()
    decoded = base64.b64decode(user_message["images"][0])
    with Image.open(BytesIO(decoded)) as image:
        assert image.size == (4, 3)


@pytest.mark.asyncio
async def test_ollama_vision_assist_rejects_when_feature_flag_disabled() -> None:
    """Verify image bytes are not sent when the multimodal flag is disabled."""
    fake_client = _FakeHTTPClient({"message": {"content": _response_content()}})
    settings = _settings(enable_multimodal_llm=False)
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    with pytest.raises(OllamaConfigurationError):
        await OllamaVisionAssistAdapter(settings, client=chat_client).extract_text(
            _ocr_image_input()
        )

    assert fake_client.request_json is None


@pytest.mark.asyncio
async def test_ollama_vision_assist_blocks_remote_base_url() -> None:
    """Verify identifiable image data is not sent to remote Ollama endpoints by default."""
    fake_client = _FakeHTTPClient({"message": {"content": _response_content()}})
    settings = _settings(ollama_base_url="https://ollama.example.com")
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    with pytest.raises(OllamaConfigurationError):
        await OllamaVisionAssistAdapter(settings, client=chat_client).extract_text(
            _ocr_image_input()
        )

    assert fake_client.request_json is None


@pytest.mark.asyncio
async def test_ollama_vision_assist_allows_docker_desktop_host_in_development() -> None:
    """Verify Docker Desktop's host alias is allowed only as a development local endpoint."""
    fake_client = _FakeHTTPClient({"message": {"content": _response_content()}})
    settings = _settings(ollama_base_url="http://host.docker.internal:11434")
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    await OllamaVisionAssistAdapter(settings, client=chat_client).extract_text(_ocr_image_input())

    assert fake_client.post_url == "http://host.docker.internal:11434/api/chat"


@pytest.mark.asyncio
async def test_ollama_vision_assist_blocks_docker_desktop_host_outside_development() -> None:
    """Verify non-development runtimes do not treat Docker host alias as local."""
    fake_client = _FakeHTTPClient({"message": {"content": _response_content()}})
    settings = _settings(
        environment="staging",
        ollama_base_url="http://host.docker.internal:11434",
    )
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    with pytest.raises(OllamaConfigurationError):
        await OllamaVisionAssistAdapter(settings, client=chat_client).extract_text(
            _ocr_image_input()
        )

    assert fake_client.request_json is None


@pytest.mark.asyncio
async def test_ollama_vision_assist_rejects_schema_invalid_content() -> None:
    """Verify model output must match the visible-text candidate schema."""
    fake_client = _FakeHTTPClient({"message": {"content": '{"medical_advice": "take more"}'}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)

    with pytest.raises(OllamaStructuredOutputError):
        await OllamaVisionAssistAdapter(_settings(), client=chat_client).extract_text(
            _ocr_image_input()
        )


@pytest.mark.asyncio
async def test_ollama_vision_verification_rejects_schema_invalid_content() -> None:
    """Verify verification output must match the schema."""
    fake_client = _FakeHTTPClient({"message": {"content": '{"medical_advice": "take more"}'}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)

    with pytest.raises(OllamaStructuredOutputError):
        await OllamaVisionAssistAdapter(_settings(), client=chat_client).verify_text(
            _ocr_image_input(),
            "비타민 D 25 ug",
        )


@pytest.mark.asyncio
async def test_ollama_vision_assist_rejects_invalid_roi_crop() -> None:
    """Verify bad ROI metadata fails before the model call."""
    fake_client = _FakeHTTPClient({"message": {"content": _response_content()}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)

    with pytest.raises(OllamaClientError, match="ROI crop"):
        await OllamaVisionAssistAdapter(_settings(), client=chat_client).extract_text(
            _ocr_image_input(BoundingBox(x=20, y=20, width=5, height=5, confidence=0.8))
        )

    assert fake_client.request_json is None


@pytest.mark.asyncio
async def test_check_ollama_vision_readiness_reports_installed_model() -> None:
    """Verify readiness checks the configured local vision model tag."""
    settings = _settings()
    fake_client = _FakeHTTPClient(
        get_payload={"models": [{"name": "qwen3.5:9b"}, {"name": "gemma4:e4b"}]}
    )
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_vision_readiness(settings, chat_client)

    assert readiness.ready is True
    assert readiness.model == "gemma4:e4b"
    assert readiness.model_present is True
    assert readiness.error_code is None
    assert fake_client.get_url == "http://127.0.0.1:11434/api/tags"


@pytest.mark.asyncio
async def test_check_ollama_vision_readiness_can_probe_image_payload() -> None:
    """Verify readiness can fail closed on an actual local image-input smoke."""
    settings = _settings()
    fake_client = _FakeHTTPClient(
        {"message": {"content": '{"vision_input_supported": true, "visible_text_present": false}'}},
        get_payload={"models": [{"name": "gemma4:e4b"}]},
    )
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_vision_readiness(
        settings,
        chat_client,
        probe_image_input=True,
    )

    assert readiness.ready is True
    assert readiness.error_code is None
    assert fake_client.post_url == "http://127.0.0.1:11434/api/chat"
    assert fake_client.request_json is not None
    messages = fake_client.request_json["messages"]
    assert messages[1]["images"]
    assert fake_client.request_json["format"]["required"] == [
        "vision_input_supported",
        "visible_text_present",
    ]


@pytest.mark.asyncio
async def test_check_ollama_vision_readiness_probe_fails_closed() -> None:
    """Verify malformed image-probe output disables vision readiness."""
    settings = _settings()
    fake_client = _FakeHTTPClient(
        {"message": {"content": '{"visible_text_present": true}'}},
        get_payload={"models": [{"name": "gemma4:e4b"}]},
    )
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_vision_readiness(
        settings,
        chat_client,
        probe_image_input=True,
    )

    assert readiness.ready is False
    assert readiness.model_present is True
    assert readiness.error_code == "vision_probe_failed"


def _extraction_response_content() -> str:
    """Return a schema-valid structured extraction response body.

    Returns:
        JSON response content.
    """
    return json.dumps(
        {
            "product_category_key": "비타민D",
            "ingredients": [
                {"name": "비타민 D", "amount": 25, "unit": "ug"},
                {"name": "마그네슘", "amount": None, "unit": None},
            ],
            "low_confidence_fields": ["serving_size"],
            "warnings": ["라벨 일부가 흐립니다."],
        },
        ensure_ascii=False,
    )


def test_vision_structured_extraction_result_parses_good_json() -> None:
    """Verify the extraction schema validates a clean transcription payload."""
    result = OllamaVisionStructuredExtractionResult.model_validate_json(
        _extraction_response_content()
    )

    assert result.product_category_key == "비타민D"
    assert len(result.ingredients) == 2
    assert result.ingredients[0].name == "비타민 D"
    assert result.ingredients[0].amount == 25
    assert result.ingredients[0].unit == "ug"
    assert result.ingredients[1].amount is None
    assert result.ingredients[1].unit is None


@pytest.mark.asyncio
async def test_ollama_vision_extract_structured_posts_payload_and_parses() -> None:
    """Verify extract_structured sends a local structured request and parses it."""
    fake_client = _FakeHTTPClient({"message": {"content": _extraction_response_content()}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)
    adapter = OllamaVisionAssistAdapter(_settings(), client=chat_client)

    result = await adapter.extract_structured(
        _ocr_image_input(
            BoundingBox(x=2, y=1, width=4, height=3, confidence=0.9, label="supplement_facts")
        ),
        ["비타민D", "마그네슘"],
    )

    assert result.product_category_key == "비타민D"
    assert result.ingredients[0].amount == 25
    assert fake_client.post_url == "http://127.0.0.1:11434/api/chat"
    assert fake_client.request_json is not None
    assert fake_client.request_json["model"] == "gemma4:e4b"
    assert fake_client.request_json["stream"] is False
    assert fake_client.request_json["think"] is False
    assert fake_client.request_json["format"]["type"] == "object"
    user_message = fake_client.request_json["messages"][1]
    assert "비타민D" in user_message["content"]
    assert "마그네슘" in user_message["content"]
    assert "medical advice" not in user_message["content"].casefold()
    assert "images" in user_message
    decoded = base64.b64decode(user_message["images"][0])
    with Image.open(BytesIO(decoded)) as image:
        assert image.size == (4, 3)


@pytest.mark.asyncio
async def test_ollama_vision_extract_structured_tolerates_fenced_json() -> None:
    """Verify a markdown-fenced extraction payload still validates."""
    fenced = f"```json\n{_extraction_response_content()}\n```"
    fake_client = _FakeHTTPClient({"message": {"content": fenced}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)
    adapter = OllamaVisionAssistAdapter(_settings(), client=chat_client)

    result = await adapter.extract_structured(_ocr_image_input(), ["비타민D"])

    assert result.product_category_key == "비타민D"
    assert result.ingredients[0].name == "비타민 D"


@pytest.mark.asyncio
async def test_ollama_vision_extract_structured_rejects_schema_invalid_content() -> None:
    """Verify extraction output must match the structured schema."""
    fake_client = _FakeHTTPClient({"message": {"content": '{"medical_advice": "take more"}'}})
    chat_client = OllamaChatClient(_settings(), http_client=fake_client)

    with pytest.raises(OllamaStructuredOutputError):
        await OllamaVisionAssistAdapter(_settings(), client=chat_client).extract_structured(
            _ocr_image_input(),
            ["비타민D"],
        )


@pytest.mark.asyncio
async def test_ollama_vision_extract_structured_rejects_when_flag_disabled() -> None:
    """Verify image bytes are not sent when the multimodal flag is disabled."""
    fake_client = _FakeHTTPClient({"message": {"content": _extraction_response_content()}})
    settings = _settings(enable_multimodal_llm=False)
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    with pytest.raises(OllamaConfigurationError):
        await OllamaVisionAssistAdapter(settings, client=chat_client).extract_structured(
            _ocr_image_input(),
            ["비타민D"],
        )

    assert fake_client.request_json is None


@pytest.mark.asyncio
async def test_check_ollama_vision_readiness_reports_missing_model() -> None:
    """Verify readiness is explicit when the configured vision model is absent."""
    settings = _settings()
    fake_client = _FakeHTTPClient(get_payload={"models": [{"name": "qwen3.5:9b"}]})
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_vision_readiness(settings, chat_client)

    assert readiness.ready is False
    assert readiness.model_present is False
    assert readiness.error_code == "model_missing"
