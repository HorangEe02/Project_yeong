"""Ollama supplement parser adapter tests."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from src.config import Settings
from src.llm.ollama import (
    MAX_OLLAMA_OCR_PROMPT_CHARS,
    TRUNCATED_OCR_TEXT_MARKER,
    OllamaChatClient,
    OllamaClientError,
    OllamaConfigurationError,
    OllamaStructuredOutputError,
    OllamaSupplementParser,
    _salvage_parse_result,
    check_ollama_readiness,
)
from src.models.schemas.supplement_parser import SupplementStructuredParseResult


class _FakeResponse:
    """Fake HTTP response for Ollama adapter tests."""

    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Raise an HTTP status error when configured to do so.

        Returns:
            None.
        """
        if self.status_code < 400:
            return
        request = httpx.Request("GET", "http://127.0.0.1:11434/api/test")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("Fake Ollama status error.", request=request, response=response)

    def json(self) -> Any:
        """Return the configured response payload.

        Returns:
            Fake JSON payload.
        """
        return self.payload


class _FakeHTTPClient:
    """Fake async HTTP client that captures the submitted request."""

    def __init__(
        self,
        post_payload: Any = None,
        *,
        get_payload: Any = None,
        post_status_code: int = 200,
        get_status_code: int = 200,
    ) -> None:
        self.post_payload = post_payload
        self.get_payload = get_payload if get_payload is not None else {"models": []}
        self.post_status_code = post_status_code
        self.get_status_code = get_status_code
        self.post_url: str | None = None
        self.get_url: str | None = None
        self.request_json: Mapping[str, Any] | None = None
        self.post_timeout: float | None = None
        self.get_timeout: float | None = None

    async def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        timeout: float,
    ) -> _FakeResponse:
        """Capture the request and return the fake response.

        Args:
            url: Request URL.
            json: Request JSON payload.
            timeout: Request timeout.

        Returns:
            Fake HTTP response.
        """
        self.post_url = url
        self.request_json = json
        self.post_timeout = timeout
        return _FakeResponse(self.post_payload, self.post_status_code)

    async def get(
        self,
        url: str,
        *,
        timeout: float,
    ) -> _FakeResponse:
        """Capture the request and return the fake response.

        Args:
            url: Request URL.
            timeout: Request timeout.

        Returns:
            Fake HTTP response.
        """
        self.get_url = url
        self.get_timeout = timeout
        return _FakeResponse(self.get_payload, self.get_status_code)


def _settings(
    *,
    ollama_base_url: str = "http://127.0.0.1:11434",
    ollama_temperature: float = 0.0,
    environment: str = "development",
) -> Settings:
    """Return settings for Ollama parser tests.

    Args:
        ollama_base_url: Ollama endpoint used by the parser.
        ollama_temperature: Sampling temperature sent to Ollama.

    Returns:
        Settings object.
    """
    return Settings(
        ollama_base_url=ollama_base_url,
        ollama_temperature=ollama_temperature,
        environment=environment,
        auth_mode="jwt" if environment != "development" else "disabled",
        allowed_hosts=["localhost"] if environment != "development" else [],
    )


@pytest.mark.asyncio
async def test_ollama_parser_posts_json_schema_and_validates_content() -> None:
    """Verify the adapter sends JSON Schema and validates the structured response."""
    response_content = json.dumps(
        {
            "parsed_product": {
                "product_name": "비타민 D 1000",
                "serving_size": "1 tablet",
                "daily_servings": 1,
            },
            "ingredient_candidates": [
                {
                    "display_name": "비타민 D",
                    "original_name": "Vitamin D",
                    "amount": 25,
                    "unit": "ug",
                    "confidence": 0.91,
                }
            ],
            "label_sections": [
                {
                    "section_type": "supplement_facts",
                    "heading_text": "Supplement Facts",
                    "text_bundle": "Vitamin D 25 ug",
                    "confidence": 0.9,
                    "evidence_refs": ["span-1"],
                }
            ],
            "intake_method": {
                "text": "1일 1정 섭취",
                "structured": {
                    "frequency": "daily",
                    "times_per_day": 1,
                    "amount_per_time": 1,
                    "amount_unit": "tablet",
                },
                "confidence": 0.8,
                "evidence_refs": ["span-2"],
            },
            "precautions": [
                {
                    "text": "임산부는 전문가와 상담",
                    "category": "pregnancy",
                    "severity": "caution",
                    "confidence": 0.8,
                }
            ],
            "functional_claims": [
                {
                    "text": "뼈 건강에 도움",
                    "claim_type": "label_claim",
                    "confidence": 0.7,
                }
            ],
            "evidence_spans": [
                {
                    "section_type": "supplement_facts",
                    "text_excerpt": "Vitamin D 25 ug",
                    "confidence": 0.9,
                }
            ],
            "missing_required_sections": ["intake_method", "not_allowed"],
            "low_confidence_fields": ["manufacturer"],
            "warnings": [],
        },
        ensure_ascii=False,
    )
    fake_client = _FakeHTTPClient({"message": {"content": response_content}})
    settings = _settings(ollama_temperature=0)

    result = await OllamaSupplementParser(
        settings,
        http_client=fake_client,
    ).parse_supplement_ocr_text("비타민 D 1000\n1정당 비타민 D 25 ug")

    assert fake_client.post_url == "http://127.0.0.1:11434/api/chat"
    assert fake_client.post_timeout == settings.ollama_timeout_sec
    assert fake_client.request_json is not None
    assert fake_client.request_json["model"] == "gemma4:e4b"
    assert fake_client.request_json["stream"] is False
    assert fake_client.request_json["think"] is False
    assert fake_client.request_json["format"]["type"] == "object"
    assert fake_client.request_json["options"] == {"temperature": 0.0}
    user_prompt = fake_client.request_json["messages"][1]["content"]
    assert "비타민 D 25 μg" in user_prompt
    assert "ingredient_candidates" in user_prompt
    assert "original_name" in user_prompt
    assert "display_name equal to original_name" in user_prompt
    assert "package counts" in user_prompt
    assert result.parsed_product.product_name == "비타민 D 1000"
    assert result.ingredient_candidates[0].source == "ollama_structured"
    assert result.ingredient_candidates[0].display_name == "비타민 D"
    assert result.ingredient_candidates[0].original_name == "Vitamin D"
    assert result.label_sections[0].section_id == "section-001"
    assert result.intake_method.text == "1일 1정 섭취"
    assert result.precautions[0].category == "pregnancy"
    assert result.functional_claims[0].claim_type == "label_claim"
    assert result.evidence_spans[0].span_id == "evidence-001"
    assert result.missing_required_sections == ["intake_method"]


@pytest.mark.asyncio
async def test_ollama_parser_bounds_long_ocr_text_in_prompt() -> None:
    """Verify long OCR text is compacted before local structured-output calls."""
    response_content = json.dumps({"ingredient_candidates": []}, ensure_ascii=False)
    fake_client = _FakeHTTPClient({"message": {"content": response_content}})
    long_ocr_text = "비타민 D 25 ug\n" + ("middle-noise-line\n" * 1200) + "마그네슘 100 mg\n"

    await OllamaSupplementParser(
        _settings(),
        http_client=fake_client,
    ).parse_supplement_ocr_text(long_ocr_text)

    assert fake_client.request_json is not None
    assert fake_client.request_json["format"]["type"] == "object"
    user_prompt = fake_client.request_json["messages"][1]["content"]
    assert len(user_prompt) < len(long_ocr_text)
    assert TRUNCATED_OCR_TEXT_MARKER in user_prompt
    assert "비타민 D 25 ug" in user_prompt
    assert "마그네슘 100 mg" in user_prompt
    # The OCR block is still compacted to MAX_OLLAMA_OCR_PROMPT_CHARS (asserted
    # above); this bound only caps the fixed instruction template, which grew for
    # the bilingual "한글 (English)" ingredient contract and the §5.3 fusion-aware
    # image-fragment integration clause.
    assert len(user_prompt) < MAX_OLLAMA_OCR_PROMPT_CHARS + 2_000


@pytest.mark.asyncio
async def test_ollama_parser_salvages_schema_invalid_content_to_empty() -> None:
    """Verify structurally-invalid output salvages to an empty result, not a crash.

    Constraint failures no longer discard the whole parse: with no salvageable
    candidates the parser returns an empty result (the caller then shows the
    "re-check needed" state) instead of raising.
    """
    fake_client = _FakeHTTPClient({"message": {"content": '{"unexpected": true}'}})

    result = await OllamaSupplementParser(
        _settings(),
        http_client=fake_client,
    ).parse_supplement_ocr_text("비타민 D")

    assert result.ingredient_candidates == []


@pytest.mark.asyncio
async def test_ollama_parser_rejects_malformed_json_content() -> None:
    """Verify malformed structured content is rejected."""
    fake_client = _FakeHTTPClient({"message": {"content": "{not-json"}})

    with pytest.raises(OllamaStructuredOutputError):
        await OllamaSupplementParser(
            _settings(),
            http_client=fake_client,
        ).parse_supplement_ocr_text("비타민 D")


@pytest.mark.asyncio
async def test_ollama_parser_discards_non_null_nutrient_code() -> None:
    """Verify the LLM cannot persist invented internal nutrient codes."""
    response_content = json.dumps(
        {
            "ingredient_candidates": [
                {
                    "display_name": "비타민 D",
                    "nutrient_code": "VITAMIN_D",
                    "confidence": 0.8,
                }
            ]
        },
        ensure_ascii=False,
    )
    fake_client = _FakeHTTPClient({"message": {"content": response_content}})

    result = await OllamaSupplementParser(
        _settings(),
        http_client=fake_client,
    ).parse_supplement_ocr_text("비타민 D")

    assert result.ingredient_candidates[0].nutrient_code is None
    assert result.ingredient_candidates[0].original_name == "비타민 D"


@pytest.mark.asyncio
async def test_ollama_parser_normalizes_common_model_shape_aliases() -> None:
    """Verify common model output aliases are normalized before validation."""
    response_content = json.dumps(
        {
            "product": {
                "product_name": "오메가3",
                "serving_size": "1 capsule",
                "raw_ocr_text": "must not persist",
            },
            "ingredients": [
                {
                    "name": "EPA",
                    "quantity": "180",
                    "units": "mg",
                    "nutrient_code": "EPA",
                    "source": "model_generated",
                    "extra": "ignored",
                }
            ],
            "low_confidence_fields": "ingredient_candidates[0].confidence",
            "warnings": ["needs_review"],
            "raw_model_response": "must not persist",
        },
        ensure_ascii=False,
    )
    fake_client = _FakeHTTPClient({"message": {"content": response_content}})

    result = await OllamaSupplementParser(
        _settings(),
        http_client=fake_client,
    ).parse_supplement_ocr_text("EPA 180 mg")

    ingredient = result.ingredient_candidates[0]
    assert result.parsed_product.product_name == "오메가3"
    assert result.parsed_product.serving_size == "1 capsule"
    assert ingredient.display_name == "EPA"
    assert ingredient.original_name == "EPA"
    assert ingredient.amount == 180
    assert ingredient.unit == "mg"
    assert ingredient.nutrient_code is None
    assert ingredient.confidence == 0.0
    assert ingredient.source == "ollama_structured"
    assert result.low_confidence_fields == ["ingredient_candidates[0].confidence"]
    assert result.warnings == ["needs_review"]
    serialized = result.model_dump_json()
    assert "raw_ocr_text" not in serialized
    assert "raw_model_response" not in serialized


@pytest.mark.asyncio
async def test_ollama_parser_marks_untranslated_english_display_name_for_review() -> None:
    """Verify long English labels kept as display names require translation review."""
    response_content = json.dumps(
        {
            "ingredient_candidates": [
                {
                    "display_name": "Glucosamine Hydrochloride",
                    "original_name": "Glucosamine Hydrochloride",
                    "amount": 1500,
                    "unit": "mg",
                    "confidence": 0.86,
                }
            ],
            "low_confidence_fields": ["ingredient_candidates[0].unit"],
        },
        ensure_ascii=False,
    )
    fake_client = _FakeHTTPClient({"message": {"content": response_content}})

    result = await OllamaSupplementParser(
        _settings(),
        http_client=fake_client,
    ).parse_supplement_ocr_text("Glucosamine Hydrochloride 1500 mg")

    ingredient = result.ingredient_candidates[0]
    assert ingredient.display_name == "Glucosamine Hydrochloride"
    assert ingredient.original_name == "Glucosamine Hydrochloride"
    assert result.low_confidence_fields == [
        "ingredient_candidates[0].display_name",
        "ingredient_candidates[0].unit",
    ]


@pytest.mark.asyncio
async def test_ollama_parser_downgrades_invalid_confidence() -> None:
    """Verify malformed confidence does not invalidate visible ingredients."""
    response_content = json.dumps(
        {
            "ingredient_candidates": [
                {
                    "display_name": "비타민 D",
                    "confidence": 1.2,
                }
            ]
        },
        ensure_ascii=False,
    )
    fake_client = _FakeHTTPClient({"message": {"content": response_content}})

    result = await OllamaSupplementParser(
        _settings(),
        http_client=fake_client,
    ).parse_supplement_ocr_text("비타민 D")

    assert result.ingredient_candidates[0].confidence == 0.0


@pytest.mark.asyncio
async def test_ollama_parser_decodes_fenced_json_content() -> None:
    """Verify common fenced JSON responses are decoded without storing raw text."""
    response_content = (
        "```json\n"
        + json.dumps(
            {
                "ingredient_candidates": [
                    {
                        "display_name": "마그네슘",
                        "amount": "100",
                        "unit": "mg",
                        "confidence": "0.7",
                    }
                ]
            },
            ensure_ascii=False,
        )
        + "\n```"
    )
    fake_client = _FakeHTTPClient({"message": {"content": response_content}})

    result = await OllamaSupplementParser(
        _settings(),
        http_client=fake_client,
    ).parse_supplement_ocr_text("마그네슘 100 mg")

    ingredient = result.ingredient_candidates[0]
    assert ingredient.display_name == "마그네슘"
    assert ingredient.amount == 100
    assert ingredient.confidence == 0.7


@pytest.mark.asyncio
async def test_ollama_parser_rejects_missing_message_content() -> None:
    """Verify malformed Ollama chat responses are rejected before validation."""
    fake_client = _FakeHTTPClient({"message": {}})

    with pytest.raises(OllamaClientError):
        await OllamaSupplementParser(
            _settings(),
            http_client=fake_client,
        ).parse_supplement_ocr_text("비타민 D")


@pytest.mark.asyncio
async def test_ollama_parser_rejects_non_object_response_body() -> None:
    """Verify non-object Ollama responses are rejected."""
    fake_client = _FakeHTTPClient(["not", "an", "object"])

    with pytest.raises(OllamaClientError):
        await OllamaSupplementParser(
            _settings(),
            http_client=fake_client,
        ).parse_supplement_ocr_text("비타민 D")


@pytest.mark.asyncio
async def test_ollama_parser_blocks_remote_base_url_when_external_llm_disabled() -> None:
    """Verify sensitive OCR text is not sent to non-local Ollama endpoints by default."""
    fake_client = _FakeHTTPClient({"message": {"content": "{}"}})

    with pytest.raises(OllamaConfigurationError):
        await OllamaSupplementParser(
            _settings(ollama_base_url="https://ollama.example.com"),
            http_client=fake_client,
        ).parse_supplement_ocr_text("비타민 D")

    assert fake_client.request_json is None


@pytest.mark.asyncio
async def test_check_ollama_readiness_reports_ready_for_installed_model() -> None:
    """Verify readiness succeeds when the configured model is present."""
    settings = _settings()
    fake_client = _FakeHTTPClient(
        get_payload={
            "models": [
                {"name": "qwen3.5:9b", "model": "qwen3.5:9b"},
                {"name": "gemma4:e4b"},
            ]
        }
    )
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_readiness(settings, chat_client)

    assert readiness.ready is True
    assert readiness.model_present is True
    assert readiness.error_code is None
    assert readiness.model_names == ("qwen3.5:9b", "gemma4:e4b")
    assert fake_client.get_url == "http://127.0.0.1:11434/api/tags"
    assert fake_client.get_timeout == settings.ollama_timeout_sec


@pytest.mark.asyncio
async def test_check_ollama_readiness_reports_missing_model() -> None:
    """Verify readiness reports a missing configured model without raising."""
    settings = _settings()
    fake_client = _FakeHTTPClient(get_payload={"models": [{"name": "qwen3.5:9b"}]})
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_readiness(settings, chat_client)

    assert readiness.ready is False
    assert readiness.model_present is False
    assert readiness.error_code == "model_missing"
    assert readiness.model_names == ("qwen3.5:9b",)


@pytest.mark.asyncio
async def test_check_ollama_readiness_blocks_remote_base_url() -> None:
    """Verify readiness does not call a remote URL when external LLM is disabled."""
    settings = _settings(ollama_base_url="https://ollama.example.com")
    fake_client = _FakeHTTPClient(get_payload={"models": [{"name": "gemma4:e4b"}]})
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_readiness(settings, chat_client)

    assert readiness.ready is False
    assert readiness.error_code == "configuration_invalid"
    assert fake_client.get_url is None


@pytest.mark.asyncio
async def test_check_ollama_readiness_allows_docker_desktop_host_in_development() -> None:
    """Verify Docker Desktop's host alias is treated as local only in development."""
    settings = _settings(ollama_base_url="http://host.docker.internal:11434")
    fake_client = _FakeHTTPClient(get_payload={"models": [{"name": "gemma4:e4b"}]})
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_readiness(settings, chat_client)

    assert readiness.ready is True
    assert readiness.error_code is None
    assert fake_client.get_url == "http://host.docker.internal:11434/api/tags"


@pytest.mark.asyncio
async def test_check_ollama_readiness_blocks_docker_desktop_host_outside_development() -> None:
    """Verify the Docker host alias does not bypass non-development LLM policy."""
    settings = _settings(
        environment="staging",
        ollama_base_url="http://host.docker.internal:11434",
    )
    fake_client = _FakeHTTPClient(get_payload={"models": [{"name": "qwen3.5:9b"}]})
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_readiness(settings, chat_client)

    assert readiness.ready is False
    assert readiness.error_code == "configuration_invalid"
    assert fake_client.get_url is None


@pytest.mark.asyncio
async def test_check_ollama_readiness_handles_unavailable_api() -> None:
    """Verify readiness returns a stable status when Ollama is unavailable."""
    settings = _settings()
    fake_client = _FakeHTTPClient(get_payload={"error": "unavailable"}, get_status_code=500)
    chat_client = OllamaChatClient(settings, http_client=fake_client)

    readiness = await check_ollama_readiness(settings, chat_client)

    assert readiness.ready is False
    assert readiness.model_present is False
    assert readiness.error_code == "ollama_unavailable"


_NONEMPTY_PARSE_CONTENT = json.dumps(
    {
        "ingredient_candidates": [
            {
                "display_name": "비타민 D",
                "original_name": "Vitamin D",
                "amount": 25,
                "unit": "ug",
                "confidence": 0.9,
                "source": "ollama_structured",
            }
        ]
    },
    ensure_ascii=False,
)
_EMPTY_PARSE_CONTENT = json.dumps({"ingredient_candidates": []}, ensure_ascii=False)
_SUBSTANTIAL_OCR = "비타민 D 25 ug\n아연 10 mg\n원재료명: 비타민D, 아연"


class _ConcurrencyRecordingClient:
    """Fake client that records the peak concurrency observed at the post boundary."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.active = 0
        self.max_active = 0
        self.calls = 0

    async def post(self, url: str, *, json: Mapping[str, Any], timeout: float) -> _FakeResponse:
        del url, json, timeout
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.05)
        finally:
            self.active -= 1
        return _FakeResponse({"message": {"content": self.content}})

    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        del url, timeout
        return _FakeResponse({"models": []})


class _FlakyEmptyThenFullClient:
    """Fake client returning an empty parse first, then a populated one."""

    def __init__(self) -> None:
        self.calls = 0

    async def post(self, url: str, *, json: Mapping[str, Any], timeout: float) -> _FakeResponse:
        del url, json, timeout
        self.calls += 1
        content = _EMPTY_PARSE_CONTENT if self.calls == 1 else _NONEMPTY_PARSE_CONTENT
        return _FakeResponse({"message": {"content": content}})

    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        del url, timeout
        return _FakeResponse({"models": []})


@pytest.mark.asyncio
async def test_parse_serializes_concurrent_calls_through_semaphore() -> None:
    """Verify concurrent parses are serialized to one model call at a time."""
    settings = _settings()
    client = _ConcurrencyRecordingClient(_NONEMPTY_PARSE_CONTENT)

    results = await asyncio.gather(
        *(
            OllamaSupplementParser(settings, http_client=client).parse_supplement_ocr_text(
                _SUBSTANTIAL_OCR
            )
            for _ in range(6)
        )
    )

    assert client.max_active == 1
    assert client.calls == 6
    assert all(len(result.ingredient_candidates) == 1 for result in results)


@pytest.mark.asyncio
async def test_parse_retries_empty_result_on_substantial_ocr() -> None:
    """Verify a 0-ingredient parse on substantial OCR text is retried once."""
    settings = _settings()
    client = _FlakyEmptyThenFullClient()

    result = await OllamaSupplementParser(
        settings,
        http_client=client,
    ).parse_supplement_ocr_text(_SUBSTANTIAL_OCR)

    assert client.calls == 2
    assert len(result.ingredient_candidates) == 1


@pytest.mark.asyncio
async def test_parse_does_not_retry_empty_on_trivial_ocr() -> None:
    """Verify a 0-ingredient parse on trivial OCR text is not retried."""
    settings = _settings()
    client = _FlakyEmptyThenFullClient()

    result = await OllamaSupplementParser(
        settings,
        http_client=client,
    ).parse_supplement_ocr_text("  ")

    assert client.calls == 1
    assert result.ingredient_candidates == []


class _AlwaysEmptyClient:
    """Fake client that always returns an empty parse."""

    def __init__(self) -> None:
        self.calls = 0

    async def post(self, url: str, *, json: Mapping[str, Any], timeout: float) -> _FakeResponse:
        del url, json, timeout
        self.calls += 1
        return _FakeResponse({"message": {"content": _EMPTY_PARSE_CONTENT}})

    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        del url, timeout
        return _FakeResponse({"models": []})


class _RaiseThenSucceedClient:
    """Fake client that raises a transport error first, then returns a full parse."""

    def __init__(self) -> None:
        self.calls = 0

    async def post(self, url: str, *, json: Mapping[str, Any], timeout: float) -> _FakeResponse:
        del url, json, timeout
        self.calls += 1
        if self.calls == 1:
            raise httpx.ConnectError("fake transport failure")
        return _FakeResponse({"message": {"content": _NONEMPTY_PARSE_CONTENT}})

    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        del url, timeout
        return _FakeResponse({"models": []})


class _AlwaysRaiseClient:
    """Fake client that always raises a transport error."""

    def __init__(self) -> None:
        self.calls = 0

    async def post(self, url: str, *, json: Mapping[str, Any], timeout: float) -> _FakeResponse:
        del url, json, timeout
        self.calls += 1
        raise httpx.ConnectError("fake transport failure")

    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        del url, timeout
        return _FakeResponse({"models": []})


@pytest.mark.asyncio
async def test_parse_skips_retry_when_budget_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the retry is declined when the time budget would be overrun."""
    settings = _settings().model_copy(update={"ollama_parse_total_budget_sec": 10.0})
    client = _AlwaysEmptyClient()
    # started=0 (call 1); attempt 0 sees remaining=10 (call 2); attempt 1 sees
    # elapsed=6 -> remaining=4 < floor (call 3) and breaks before any second post.
    times = [0.0, 0.0, 6.0]
    state = {"i": 0}

    def fake_monotonic() -> float:
        value = times[min(state["i"], len(times) - 1)]
        state["i"] += 1
        return value

    monkeypatch.setattr("src.llm.ollama._monotonic", fake_monotonic)

    result = await OllamaSupplementParser(
        settings,
        http_client=client,
    ).parse_supplement_ocr_text(_SUBSTANTIAL_OCR)

    assert client.calls == 1
    assert result.ingredient_candidates == []


@pytest.mark.asyncio
async def test_parse_retries_after_transport_error() -> None:
    """Verify a transient transport error triggers a retry that then succeeds."""
    settings = _settings()
    client = _RaiseThenSucceedClient()

    result = await OllamaSupplementParser(
        settings,
        http_client=client,
    ).parse_supplement_ocr_text(_SUBSTANTIAL_OCR)

    assert client.calls == 2
    assert len(result.ingredient_candidates) == 1


@pytest.mark.asyncio
async def test_parse_returns_last_empty_after_attempts_exhausted() -> None:
    """Verify an always-empty parse returns the empty result after all attempts."""
    settings = _settings()
    client = _AlwaysEmptyClient()

    result = await OllamaSupplementParser(
        settings,
        http_client=client,
    ).parse_supplement_ocr_text(_SUBSTANTIAL_OCR)

    assert client.calls == settings.ollama_parse_max_attempts
    assert result.ingredient_candidates == []


@pytest.mark.asyncio
async def test_parse_raises_after_all_attempts_error() -> None:
    """Verify the last error is raised when every attempt fails."""
    settings = _settings()
    client = _AlwaysRaiseClient()

    with pytest.raises(OllamaClientError):
        await OllamaSupplementParser(
            settings,
            http_client=client,
        ).parse_supplement_ocr_text(_SUBSTANTIAL_OCR)

    assert client.calls == settings.ollama_parse_max_attempts


_VALID_SALVAGE_CANDIDATE = {
    "display_name": "비타민 B6",
    "original_name": "Vitamin B6",
    "amount": 10.5,
    "unit": "mg",
    "daily_value_percent": 618.0,
    "confidence": 0.0,
    "source": "ollama_structured",
}
# display_name exceeds the schema's 120-char cap -> whole-object validation fails.
_OVERLENGTH_SALVAGE_CANDIDATE = {
    "display_name": "X" * 200,
    "confidence": 0.0,
    "source": "ollama_structured",
}
_OVERLENGTH_RESPONSE_CONTENT = json.dumps(
    {"ingredient_candidates": [_VALID_SALVAGE_CANDIDATE, _OVERLENGTH_SALVAGE_CANDIDATE]},
    ensure_ascii=False,
)


def test_salvage_parse_result_keeps_valid_drops_invalid_candidate() -> None:
    """Verify salvage keeps individually-valid candidates and drops the bad one."""
    norm = {
        "parsed_product": {},
        "ingredient_candidates": [_VALID_SALVAGE_CANDIDATE, _OVERLENGTH_SALVAGE_CANDIDATE],
    }
    try:
        SupplementStructuredParseResult.model_validate_json(json.dumps(norm, ensure_ascii=False))
        raise AssertionError("expected the over-length candidate to fail validation")
    except ValidationError as error:
        result = _salvage_parse_result(norm, error)
    assert len(result.ingredient_candidates) == 1
    assert result.ingredient_candidates[0].display_name == "비타민 B6"


class _OverlengthCandidateClient:
    """Fake client returning one valid + one over-length ingredient candidate."""

    def __init__(self) -> None:
        self.calls = 0

    async def post(self, url: str, *, json: Mapping[str, Any], timeout: float) -> _FakeResponse:
        del url, json, timeout
        self.calls += 1
        return _FakeResponse({"message": {"content": _OVERLENGTH_RESPONSE_CONTENT}})

    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        del url, timeout
        return _FakeResponse({"models": []})


@pytest.mark.asyncio
async def test_parse_salvages_valid_candidate_when_one_overflows() -> None:
    """Verify the parser returns the salvageable ingredient instead of empty."""
    settings = _settings()
    client = _OverlengthCandidateClient()

    result = await OllamaSupplementParser(
        settings,
        http_client=client,
    ).parse_supplement_ocr_text(_SUBSTANTIAL_OCR)

    assert client.calls == 1
    assert len(result.ingredient_candidates) == 1
    assert result.ingredient_candidates[0].display_name == "비타민 B6"
