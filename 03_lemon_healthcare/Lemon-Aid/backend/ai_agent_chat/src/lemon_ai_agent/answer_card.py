from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from lemon_ai_agent.knowledge import (
    REVIEWED_MEDICAL_SOURCE_REGISTRY,
    ChatIntentAnalysis,
    Condition,
    MedicalKnowledgeItem,
    SourceFamily,
    SourceStatus,
    analyze_chat_intent,
    select_medical_knowledge,
)

Answerability = Literal[
    "answerable",
    "answerable_with_caution",
    "needs_more_info",
    "unknown_no_reviewed_source",
    "medical_decision_boundary",
    "urgent_escalation",
    "safety_boundary",
]

RetrievalStatus = Literal["found", "no_match", "stale_only", "not_reviewed_only"]


@dataclass(frozen=True)
class AnswerCard:
    card_id: str
    answerability: Answerability
    topic: str
    intent: str
    condition: Condition | None
    allowed_guidance: tuple[str, ...]
    specific_examples: tuple[str, ...]
    checklist: tuple[str, ...]
    caution_conditions: tuple[str, ...]
    must_not_say: tuple[str, ...]
    source_id: str
    source_url: str
    source_family: SourceFamily
    source_version_id: str | None
    version_label: str
    review_status: SourceStatus
    reviewed_at: str
    expires_at: str
    grounding_snippet_ids: tuple[str, ...]
    source_name: str
    concrete_guidance: str
    severity: str = ""
    primary_action: str = ""
    blocked_wording: tuple[str, ...] = ()
    linked_claim_id: str = ""

    def source_metadata(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "source_title": self.source_name,
            "source_family": self.source_family,
            "review_status": self.review_status,
            "version_label": self.version_label,
            "reviewed_at": self.reviewed_at,
            "expires_at": self.expires_at,
            "source_url": self.source_url,
        }


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    cards: tuple[AnswerCard, ...]
    knowledge_items: tuple[MedicalKnowledgeItem, ...]
    missing_topics: tuple[str, ...]
    warnings: tuple[str, ...]
    retrieval_status: RetrievalStatus


@dataclass(frozen=True)
class MedicalEvidenceAnswerCardRecord:
    evidence_id: str
    source_id: str
    source_url: str
    source_family: SourceFamily
    source_version_id: str
    version_label: str
    source_review_status: SourceStatus
    reviewed_at: str
    expires_at: str
    topic: str
    audience: str
    claim_summary: str
    allowed_user_wording: str
    blocked_wording: str
    applicability_note: str | None
    caution_level: str
    evidence_review_status: SourceStatus
    specific_examples: tuple[str, ...]
    checklist: tuple[str, ...]
    caution_conditions: tuple[str, ...]
    must_not_say: tuple[str, ...]
    source_title: str = ""


class AnswerCardNormalizer:
    """Converts reviewed seed knowledge into the runtime answer-card contract."""

    def __init__(self, today: date | None = None) -> None:
        self._today = today or date.today()

    def has_stale_source(self, item: MedicalKnowledgeItem) -> bool:
        source = _reviewed_source_by_id(item.source_id)
        if source is None:
            return False
        return _source_is_stale(source.review_expires_at, self._today)

    def from_medical_knowledge_item(
        self,
        item: MedicalKnowledgeItem,
        *,
        answerability: Answerability,
    ) -> AnswerCard | None:
        if item.reviewed_status != "reviewed" or item.evidence_type == "paper_candidate":
            return None

        source = _reviewed_source_by_id(item.source_id)
        if source is None or source.status != "reviewed" or not source.user_facing_allowed:
            return None
        if _source_is_stale(source.review_expires_at, self._today):
            return None

        if (
            not item.allowed_guidance
            or not item.specific_examples
            or not item.checklist
            or not item.must_not_say
            or not item.source_url
        ):
            return None

        source_family = _source_family_for_item(item, source.source_families)
        return AnswerCard(
            card_id=f"seed:{item.topic}",
            answerability=answerability,
            topic=item.topic,
            intent=item.intent,
            condition=item.condition,
            allowed_guidance=item.allowed_guidance,
            specific_examples=item.specific_examples,
            checklist=item.checklist,
            caution_conditions=item.caution_conditions,
            must_not_say=item.must_not_say,
            source_id=item.source_id,
            source_url=item.source_url,
            source_family=source_family,
            source_version_id=None,
            version_label=source.version_label,
            review_status=item.reviewed_status,
            reviewed_at=source.last_reviewed_at,
            expires_at=source.review_expires_at,
            grounding_snippet_ids=(f"seed:{item.topic}",),
            source_name=item.source,
            concrete_guidance=item.concrete_guidance,
        )

    def from_evidence_record(
        self,
        record: MedicalEvidenceAnswerCardRecord,
        *,
        answerability: Answerability,
        intent: str,
        condition: Condition | None,
    ) -> AnswerCard | None:
        if record.source_review_status != "reviewed" or record.evidence_review_status != "reviewed":
            return None
        if _source_is_stale(record.expires_at, self._today):
            return None
        if (
            not record.allowed_user_wording
            or not record.blocked_wording
            or not record.specific_examples
            or not record.checklist
            or not record.must_not_say
            or not record.source_url
        ):
            return None

        allowed_guidance = (record.allowed_user_wording,)
        return AnswerCard(
            card_id=f"db:{record.evidence_id}",
            answerability=answerability,
            topic=record.topic,
            intent=intent,
            condition=condition,
            allowed_guidance=allowed_guidance,
            specific_examples=record.specific_examples,
            checklist=record.checklist,
            caution_conditions=record.caution_conditions,
            must_not_say=record.must_not_say,
            source_id=record.source_id,
            source_url=record.source_url,
            source_family=record.source_family,
            source_version_id=record.source_version_id,
            version_label=record.version_label,
            review_status=record.evidence_review_status,
            reviewed_at=record.reviewed_at,
            expires_at=record.expires_at,
            grounding_snippet_ids=(f"db:{record.evidence_id}",),
            source_name=record.source_title or record.source_id,
            concrete_guidance=record.claim_summary,
        )


class MedicalKnowledgeRetriever:
    """Registry-backed v1 retriever for reviewed user-facing answer cards."""

    def __init__(self, normalizer: AnswerCardNormalizer | None = None) -> None:
        self._normalizer = normalizer or AnswerCardNormalizer()

    def retrieve(self, analysis: ChatIntentAnalysis) -> KnowledgeRetrievalResult:
        answerability = answerability_for_analysis(analysis, has_cards=True)
        selected_items = tuple(
            item
            for item in select_medical_knowledge(analysis)
            if _item_is_relevant_to_question(item, analysis.normalized_question, analysis)
        )
        cards = tuple(
            card
            for item in selected_items
            if (
                card := self._normalizer.from_medical_knowledge_item(
                    item,
                    answerability=answerability,
                )
            )
            is not None
        )

        if cards:
            return KnowledgeRetrievalResult(
                cards=cards,
                knowledge_items=selected_items,
                missing_topics=(),
                warnings=(),
                retrieval_status="found",
            )

        if selected_items and all(
            self._normalizer.has_stale_source(item) for item in selected_items
        ):
            return KnowledgeRetrievalResult(
                cards=(),
                knowledge_items=(),
                missing_topics=(analysis.primary_intent,),
                warnings=("source_stale",),
                retrieval_status="stale_only",
            )

        return KnowledgeRetrievalResult(
            cards=(),
            knowledge_items=(),
            missing_topics=(analysis.primary_intent,),
            warnings=("no_reviewed_answer_card",),
            retrieval_status="no_match",
        )

    def retrieve_for_question(
        self,
        question: str,
        context: dict[str, object] | None = None,
    ) -> KnowledgeRetrievalResult:
        return self.retrieve(analyze_chat_intent(question, context))


class EvidenceRecordMedicalKnowledgeRetriever:
    """DB-evidence-backed retriever for reviewed runtime answer cards."""

    def __init__(
        self,
        records: tuple[MedicalEvidenceAnswerCardRecord, ...],
        *,
        normalizer: AnswerCardNormalizer | None = None,
        fallback: MedicalKnowledgeRetriever | None = None,
    ) -> None:
        self._records = records
        self._normalizer = normalizer or AnswerCardNormalizer()
        self._fallback = fallback

    def retrieve(self, analysis: ChatIntentAnalysis) -> KnowledgeRetrievalResult:
        answerability = answerability_for_analysis(analysis, has_cards=True)
        selected_records = tuple(
            record
            for record in self._records
            if _record_is_relevant_to_question(record, analysis.normalized_question, analysis)
        )
        cards = tuple(
            card
            for record in selected_records
            if (
                card := self._normalizer.from_evidence_record(
                    record,
                    answerability=answerability,
                    intent=analysis.primary_intent,
                    condition=(
                        analysis.related_conditions[0] if analysis.related_conditions else None
                    ),
                )
            )
            is not None
        )

        if cards:
            return KnowledgeRetrievalResult(
                cards=cards,
                knowledge_items=(),
                missing_topics=(),
                warnings=(),
                retrieval_status="found",
            )

        if self._fallback is not None:
            fallback_result = self._fallback.retrieve(analysis)
            if fallback_result.cards:
                return fallback_result

        if selected_records and all(
            record.source_review_status != "reviewed" or record.evidence_review_status != "reviewed"
            for record in selected_records
        ):
            return KnowledgeRetrievalResult(
                cards=(),
                knowledge_items=(),
                missing_topics=(analysis.primary_intent,),
                warnings=("evidence_not_reviewed",),
                retrieval_status="not_reviewed_only",
            )

        if selected_records and all(
            _source_is_stale(record.expires_at, self._normalizer._today)
            for record in selected_records
        ):
            return KnowledgeRetrievalResult(
                cards=(),
                knowledge_items=(),
                missing_topics=(analysis.primary_intent,),
                warnings=("source_stale",),
                retrieval_status="stale_only",
            )

        return KnowledgeRetrievalResult(
            cards=(),
            knowledge_items=(),
            missing_topics=(analysis.primary_intent,),
            warnings=("no_reviewed_answer_card",),
            retrieval_status="no_match",
        )

    def retrieve_for_question(
        self,
        question: str,
        context: dict[str, object] | None = None,
    ) -> KnowledgeRetrievalResult:
        return self.retrieve(analyze_chat_intent(question, context))


def answerability_for_analysis(
    analysis: ChatIntentAnalysis,
    *,
    has_cards: bool,
) -> Answerability:
    if analysis.category in {"symptom_or_emergency", "mental_health_risk"}:
        return "urgent_escalation"
    if analysis.category in {"drug_or_interaction", "out_of_scope"}:
        return "medical_decision_boundary"
    if not has_cards:
        return "unknown_no_reviewed_source"
    if analysis.category == "medication_supplement_caution":
        return "answerable_with_caution"
    return "answerable"


def unique_source_metadata(cards: tuple[AnswerCard, ...]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for card in cards:
        key = (card.source_id, card.source_family)
        if key in seen:
            continue
        seen.add(key)
        sources.append(card.source_metadata())
    return sources


def _reviewed_source_by_id(source_id: str):
    return next(
        (source for source in REVIEWED_MEDICAL_SOURCE_REGISTRY if source.source_id == source_id),
        None,
    )


def _source_is_stale(review_expires_at: str, today: date) -> bool:
    try:
        expires_at = date.fromisoformat(review_expires_at)
    except ValueError:
        return True
    return expires_at < today


def _source_family_for_item(
    item: MedicalKnowledgeItem,
    source_families: tuple[SourceFamily, ...],
) -> SourceFamily:
    if item.source_id == "kdris-2025" and "nutrition_reference" in source_families:
        return "nutrition_reference"
    if item.intent == "supplement" and "supplement_reference" in source_families:
        return "supplement_reference"
    if item.condition is not None and "chronic_condition" in source_families:
        return "chronic_condition"
    if "general_medical" in source_families:
        return "general_medical"
    return source_families[0]


def _item_is_relevant_to_question(
    item: MedicalKnowledgeItem,
    normalized_question: str,
    analysis: ChatIntentAnalysis,
) -> bool:
    if analysis.category == "nutrition_analysis":
        return _nutrition_item_matches_question(item, normalized_question)
    if analysis.category == "medication_supplement_caution":
        return _caution_item_matches_question(item, normalized_question)
    if analysis.category == "supplement_question":
        return _supplement_item_matches_question(item, normalized_question)
    return True


def _caution_item_matches_question(
    item: MedicalKnowledgeItem,
    normalized_question: str,
) -> bool:
    if item.topic == "magnesium_supplement_caution":
        return "마그네슘" in normalized_question or "magnesium" in normalized_question
    return False


def _supplement_item_matches_question(
    item: MedicalKnowledgeItem,
    normalized_question: str,
) -> bool:
    if item.intent != "supplement":
        return True
    if (
        _is_supplement_effect_claim_question(normalized_question)
        and item.topic == "supplement_label_check"
    ):
        return False
    if item.topic == "magnesium_supplement_caution":
        return "마그네슘" in normalized_question or "magnesium" in normalized_question
    return _topic_keyword_matches(item.topic, normalized_question)


def _nutrition_item_matches_question(
    item: MedicalKnowledgeItem,
    normalized_question: str,
) -> bool:
    topic_terms = {
        "sodium_dinner_adjustment": ("나트륨", "소금", "짠", "sodium", "salt"),
        "protein_food_candidates": ("단백질", "protein"),
        "fiber_food_candidates": ("식이섬유", "섬유질", "fiber"),
        "vitamin_d_food_candidates": ("비타민 d", "비타민d", "vitamin d", "vitamin_d"),
        "adult_activity": ("운동", "걷기", "활동", "exercise", "activity", "walking"),
        "adult_sleep": ("수면", "잠", "sleep"),
        "exercise_dizziness": (
            "어지러움",
            "어지러워",
            "현기증",
            "dizzy",
            "dizziness",
        ),
        "general_health_record_review": ("기록", "식사 기록", "활동 기록", "건강 기록"),
    }
    terms = topic_terms.get(item.topic)
    return bool(terms and _has_any_term(normalized_question, terms))


def _record_is_relevant_to_question(
    record: MedicalEvidenceAnswerCardRecord,
    normalized_question: str,
    analysis: ChatIntentAnalysis,
) -> bool:
    topic = record.topic.casefold()
    if _record_condition_conflicts_with_question(topic, analysis):
        return False
    if analysis.primary_intent == "symptom":
        return topic == "exercise_dizziness" and _topic_keyword_matches(topic, normalized_question)
    if analysis.category == "medication_supplement_caution":
        return _caution_record_matches_question(topic, normalized_question)
    if _topic_keyword_matches(topic, normalized_question):
        return True

    matches_category = False
    if analysis.primary_intent == "meal":
        matches_category = _meal_record_matches_question(topic, normalized_question, analysis)
    elif analysis.category == "chronic_condition_context":
        matches_category = any(condition in topic for condition in analysis.related_conditions)
    elif analysis.category == "supplement_question":
        matches_category = _supplement_record_matches_question(topic, normalized_question)
    else:
        matches_category = analysis.category in topic
    return matches_category


def _record_condition_conflicts_with_question(
    topic: str,
    analysis: ChatIntentAnalysis,
) -> bool:
    related = set(analysis.related_conditions)
    if "kidney" in topic and "kidney_disease" not in related:
        return True
    if "diabetes" in topic and "diabetes" not in related:
        return True
    return "hypertension" in topic and "hypertension" not in related


def _topic_keyword_matches(topic: str, normalized_question: str) -> bool:
    topic_keywords: dict[str, tuple[str, ...]] = {
        "diabetes_plate_method": ("당뇨", "혈당", "diabetes", "glucose", "탄수화물", "초콜릿"),
        "diabetes_healthy_living": ("당뇨", "혈당", "diabetes", "glucose", "생활관리", "개선"),
        "adult_activity": ("운동", "걷기", "활동", "exercise", "activity", "walking"),
        "adult_sleep": ("수면", "잠", "sleep"),
        "exercise_dizziness": ("어지러움", "어지러워", "현기증", "dizzy", "dizziness"),
        "hypertension_meal_adjustment": ("고혈압", "혈압", "hypertension", "blood pressure"),
        "kidney_disease_meal_caution": ("신장", "콩팥", "kidney", "renal", "칼륨"),
        "sodium_dinner_adjustment": ("나트륨", "소금", "짠", "sodium", "salt"),
        "vitamin_d_food_candidates": ("비타민 d", "vitamin d", "vitamin_d"),
        "protein_food_candidates": ("단백질", "protein"),
        "fiber_food_candidates": ("식이섬유", "섬유질", "fiber"),
        "general_health_record_review": ("기록", "식사 기록", "활동 기록", "건강 기록"),
        "supplement_label_check": ("영양제", "건강기능식품", "라벨", "성분", "supplement", "label"),
        "magnesium_supplement_caution": ("마그네슘", "magnesium"),
        "dyslipidemia_saturated_fat_reduction": (
            "고지혈증",
            "콜레스테롤",
            "ldl",
            "포화지방",
            "dyslipidemia",
            "cholesterol",
        ),
        "dyslipidemia_omega3_fish_sources": (
            "고지혈증",
            "콜레스테롤",
            "오메가3",
            "등푸른 생선",
            "omega3",
            "dyslipidemia",
        ),
        "triglyceride_sugar_alcohol_reduction": (
            "중성지방",
            "당분",
            "알코올",
            "triglyceride",
            "술",
        ),
        "weight_management_plate_composition": ("체중", "식단", "다이어트", "weight management"),
        "weight_management_meal_timing": ("체중", "야식", "식사 간격", "다이어트"),
        "weight_management_record_pattern_review": (
            "체중 기록",
            "체중",
            "기록 활용",
            "weight management",
        ),
    }
    actual_korean_keywords: dict[str, tuple[str, ...]] = {
        "diabetes_plate_method": ("당뇨", "혈당", "탄수화물", "초콜릿", "밥", "과식"),
        "diabetes_healthy_living": ("당뇨", "혈당", "생활관리", "개선"),
        "adult_activity": ("운동", "걷기", "활동"),
        "adult_sleep": ("수면", "잠"),
        "exercise_dizziness": ("어지러움", "어지러워", "현기증"),
        "hypertension_meal_adjustment": ("고혈압", "혈압", "나트륨", "소금", "짠", "라면"),
        "kidney_disease_meal_caution": ("신장", "콩팥", "칼륨", "채소", "과일"),
        "sodium_dinner_adjustment": ("나트륨", "소금", "짠", "국물", "라면", "찌개"),
        "vitamin_d_food_candidates": ("비타민 d", "비타민d"),
        "protein_food_candidates": ("단백질",),
        "fiber_food_candidates": ("식이섬유", "섬유질"),
        "general_health_record_review": ("기록", "식사 기록", "활동 기록", "건강 기록"),
        "supplement_label_check": ("영양제", "건강기능식품", "라벨", "성분"),
        "magnesium_supplement_caution": ("마그네슘", "magnesium"),
        "dyslipidemia_saturated_fat_reduction": ("고지혈증", "콜레스테롤", "포화지방"),
        "dyslipidemia_omega3_fish_sources": ("고지혈증", "콜레스테롤", "오메가3", "등푸른 생선"),
        "triglyceride_sugar_alcohol_reduction": ("중성지방", "당분", "알코올"),
        "weight_management_plate_composition": ("체중", "식단", "다이어트"),
        "weight_management_meal_timing": ("체중", "야식", "식사 간격"),
        "weight_management_record_pattern_review": ("체중 기록", "체중", "기록 활용"),
    }
    keywords = (*topic_keywords.get(topic, ()), *actual_korean_keywords.get(topic, ()))
    return any(keyword in normalized_question for keyword in keywords)


def _caution_record_matches_question(topic: str, normalized_question: str) -> bool:
    if topic == "magnesium_supplement_caution":
        return "마그네슘" in normalized_question or "magnesium" in normalized_question
    return False


def _has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _meal_record_matches_question(
    topic: str,
    normalized_question: str,
    analysis: ChatIntentAnalysis,
) -> bool:
    if "sodium" in topic or "나트륨" in topic:
        return any(term in normalized_question for term in ("나트륨", "소금", "sodium", "salt"))
    return "meal" in topic or any(condition in topic for condition in analysis.related_conditions)


def _supplement_record_matches_question(topic: str, normalized_question: str) -> bool:
    if (
        _is_supplement_effect_claim_question(normalized_question)
        and topic == "supplement_label_check"
    ):
        return False
    if topic == "magnesium_supplement_caution":
        return "마그네슘" in normalized_question or "magnesium" in normalized_question
    return _topic_keyword_matches(topic, normalized_question)


def _is_supplement_effect_claim_question(normalized_question: str) -> bool:
    return _has_any_term(
        normalized_question,
        (
            "효과",
            "도움",
            "좋아져",
            "좋아지",
            "개선",
            "수면",
            "sleep",
            "피로",
            "집중",
            "근육",
        ),
    )
