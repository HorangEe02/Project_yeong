"""Daily health score WIKI citation tests."""

from __future__ import annotations

from typing import Any

import pytest
from src.config import Settings
from src.services import daily_health_score_explanation
from src.services.daily_health_score_explanation import wiki_citations_for_score
from src.services.llm_wiki_retrieval import LlmWikiCitation, LlmWikiRetrievalResult


def _settings() -> Settings:
    """Return minimal settings for explanation tests.

    Returns:
        Settings object; WIKI retrieval is stubbed so values are irrelevant.
    """
    return Settings(_env_file=None)


@pytest.mark.asyncio
async def test_wiki_citations_map_five_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify retriever citations map to the five daily-score citation fields."""

    async def fake_retriever(
        _query: str,
        _settings: Settings,
        *,
        entity_keys: tuple[str, ...] = (),  # noqa: ARG001
    ) -> LlmWikiRetrievalResult:
        return LlmWikiRetrievalResult(
            query=_query,
            citations=(
                LlmWikiCitation(
                    title="나트륨 섭취",
                    source_path="minerals/sodium.md",
                    heading="권장량",
                    excerpt="나트륨 권장 섭취 기준 안내.",
                    score=0.91,
                ),
            ),
        )

    monkeypatch.setattr(
        daily_health_score_explanation,
        "retrieve_llm_wiki_context_db",
        fake_retriever,
    )

    citations = await wiki_citations_for_score(["sodium_over"], _settings())

    assert len(citations) == 1
    citation = citations[0]
    assert citation.title == "나트륨 섭취"
    assert citation.source_path == "minerals/sodium.md"
    assert citation.heading == "권장량"
    assert citation.excerpt == "나트륨 권장 섭취 기준 안내."
    assert citation.score == 0.91


@pytest.mark.asyncio
async def test_wiki_citations_empty_result_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an empty retriever result returns an empty list (fail-open)."""

    async def fake_retriever(
        _query: str,
        _settings: Settings,
        *,
        entity_keys: tuple[str, ...] = (),  # noqa: ARG001
    ) -> LlmWikiRetrievalResult:
        return LlmWikiRetrievalResult(query=_query, citations=())

    monkeypatch.setattr(
        daily_health_score_explanation,
        "retrieve_llm_wiki_context_db",
        fake_retriever,
    )

    citations = await wiki_citations_for_score(["sodium_over"], _settings())

    assert citations == []


@pytest.mark.asyncio
async def test_wiki_citations_no_mappable_drivers_skips_retriever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an unmappable driver returns an empty list without calling the retriever."""

    async def fail_retriever(*_args: object, **_kwargs: object) -> LlmWikiRetrievalResult:
        raise AssertionError("retriever must not be called for unmappable drivers")

    monkeypatch.setattr(
        daily_health_score_explanation,
        "retrieve_llm_wiki_context_db",
        fail_retriever,
    )

    citations = await wiki_citations_for_score(["unknown_driver"], _settings())

    assert citations == []


@pytest.mark.asyncio
async def test_sodium_driver_passes_sodium_category_entity_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the sodium driver resolves the sodium nutrient code into entity keys."""
    captured: dict[str, Any] = {}

    async def fake_retriever(
        query: str,
        _settings: Settings,
        *,
        entity_keys: tuple[str, ...] = (),
    ) -> LlmWikiRetrievalResult:
        captured["query"] = query
        captured["entity_keys"] = entity_keys
        return LlmWikiRetrievalResult(query=query, citations=())

    def spy_category_keys(codes: Any) -> tuple[str, ...]:
        captured["codes"] = tuple(codes)
        return ("나트륨",)

    monkeypatch.setattr(
        daily_health_score_explanation,
        "retrieve_llm_wiki_context_db",
        fake_retriever,
    )
    monkeypatch.setattr(
        daily_health_score_explanation,
        "category_keys_for_nutrient_codes",
        spy_category_keys,
    )

    await wiki_citations_for_score(["sodium_over"], _settings())

    assert captured["codes"] == ("sodium_mg",)
    assert captured["entity_keys"] == ("나트륨",)
    assert "나트륨" in captured["query"]
