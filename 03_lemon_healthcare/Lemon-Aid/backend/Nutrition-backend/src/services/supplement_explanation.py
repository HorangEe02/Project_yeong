"""Safe wording refinement for deterministic supplement impact previews."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from typing import Any

from pydantic import ValidationError

from src.config import Settings
from src.llm.ollama import (
    OllamaChatClient,
    OllamaClientError,
    OllamaConfigurationError,
    extract_ollama_message_content,
)
from src.models.db.health import BodyProfileSnapshot
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.supplement_recommendation import (
    SupplementAnalysisExplainRequest,
    SupplementExplanationSourceCitation,
    SupplementRecommendationExplainRequest,
    SupplementRecommendationExplainResponse,
)
from src.nutrition.deficiency_analysis import FORBIDDEN_TERMS, contains_forbidden_terms
from src.services.llm_wiki_retrieval import LlmWikiCitation, retrieve_llm_wiki_context_db
from src.services.medical_records import MedicalContextSummary
from src.services.nutrient_category_map import (
    category_keys_for_ingredient_texts,
    category_keys_for_nutrient_codes,
)
from src.services.supplement_recommendation import SUPPLEMENT_IMPACT_DISCLAIMER

SUPPLEMENT_EXPLAIN_SYSTEM_PROMPT = """
You rewrite deterministic supplement impact results for a healthcare app.
Do not create new nutrition facts, risk labels, amounts, supplement names, or
medical claims. Do not tell the user to change a dose, treat a disease, diagnose
a condition, or change medication. Use only the provided deterministic preview
and provided WIKI excerpts. Cite only server-provided source_citations and never
invent a source. Return only JSON matching the supplied schema.
""".strip()

SUPPLEMENT_ANALYSIS_EXPLAIN_SYSTEM_PROMPT = """
You explain a supplement OCR analysis preview for a healthcare app.
Use only the provided sanitized fields. Do not infer unseen ingredients, amounts,
risks, diagnoses, treatments, or dosage changes. Do not ask the user to change
medication. Use WIKI excerpts only as background for recommendation, caution,
consultation, or confirmation language. Cite only server-provided source_citations
and never invent a source. Return only JSON matching the supplied schema.
""".strip()
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.6
MAX_SAFE_PROMPT_NUMBER = 1_000_000
MAX_PROFILE_AGE = 120


class SupplementExplanationError(RuntimeError):
    """Raised when a supplement explanation cannot be safely generated."""


async def explain_supplement_recommendation(
    request: SupplementRecommendationExplainRequest,
    settings: Settings,
) -> SupplementRecommendationExplainResponse:
    """Return a safe explanation for a deterministic supplement impact preview.

    Args:
        request: Explanation request.
        settings: Runtime settings.

    Returns:
        Safe explanation response. If local LLM refinement is disabled or rejected,
        a deterministic fallback is returned.
    """
    source_citations = await _wiki_citations_for_recommendation(request, settings)
    fallback = build_deterministic_explanation(
        request,
        warnings=(),
        source_citations=source_citations,
    )
    if not request.use_local_llm:
        return fallback

    try:
        response = await _explain_with_local_ollama(
            request,
            settings,
            source_citations=source_citations,
        )
    except (OllamaClientError, OllamaConfigurationError, SupplementExplanationError):
        return build_deterministic_explanation(
            request,
            warnings=("llm_explanation_unavailable",),
            source_citations=source_citations,
        )
    return response


async def explain_supplement_analysis_preview(
    record: SupplementAnalysisRun,
    request: SupplementAnalysisExplainRequest,
    settings: Settings,
    *,
    profile_snapshot: BodyProfileSnapshot | None = None,
    medical_context_summary: MedicalContextSummary | None = None,
) -> SupplementRecommendationExplainResponse:
    """Return a safe explanation for an OCR analysis preview before registration.

    Args:
        record: Stored supplement analysis preview. Raw OCR text must not be present.
        request: Explanation options.
        settings: Runtime settings.
        profile_snapshot: Optional latest current-user profile snapshot. The caller
            must enforce sensitive-health consent before providing this value.
        medical_context_summary: Optional current-user medical summary. The caller
            must enforce sensitive-health consent before providing this value.

    Returns:
        Safe explanation response. If local LLM refinement is disabled or rejected,
        a deterministic fallback is returned.
    """
    context = _build_analysis_explanation_context(
        record,
        include_profile_context=request.include_profile_context,
        profile_snapshot=profile_snapshot,
        include_medical_context=request.include_medical_context,
        medical_context_summary=medical_context_summary,
    )
    source_citations = await _wiki_citations_for_analysis_context(context, settings)
    fallback = build_deterministic_analysis_explanation(
        record,
        warnings=(),
        include_profile_context=request.include_profile_context,
        profile_snapshot=profile_snapshot,
        include_medical_context=request.include_medical_context,
        medical_context_summary=medical_context_summary,
        context=context,
        source_citations=source_citations,
    )
    if not request.use_local_llm:
        return fallback

    try:
        response = await _explain_analysis_with_local_ollama(
            record,
            settings,
            include_profile_context=request.include_profile_context,
            profile_snapshot=profile_snapshot,
            include_medical_context=request.include_medical_context,
            medical_context_summary=medical_context_summary,
            context=context,
            source_citations=source_citations,
        )
    except (OllamaClientError, OllamaConfigurationError, SupplementExplanationError):
        return build_deterministic_analysis_explanation(
            record,
            warnings=("llm_explanation_unavailable",),
            include_profile_context=request.include_profile_context,
            profile_snapshot=profile_snapshot,
            include_medical_context=request.include_medical_context,
            medical_context_summary=medical_context_summary,
            context=context,
            source_citations=source_citations,
        )
    return response


def build_deterministic_explanation(
    request: SupplementRecommendationExplainRequest,
    *,
    warnings: tuple[str, ...],
    source_citations: tuple[SupplementExplanationSourceCitation, ...] = (),
) -> SupplementRecommendationExplainResponse:
    """Build an explanation without calling an LLM.

    Args:
        request: Explanation request.
        warnings: Safe warning strings.

    Returns:
        Deterministic explanation response.
    """
    preview = request.preview
    bullets: list[str] = []
    if preview.current_supplement_contributions:
        bullets.append(
            f"계산된 보충제 영양소는 {len(preview.current_supplement_contributions)}종입니다."
        )
    if preview.deficiency_support_candidates:
        bullets.append(
            f"낮은 섭취로 표시된 영양소와 겹치는 항목이 "
            f"{len(preview.deficiency_support_candidates)}종 있습니다."
        )
    if preview.excess_or_duplicate_risks:
        bullets.append(
            f"중복 또는 상한 확인이 필요한 항목이 "
            f"{len(preview.excess_or_duplicate_risks)}종 있습니다."
        )
    if preview.missing_profile_fields:
        bullets.append("나이, 성별, 생애주기 같은 개인화 입력 확인이 필요합니다.")
    if not bullets:
        bullets.append("현재 입력 기준으로 표시할 추가 보충제 영향 항목이 없습니다.")

    response = SupplementRecommendationExplainResponse(
        safe_user_message=preview.safe_user_message,
        explanation_bullets=bullets[:6],
        clinical_disclaimer=SUPPLEMENT_IMPACT_DISCLAIMER,
        blocked_terms_detected=[],
        llm_used=False,
        source_citations=list(source_citations),
        warnings=list(warnings),
    )
    _reject_forbidden_response(response)
    return response


def build_deterministic_analysis_explanation(
    record: SupplementAnalysisRun,
    *,
    warnings: tuple[str, ...],
    include_profile_context: bool = False,
    profile_snapshot: BodyProfileSnapshot | None = None,
    include_medical_context: bool = False,
    medical_context_summary: MedicalContextSummary | None = None,
    context: Mapping[str, Any] | None = None,
    source_citations: tuple[SupplementExplanationSourceCitation, ...] = (),
) -> SupplementRecommendationExplainResponse:
    """Build a pre-registration analysis explanation without calling an LLM.

    Args:
        record: Stored supplement analysis preview.
        warnings: Safe warning strings.
        include_profile_context: Whether profile context was requested.
        profile_snapshot: Optional latest current-user profile snapshot.
        include_medical_context: Whether medical context was requested.
        medical_context_summary: Optional current-user medical summary.

    Returns:
        Deterministic explanation response.
    """
    context = (
        dict(context)
        if context is not None
        else _build_analysis_explanation_context(
            record,
            include_profile_context=include_profile_context,
            profile_snapshot=profile_snapshot,
            include_medical_context=include_medical_context,
            medical_context_summary=medical_context_summary,
        )
    )
    ingredient_count = int(context["ingredient_count"])
    missing_sections = list(context["missing_required_sections"])
    bullets: list[str] = []

    product_name = context["product_name"]
    if isinstance(product_name, str) and product_name:
        bullets.append(f"제품명 후보는 {product_name}입니다.")
    else:
        bullets.append("제품명은 라벨을 보며 직접 확인해야 합니다.")

    ingredient_summary = _format_context_ingredients(context["ingredients"])
    if ingredient_count and ingredient_summary:
        bullets.append(
            f"성분 후보 {ingredient_count}개: {ingredient_summary}를 등록 전 검토하세요."
        )
    elif ingredient_count:
        bullets.append(f"성분 후보 {ingredient_count}개를 등록 전 검토하세요.")
    else:
        bullets.append("성분 후보가 비어 있어 수동 입력이나 추가 사진이 필요합니다.")

    intake_method = _mapping(context["intake_method"])
    intake_text = intake_method.get("text")
    if isinstance(intake_text, str) and intake_text:
        bullets.append(f"섭취 방법 후보: {intake_text}")
    elif context["intake_method_present"]:
        bullets.append("섭취 방법 후보가 있어 저장 전 빈도와 1회량을 확인할 수 있습니다.")
    else:
        bullets.append("섭취 방법은 아직 충분하지 않아 직접 확인이 필요합니다.")

    if context["precaution_count"]:
        bullets.append(f"주의 문구 후보 {context['precaution_count']}개가 있습니다.")
    if context["functional_claim_count"]:
        bullets.append(f"기능성 문구 후보 {context['functional_claim_count']}개가 있습니다.")
    _append_profile_context_bullets(bullets, context)
    _append_medical_context_bullets(bullets, context)
    if missing_sections:
        bullets.append(f"추가 확인 섹션: {', '.join(missing_sections[:4])}")

    message = (
        "등록 전 라벨 분석 결과를 확인하세요."
        if ingredient_count
        else "성분 후보가 부족해 제품명과 성분을 직접 확인해야 합니다."
    )
    response = SupplementRecommendationExplainResponse(
        safe_user_message=message,
        explanation_bullets=bullets[:6],
        clinical_disclaimer=SUPPLEMENT_IMPACT_DISCLAIMER,
        blocked_terms_detected=[],
        llm_used=False,
        source_citations=list(source_citations),
        warnings=list(warnings),
    )
    _reject_forbidden_response(response)
    return response


async def _explain_with_local_ollama(
    request: SupplementRecommendationExplainRequest,
    settings: Settings,
    *,
    source_citations: tuple[SupplementExplanationSourceCitation, ...],
) -> SupplementRecommendationExplainResponse:
    """Call local Ollama for schema-constrained wording refinement.

    Args:
        request: Explanation request.
        settings: Runtime settings.

    Returns:
        Validated safe explanation response.

    Raises:
        OllamaClientError: If the local API call fails.
        SupplementExplanationError: If the output is unsafe or schema-invalid.
    """
    payload = _build_explanation_payload(request, settings, source_citations=source_citations)
    data = await OllamaChatClient(settings).post_chat(payload)
    content = extract_ollama_message_content(data)
    try:
        response = SupplementRecommendationExplainResponse.model_validate_json(content)
    except ValidationError as exc:
        raise SupplementExplanationError("Local explanation output failed validation.") from exc
    response.clinical_disclaimer = SUPPLEMENT_IMPACT_DISCLAIMER
    response.llm_used = True
    response.source_citations = list(source_citations)
    _reject_forbidden_response(response)
    return response


async def _explain_analysis_with_local_ollama(
    record: SupplementAnalysisRun,
    settings: Settings,
    *,
    include_profile_context: bool,
    profile_snapshot: BodyProfileSnapshot | None,
    include_medical_context: bool,
    medical_context_summary: MedicalContextSummary | None,
    context: Mapping[str, Any],
    source_citations: tuple[SupplementExplanationSourceCitation, ...],
) -> SupplementRecommendationExplainResponse:
    """Call local Ollama for a pre-registration analysis explanation.

    Args:
        record: Stored supplement analysis preview.
        settings: Runtime settings.
        include_profile_context: Whether profile context was requested.
        profile_snapshot: Optional latest current-user profile snapshot.
        include_medical_context: Whether medical context was requested.
        medical_context_summary: Optional current-user medical summary.

    Returns:
        Validated safe explanation response.

    Raises:
        OllamaClientError: If the local API call fails.
        SupplementExplanationError: If the output is unsafe or schema-invalid.
    """
    payload = _build_analysis_explanation_payload(
        record,
        settings,
        include_profile_context=include_profile_context,
        profile_snapshot=profile_snapshot,
        include_medical_context=include_medical_context,
        medical_context_summary=medical_context_summary,
        context=context,
        source_citations=source_citations,
    )
    data = await OllamaChatClient(settings).post_chat(payload)
    content = extract_ollama_message_content(data)
    try:
        response = SupplementRecommendationExplainResponse.model_validate_json(content)
    except ValidationError as exc:
        raise SupplementExplanationError(
            "Local analysis explanation output failed validation."
        ) from exc
    response.clinical_disclaimer = SUPPLEMENT_IMPACT_DISCLAIMER
    response.llm_used = True
    response.source_citations = list(source_citations)
    _reject_forbidden_response(response)
    return response


def _build_explanation_payload(
    request: SupplementRecommendationExplainRequest,
    settings: Settings,
    *,
    source_citations: tuple[SupplementExplanationSourceCitation, ...],
) -> dict[str, Any]:
    """Build an Ollama Chat payload for safe explanation.

    Args:
        request: Explanation request.
        settings: Runtime settings.

    Returns:
        Ollama chat payload.
    """
    schema = SupplementRecommendationExplainResponse.model_json_schema()
    preview_json = request.preview.model_dump_json()
    wiki_context_json = _wiki_context_json(source_citations)
    user_prompt = (
        "Rewrite the deterministic supplement impact preview in concise Korean. "
        "Do not change any action labels, reason codes, nutrient amounts, or counts. "
        "Do not add new supplement or disease facts. Use the WIKI excerpts only "
        "for source-backed recommendation, caution, consultation, or confirmation "
        "language. If no source supports a claim, say it needs confirmation. Return "
        "JSON that conforms to the schema.\n\n"
        "<deterministic_preview>\n"
        f"{preview_json}\n"
        "</deterministic_preview>\n\n"
        "<server_wiki_context>\n"
        f"{wiki_context_json}\n"
        "</server_wiki_context>\n\n"
        "JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    return {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SUPPLEMENT_EXPLAIN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0},
    }


def _build_analysis_explanation_payload(
    record: SupplementAnalysisRun,
    settings: Settings,
    *,
    include_profile_context: bool,
    profile_snapshot: BodyProfileSnapshot | None,
    include_medical_context: bool,
    medical_context_summary: MedicalContextSummary | None,
    context: Mapping[str, Any] | None = None,
    source_citations: tuple[SupplementExplanationSourceCitation, ...] = (),
) -> dict[str, Any]:
    """Build an Ollama Chat payload from sanitized analysis fields only.

    Args:
        record: Stored supplement analysis preview.
        settings: Runtime settings.
        include_profile_context: Whether profile context was requested.
        profile_snapshot: Optional latest current-user profile snapshot.
        include_medical_context: Whether medical context was requested.
        medical_context_summary: Optional current-user medical summary.

    Returns:
        Ollama chat payload.
    """
    schema = SupplementRecommendationExplainResponse.model_json_schema()
    context = (
        dict(context)
        if context is not None
        else _build_analysis_explanation_context(
            record,
            include_profile_context=include_profile_context,
            profile_snapshot=profile_snapshot,
            include_medical_context=include_medical_context,
            medical_context_summary=medical_context_summary,
        )
    )
    context_json = json.dumps(context, ensure_ascii=False)
    wiki_context_json = _wiki_context_json(source_citations)
    user_prompt = (
        "Rewrite this supplement label analysis preview in concise Korean. "
        "Use only the sanitized OCR-derived fields and optional profile/medical "
        "bucket fields in the JSON context. "
        "Restate ingredient names and amounts only from the provided "
        "ingredients[].amount_text values. When ingredients[].original_name is "
        "present and differs from display_name, write the ingredient as "
        "display_name(original_name). Do not add new ingredients, amounts, "
        "product claims, medical risks, diagnoses, or dosage advice. "
        "If profile_context.available is true, explain only why the user should "
        "review label precautions against that profile bucket. "
        "If medical_context.available is true, use only condition counts, "
        "canonical condition codes, and medication review categories; never quote "
        "raw condition names, raw medication names, doses, or frequencies. "
        "Use WIKI excerpts only for source-backed recommendation, caution, "
        "consultation, or confirmation language. If no source supports a claim, "
        "say it needs confirmation. "
        "Return JSON that conforms to the schema.\n\n"
        "<analysis_preview_context>\n"
        f"{context_json}\n"
        "</analysis_preview_context>\n\n"
        "<server_wiki_context>\n"
        f"{wiki_context_json}\n"
        "</server_wiki_context>\n\n"
        "JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    return {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SUPPLEMENT_ANALYSIS_EXPLAIN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0},
    }


def _build_analysis_explanation_context(
    record: SupplementAnalysisRun,
    *,
    include_profile_context: bool = False,
    profile_snapshot: BodyProfileSnapshot | None = None,
    include_medical_context: bool = False,
    medical_context_summary: MedicalContextSummary | None = None,
) -> dict[str, Any]:
    """Build bounded fields safe to send to the local explanation model.

    Args:
        record: Stored supplement analysis preview.
        include_profile_context: Whether profile context was requested.
        profile_snapshot: Optional latest current-user profile snapshot.
        include_medical_context: Whether medical context was requested.
        medical_context_summary: Optional current-user medical summary.

    Returns:
        Sanitized analysis context without raw OCR text, image bytes, object URIs,
        or provider payloads.
    """
    snapshot = _mapping(record.parsed_snapshot)
    parsed_product = _mapping(snapshot.get("parsed_product"))
    ingredient_candidates = _list_of_mappings(snapshot.get("ingredient_candidates"))
    intake_method = _mapping(snapshot.get("intake_method"))
    label_sections = _list_of_mappings(snapshot.get("label_sections"))
    precautions = _list_of_mappings(snapshot.get("precautions"))
    return {
        "status": _safe_text(record.status, limit=60),
        "ocr_provider": _safe_text(record.ocr_provider, limit=80),
        "ocr_confidence_bucket": _confidence_bucket(record.ocr_confidence),
        "product_name": _safe_text(parsed_product.get("product_name"), limit=120),
        "manufacturer": _safe_text(parsed_product.get("manufacturer"), limit=120),
        "ingredient_count": len(ingredient_candidates),
        "ingredients": [_ingredient_summary(candidate) for candidate in ingredient_candidates[:6]],
        "label_section_excerpts": [
            section
            for section in (_label_section_summary(section) for section in label_sections[:6])
            if section["text_excerpt"]
        ],
        "label_section_types": [
            _safe_text(section.get("section_type"), limit=80) for section in label_sections[:8]
        ],
        "intake_method": _intake_method_summary(intake_method),
        "intake_method_present": bool(intake_method),
        "precautions": [
            precaution
            for precaution in (_precaution_summary(item) for item in precautions[:4])
            if precaution["text"]
        ],
        "precaution_count": len(precautions),
        "functional_claim_count": len(_list_of_mappings(snapshot.get("functional_claims"))),
        "missing_required_sections": _safe_string_list(
            snapshot.get("missing_required_sections"),
            max_items=8,
            limit=80,
        ),
        "low_confidence_fields": _safe_string_list(
            snapshot.get("low_confidence_fields"),
            max_items=12,
            limit=80,
        ),
        "warnings": [
            _safe_text(warning, limit=140)
            for warning in list(record.warnings or [])[:6]
            if _safe_text(warning, limit=140)
        ],
        "profile_context_requested": include_profile_context,
        "profile_context": _profile_context_summary(
            profile_snapshot if include_profile_context else None
        ),
        "medical_context_requested": include_medical_context,
        "medical_context": _medical_context_summary(
            medical_context_summary if include_medical_context else None
        ),
    }


def _recommendation_entity_keys(
    request: SupplementRecommendationExplainRequest,
) -> tuple[str, ...]:
    """Return supplement category keys for a recommendation request's nutrients.

    Maps the deterministic preview's nutrient codes to ``category_key`` values
    (via ``nutrient_category_map``) so the retriever can boost each category's
    canonical wiki page.

    Args:
        request: Explanation request with deterministic preview fields.

    Returns:
        Deduplicated supplement category keys (possibly empty).
    """
    preview = request.preview
    codes: list[str] = []
    for contribution in preview.current_supplement_contributions:
        codes.append(contribution.nutrient_code)
        codes.extend(item.nutrient_code for item in contribution.items)
    for insight in (
        *preview.deficiency_support_candidates,
        *preview.excess_or_duplicate_risks,
    ):
        codes.append(insight.nutrient_code)
    return category_keys_for_nutrient_codes(codes)


def _analysis_entity_keys(context: Mapping[str, Any]) -> tuple[str, ...]:
    """Return supplement category keys inferred from analysis ingredient text.

    Args:
        context: Sanitized analysis context with ingredient candidates.

    Returns:
        Deduplicated supplement category keys (possibly empty).
    """
    texts: list[str] = []
    for ingredient in _list_of_mappings(context.get("ingredients")):
        texts.append(_safe_text(ingredient.get("display_name"), limit=120) or "")
        texts.append(_safe_text(ingredient.get("original_name"), limit=120) or "")
    return category_keys_for_ingredient_texts(texts)


async def _wiki_citations_for_recommendation(
    request: SupplementRecommendationExplainRequest,
    settings: Settings,
) -> tuple[SupplementExplanationSourceCitation, ...]:
    """Retrieve source citations for deterministic supplement impact context.

    Uses the database-backed retriever so vector/hybrid semantic search is used
    when enabled, transparently falling back to the lexical scanner otherwise.
    The preview's nutrient codes are mapped to supplement ``category_key`` values
    and passed as ``entity_keys`` so the retriever boosts each category's
    canonical wiki page.

    Args:
        request: Explanation request with deterministic preview fields.
        settings: Runtime settings with local WIKI controls.

    Returns:
        Server-selected WIKI citations safe to expose to the client.
    """
    query = _recommendation_wiki_query(request)
    entity_keys = _recommendation_entity_keys(request)
    result = await retrieve_llm_wiki_context_db(query, settings, entity_keys=entity_keys)
    return tuple(_source_citation(citation) for citation in result.citations)


async def _wiki_citations_for_analysis_context(
    context: Mapping[str, Any],
    settings: Settings,
) -> tuple[SupplementExplanationSourceCitation, ...]:
    """Retrieve source citations for sanitized analysis-preview context.

    Uses the database-backed retriever (vector/hybrid when enabled, lexical
    otherwise). Ingredient display/original names are keyword-mapped to supplement
    ``category_key`` values (via ``nutrient_category_map``) and passed as
    ``entity_keys`` for entity-link boosting.

    Args:
        context: Sanitized analysis context sent to local Ollama.
        settings: Runtime settings with local WIKI controls.

    Returns:
        Server-selected WIKI citations safe to expose to the client.
    """
    query = _analysis_wiki_query(context)
    entity_keys = _analysis_entity_keys(context)
    result = await retrieve_llm_wiki_context_db(query, settings, entity_keys=entity_keys)
    return tuple(_source_citation(citation) for citation in result.citations)


def _source_citation(citation: LlmWikiCitation) -> SupplementExplanationSourceCitation:
    """Convert a local WIKI retrieval hit into an API citation schema.

    Args:
        citation: Internal WIKI retrieval hit.

    Returns:
        API-safe citation with relative source path only.
    """
    return SupplementExplanationSourceCitation(
        title=citation.title,
        source_path=citation.source_path,
        heading=citation.heading,
        excerpt=citation.excerpt,
        score=citation.score,
    )


def _wiki_context_json(
    citations: tuple[SupplementExplanationSourceCitation, ...],
) -> str:
    """Serialize server-selected citations for local Ollama grounding.

    Args:
        citations: Server-selected local WIKI citations.

    Returns:
        JSON list string containing only safe citation fields.
    """
    return json.dumps([citation.model_dump() for citation in citations], ensure_ascii=False)


def _recommendation_wiki_query(request: SupplementRecommendationExplainRequest) -> str:
    """Build a bounded WIKI query from deterministic impact preview fields.

    Args:
        request: Explanation request.

    Returns:
        Query text that excludes raw OCR, provider payloads, and identifiers.
    """
    preview = request.preview
    texts: list[str] = [preview.safe_user_message]
    for contribution in preview.current_supplement_contributions[:8]:
        texts.extend(
            [
                contribution.nutrient_code,
                contribution.nutrient_name or "",
                *contribution.warnings[:4],
            ]
        )
        for item in contribution.items[:6]:
            texts.extend([item.display_name, item.nutrient_code, item.supplement_name])
    for insight in (
        *preview.deficiency_support_candidates[:8],
        *preview.excess_or_duplicate_risks[:8],
    ):
        texts.extend(
            [
                insight.nutrient_code,
                insight.nutrient_name or "",
                insight.reason_code,
                insight.user_message,
            ]
        )
    texts.extend(preview.missing_profile_fields[:8])
    return _join_query_texts(texts)


def _analysis_wiki_query(context: Mapping[str, Any]) -> str:
    """Build a bounded WIKI query from sanitized label-analysis context.

    Args:
        context: Sanitized analysis context.

    Returns:
        Query text that excludes raw OCR, provider payloads, and exact medical text.
    """
    texts: list[str] = []
    for key in ("product_name", "manufacturer", "ocr_provider"):
        texts.append(_safe_text(context.get(key), limit=120) or "")
    for ingredient in _list_of_mappings(context.get("ingredients")):
        texts.extend(
            [
                _safe_text(ingredient.get("display_name"), limit=120) or "",
                _safe_text(ingredient.get("original_name"), limit=120) or "",
                _safe_text(ingredient.get("amount_text"), limit=80) or "",
                _safe_text(ingredient.get("unit"), limit=40) or "",
            ]
        )
    for section in _list_of_mappings(context.get("label_section_excerpts")):
        texts.extend(
            [
                _safe_text(section.get("section_type"), limit=80) or "",
                _safe_text(section.get("heading_text"), limit=120) or "",
                _safe_text(section.get("text_excerpt"), limit=220) or "",
            ]
        )
    intake_method = _mapping(context.get("intake_method"))
    texts.extend(
        [
            _safe_text(intake_method.get("text"), limit=180) or "",
            _safe_text(intake_method.get("frequency"), limit=40) or "",
        ]
    )
    for precaution in _list_of_mappings(context.get("precautions")):
        texts.extend(
            [
                _safe_text(precaution.get("category"), limit=80) or "",
                _safe_text(precaution.get("text"), limit=220) or "",
            ]
        )
    profile_context = _mapping(context.get("profile_context"))
    texts.extend(
        [
            _safe_text(profile_context.get("sex"), limit=20) or "",
            _safe_text(profile_context.get("age_band"), limit=20) or "",
            _safe_text(profile_context.get("pregnancy_status"), limit=40) or "",
            _safe_text(profile_context.get("lactation_status"), limit=40) or "",
        ]
    )
    medical_context = _mapping(context.get("medical_context"))
    texts.extend(
        _safe_string_list(
            medical_context.get("canonical_condition_codes"),
            max_items=8,
            limit=80,
        )
    )
    texts.extend(
        _safe_string_list(
            medical_context.get("medication_review_categories"),
            max_items=8,
            limit=80,
        )
    )
    return _join_query_texts(texts)


def _join_query_texts(texts: list[str]) -> str:
    """Join safe query fragments with duplicate removal.

    Args:
        texts: Candidate query fragments.

    Returns:
        Bounded query string.
    """
    joined: list[str] = []
    seen: set[str] = set()
    for text in texts:
        normalized = _safe_text(text, limit=220)
        if not normalized or normalized in seen:
            continue
        joined.append(normalized)
        seen.add(normalized)
    return " ".join(joined)[:800]


def _profile_context_summary(profile_snapshot: BodyProfileSnapshot | None) -> dict[str, Any]:
    """Return a bounded current-user profile bucket for explanation context.

    Args:
        profile_snapshot: Latest current-user body profile snapshot.

    Returns:
        Sanitized profile bucket without owner identifiers, consent snapshots, or
        exact source metadata.
    """
    if profile_snapshot is None:
        return {"available": False}
    return {
        "available": True,
        "sex": _safe_text(profile_snapshot.sex, limit=20),
        "age_band": _age_band(profile_snapshot.birth_year),
        "height_cm_present": profile_snapshot.height_cm is not None,
        "weight_kg_present": profile_snapshot.weight_kg is not None,
        "waist_cm_present": profile_snapshot.waist_cm is not None,
        "pregnancy_status": _safe_text(profile_snapshot.pregnancy_status, limit=40),
        "lactation_status": _safe_text(profile_snapshot.lactation_status, limit=40),
        "activity_level": _safe_text(profile_snapshot.activity_level, limit=40),
    }


def _medical_context_summary(
    medical_context_summary: MedicalContextSummary | None,
) -> dict[str, Any]:
    """Return bounded current-user medical context for explanation prompts.

    Args:
        medical_context_summary: Consent-gated current-user medical summary.

    Returns:
        Sanitized medical context without owner identifiers, raw condition text,
        raw medication text, medication doses, source IDs, or consent snapshots.
    """
    if medical_context_summary is None or not medical_context_summary.available:
        return {"available": False}
    return {
        "available": True,
        "condition_count": medical_context_summary.condition_count,
        "canonical_condition_codes": list(medical_context_summary.canonical_condition_codes[:8]),
        "uncategorized_condition_count": medical_context_summary.uncategorized_condition_count,
        "active_medication_count": medical_context_summary.active_medication_count,
        "medication_review_categories": list(
            medical_context_summary.medication_review_categories[:8]
        ),
        "uncategorized_medication_count": (medical_context_summary.uncategorized_medication_count),
        "raw_medical_text_included": False,
    }


def _age_band(birth_year: int | None) -> str | None:
    """Return a coarse age band from a birth year.

    Args:
        birth_year: Profile birth year.

    Returns:
        Coarse age bucket, or None when unavailable.
    """
    if birth_year is None:
        return None
    current_year = datetime.now(UTC).year
    age = current_year - birth_year
    if age < 0 or age > MAX_PROFILE_AGE:
        return None
    decade = age // 10 * 10
    return f"{decade}s"


def _append_profile_context_bullets(
    bullets: list[str],
    context: Mapping[str, Any],
) -> None:
    """Append deterministic profile-context bullets when requested.

    Args:
        bullets: Mutable explanation bullet list.
        context: Sanitized analysis explanation context.

    Returns:
        None.
    """
    profile_context = _mapping(context.get("profile_context"))
    if profile_context.get("available"):
        bullets.append(_profile_context_bullet(profile_context))
        if _has_profile_precaution_overlap(context):
            bullets.append(
                "개인 상태와 라벨 주의 문구가 겹칠 수 있어 전문가 상담 여부를 확인하세요."
            )
        return
    if context.get("profile_context_requested"):
        bullets.append("개인 프로필이 없어 일반 라벨 확인 기준으로만 설명합니다.")


def _append_medical_context_bullets(
    bullets: list[str],
    context: Mapping[str, Any],
) -> None:
    """Append deterministic medical-context bullets when requested.

    Args:
        bullets: Mutable explanation bullet list.
        context: Sanitized analysis explanation context.

    Returns:
        None.
    """
    medical_context = _mapping(context.get("medical_context"))
    if medical_context.get("available"):
        bullets.append(_medical_context_bullet(medical_context))
        if _has_medical_precaution_overlap(context):
            bullets.append("의료정보 요약과 라벨 주의 문구가 겹쳐 전문가 상담 여부를 확인하세요.")
        return
    if context.get("medical_context_requested"):
        bullets.append("의료정보 요약이 없어 일반 라벨 확인 기준으로만 설명합니다.")


def _profile_context_bullet(profile_context: Mapping[str, Any]) -> str:
    """Build deterministic wording for included profile context.

    Args:
        profile_context: Sanitized profile context mapping.

    Returns:
        Safe Korean explanation bullet.
    """
    present_fields: list[str] = []
    for key, label in (
        ("sex", "성별"),
        ("age_band", "연령대"),
        ("activity_level", "활동 수준"),
        ("pregnancy_status", "임신 상태"),
        ("lactation_status", "수유 상태"),
    ):
        if profile_context.get(key):
            present_fields.append(label)
    if profile_context.get("height_cm_present") or profile_context.get("weight_kg_present"):
        present_fields.append("신체 정보")
    if profile_context.get("waist_cm_present"):
        present_fields.append("허리둘레")
    if not present_fields:
        return "개인 프로필은 있으나 설명에 쓸 수 있는 필드는 제한적입니다."
    return f"개인 프로필({', '.join(present_fields[:5])})을 함께 확인합니다."


def _medical_context_bullet(medical_context: Mapping[str, Any]) -> str:
    """Build deterministic wording for included medical context.

    Args:
        medical_context: Sanitized medical context mapping.

    Returns:
        Safe Korean explanation bullet.
    """
    condition_count = _bounded_int(medical_context.get("condition_count"))
    medication_count = _bounded_int(medical_context.get("active_medication_count"))
    category_count = len(
        _safe_string_list(
            medical_context.get("medication_review_categories"),
            max_items=8,
            limit=80,
        )
    )
    condition_code_count = len(
        _safe_string_list(
            medical_context.get("canonical_condition_codes"),
            max_items=8,
            limit=80,
        )
    )
    detail_parts: list[str] = []
    if condition_count:
        detail_parts.append(f"질환 {condition_count}개")
    if medication_count:
        detail_parts.append(f"복약 {medication_count}개")
    if condition_code_count:
        detail_parts.append(f"질환 분류 {condition_code_count}개")
    if category_count:
        detail_parts.append(f"복약 검토 분류 {category_count}개")
    if not detail_parts:
        return "의료정보 요약은 있으나 설명에 쓸 수 있는 필드는 제한적입니다."
    return f"의료정보 요약({', '.join(detail_parts[:4])})을 함께 확인합니다."


def _has_profile_precaution_overlap(context: Mapping[str, Any]) -> bool:
    """Return whether profile buckets overlap visible precaution categories.

    Args:
        context: Sanitized analysis explanation context.

    Returns:
        True when pregnancy or lactation profile buckets overlap precaution text.
    """
    profile_context = _mapping(context.get("profile_context"))
    if not profile_context.get("available"):
        return False
    pregnancy_status = profile_context.get("pregnancy_status")
    lactation_status = profile_context.get("lactation_status")
    if not pregnancy_status and not lactation_status:
        return False
    precautions = _list_of_mappings(context.get("precautions"))
    for precaution in precautions:
        category = _safe_text(precaution.get("category"), limit=80)
        text = _safe_text(precaution.get("text"), limit=220)
        haystack = f"{category or ''} {text or ''}".casefold()
        if pregnancy_status and any(
            token in haystack for token in ("pregnancy", "pregnant", "임신")
        ):
            return True
        if lactation_status and any(
            token in haystack for token in ("lactation", "nursing", "수유")
        ):
            return True
    return False


def _has_medical_precaution_overlap(context: Mapping[str, Any]) -> bool:
    """Return whether medical buckets overlap visible precaution text.

    Args:
        context: Sanitized analysis explanation context.

    Returns:
        True when medication or condition buckets should raise review urgency.
    """
    medical_context = _mapping(context.get("medical_context"))
    if not medical_context.get("available"):
        return False
    has_medication_review = bool(
        _safe_string_list(
            medical_context.get("medication_review_categories"),
            max_items=8,
            limit=80,
        )
    )
    has_condition_review = bool(
        _safe_string_list(
            medical_context.get("canonical_condition_codes"),
            max_items=8,
            limit=80,
        )
    )
    if has_medication_review:
        return True
    if not has_condition_review:
        return False
    precautions = _list_of_mappings(context.get("precautions"))
    for precaution in precautions:
        category = _safe_text(precaution.get("category"), limit=80)
        text = _safe_text(precaution.get("text"), limit=220)
        haystack = f"{category or ''} {text or ''}".casefold()
        if any(token in haystack for token in ("condition", "disease", "질환", "상담")):
            return True
    return False


def _ingredient_summary(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return bounded ingredient fields for explanation context.

    Args:
        candidate: Parsed ingredient candidate.

    Returns:
        Safe ingredient summary.
    """
    return {
        "display_name": _safe_text(candidate.get("display_name"), limit=120),
        "original_name": _safe_text(candidate.get("original_name"), limit=120),
        "amount": _safe_number(candidate.get("amount")),
        "amount_text": _format_amount_text(candidate.get("amount"), candidate.get("unit")),
        "amount_present": candidate.get("amount") is not None,
        "unit": _safe_text(candidate.get("unit"), limit=40),
        "confidence_bucket": _confidence_bucket(candidate.get("confidence")),
    }


def _label_section_summary(section: Mapping[str, Any]) -> dict[str, str | None]:
    """Return a bounded OCR-derived label section excerpt.

    Args:
        section: Parsed label section mapping.

    Returns:
        Safe section type, heading, and bounded text excerpt.
    """
    return {
        "section_type": _safe_text(section.get("section_type"), limit=80),
        "heading_text": _safe_text(section.get("heading_text"), limit=120),
        "text_excerpt": _safe_text(section.get("text_bundle"), limit=220),
    }


def _intake_method_summary(intake_method: Mapping[str, Any]) -> dict[str, Any]:
    """Return bounded intake-method fields for explanation context.

    Args:
        intake_method: Parsed intake-method mapping.

    Returns:
        Safe intake-method summary.
    """
    structured = _mapping(intake_method.get("structured"))
    return {
        "text": _safe_text(intake_method.get("text"), limit=180),
        "frequency": _safe_text(structured.get("frequency"), limit=40),
        "times_per_day": _safe_number(structured.get("times_per_day")),
        "amount_per_time": _safe_number(structured.get("amount_per_time")),
        "amount_unit": _safe_text(structured.get("amount_unit"), limit=40),
    }


def _precaution_summary(precaution: Mapping[str, Any]) -> dict[str, str | None]:
    """Return a bounded precaution sentence for explanation context.

    Args:
        precaution: Parsed precaution mapping.

    Returns:
        Safe precaution summary.
    """
    return {
        "text": _safe_text(precaution.get("text"), limit=220),
        "category": _safe_text(precaution.get("category"), limit=80),
        "severity": _safe_text(precaution.get("severity"), limit=80),
    }


def _format_context_ingredients(value: Any) -> str:
    """Format sanitized ingredient summaries for deterministic user wording.

    Args:
        value: Ingredient summary list from the explanation context.

    Returns:
        Comma-separated safe ingredient and amount summary.
    """
    if not isinstance(value, list):
        return ""
    formatted: list[str] = []
    for item in value[:3]:
        if not isinstance(item, Mapping):
            continue
        display_name = item.get("display_name")
        if not isinstance(display_name, str) or not display_name:
            continue
        original_name = item.get("original_name")
        name_text = display_name
        if isinstance(original_name, str) and original_name and original_name != display_name:
            name_text = f"{display_name}({original_name})"
        amount_text = item.get("amount_text")
        if isinstance(amount_text, str) and amount_text:
            formatted.append(f"{name_text} {amount_text}")
        else:
            formatted.append(f"{name_text} 함량 확인 필요")
    return ", ".join(formatted)


def _format_amount_text(amount: Any, unit: Any) -> str | None:
    """Return a display-safe ingredient amount string.

    Args:
        amount: Parsed numeric amount.
        unit: Parsed unit string.

    Returns:
        Bounded amount text, or None when amount is absent.
    """
    numeric = _safe_number(amount)
    if numeric is None:
        return None
    amount_text = str(numeric)
    normalized_unit = _safe_text(unit, limit=40)
    if normalized_unit:
        return f"{amount_text} {normalized_unit}"
    return amount_text


def _safe_number(value: Any) -> int | float | None:
    """Return a JSON-serializable number for safe prompt context.

    Args:
        value: Candidate numeric value.

    Returns:
        int or float when finite and reasonably bounded; otherwise None.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal | int | float):
        numeric = float(value)
    else:
        return None
    if not isfinite(numeric) or not -MAX_SAFE_PROMPT_NUMBER <= numeric <= MAX_SAFE_PROMPT_NUMBER:
        return None
    if numeric.is_integer():
        return int(numeric)
    return numeric


def _bounded_int(value: Any) -> int:
    """Return a bounded non-negative integer for deterministic wording.

    Args:
        value: Candidate integer-like value.

    Returns:
        Non-negative integer capped by ``MAX_SAFE_PROMPT_NUMBER``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, min(value, MAX_SAFE_PROMPT_NUMBER))


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return value when it is a mapping, otherwise an empty mapping."""
    if isinstance(value, Mapping):
        return value
    return {}


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    """Return bounded mappings from a possibly invalid list value."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _safe_string_list(value: Any, *, max_items: int, limit: int) -> list[str]:
    """Return bounded non-empty strings from a possibly invalid list value."""
    if not isinstance(value, list):
        return []
    strings: list[str] = []
    for item in value:
        text = _safe_text(item, limit=limit)
        if text:
            strings.append(text)
        if len(strings) >= max_items:
            break
    return strings


def _safe_text(value: Any, *, limit: int) -> str | None:
    """Return a bounded string or None for non-string/empty values."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:limit]


def _confidence_bucket(value: Any) -> str:
    """Return a coarse confidence bucket without exposing provider payloads."""
    if isinstance(value, Decimal | int | float):
        numeric = float(value)
    else:
        return "none"
    if numeric >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if numeric >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _reject_forbidden_response(response: SupplementRecommendationExplainResponse) -> None:
    """Reject forbidden wording from an explanation response.

    Args:
        response: Candidate explanation response.

    Raises:
        SupplementExplanationError: If a forbidden term is present.
    """
    messages = [
        response.safe_user_message,
        response.clinical_disclaimer,
        *response.explanation_bullets,
    ]
    blocked_terms = [term for term in FORBIDDEN_TERMS if any(term in text for text in messages)]
    if blocked_terms or contains_forbidden_terms(messages):
        response.blocked_terms_detected = blocked_terms
        raise SupplementExplanationError("Supplement explanation contains unsafe wording.")
