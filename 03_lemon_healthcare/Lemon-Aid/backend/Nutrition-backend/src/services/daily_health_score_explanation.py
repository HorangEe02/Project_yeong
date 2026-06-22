"""RAG-backed safe citations for the daily health score.

Thin counterpart to :mod:`src.services.meal_explanation`: it turns daily-score
driver codes (e.g. ``sodium_over``) into nutrient codes, resolves supplement
``category_key`` entity keys, builds a bounded Korean query, and retrieves local
WIKI citations via :func:`retrieve_llm_wiki_context_db`.

It is intentionally fail-open: when no driver maps to a nutrient or the WIKI path
is unavailable, it returns an empty list rather than raising. Citations are never
fabricated; only what the retriever returns is mapped to the API contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from src.models.schemas.dashboard import DailyScoreSourceCitation
from src.services.llm_wiki_retrieval import retrieve_llm_wiki_context_db
from src.services.nutrient_category_map import category_keys_for_nutrient_codes

if TYPE_CHECKING:
    from src.config import Settings
    from src.services.llm_wiki_retrieval import LlmWikiCitation

# Daily-score driver code -> (nutrient code, bounded Korean query string).
_DRIVER_TO_NUTRIENT_QUERY: dict[str, tuple[str, str]] = {
    "sodium_over": ("sodium_mg", "나트륨 섭취 기준 권장량"),
    "kcal_over": ("", "하루 열량 섭취 기준 권장량"),
    "kcal_under": ("", "하루 열량 섭취 기준 권장량"),
    "low_steps": ("", "하루 권장 걸음수와 신체 활동 기준"),
}


async def wiki_citations_for_score(
    drivers: Sequence[str],
    settings: Settings,
) -> list[DailyScoreSourceCitation]:
    """Retrieve WIKI citations grounding the daily health score drivers.

    Args:
        drivers: Deduction reason codes produced by the daily score service.
        settings: Runtime settings with local WIKI retrieval controls.

    Returns:
        Server-selected WIKI citations safe to expose to the client. Empty when no
        driver maps to a known query or the WIKI path is unavailable (fail-open).
    """
    nutrient_codes, query_terms = _drivers_to_query(drivers)
    if not query_terms:
        return []

    entity_keys = category_keys_for_nutrient_codes(nutrient_codes)
    query = " ".join(query_terms)
    result = await retrieve_llm_wiki_context_db(query, settings, entity_keys=entity_keys)
    return [_source_citation(citation) for citation in result.citations]


def _drivers_to_query(drivers: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Map driver codes to deduplicated nutrient codes and query terms.

    Args:
        drivers: Deduction reason codes.

    Returns:
        ``(nutrient_codes, query_terms)`` in first-seen order, both deduplicated
        and free of empty entries.
    """
    nutrient_codes: list[str] = []
    query_terms: list[str] = []
    seen_codes: set[str] = set()
    seen_terms: set[str] = set()
    for driver in drivers:
        mapping = _DRIVER_TO_NUTRIENT_QUERY.get(driver)
        if mapping is None:
            continue
        code, term = mapping
        if code and code not in seen_codes:
            nutrient_codes.append(code)
            seen_codes.add(code)
        if term and term not in seen_terms:
            query_terms.append(term)
            seen_terms.add(term)
    return tuple(nutrient_codes), tuple(query_terms)


def _source_citation(citation: LlmWikiCitation) -> DailyScoreSourceCitation:
    """Map a generic WIKI retrieval citation to the daily-score API citation.

    Args:
        citation: Retriever citation.

    Returns:
        Daily-score source citation with the five contract fields.
    """
    return DailyScoreSourceCitation(
        title=citation.title,
        source_path=citation.source_path,
        heading=citation.heading,
        excerpt=citation.excerpt,
        score=citation.score,
    )
