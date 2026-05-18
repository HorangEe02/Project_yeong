"""``OllamaAdapter`` 단위 테스트 (성공 + API/파싱 오류 분기).

S2 forbidden term 게이트는 별도 ``test_ollama_refusal.py`` 에서 검증.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 7
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from ollama import ResponseError
from src.llm.exceptions import LLMApiError, LLMParseError
from src.llm.ollama import OllamaAdapter


def _mock_chat_response(content: str | None) -> Any:
    response = MagicMock()
    response.message.content = content
    return response


class TestOllamaAdapterSuccess:
    @pytest.mark.asyncio
    async def test_parse_supplement_success(self) -> None:
        client = AsyncMock()
        payload = json.dumps(
            {
                "product_name": "종합비타민",
                "ingredients": [
                    {"name_ko": "비타민 C", "amount": 1000, "unit": "mg"},
                    {"name_ko": "비타민 D", "amount": 25, "unit": "μg"},
                ],
            },
            ensure_ascii=False,
        )
        client.chat.return_value = _mock_chat_response(payload)

        adapter = OllamaAdapter(model="qwen3.5:9b", client=client)
        result = await adapter.parse_supplement("OCR 텍스트")

        assert result.product_name == "종합비타민"
        assert len(result.ingredients) == 2
        assert result.engine == "ollama:qwen3.5:9b"
        assert result.raw_text == "OCR 텍스트"

    @pytest.mark.asyncio
    async def test_chat_call_uses_system_prompt_and_sandbox(self) -> None:
        """system + wrapped user 메시지 두 개를 보낸다."""
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response('{"ingredients":[]}')
        adapter = OllamaAdapter(model="qwen3.5:9b", client=client)
        await adapter.parse_supplement("샘플 OCR")

        called_kwargs = client.chat.await_args.kwargs
        messages = called_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "<USER_OCR>" in messages[1]["content"]
        assert "</USER_OCR>" in messages[1]["content"]
        assert "샘플 OCR" in messages[1]["content"]
        # JSON Schema가 format으로 전달됨
        assert isinstance(called_kwargs["format"], dict)

    def test_engine_name(self) -> None:
        adapter = OllamaAdapter(model="qwen3.5:9b", client=AsyncMock())
        assert adapter.engine_name == "ollama:qwen3.5:9b"


class TestOllamaAdapterErrors:
    @pytest.mark.asyncio
    async def test_response_error_wrapped_to_api_error(self) -> None:
        client = AsyncMock()
        client.chat.side_effect = ResponseError("server down")
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMApiError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_connection_error_wrapped(self) -> None:
        client = AsyncMock()
        client.chat.side_effect = ConnectionError("refused")
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMApiError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_empty_content_raises_parse_error(self) -> None:
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response("")
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMParseError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_invalid_json_raises_parse_error(self) -> None:
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response("not-json-at-all")
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMParseError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_schema_violation_raises_parse_error(self) -> None:
        """amount 음수 등 schema 위반은 LLMParseError."""
        client = AsyncMock()
        bad = json.dumps({"ingredients": [{"name_ko": "x", "amount": -10, "unit": "mg"}]})
        client.chat.return_value = _mock_chat_response(bad)
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMParseError):
            await adapter.parse_supplement("text")
