"""Medical knowledge registry and Q&A policy coverage tests."""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from lemon_ai_agent.entity_normalization import (
    has_p0_entity_pair,
    match_p0_boundary,
    normalize_health_entities,
)
from lemon_ai_agent.knowledge import (
    LLM_QA_EVAL_SET,
    MEDICAL_KNOWLEDGE_ITEMS,
    REVIEWED_MEDICAL_SOURCE_REGISTRY,
    analyze_chat_intent,
    policy_for_question,
    select_medical_knowledge,
)


def test_entity_normalizer_maps_aliases_to_canonical_ids() -> None:
    """Verify interaction routing can use entity ids instead of raw product text."""
    result = normalize_health_entities("탄산리튬 복용 중 셀레늄 영양제를 먹어도 돼?")

    ids = {entity.canonical_id for entity in result.entities}

    assert {"lithium", "selenium"}.issubset(ids)
    assert has_p0_entity_pair("탄산리튬 복용 중 셀레늄 영양제를 먹어도 돼?") is True


def test_entity_normalizer_requires_specific_medication_for_broad_terms() -> None:
    """Broad medication terms should request details before co-use judgment."""
    result = normalize_health_entities("혈압약 먹는데 칼륨 영양제 같이 먹어도 돼?")

    assert result.needs_specific_medication_name is True
    assert result.missing_topics == ("unknown_medication",)


def test_p0_entity_pair_returns_reviewed_boundary_code() -> None:
    """Verify normalized P0 pairs expose a stable boundary code for audit/reporting."""
    boundary = match_p0_boundary("세인트존스워트랑 SSRI를 같이 먹어도 돼?")

    assert boundary is not None
    assert boundary.boundary_code == "p0_st_johns_wort_antidepressant"
    assert boundary.topic == "st_johns_wort_antidepressant_interaction"
    assert set(boundary.entity_ids) == {"ssri", "st_johns_wort"}


def test_reviewed_medical_source_registry_tracks_keyed_sources() -> None:
    """Verify MVP medical sources have review metadata and env-key ownership."""
    by_id = {source.source_id: source for source in REVIEWED_MEDICAL_SOURCE_REGISTRY}

    kdca = by_id["kdca-healthinfo"]
    assert kdca.status == "reviewed"
    assert kdca.publisher == "Korea Disease Control and Prevention Agency"
    assert kdca.env_key is None
    assert "chronic_condition" in kdca.source_families
    assert {"hypertension", "diabetes", "kidney_disease"}.issubset(set(kdca.topics))
    assert len(kdca.topic_id_requirements) == 54
    assert ("hypertension", "고혈압") in kdca.topic_id_requirements
    assert kdca.last_reviewed_at

    semantic_scholar = by_id["semantic-scholar"]
    assert semantic_scholar.status == "draft"
    assert semantic_scholar.env_key == "SEMANTIC_SCHOLAR_API_KEY"
    assert semantic_scholar.user_facing_allowed is False


def test_backend_qna_eval_set_matches_classifier_targets() -> None:
    """Keep backend-integrated chatbot policy aligned with the MVP eval set."""
    groups = Counter(item.group for item in LLM_QA_EVAL_SET)

    assert len(LLM_QA_EVAL_SET) >= 230
    assert groups["general_medical"] >= 30
    assert groups["chronic_condition"] >= 50
    assert groups["nutrition_kdris"] >= 50
    assert groups["supplement_functional_food"] >= 40
    assert groups["drug_interaction_boundary"] >= 30
    assert groups["emergency_mental_health_escalation"] >= 30

    mismatches = [
        (item.case_id, policy_for_question(item.question).category, item.expected_category)
        for item in LLM_QA_EVAL_SET
        if policy_for_question(item.question).category != item.expected_category
    ]
    assert mismatches == []


def test_intent_analysis_keeps_profile_context_relevant_to_question() -> None:
    """Use profile disease context only when it matters to the user question."""
    unrelated = analyze_chat_intent(
        "오늘 수면을 어떻게 관리하면 좋아?",
        {"profile": {"chronic_conditions": ["diabetes", "hypertension"]}},
    )
    dizziness = analyze_chat_intent(
        "운동 후 어지러움이 있어",
        {"profile": {"chronic_conditions": ["diabetes", "hypertension"]}},
    )

    assert unrelated.primary_intent == "sleep"
    assert unrelated.related_conditions == ()
    assert dizziness.primary_intent == "symptom"
    assert dizziness.related_conditions == ("diabetes",)
    assert dizziness.red_flags == ()


def test_reviewed_medical_knowledge_selection_suppresses_draft_paper_sources() -> None:
    """Draft research sources stay internal and are not selected for user answers."""
    analysis = analyze_chat_intent("당뇨를 개선하려면 식사와 운동을 어떻게 관리해?")

    items = select_medical_knowledge(analysis)

    assert any(item.source == "CDC Diabetes Meal Planning" for item in items)
    assert any(item.source == "CDC Adult Physical Activity Guidelines" for item in items)
    assert all(item.reviewed_status == "reviewed" for item in items)
    assert all(item.evidence_type != "paper_candidate" for item in items)
    assert "Semantic Scholar Graph API" in {item.source for item in MEDICAL_KNOWLEDGE_ITEMS}
    assert "Semantic Scholar Graph API" not in {item.source for item in items}


def test_user_facing_knowledge_cards_are_reviewed_structured_and_source_backed() -> None:
    """Verify answer cards carry enough reviewed detail for deterministic fallback."""
    reviewed_sources = {
        source.source_id: source
        for source in REVIEWED_MEDICAL_SOURCE_REGISTRY
        if source.status == "reviewed" and source.user_facing_allowed
    }

    user_facing_cards = [
        item for item in MEDICAL_KNOWLEDGE_ITEMS if item.reviewed_status == "reviewed"
    ]

    assert 8 <= len(user_facing_cards) <= 40
    for item in user_facing_cards:
        assert item.source_id in reviewed_sources
        assert item.allowed_guidance
        assert item.specific_examples
        assert item.checklist
        assert item.must_not_say
        assert item.source_url
        assert _same_or_child_domain(item.source_url, reviewed_sources[item.source_id].url)


def test_reviewed_source_registry_has_unique_active_ids_and_expiry_metadata() -> None:
    """Every user-facing source has traceable non-empty governance metadata."""
    source_ids = [source.source_id for source in REVIEWED_MEDICAL_SOURCE_REGISTRY]

    assert len(source_ids) == len(set(source_ids))
    for source in REVIEWED_MEDICAL_SOURCE_REGISTRY:
        assert source.publisher
        assert source.url
        assert source.version_label
        assert source.last_reviewed_at
        assert source.review_expires_at
        if source.user_facing_allowed:
            assert source.status == "reviewed"


def test_p0_interaction_and_context_questions_route_to_boundary_policy() -> None:
    """P0 interaction candidates stay deterministic until source review is complete."""
    questions = [
        "와파린 복용 중인데 비타민 K 영양제를 같이 먹어도 돼?",
        "갑상선약이랑 칼슘, 철분을 같이 먹어도 되는지 알려줘",
        "메트포민 먹는데 비타민 B12를 추가해도 괜찮아?",
        "항응고제 복용 중 오메가3, 은행잎, 비타민 E 같이 먹어도 돼?",
        "MAOI 약을 먹는데 티라민 많은 음식을 피해야 하는지 판단해줘",
        "흡연자인데 베타카로틴이나 비타민 A 영양제를 먹어도 돼?",
        "음주가 잦은데 비타민 A 단일제나 아세트아미노펜을 같이 써도 돼?",
        "세인트존스워트랑 항우울제를 같이 먹어도 돼?",
        "자몽주스랑 스타틴을 같이 먹어도 돼?",
        "고지혈증 약 먹는데 자몽주스 마셔도 돼?",
        "칼륨 보충제랑 저염소금을 같이 써도 돼?",
        "협심증 니트로글리세린이 있는데 발기부전약을 같이 먹어도 돼?",
        "협심증약 먹는데 비아그라 같이 먹어도 돼?",
        "SSRI 복용 중인데 5-HTP 영양제를 같이 먹어도 돼?",
        "SNRI 복용 중인데 트립토판 보충제를 같이 먹어도 돼?",
        "스타틴 먹는데 홍국 영양제를 같이 먹어도 돼?",
        "lithium medicine selenium supplement interaction",
    ]

    for question in questions:
        assert policy_for_question(question).category == "drug_or_interaction"


def test_magnesium_blood_pressure_med_routes_to_caution_not_boundary_policy() -> None:
    """Common magnesium plus blood-pressure-medication questions are explainable."""
    policy = policy_for_question("혈압약 먹는데 마그네슘 영양제 같이 먹어도 돼?")

    assert policy.category == "medication_supplement_caution"
    assert policy.source_families == (
        "supplement_reference",
        "drug_safety_boundary",
        "chronic_condition",
    )


def _same_or_child_domain(item_url: str, source_url: str) -> bool:
    item_host = urlparse(item_url).hostname or ""
    source_host = urlparse(source_url).hostname or ""
    return item_host == source_host or item_host.endswith(f".{source_host}")
