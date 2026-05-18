"""실 로컬 Ollama 서버 통합 테스트.

``RUN_OLLAMA_TESTS=1`` + ``ollama pull qwen3.5:9b`` (또는 ``OLLAMA_MODEL`` 환경변수
지정 모델) 필요. 본 테스트는 ``integration`` 마커로 표시되어 기본 ``pytest`` 실행에서
제외된다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 7
"""

from __future__ import annotations

import os

import pytest
from src.llm.ollama import OllamaAdapter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_OLLAMA_TESTS") != "1",
        reason="Set RUN_OLLAMA_TESTS=1 (and run a local Ollama server) to enable.",
    ),
]


@pytest.mark.asyncio
async def test_parse_typical_label() -> None:
    """일반 영양제 라벨 OCR 텍스트가 ingredient 2개 이상으로 파싱된다."""
    adapter = OllamaAdapter(model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"))
    ocr_text = (
        "종합비타민\n" "1정 중\n" "비타민 C 1000mg\n" "비타민 D3 25μg (1000 IU)\n" "칼슘 600mg\n"
    )
    result = await adapter.parse_supplement(ocr_text)
    assert len(result.ingredients) >= 2
    assert any("비타민" in i.name_ko for i in result.ingredients)


@pytest.mark.asyncio
async def test_response_passes_forbidden_term_filter() -> None:
    """실 모델 응답이 의료법 금지 표현 0건으로 통과한다."""
    adapter = OllamaAdapter(model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"))
    # 의료 표현 trigger를 OCR 텍스트에 포함하지 않으면 응답에도 통상 없음.
    result = await adapter.parse_supplement("비타민 C 1000mg")
    for ing in result.ingredients:
        assert "진단" not in ing.name_ko
        assert "처방" not in ing.name_ko
