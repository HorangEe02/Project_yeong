"""Tiered wiki-RAG chatbot fallback tests (pure, no network/DB)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from src.config import Settings
from src.services import chatbot_wiki_rag
from src.services.chatbot_wiki_rag import (
    WikiRagAnswer,
    _build_chat_payload,
    _citation_to_public_source,
    answer_with_wiki_rag,
)
from src.services.llm_wiki_retrieval import LlmWikiCitation, LlmWikiRetrievalResult


def _settings() -> Settings:
    """Return hermetic settings for the fallback under test."""
    return Settings(_env_file=None)


def _citation(*, title: str, path: str, heading: str | None = None) -> LlmWikiCitation:
    """Build a wiki citation fixture."""
    return LlmWikiCitation(
        title=title,
        source_path=path,
        heading=heading,
        excerpt=f"{title} 관련 근거 발췌.",
        score=0.9,
    )


def _patch_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    citations: tuple[LlmWikiCitation, ...] | Exception,
) -> None:
    """Patch the DB retrieval seam to return citations or raise."""

    async def _fake_retrieve(query: str, _settings_arg: Settings, **_kwargs: Any) -> Any:
        if isinstance(citations, Exception):
            raise citations
        return LlmWikiRetrievalResult(query=query, citations=citations)

    monkeypatch.setattr(chatbot_wiki_rag, "retrieve_llm_wiki_context_db", _fake_retrieve)


def _patch_llm(monkeypatch: pytest.MonkeyPatch, content: str | Exception) -> None:
    """Patch OllamaChatClient.post_chat to return content or raise."""

    async def _fake_post_chat(_self: Any, _payload: Any) -> dict[str, Any]:
        if isinstance(content, Exception):
            raise content
        return {"message": {"content": content}}

    monkeypatch.setattr(chatbot_wiki_rag.OllamaChatClient, "post_chat", _fake_post_chat)


@pytest.mark.asyncio
async def test_grounded_answer_cites_used_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """Grounded answer maps cited index to a public source from citation[0]."""
    citations = (
        _citation(title="비타민 D", path="vitamins/vitamin-d.md", heading="비타민 D 개요"),
        _citation(title="마그네슘", path="minerals/magnesium.md"),
    )
    _patch_retrieval(monkeypatch, citations)
    _patch_llm(
        monkeypatch,
        json.dumps({"answer": "비타민 D는 뼈 건강에 도움이 됩니다.", "used_sources": [1]}),
    )

    answer = await answer_with_wiki_rag("비타민 D 효능 알려줘", settings=_settings())

    assert isinstance(answer, WikiRagAnswer)
    assert answer.message == "비타민 D는 뼈 건강에 도움이 됩니다."
    assert answer.answerability == "answered_from_wiki"
    assert answer.provider == "gemma_wiki_rag"
    assert answer.used_tools == ["llm_wiki_rag"]
    assert answer.safety_warnings == [chatbot_wiki_rag.SAFETY_DISCLAIMER]
    assert len(answer.sources) == 1
    assert answer.sources[0] == {
        "source_id": "vitamins/vitamin-d.md",
        "source_title": "비타민 D 개요",
        "source_family": "lemon_wiki",
        "review_status": "reference",
    }


@pytest.mark.asyncio
async def test_off_topic_general_answer_has_no_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty used_sources yields a general fallback with no sources."""
    citations = (_citation(title="철분", path="minerals/iron.md"),)
    _patch_retrieval(monkeypatch, citations)
    _patch_llm(
        monkeypatch,
        json.dumps({"answer": "일반적인 정보로 안내드릴게요.", "used_sources": []}),
    )

    answer = await answer_with_wiki_rag("오늘 날씨 어때?", settings=_settings())

    assert answer.message == "일반적인 정보로 안내드릴게요."
    assert answer.sources == []
    assert answer.answerability == "general_fallback"
    assert answer.safety_warnings == [chatbot_wiki_rag.SAFETY_DISCLAIMER]


@pytest.mark.asyncio
async def test_non_json_llm_response_is_used_as_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-JSON content becomes the message with no sources and no exception."""
    citations = (_citation(title="아연", path="minerals/zinc.md"),)
    _patch_retrieval(monkeypatch, citations)
    _patch_llm(monkeypatch, "이건 그냥 평문 응답이에요.")

    answer = await answer_with_wiki_rag("아연이 뭐야?", settings=_settings())

    assert answer.message == "이건 그냥 평문 응답이에요."
    assert answer.sources == []
    assert answer.answerability == "general_fallback"


@pytest.mark.asyncio
async def test_retrieval_failure_is_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retrieval raising yields the safe message, not an exception."""
    _patch_retrieval(monkeypatch, RuntimeError("pgvector down"))
    _patch_llm(monkeypatch, json.dumps({"answer": "unused", "used_sources": [1]}))

    answer = await answer_with_wiki_rag("질문", settings=_settings())

    assert answer.message == chatbot_wiki_rag._SAFE_FALLBACK_MESSAGE
    assert answer.sources == []
    assert answer.answerability == "general_fallback"
    assert answer.provider == "gemma_wiki_rag"


@pytest.mark.asyncio
async def test_llm_failure_is_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM raising yields the safe message, not an exception."""
    citations = (_citation(title="칼슘", path="minerals/calcium.md"),)
    _patch_retrieval(monkeypatch, citations)
    _patch_llm(monkeypatch, RuntimeError("ollama down"))

    answer = await answer_with_wiki_rag("칼슘", settings=_settings())

    assert answer.message == chatbot_wiki_rag._SAFE_FALLBACK_MESSAGE
    assert answer.sources == []
    assert answer.answerability == "general_fallback"


@pytest.mark.asyncio
async def test_out_of_range_index_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid 1-based indices are dropped without error."""
    citations = (_citation(title="엽산", path="vitamins/folate.md"),)
    _patch_retrieval(monkeypatch, citations)
    _patch_llm(
        monkeypatch,
        json.dumps({"answer": "엽산 정보입니다.", "used_sources": [1, 5, 0, -2]}),
    )

    answer = await answer_with_wiki_rag("엽산", settings=_settings())

    assert answer.answerability == "answered_from_wiki"
    assert [source["source_id"] for source in answer.sources] == ["vitamins/folate.md"]


@pytest.mark.asyncio
async def test_dangerous_directive_in_answer_degrades_to_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answer containing a forbidden medical directive is degraded to the safe fallback."""
    citations = (_citation(title="비타민 B12", path="vitamins/b12.md"),)
    _patch_retrieval(monkeypatch, citations)
    # "약을 중단하세요" is in _DANGEROUS_DIRECTIVE_PHRASES — must never reach the user.
    _patch_llm(
        monkeypatch,
        json.dumps(
            {
                "answer": "지금 드시는 약을 중단하세요. 대신 비타민 B12만 드세요.",
                "used_sources": [1],
            }
        ),
    )

    answer = await answer_with_wiki_rag("B12 권장량이 얼마야?", settings=_settings())

    assert answer.message == chatbot_wiki_rag._SAFE_FALLBACK_MESSAGE
    assert answer.sources == []
    assert answer.answerability == "general_fallback"
    assert answer.safety_warnings == [chatbot_wiki_rag.SAFETY_DISCLAIMER]


@pytest.mark.asyncio
async def test_safe_answer_passes_safety_screen_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A safe deferral mentioning 진단/치료/처방 must NOT trip the screen."""
    citations = (_citation(title="비타민 C", path="vitamins/c.md", heading="비타민 C 효능"),)
    _patch_retrieval(monkeypatch, citations)
    _patch_llm(
        monkeypatch,
        json.dumps(
            {
                # 진단/치료/처방 in a SAFE deferral — must NOT false-positive.
                "answer": (
                    "비타민 C는 항산화 작용을 합니다. 정확한 진단·치료·처방은 "
                    "전문가와 상담하세요."
                ),
                "used_sources": [1],
            }
        ),
    )

    answer = await answer_with_wiki_rag("비타민 C 효능 알려줘", settings=_settings())

    assert "비타민 C는 항산화 작용" in answer.message
    assert answer.answerability == "answered_from_wiki"
    assert len(answer.sources) == 1


def test_user_health_summary_is_injected_as_health_context() -> None:
    """The user's meds/supplements reach the prompt as actionable health context."""
    payload = _build_chat_payload(
        message="비타민 C 먹어도 돼?",
        citations=[],
        user_context_summary="복용 중인 약: 메트포르민 / 복용 중인 영양제: 아연",
        settings=_settings(),
    )

    user_content = payload["messages"][1]["content"]
    assert "메트포르민" in user_content
    assert "아연" in user_content
    # Framed as the user's health info (not the old "말투 참고용" tone label).
    assert "사용자 건강 정보" in user_content
    assert "상호작용" in user_content  # interaction guidance present


def test_citation_to_public_source_only_allowed_fields() -> None:
    """Public source mapping emits only PUBLIC_CHATBOT_SOURCE_FIELDS-safe keys."""
    citation = _citation(title="제목", path="topic/doc.md", heading="섹션 제목")

    source = _citation_to_public_source(citation)

    assert source == {
        "source_id": "topic/doc.md",
        "source_title": "섹션 제목",
        "source_family": "lemon_wiki",
        "review_status": "reference",
    }
    assert "source_url" not in source
    # heading falls back to title when no heading is present.
    no_heading = _citation_to_public_source(_citation(title="제목만", path="t/d.md"))
    assert no_heading["source_title"] == "제목만"
