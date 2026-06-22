"""AnswerCard normalization and retrieval tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import lemon_ai_agent.answer_card as answer_card_module
from lemon_ai_agent.answer_card import (
    AnswerCardNormalizer,
    EvidenceRecordMedicalKnowledgeRetriever,
    MedicalEvidenceAnswerCardRecord,
    MedicalKnowledgeRetriever,
)
from lemon_ai_agent.knowledge import (
    MEDICAL_KNOWLEDGE_ITEMS,
    analyze_chat_intent,
)


def test_answer_card_normalizer_converts_reviewed_seed_item() -> None:
    """Reviewed seed cards become source-traceable AnswerCards."""
    item = next(
        item for item in MEDICAL_KNOWLEDGE_ITEMS if item.topic == "magnesium_supplement_caution"
    )

    card = AnswerCardNormalizer().from_medical_knowledge_item(
        item,
        answerability="answerable_with_caution",
    )

    assert card is not None
    assert card.card_id == "seed:magnesium_supplement_caution"
    assert card.answerability == "answerable_with_caution"
    assert card.source_id == "nih-ods-magnesium"
    assert card.review_status == "reviewed"
    assert card.source_family == "supplement_reference"
    assert card.allowed_guidance
    assert card.specific_examples
    assert card.checklist
    assert card.must_not_say
    assert card.reviewed_at
    assert card.expires_at
    assert card.grounding_snippet_ids == ("seed:magnesium_supplement_caution",)


def test_answer_card_normalizer_rejects_draft_seed_item() -> None:
    """Draft or paper-candidate seed items cannot become user-facing cards."""
    draft_item = next(
        item for item in MEDICAL_KNOWLEDGE_ITEMS if item.source_id == "semantic-scholar"
    )

    card = AnswerCardNormalizer().from_medical_knowledge_item(
        draft_item,
        answerability="answerable",
    )

    assert card is None


def test_answer_card_normalizer_adapts_reviewed_kdris_seed_as_nutrition_source() -> None:
    """KDRIs approved project data is exposed to chatbot cards as reviewed nutrition evidence."""
    item = next(
        item for item in MEDICAL_KNOWLEDGE_ITEMS if item.topic == "sodium_dinner_adjustment"
    )

    card = AnswerCardNormalizer(today=date(2026, 5, 29)).from_medical_knowledge_item(
        item,
        answerability="answerable",
    )

    assert card is not None
    assert card.source_id == "kdris-2025"
    assert card.source_family == "nutrition_reference"
    assert card.review_status == "reviewed"
    assert card.version_label == "KDRIs 2025"
    assert card.reviewed_at == "2026-05-19"
    assert card.expires_at == "2027-05-19"
    assert "오이" in card.specific_examples
    assert "라면은 절대 먹지 마세요" in card.must_not_say


def test_answer_card_normalizer_converts_reviewed_db_evidence_record() -> None:
    """Reviewed DB evidence rows can become runtime AnswerCards."""
    record = MedicalEvidenceAnswerCardRecord(
        evidence_id="evidence-magnesium-bp",
        source_id="nih-ods-magnesium",
        source_url="https://ods.od.nih.gov/factsheets/Magnesium-Consumer/",
        source_family="supplement_reference",
        source_version_id="source-version-1",
        version_label="2026-05 DB reviewed source",
        source_review_status="reviewed",
        reviewed_at="2026-05-29",
        expires_at="2026-11-29",
        topic="magnesium_supplement_caution",
        audience="adult",
        claim_summary="Magnesium supplement use needs label and medication review.",
        allowed_user_wording="제품 라벨과 혈압약 종류, 신장 기능을 확인한다.",
        blocked_wording="혈압약과 함께 먹어도 됩니다.",
        applicability_note="혈압약 복용 중인 성인",
        caution_level="professional_review",
        evidence_review_status="reviewed",
        specific_examples=("제품 라벨", "견과류", "콩류"),
        checklist=("함량", "혈압약 종류", "신장 기능"),
        caution_conditions=("이상 증상", "새 보충제 시작"),
        must_not_say=("먹어도 됩니다", "안전합니다"),
    )

    card = AnswerCardNormalizer(today=date(2026, 5, 29)).from_evidence_record(
        record,
        answerability="answerable_with_caution",
        intent="supplement",
        condition=None,
    )

    assert card is not None
    assert card.card_id == "db:evidence-magnesium-bp"
    assert card.source_version_id == "source-version-1"
    assert card.allowed_guidance == ("제품 라벨과 혈압약 종류, 신장 기능을 확인한다.",)
    assert card.must_not_say == ("먹어도 됩니다", "안전합니다")


def test_answer_card_normalizer_rejects_unreviewed_or_stale_db_evidence_record() -> None:
    """DB evidence must be reviewed and not stale before user-facing use."""
    record = MedicalEvidenceAnswerCardRecord(
        evidence_id="draft-evidence",
        source_id="nih-ods-magnesium",
        source_url="https://ods.od.nih.gov/factsheets/Magnesium-Consumer/",
        source_family="supplement_reference",
        source_version_id="source-version-1",
        version_label="draft",
        source_review_status="reviewed",
        reviewed_at="2026-05-29",
        expires_at="2026-05-28",
        topic="magnesium_supplement_caution",
        audience="adult",
        claim_summary="Draft claim.",
        allowed_user_wording="제품 라벨을 확인한다.",
        blocked_wording="먹어도 됩니다.",
        applicability_note=None,
        caution_level="professional_review",
        evidence_review_status="reviewed",
        specific_examples=("제품 라벨",),
        checklist=("함량",),
        caution_conditions=("새 보충제 시작",),
        must_not_say=("먹어도 됩니다",),
    )

    stale_card = AnswerCardNormalizer(today=date(2026, 5, 29)).from_evidence_record(
        record,
        answerability="answerable_with_caution",
        intent="supplement",
        condition=None,
    )
    draft_card = AnswerCardNormalizer(today=date(2026, 5, 27)).from_evidence_record(
        replace(record, evidence_review_status="draft"),
        answerability="answerable_with_caution",
        intent="supplement",
        condition=None,
    )

    assert stale_card is None
    assert draft_card is None


def test_answer_card_normalizer_rejects_stale_source(
    monkeypatch,
) -> None:
    """Expired reviewed sources cannot become user-facing answer cards."""
    item = next(
        item for item in MEDICAL_KNOWLEDGE_ITEMS if item.topic == "magnesium_supplement_caution"
    )
    expired_registry = tuple(
        (
            replace(source, review_expires_at="2026-05-28")
            if source.source_id == "nih-ods-magnesium"
            else source
        )
        for source in answer_card_module.REVIEWED_MEDICAL_SOURCE_REGISTRY
    )
    monkeypatch.setattr(
        answer_card_module,
        "REVIEWED_MEDICAL_SOURCE_REGISTRY",
        expired_registry,
    )

    card = AnswerCardNormalizer(today=date(2026, 5, 29)).from_medical_knowledge_item(
        item,
        answerability="answerable_with_caution",
    )

    assert card is None


def test_retriever_reports_stale_only_when_matching_source_is_expired(
    monkeypatch,
) -> None:
    """A matched but expired source is reported distinctly from no-match."""
    expired_registry = tuple(
        (
            replace(source, review_expires_at="2026-05-28")
            if source.source_id == "nih-ods-magnesium"
            else source
        )
        for source in answer_card_module.REVIEWED_MEDICAL_SOURCE_REGISTRY
    )
    monkeypatch.setattr(
        answer_card_module,
        "REVIEWED_MEDICAL_SOURCE_REGISTRY",
        expired_registry,
    )
    analysis = analyze_chat_intent("혈압약 먹는데 마그네슘 영양제 같이 먹어도 돼?")

    result = MedicalKnowledgeRetriever(
        normalizer=AnswerCardNormalizer(today=date(2026, 5, 29)),
    ).retrieve(analysis)

    assert result.retrieval_status == "stale_only"
    assert result.cards == ()
    assert "source_stale" in result.warnings


def test_retriever_returns_no_match_for_unreviewed_specific_couse_question() -> None:
    """Uncovered medication/supplement combinations fail closed instead of reusing a broad card."""
    analysis = analyze_chat_intent("리튬 약을 먹는데 셀레늄 영양제 같이 먹어도 돼?")

    result = MedicalKnowledgeRetriever().retrieve(analysis)

    assert result.retrieval_status == "no_match"
    assert result.cards == ()
    assert "no_reviewed_answer_card" in result.warnings


def test_retriever_returns_magnesium_caution_card_for_supported_couse_question() -> None:
    """Known caution topics can be explained through a reviewed AnswerCard."""
    analysis = analyze_chat_intent("혈압약 먹는데 마그네슘 영양제 같이 먹어도 돼?")

    result = MedicalKnowledgeRetriever().retrieve(analysis)

    assert result.retrieval_status == "found"
    assert any(card.topic == "magnesium_supplement_caution" for card in result.cards)
    assert all(card.review_status == "reviewed" for card in result.cards)


def test_db_evidence_retriever_returns_reviewed_answer_card() -> None:
    """DB evidence records are the production-like AnswerCard source."""
    record = MedicalEvidenceAnswerCardRecord(
        evidence_id="evidence-magnesium-bp",
        source_id="nih-ods-magnesium",
        source_url="https://ods.od.nih.gov/factsheets/Magnesium-Consumer/",
        source_family="supplement_reference",
        source_version_id="source-version-1",
        version_label="2026-05 DB reviewed source",
        source_review_status="reviewed",
        reviewed_at="2026-05-29",
        expires_at="2026-11-29",
        topic="magnesium_supplement_caution",
        audience="adult",
        claim_summary="Magnesium supplement use needs label and medication review.",
        allowed_user_wording="제품 라벨, 마그네슘 함량, 혈압약 종류, 신장 기능을 확인한다.",
        blocked_wording="먹어도 됩니다.",
        applicability_note="혈압약 복용 중인 성인",
        caution_level="professional_review",
        evidence_review_status="reviewed",
        specific_examples=("제품 라벨", "마그네슘 함량", "혈압약 종류"),
        checklist=("제품 라벨", "함량", "신장 기능", "이상 증상"),
        caution_conditions=("새 보충제 시작", "이상 증상"),
        must_not_say=("먹어도 됩니다", "안전합니다", "먹으면 안 됩니다"),
    )

    result = EvidenceRecordMedicalKnowledgeRetriever(
        (record,),
        normalizer=AnswerCardNormalizer(today=date(2026, 5, 29)),
    ).retrieve(analyze_chat_intent("혈압약 먹는데 마그네슘 영양제 같이 먹어도 돼?"))

    assert result.retrieval_status == "found"
    assert result.knowledge_items == ()
    assert result.cards[0].card_id == "db:evidence-magnesium-bp"
    assert result.cards[0].source_version_id == "source-version-1"


def test_db_evidence_retriever_does_not_reuse_generic_cards_for_unknown_interaction() -> None:
    """Uncovered supplement/medication pairs must fail closed in DB-backed retrieval."""
    records = (
        _db_record(
            evidence_id="evidence-kidney-caution",
            topic="kidney_disease_meal_caution",
            source_id="niddk-kidney-disease",
            source_family="chronic_condition",
            claim_summary="Kidney disease meal guidance requires potassium and sodium review.",
            examples=("potassium", "sodium", "label"),
            checklist=("kidney function", "potassium", "sodium"),
        ),
        _db_record(
            evidence_id="evidence-supplement-label",
            topic="supplement_label_check",
            source_id="mfds-drug-safety",
            source_family="supplement_reference",
            claim_summary="Supplement labels should be checked before use.",
            examples=("label", "ingredient", "dose"),
            checklist=("ingredient", "dose", "warning"),
        ),
    )
    retriever = EvidenceRecordMedicalKnowledgeRetriever(
        records,
        normalizer=AnswerCardNormalizer(today=date(2026, 5, 29)),
    )

    result = retriever.retrieve(
        analyze_chat_intent("lithium medicine taurine supplement interaction")
    )

    assert result.retrieval_status == "no_match"
    assert result.cards == ()
    assert "no_reviewed_answer_card" in result.warnings


def test_db_evidence_retriever_matches_reviewed_topic_keywords() -> None:
    """DB-only retrieval can find seeded topics that do not share the intent name."""
    records = (
        _db_record(
            evidence_id="evidence-activity",
            topic="adult_activity",
            source_id="cdc-public-health",
            source_family="lifestyle_guideline",
            claim_summary="Adults can start with walking and activity tracking.",
            examples=("걷기", "자전거", "가벼운 근력운동"),
            checklist=("운동 시간", "강도", "통증"),
        ),
        _db_record(
            evidence_id="evidence-protein",
            topic="protein_food_candidates",
            source_id="kdris-2025",
            source_family="nutrition_reference",
            claim_summary="Protein food guidance should use concrete lower-salt protein foods.",
            examples=("두부", "달걀", "생선구이"),
            checklist=("단백질 반찬", "가공육 여부", "조리 간"),
        ),
        _db_record(
            evidence_id="evidence-dizziness",
            topic="exercise_dizziness",
            source_id="cdc-public-health",
            source_family="general_medical",
            claim_summary="Dizziness after exercise should prompt rest and hydration.",
            examples=("휴식", "수분 보충", "서늘한 곳"),
            checklist=("어지러움", "운동 강도", "증상 악화"),
        ),
    )
    retriever = EvidenceRecordMedicalKnowledgeRetriever(
        records,
        normalizer=AnswerCardNormalizer(today=date(2026, 5, 29)),
    )

    activity = retriever.retrieve(analyze_chat_intent("운동은 걷기부터 시작해도 돼?"))
    protein = retriever.retrieve(analyze_chat_intent("저녁 단백질 반찬 후보 알려줘"))
    dizziness = retriever.retrieve(analyze_chat_intent("운동 후 어지러움이 있는데 어떻게 해?"))

    assert [card.topic for card in activity.cards] == ["adult_activity"]
    assert [card.topic for card in protein.cards] == ["protein_food_candidates"]
    assert [card.topic for card in dizziness.cards] == ["exercise_dizziness"]


def test_db_evidence_retriever_handles_actual_korean_without_cross_condition_leakage() -> None:
    """Real Korean user wording should match reviewed cards without unrelated disease cards."""
    records = (
        _db_record(
            evidence_id="evidence-hypertension",
            topic="hypertension_meal_adjustment",
            source_id="kdca-healthinfo",
            source_family="chronic_condition",
            claim_summary="Hypertension meal guidance should reduce salty foods.",
            examples=("soup", "sauce", "processed meat"),
            checklist=("sodium", "sauce", "processed meat"),
        ),
        _db_record(
            evidence_id="evidence-sodium",
            topic="sodium_dinner_adjustment",
            source_id="kdris-2025",
            source_family="nutrition_reference",
            claim_summary="Sodium dinner guidance should use low-salt swaps.",
            examples=("cucumber", "tofu", "fish"),
            checklist=("soup", "sauce", "kimchi"),
        ),
        _db_record(
            evidence_id="evidence-kidney",
            topic="kidney_disease_meal_caution",
            source_id="niddk-kidney-disease",
            source_family="chronic_condition",
            claim_summary="Kidney disease meal guidance requires potassium review.",
            examples=("potassium", "vegetable", "fruit"),
            checklist=("kidney function", "potassium", "sodium"),
        ),
        _db_record(
            evidence_id="evidence-diabetes",
            topic="diabetes_plate_method",
            source_id="cdc-public-health",
            source_family="chronic_condition",
            claim_summary="Diabetes meal guidance should adjust carbohydrates.",
            examples=("vegetable", "protein", "carbohydrate"),
            checklist=("carbohydrate", "sweets", "next meal"),
        ),
        _db_record(
            evidence_id="evidence-magnesium-bp",
            topic="magnesium_supplement_caution",
            source_id="nih-ods-magnesium",
            source_family="supplement_reference",
            claim_summary="Magnesium supplement use needs label and medication review.",
            examples=("label", "dose", "medication"),
            checklist=("label", "dose", "kidney function"),
        ),
    )
    retriever = EvidenceRecordMedicalKnowledgeRetriever(
        records,
        normalizer=AnswerCardNormalizer(today=date(2026, 5, 29)),
    )

    hypertension = retriever.retrieve(
        analyze_chat_intent(
            "\uace0\ud608\uc555\uc774 \uc788\ub294\ub370 \ub77c\uba74\uc744 \uba39\uc5b4\uc11c "
            "\ub098\ud2b8\ub968\uc774 \ub192\uc544. \uc800\ub141\uc740 \uc5b4\ub5bb\uac8c \uba39\uc73c\uba74 \uc88b\uc744\uae4c?",
            {"profile": {"chronic_conditions": ["hypertension"]}},
        )
    )
    diabetes = retriever.retrieve(
        analyze_chat_intent(
            "\ub2f9\ub1e8\uac00 \uc788\ub294\ub370 \uc810\uc2ec\uc5d0 \ubc25\uacfc "
            "\ucd08\ucf5c\ub9bf\uc744 \ub9ce\uc774 \uba39\uc5c8\uc5b4. \ub2e4\uc74c \ub07c\ub2c8\ub294?",
            {"profile": {"chronic_conditions": ["diabetes"]}},
        )
    )
    magnesium = retriever.retrieve(
        analyze_chat_intent(
            "\ud608\uc555\uc57d\uc744 \uba39\ub294\ub370 \ub9c8\uadf8\ub124\uc298 "
            "\uc601\uc591\uc81c\ub97c \uac19\uc774 \uba39\uc5b4\ub3c4 \ub3fc?"
        )
    )
    unknown = retriever.retrieve(
        analyze_chat_intent(
            "\ub9ac\ud2ac \uc57d\uc744 \uba39\ub294\ub370 \uc140\ub808\ub284 "
            "\uc601\uc591\uc81c \uac19\uc774 \uba39\uc5b4\ub3c4 \ub3fc?"
        )
    )

    assert {card.topic for card in hypertension.cards} == {
        "hypertension_meal_adjustment",
        "sodium_dinner_adjustment",
    }
    assert {card.topic for card in diabetes.cards} == {"diabetes_plate_method"}
    assert {card.topic for card in magnesium.cards} == {"magnesium_supplement_caution"}
    assert unknown.retrieval_status == "no_match"
    assert unknown.cards == ()


def test_db_evidence_retriever_falls_back_only_when_configured() -> None:
    """Local/dev can keep registry fallback while production-like retrieval can fail closed."""
    analysis = analyze_chat_intent("혈압약 먹는데 마그네슘 영양제 같이 먹어도 돼?")

    production_like = EvidenceRecordMedicalKnowledgeRetriever(()).retrieve(analysis)
    local_dev = EvidenceRecordMedicalKnowledgeRetriever(
        (),
        fallback=MedicalKnowledgeRetriever(),
    ).retrieve(analysis)

    assert production_like.retrieval_status == "no_match"
    assert production_like.cards == ()
    assert local_dev.retrieval_status == "found"
    assert any(card.card_id.startswith("seed:") for card in local_dev.cards)


def test_db_evidence_retriever_matches_dyslipidemia_topics() -> None:
    """고지혈증·중성지방 관련 한국어 질문이 올바른 카드를 검색한다."""
    records = (
        _db_record(
            evidence_id="evidence-dyslipidemia-sat-fat",
            topic="dyslipidemia_saturated_fat_reduction",
            source_id="cdc-public-health",
            source_family="general_medical",
            claim_summary="Reducing saturated fat and trans fat helps manage LDL cholesterol.",
            examples=("소고기 -> 생선", "버터 -> 올리브오일", "가공식품 성분표 확인"),
            checklist=("포화지방 섭취 빈도", "약 복용 여부", "최근 혈액검사 수치"),
        ),
        _db_record(
            evidence_id="evidence-triglyceride-sugar",
            topic="triglyceride_sugar_alcohol_reduction",
            source_id="kdca-healthinfo",
            source_family="public_health_guidance",
            claim_summary="High triglycerides are linked to excess simple sugar and alcohol.",
            examples=("탄산음료 -> 물", "과자 -> 견과류", "음주 횟수 줄이기"),
            checklist=("당분 음료 섭취 빈도", "음주 빈도", "당뇨 동반 여부"),
        ),
    )
    retriever = EvidenceRecordMedicalKnowledgeRetriever(
        records,
        normalizer=AnswerCardNormalizer(today=date(2026, 6, 13)),
    )

    sat_fat_result = retriever.retrieve(analyze_chat_intent("고지혈증인데 뭘 먹으면 안 되나요?"))
    triglyceride_result = retriever.retrieve(
        analyze_chat_intent("중성지방이 높으면 어떤 음식을 줄여야 해요?")
    )

    assert any(
        card.topic == "dyslipidemia_saturated_fat_reduction" for card in sat_fat_result.cards
    )
    assert any(
        card.topic == "triglyceride_sugar_alcohol_reduction" for card in triglyceride_result.cards
    )


def test_db_evidence_retriever_matches_weight_management_topics() -> None:
    """체중 관리 관련 한국어 질문이 올바른 카드를 검색한다."""
    records = (
        _db_record(
            evidence_id="evidence-weight-plate",
            topic="weight_management_plate_composition",
            source_id="cdc-public-health",
            source_family="general_medical",
            claim_summary="Balanced plate: half vegetables, quarter protein, quarter complex carbs.",
            examples=("비전분 채소 절반", "단백질 1/4", "현미 1/4"),
            checklist=("채소 비중", "단백질 공급원", "정제 탄수화물 비중"),
        ),
        _db_record(
            evidence_id="evidence-weight-record",
            topic="weight_management_record_pattern_review",
            source_id="cdc-public-health",
            source_family="general_medical",
            claim_summary="Reviewing weight and meal records helps identify overeating patterns.",
            examples=("주간 체중 변화 그래프", "야식 빈도 확인", "과식 시간대 파악"),
            checklist=("기록 주기", "야식 빈도", "주간 체중 변화"),
        ),
    )
    retriever = EvidenceRecordMedicalKnowledgeRetriever(
        records,
        normalizer=AnswerCardNormalizer(today=date(2026, 6, 13)),
    )

    plate_result = retriever.retrieve(analyze_chat_intent("체중 관리 중에 식사를 어떻게 구성해요?"))
    record_result = retriever.retrieve(
        analyze_chat_intent("체중 기록이랑 식사 기록을 어떻게 활용해요?")
    )

    assert any(card.topic == "weight_management_plate_composition" for card in plate_result.cards)
    assert any(
        card.topic == "weight_management_record_pattern_review" for card in record_result.cards
    )


def _db_record(
    *,
    evidence_id: str,
    topic: str,
    source_id: str,
    source_family: str,
    claim_summary: str,
    examples: tuple[str, ...],
    checklist: tuple[str, ...],
) -> MedicalEvidenceAnswerCardRecord:
    return MedicalEvidenceAnswerCardRecord(
        evidence_id=evidence_id,
        source_id=source_id,
        source_url="https://example.test/source",
        source_family=source_family,
        source_version_id=f"{source_id}-version",
        version_label="2026-05 DB reviewed source",
        source_review_status="reviewed",
        reviewed_at="2026-05-29",
        expires_at="2026-11-29",
        topic=topic,
        audience="adult",
        claim_summary=claim_summary,
        allowed_user_wording="확인된 기록을 기준으로 낮은 위험도의 행동 후보를 안내한다.",
        blocked_wording="진단입니다.",
        applicability_note="테스트용 DB reviewed evidence",
        caution_level="info",
        evidence_review_status="reviewed",
        specific_examples=examples,
        checklist=checklist,
        caution_conditions=("증상 악화", "처방 변경"),
        must_not_say=("진단입니다", "약을 조절하세요"),
    )
