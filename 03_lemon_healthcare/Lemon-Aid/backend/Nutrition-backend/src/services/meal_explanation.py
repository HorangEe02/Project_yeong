"""RAG-backed safe explanations for confirmed meal records."""

from __future__ import annotations

import json
from collections.abc import Mapping

from pydantic import ValidationError

from src.config import Settings
from src.llm.ollama import (
    OllamaChatClient,
    OllamaClientError,
    OllamaConfigurationError,
    extract_ollama_message_content,
)
from src.models.schemas.meal import (
    MealExplainRequest,
    MealExplainResponse,
    MealExplanationGuidance,
    MealExplanationSourceCitation,
    MealRecordResponse,
)
from src.nutrition.deficiency_analysis import FORBIDDEN_TERMS, contains_forbidden_terms
from src.services.llm_wiki_retrieval import LlmWikiCitation, retrieve_llm_wiki_context_db

MEAL_EXPLAIN_SYSTEM_PROMPT = """
You explain a confirmed meal record for a healthcare app.
Use only the provided sanitized meal fields and WIKI excerpts. Do not infer
unseen foods, medical diagnoses, treatments, prescriptions, medication changes,
or dosage changes. Return recommendation, caution, consultation, and confirmation
language only. Cite only server-provided source_citations and never invent a
source. Return only JSON matching the supplied schema.
""".strip()
MEAL_EXPLANATION_DISCLAIMER = (
    "이 내용은 사용자가 확인한 식단 기록 기준의 건강관리 참고 정보이며, "
    "개인 건강 상태를 확정하거나 복약 변경을 지시하지 않습니다."
)
HIGH_SODIUM_MEAL_MG = 1500
MEAL_SUMMARY_NAME_LIMIT = 3


class MealExplanationError(RuntimeError):
    """Raised when a meal explanation cannot be safely generated."""


async def explain_meal_record(
    meal: MealRecordResponse,
    request: MealExplainRequest,
    settings: Settings,
) -> MealExplainResponse:
    """Return a safe RAG-backed explanation for one confirmed meal record.

    Args:
        meal: Confirmed meal response built with current-user owner filtering.
        request: Explanation options from the client.
        settings: Runtime settings, including local Ollama and WIKI retrieval.

    Returns:
        Safe explanation response with local WIKI citations when available.
    """
    source_citations = await _wiki_citations_for_meal(meal, settings)
    fallback = build_deterministic_meal_explanation(
        meal,
        warnings=(),
        source_citations=source_citations,
    )
    if not request.use_local_llm:
        return fallback

    try:
        return await _explain_meal_with_local_ollama(
            meal,
            settings,
            source_citations=source_citations,
        )
    except (OllamaClientError, OllamaConfigurationError, MealExplanationError):
        return build_deterministic_meal_explanation(
            meal,
            warnings=("llm_explanation_unavailable",),
            source_citations=source_citations,
        )


def build_deterministic_meal_explanation(
    meal: MealRecordResponse,
    *,
    warnings: tuple[str, ...],
    source_citations: tuple[MealExplanationSourceCitation, ...] = (),
) -> MealExplainResponse:
    """Build a deterministic meal explanation without calling a local LLM.

    Args:
        meal: Confirmed meal response.
        warnings: Stable warning codes.
        source_citations: Local WIKI citations used for grounding.

    Returns:
        Safe deterministic explanation.
    """
    food_names = [item.display_name for item in meal.food_items]
    bullets = _deterministic_meal_bullets(meal, food_names)
    guidance = _deterministic_meal_guidance(meal, food_names)
    response = MealExplainResponse(
        safe_user_message=_meal_safe_summary(food_names),
        explanation_bullets=bullets,
        guidance=guidance,
        clinical_disclaimer=MEAL_EXPLANATION_DISCLAIMER,
        llm_used=False,
        source_citations=list(source_citations),
        warnings=list(warnings),
    )
    _reject_forbidden_response(response)
    return response


async def _explain_meal_with_local_ollama(
    meal: MealRecordResponse,
    settings: Settings,
    *,
    source_citations: tuple[MealExplanationSourceCitation, ...],
) -> MealExplainResponse:
    """Ask local Ollama to refine a confirmed meal explanation."""
    payload = _build_meal_explanation_payload(
        meal,
        settings,
        source_citations=source_citations,
    )
    response_body = await OllamaChatClient(settings).post_chat(payload)
    content = extract_ollama_message_content(response_body)
    try:
        response = MealExplainResponse.model_validate_json(content)
    except ValidationError as exc:
        raise MealExplanationError("Meal explanation schema validation failed.") from exc
    response.source_citations = list(source_citations)
    response.llm_used = True
    _reject_forbidden_response(response)
    return response


def _build_meal_explanation_payload(
    meal: MealRecordResponse,
    settings: Settings,
    *,
    source_citations: tuple[MealExplanationSourceCitation, ...],
) -> dict[str, object]:
    """Build a sanitized Ollama structured-output payload for meal explanation."""
    return {
        "model": settings.ollama_model,
        "stream": False,
        "format": MealExplainResponse.model_json_schema(),
        "messages": [
            {"role": "system", "content": MEAL_EXPLAIN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "<confirmed_meal>\n"
                    f"{json.dumps(_meal_context(meal), ensure_ascii=False)}\n"
                    "</confirmed_meal>\n"
                    "<server_wiki_context>\n"
                    f"{json.dumps(_wiki_context_json(source_citations), ensure_ascii=False)}\n"
                    "</server_wiki_context>\n"
                    "Return concise Korean JSON. Use only guidance labels 권장, 주의, "
                    "상담 권고, 확인 필요. Keep the fixed clinical disclaimer."
                ),
            },
        ],
        "options": {"temperature": 0.1},
    }


def _meal_context(meal: MealRecordResponse) -> dict[str, object]:
    """Return sanitized confirmed meal fields for prompts and retrieval."""
    return {
        "meal_type": meal.meal_type.value,
        "food_items": [
            {
                "display_name": item.display_name,
                "portion_amount": item.portion_amount,
                "portion_unit": item.portion_unit,
                "kcal": item.kcal,
                "carb_g": item.carb_g,
                "protein_g": item.protein_g,
                "fat_g": item.fat_g,
                "sodium_mg": item.sodium_mg,
                "taxonomy": (
                    {
                        "cuisine_code": item.catalog_item.cuisine_code,
                        "course_code": item.catalog_item.course_code,
                        "canonical_name_ko": item.catalog_item.canonical_name_ko,
                        "canonical_name_en": item.catalog_item.canonical_name_en,
                    }
                    if item.catalog_item is not None
                    else None
                ),
            }
            for item in meal.food_items[:20]
        ],
        "nutrition_summary": _bounded_nutrition_summary(meal.nutrition_summary),
    }


def _bounded_nutrition_summary(summary: Mapping[str, object]) -> dict[str, object]:
    """Return primitive nutrition summary values suitable for LLM input."""
    allowed_keys = ("kcal", "carb_g", "protein_g", "fat_g", "sodium_mg")
    bounded: dict[str, object] = {}
    for key in allowed_keys:
        value = summary.get(key)
        if value is not None and isinstance(value, int | float | str):
            bounded[key] = value
    return bounded


async def _wiki_citations_for_meal(
    meal: MealRecordResponse,
    settings: Settings,
) -> tuple[MealExplanationSourceCitation, ...]:
    """Retrieve WIKI citations for a confirmed meal.

    Uses the database-backed retriever so vector/hybrid semantic search applies
    when enabled, with automatic lexical fallback otherwise. Confirmed food items
    expose ``catalog_item.cuisine_code``, which maps directly to ``food_cuisine``
    entity links, so those codes are passed as ``entity_keys`` to boost the
    matching cuisine wiki pages.

    Args:
        meal: Confirmed meal response built with current-user owner filtering.
        settings: Runtime settings with local WIKI controls.

    Returns:
        Server-selected WIKI citations safe to expose to the client.
    """
    query = _meal_wiki_query(meal)
    cuisine_codes = _meal_cuisine_codes(meal)
    result = await retrieve_llm_wiki_context_db(query, settings, entity_keys=cuisine_codes)
    return tuple(_source_citation(citation) for citation in result.citations)


def _meal_cuisine_codes(meal: MealRecordResponse) -> tuple[str, ...]:
    """Return distinct cuisine codes from confirmed catalog items.

    Args:
        meal: Confirmed meal response.

    Returns:
        First-seen-ordered, deduplicated non-empty cuisine codes used as
        ``food_cuisine`` entity-link keys.
    """
    codes: list[str] = []
    seen: set[str] = set()
    for item in meal.food_items[:20]:
        if item.catalog_item is None:
            continue
        code = item.catalog_item.cuisine_code
        if code and code not in seen:
            codes.append(code)
            seen.add(code)
    return tuple(codes)


def _meal_wiki_query(meal: MealRecordResponse) -> str:
    """Build a bounded lexical WIKI query from confirmed food fields."""
    tokens: list[str] = []
    for item in meal.food_items[:20]:
        tokens.append(item.display_name)
        if item.catalog_item is not None:
            tokens.extend(
                (
                    item.catalog_item.canonical_name_ko,
                    item.catalog_item.canonical_name_en or "",
                    item.catalog_item.cuisine_code,
                    item.catalog_item.course_code,
                )
            )
    tokens.extend(
        str(value) for value in _bounded_nutrition_summary(meal.nutrition_summary).values()
    )
    return " ".join(token.strip() for token in tokens if token and token.strip())[:1600]


def _source_citation(citation: LlmWikiCitation) -> MealExplanationSourceCitation:
    """Map generic WIKI retrieval citations to meal API citations."""
    return MealExplanationSourceCitation(
        title=citation.title,
        source_path=citation.source_path,
        heading=citation.heading,
        excerpt=citation.excerpt,
        score=citation.score,
    )


def _wiki_context_json(
    source_citations: tuple[MealExplanationSourceCitation, ...],
) -> list[dict[str, object]]:
    """Serialize citations into the only source list visible to Ollama."""
    return [
        {
            "title": citation.title,
            "source_path": citation.source_path,
            "heading": citation.heading,
            "excerpt": citation.excerpt,
        }
        for citation in source_citations
    ]


def _deterministic_meal_bullets(
    meal: MealRecordResponse,
    food_names: list[str],
) -> list[str]:
    """Build deterministic bullets from confirmed foods and nutrition summary."""
    bullets = [f"확인된 음식은 {len(food_names)}개입니다."]
    summary = _bounded_nutrition_summary(meal.nutrition_summary)
    if kcal := summary.get("kcal"):
        bullets.append(f"기록된 열량은 약 {kcal} kcal입니다.")
    macros = [
        f"{label} {summary[key]}g"
        for key, label in (("carb_g", "탄수화물"), ("protein_g", "단백질"), ("fat_g", "지방"))
        if summary.get(key) is not None
    ]
    if macros:
        bullets.append("주요 영양소 기록: " + ", ".join(macros))
    if summary.get("sodium_mg") is not None:
        bullets.append(f"나트륨 기록은 {summary['sodium_mg']}mg입니다.")
    if not food_names:
        bullets.append("음식명이 비어 있어 직접 확인이 필요합니다.")
    return bullets[:6]


def _deterministic_meal_guidance(
    meal: MealRecordResponse,
    food_names: list[str],
) -> list[MealExplanationGuidance]:
    """Build constrained recommendation buckets without medical claims."""
    guidance = [
        MealExplanationGuidance(
            label="확인 필요",
            message="기록된 음식명과 양이 실제 식사와 맞는지 먼저 확인하세요.",
        )
    ]
    summary = _bounded_nutrition_summary(meal.nutrition_summary)
    if not food_names:
        guidance.append(
            MealExplanationGuidance(
                label="확인 필요",
                message="음식 후보가 비어 있어 직접 입력이나 재촬영이 필요합니다.",
            )
        )
    if (
        _numeric(summary.get("sodium_mg"))
        and (_numeric(summary.get("sodium_mg")) or 0) > HIGH_SODIUM_MEAL_MG
    ):
        guidance.append(
            MealExplanationGuidance(
                label="주의",
                message="나트륨 수치가 높게 기록되어 다음 식사에서 짠 음식을 줄이는지 확인하세요.",
            )
        )
    if _numeric(summary.get("protein_g")) is None:
        guidance.append(
            MealExplanationGuidance(
                label="권장",
                message="단백질량이 비어 있으면 식단 균형 판단 전에 값을 확인해보세요.",
            )
        )
    return guidance[:8]


def _meal_safe_summary(food_names: list[str]) -> str:
    """Return a short safe summary for chat handoff."""
    if not food_names:
        return "확인된 음식 정보가 부족해 식단 설명을 위해 직접 확인이 필요합니다."
    primary = ", ".join(food_names[:MEAL_SUMMARY_NAME_LIMIT])
    suffix = (
        ""
        if len(food_names) <= MEAL_SUMMARY_NAME_LIMIT
        else f" 외 {len(food_names) - MEAL_SUMMARY_NAME_LIMIT}개"
    )
    return f"{primary}{suffix} 기준으로 식단 기록을 설명할 수 있습니다."


def _numeric(value: object) -> float | None:
    """Convert primitive numeric values to float when possible."""
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _reject_forbidden_response(response: MealExplainResponse) -> None:
    """Reject unsafe diagnostic or treatment-like wording.

    Args:
        response: Candidate response.

    Raises:
        MealExplanationError: If forbidden wording appears outside fixed labels.
    """
    messages = [
        response.safe_user_message,
        response.clinical_disclaimer,
        *response.explanation_bullets,
        *(guidance.message for guidance in response.guidance),
    ]
    if contains_forbidden_terms(messages) or any(
        term in message for term in FORBIDDEN_TERMS for message in messages
    ):
        raise MealExplanationError("Meal explanation contains unsafe wording.")
