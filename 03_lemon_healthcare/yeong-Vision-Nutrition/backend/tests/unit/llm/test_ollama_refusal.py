"""``OllamaAdapter`` S2 forbidden term 게이트 검증.

S2 ① raw content 단계 / S2 ② 파싱된 필드 단계 양쪽에서 forbidden term이 발견되면
``LLMRefusalError`` 로 차단되는지 검증한다.

Reference:
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.2 S2
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.llm.exceptions import LLMRefusalError
from src.llm.ollama import OllamaAdapter


def _mock_chat_response(content: str | None) -> Any:
    response = MagicMock()
    response.message.content = content
    return response


class TestOllamaAdapterS2:
    """S2 게이트 — raw content / parsed fields."""

    @pytest.mark.asyncio
    async def test_raw_content_with_diagnose_term_raises(self) -> None:
        """S2 ①: raw content에 의료 표현이 있으면 즉시 거부."""
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response(
            json.dumps(
                {
                    "product_name": "진단용 보조제",
                    "ingredients": [{"name_ko": "x", "amount": 1, "unit": "mg"}],
                },
                ensure_ascii=False,
            )
        )
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMRefusalError) as exc_info:
            await adapter.parse_supplement("text")
        assert "진단" in exc_info.value.terms

    @pytest.mark.asyncio
    async def test_field_value_with_phrase_term_raises(self) -> None:
        """S2 ②: product_name 등 필드 값에 phrase 금지 표현이 있어도 차단."""
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response(
            json.dumps(
                {
                    "product_name": "이 약을 드세요 정",
                    "ingredients": [{"name_ko": "비타민 X", "amount": 1, "unit": "mg"}],
                },
                ensure_ascii=False,
            )
        )
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMRefusalError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_english_forbidden_term_in_field_raises(self) -> None:
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response(
            json.dumps(
                {
                    "ingredients": [
                        {
                            "name_ko": "비타민 X",
                            "name_en": "Vitamin treatment for cold",
                            "amount": 1,
                            "unit": "mg",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMRefusalError) as exc_info:
            await adapter.parse_supplement("text")
        assert "treatment" in exc_info.value.terms

    @pytest.mark.asyncio
    async def test_warning_field_with_forbidden_term_raises(self) -> None:
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response(
            json.dumps(
                {
                    "ingredients": [{"name_ko": "비타민 C", "amount": 1, "unit": "mg"}],
                    "warnings": ["이 의약품과 함께 복용 시 주의"],
                },
                ensure_ascii=False,
            )
        )
        adapter = OllamaAdapter(client=client)
        with pytest.raises(LLMRefusalError):
            await adapter.parse_supplement("text")

    @pytest.mark.asyncio
    async def test_clean_response_passes(self) -> None:
        """clean response — 의료 표현 없는 정상 케이스는 통과."""
        client = AsyncMock()
        client.chat.return_value = _mock_chat_response(
            json.dumps(
                {
                    "product_name": "종합비타민",
                    "ingredients": [{"name_ko": "비타민 C", "amount": 1000, "unit": "mg"}],
                    "warnings": ["임산부는 섭취 전 전문가와 상담하세요"],
                },
                ensure_ascii=False,
            )
        )
        adapter = OllamaAdapter(client=client)
        result = await adapter.parse_supplement("text")
        assert result.product_name == "종합비타민"
        assert len(result.warnings) == 1
