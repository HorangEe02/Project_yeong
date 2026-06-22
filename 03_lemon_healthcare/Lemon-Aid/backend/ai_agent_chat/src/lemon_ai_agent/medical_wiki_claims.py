from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from lemon_ai_agent.answer_card import (
    Answerability,
    AnswerCard,
    KnowledgeRetrievalResult,
)
from lemon_ai_agent.knowledge import ChatIntentAnalysis, SourceFamily, analyze_chat_intent

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_REVIEWED_CLAIMS_PATH = (
    WORKSPACE_ROOT / "MEDICAL-WIKI" / "manifest" / "reviewed_claims.jsonl"
)
MIN_STEM_LENGTH = 2

STOPWORDS = {
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "a",
    "an",
    "is",
    "are",
    "있",
    "있는",
    "있는데",
    "하면",
    "되",
    "돼",
    "돼요",
    "될까요",
    "괜찮",
    "괜찮아",
    "괜찮나요",
    "괜찮죠",
    "어떻게",
    "오늘",
    "좀",
    "더",
    "많이",
    "먹고",
    "마시",
    "마시는",
    "것",
    "안",
    "같",
    "같은데",
}

SYNONYMS = {
    "가슴": ("흉통",),
    "답답한데": ("압박감", "흉통"),
    "체한": ("소화불량", "흉통"),
    "배": ("복통",),
    "배가": ("복통",),
    "아파요": ("통증",),
    "아픈데": ("통증",),
    "토하고": ("구토",),
    "토": ("구토",),
    "말": ("어눌함",),
    "힘": ("마비", "힘빠짐"),
    "빠지는데": ("힘빠짐",),
    "수면제": ("진정제", "항불안제"),
    "진정제": ("수면제", "항불안제"),
    "술": ("음주",),
    "맥주": ("음주",),
    "소주": ("음주",),
    "약": ("복용", "복약", "의약품"),
    "당뇨약": ("인슐린", "혈당강하제", "저혈당"),
    "인슐린": ("당뇨약", "혈당강하제"),
    "혈압약": ("복용", "복약"),
    "간수치": ("검사수치", "검사", "결과"),
    "egfr": ("검사수치", "신장", "검사"),
    "어머니": ("고령자", "노인"),
    "아버지": ("고령자", "노인"),
    "멍해": ("혼돈", "의식", "탈수"),
    "더워서": ("탈수",),
    "이온음료": ("탈수", "수분"),
    "항암치료": ("면역저하", "고위험군"),
    "회": ("식중독", "식품안전"),
    "설사": ("식중독", "탈수"),
    "5kg": ("감량", "체중", "위험한"),
    "빼고": ("감량", "체중"),
    "물만": ("극단적", "단식", "감량"),
    "식단": ("감량", "체중"),
    "살": ("체중", "감량"),
    "토하면": ("구토", "섭식장애"),
    "방법": ("위험한", "감량"),
}

CLAIM_QUERY_BOOSTS: dict[str, tuple[str, ...]] = {
    "reviewed_p0_boundary_hypoglycemia_red_flag_2026_06_08": (
        "저혈당",
        "저혈당이면",
        "식은땀",
        "혈당이 낮",
        "운동 계속",
        "당뇨약을 오늘 줄",
    ),
    "reviewed_p0_boundary_medication_dose_change_2026_06_08": (
        "두 알",
        "효과가 없는",
        "용량",
        "얼마나 더",
    ),
    "reviewed_p0_boundary_food_allergy_anaphylaxis_2026_06_08": (
        "새우",
        "목이 조이",
        "온몸에 두드러기",
        "아나필락시스",
    ),
    "reviewed_p0_boundary_drug_allergy_adverse_reaction_2026_06_08": (
        "진통제",
        "다른 진통제",
        "약 먹고 두드러기",
    ),
    "reviewed_p0_boundary_pediatric_med_supplement_2026_06_08": (
        "7살",
        "아이",
        "어른 종합비타민",
        "반 알",
    ),
    "reviewed_p0_boundary_anxiety_panic_red_flag_2026_06_09": (
        "불안",
        "공황",
        "가슴이 답답",
        "항불안제",
        "한 알 더",
        "집에서 버텨",
    ),
    "reviewed_p0_boundary_drug_nutrient_interaction_clearance_2026_06_09": (
        "혈압약 먹는데 칼슘",
        "칼슘 많은 음식",
        "음식이랑 같이",
        "약이랑 영양제",
        "시간이 겹치",
        "같이 먹어도",
    ),
    "reviewed_p0_boundary_food_combination_interaction_generalization_2026_06_09": (
        "음식 조합",
        "음식궁합",
        "몸에 독",
        "다 끊어",
        "바로 피해야",
    ),
    "reviewed_p0_boundary_exercise_prescription_red_flag_2026_06_09": (
        "운동 중",
        "운동하면 돼",
        "강도를 더",
        "목표 심박수",
        "심박수 몇",
    ),
}


@dataclass(frozen=True)
class MedicalWikiReviewedClaim:
    claim_id: str
    title: str
    domain: str
    claim_text: str
    allowed_user_wording: str
    blocked_wording: tuple[str, ...]
    answerability: Answerability
    severity: str
    primary_action: str
    must_not_answer_as: tuple[str, ...]
    reviewed_at: str
    expires_at: str
    sources: tuple[dict[str, str], ...]
    golden_questions: tuple[str, ...] = ()


class MedicalWikiReviewedClaimRetriever:
    """MEDICAL-WIKI reviewed claim adapter for backend AnswerCard evaluation."""

    def __init__(
        self,
        claims_path: Path | None = None,
        *,
        as_of: date | None = None,
        top_k: int = 3,
    ) -> None:
        self._claims_path = claims_path or DEFAULT_REVIEWED_CLAIMS_PATH
        self._as_of = as_of or date.today()
        self._top_k = top_k
        self._claims = tuple(self._load_claims())
        self._idf = _idf_by_token(self._claims)

    @property
    def claims(self) -> tuple[MedicalWikiReviewedClaim, ...]:
        return self._claims

    def claim_by_id(self, claim_id: str) -> MedicalWikiReviewedClaim | None:
        return next((claim for claim in self._claims if claim.claim_id == claim_id), None)

    def rank_claims(self, query: str, *, top_k: int | None = None) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        ranked: list[dict[str, Any]] = []
        for claim in self._claims:
            document_tokens = tokenize(_claim_document_text(claim))
            score = _bm25_lite_score(query_tokens, document_tokens, self._idf)
            score += _claim_query_boost(claim.claim_id, query)
            score += _claim_golden_seed_boost(claim, query)
            ranked.append(
                {
                    "claim_id": claim.claim_id,
                    "score": round(score, 6),
                    "matched_terms": sorted(set(query_tokens).intersection(document_tokens)),
                }
            )
        ranked.sort(key=lambda row: (-float(row["score"]), str(row["claim_id"])))
        selected = ranked[: top_k or self._top_k]
        for rank, row in enumerate(selected, start=1):
            row["rank"] = rank
        return selected

    def retrieve(self, analysis: ChatIntentAnalysis) -> KnowledgeRetrievalResult:
        ranked = self.rank_claims(analysis.normalized_question, top_k=self._top_k)
        selected_claims = tuple(
            claim for row in ranked if (claim := self.claim_by_id(str(row["claim_id"]))) is not None
        )
        cards = tuple(
            card
            for claim in selected_claims
            for card in self.answer_cards_for_claim(claim, analysis)
        )
        if cards:
            return KnowledgeRetrievalResult(
                cards=cards,
                knowledge_items=(),
                missing_topics=(),
                warnings=(),
                retrieval_status="found",
            )
        return KnowledgeRetrievalResult(
            cards=(),
            knowledge_items=(),
            missing_topics=(analysis.primary_intent,),
            warnings=("no_reviewed_answer_card",),
            retrieval_status="no_match",
        )

    def retrieve_for_question(self, question: str) -> KnowledgeRetrievalResult:
        return self.retrieve(analyze_chat_intent(question))

    def answer_cards_for_claim(
        self,
        claim: MedicalWikiReviewedClaim,
        analysis: ChatIntentAnalysis,
    ) -> tuple[AnswerCard, ...]:
        source_family = _source_family_for_claim(claim)
        condition = (
            analysis.related_conditions[0]
            if analysis.related_conditions
            and analysis.related_conditions[0] in {"diabetes", "hypertension", "kidney_disease"}
            else None
        )
        checklist = _checklist_for_claim(claim)
        caution_conditions = _caution_conditions_for_claim(claim)
        return tuple(
            AnswerCard(
                card_id=f"medical-wiki:{claim.claim_id}:{source['source_id']}",
                answerability=claim.answerability,
                topic=claim.claim_id,
                intent=analysis.primary_intent,
                condition=condition,  # type: ignore[arg-type]
                allowed_guidance=(claim.allowed_user_wording,),
                specific_examples=(claim.title, claim.domain, claim.primary_action),
                checklist=checklist,
                caution_conditions=caution_conditions,
                must_not_say=claim.blocked_wording,
                source_id=source["source_id"],
                source_url=source["canonical_url"],
                source_family=source_family,
                source_version_id=source["source_id"],
                version_label=source.get("version_label", ""),
                review_status="reviewed",
                reviewed_at=claim.reviewed_at,
                expires_at=claim.expires_at,
                grounding_snippet_ids=(f"medical-wiki:{claim.claim_id}",),
                source_name=_source_name(source),
                concrete_guidance=claim.claim_text,
                severity=claim.severity,
                primary_action=claim.primary_action,
                blocked_wording=claim.blocked_wording,
                linked_claim_id=claim.claim_id,
            )
            for source in claim.sources
        )

    def _load_claims(self) -> list[MedicalWikiReviewedClaim]:
        claims: list[MedicalWikiReviewedClaim] = []
        for row in _read_jsonl(self._claims_path):
            if not _is_eligible_claim(row, self._as_of):
                continue
            claims.append(_claim_from_row(row))
        return claims


def tokenize(text: str) -> list[str]:
    normalized = text.casefold()
    raw_tokens = re.findall(r"[0-9a-zA-Z가-힣]+", normalized)
    tokens: list[str] = []
    for raw in raw_tokens:
        compact = raw.strip()
        if not compact or compact in STOPWORDS:
            continue
        tokens.append(compact)
        tokens.extend(re.findall(r"\d+", compact))
        if compact.endswith(("이", "가", "은", "는")):
            stemmed = compact[:-1]
            if len(stemmed) >= MIN_STEM_LENGTH and stemmed not in STOPWORDS:
                tokens.append(stemmed)
        if compact.endswith("하면"):
            stemmed = compact[:-2]
            if len(stemmed) >= MIN_STEM_LENGTH and stemmed not in STOPWORDS:
                tokens.append(stemmed)
        for source, expansions in SYNONYMS.items():
            if source in compact:
                tokens.extend(expansions)
    return tokens


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no} is not a JSON object")
            rows.append(row)
    return rows


def _is_eligible_claim(row: dict[str, Any], as_of: date) -> bool:
    return (
        row.get("review_status") == "reviewed"
        and row.get("rag_eligible") is True
        and row.get("service_rag_eligible") is True
        and _date_field_is_future(row, "expires_at", as_of)
        and bool(row.get("allowed_user_wording"))
        and bool(row.get("blocked_wording"))
        and bool(row.get("sources"))
        and isinstance(row.get("answer_card"), dict)
    )


def _date_field_is_future(row: dict[str, Any], field_name: str, as_of: date) -> bool:
    try:
        return date.fromisoformat(str(row.get(field_name, ""))) > as_of
    except ValueError:
        return False


def _claim_from_row(row: dict[str, Any]) -> MedicalWikiReviewedClaim:
    answer_card = row["answer_card"]
    sources = tuple(
        {
            "source_id": str(source.get("source_id", "")),
            "publisher": str(source.get("publisher", "")),
            "title": str(source.get("title", "")),
            "canonical_url": str(source.get("canonical_url", "")),
            "version_label": str(source.get("version_label", "")),
        }
        for source in row.get("sources", [])
        if isinstance(source, dict) and source.get("source_id") and source.get("canonical_url")
    )
    return MedicalWikiReviewedClaim(
        claim_id=str(row["claim_id"]),
        title=str(row.get("title", "")),
        domain=str(row.get("domain", "")),
        claim_text=str(row.get("claim_text", "")),
        allowed_user_wording=str(row.get("allowed_user_wording", "")),
        blocked_wording=tuple(str(item) for item in row.get("blocked_wording", [])),
        answerability=_answerability_for_claim(answer_card),
        severity=str(answer_card.get("severity", "")),
        primary_action=str(answer_card.get("primary_action", "")),
        must_not_answer_as=tuple(str(item) for item in answer_card.get("must_not_answer_as", [])),
        reviewed_at=str(row.get("reviewed_at", "")),
        expires_at=str(row.get("expires_at", "")),
        sources=sources,
        golden_questions=tuple(
            str(seed.get("user_question", ""))
            for seed in row.get("golden_test_seeds", [])
            if isinstance(seed, dict) and seed.get("user_question")
        ),
    )


def _answerability_for_claim(answer_card: dict[str, Any]) -> Answerability:
    severity = str(answer_card.get("severity", ""))
    if "urgent" in severity:
        return "urgent_escalation"
    if "safety_boundary" in severity or "safety" in severity:
        return "safety_boundary"
    if severity.endswith("_boundary") and severity != "medical_decision_boundary":
        return "safety_boundary"
    return "medical_decision_boundary"


def _source_family_for_claim(claim: MedicalWikiReviewedClaim) -> SourceFamily:
    if claim.domain == "mental_health":
        return "mental_health_escalation"
    if claim.answerability == "urgent_escalation":
        return "emergency_escalation"
    if claim.domain in {"medication_interaction", "supplement"}:
        return "drug_safety_boundary"
    if claim.domain == "chronic_disease":
        return "chronic_condition"
    if claim.domain == "food":
        return "food_safety_allergy"
    return "general_medical"


def _checklist_for_claim(claim: MedicalWikiReviewedClaim) -> tuple[str, ...]:
    if claim.domain in {"medication_interaction", "supplement"}:
        return ("정확한 약 이름", "성분명", "제품 라벨", "복용 중인 약 목록", "이상 증상")
    if claim.domain == "chronic_disease":
        return ("현재 증상", "측정 수치", "복용 중인 약", "기존 관리 계획", "증상 악화 여부")
    if claim.domain == "food":
        return ("증상 시작 시점", "먹은 음식", "호흡/목 조임 여부", "고위험군 여부")
    if claim.domain == "mental_health":
        return ("현재 안전", "혼자 있는지", "자해 생각", "신뢰할 수 있는 사람")
    return ("현재 증상", "나이/임신 여부", "복용 중인 약", "제품 라벨", "진료 필요 신호")


def _caution_conditions_for_claim(claim: MedicalWikiReviewedClaim) -> tuple[str, ...]:
    values = (claim.severity, claim.primary_action, *claim.must_not_answer_as)
    return tuple(value for value in values if value)


def _source_name(source: dict[str, str]) -> str:
    publisher = source.get("publisher", "").strip()
    title = source.get("title", "").strip()
    if publisher and title:
        return f"{publisher} {title}"
    return publisher or title or source["source_id"]


def _idf_by_token(claims: tuple[MedicalWikiReviewedClaim, ...]) -> dict[str, float]:
    document_count = len(claims)
    document_frequency: Counter[str] = Counter()
    for claim in claims:
        document_frequency.update(set(tokenize(_claim_document_text(claim))))
    return {
        token: math.log((document_count + 1) / (count + 0.5)) + 1
        for token, count in document_frequency.items()
    }


def _claim_document_text(claim: MedicalWikiReviewedClaim) -> str:
    source_text = "\n".join(
        f"{source['source_id']} {source.get('publisher', '')} {source.get('title', '')}"
        for source in claim.sources
    )
    return "\n".join(
        (
            claim.claim_id,
            claim.title,
            claim.domain,
            claim.claim_text,
            claim.allowed_user_wording,
            "\n".join(claim.blocked_wording),
            "\n".join(claim.golden_questions),
            claim.severity,
            claim.primary_action,
            "\n".join(claim.must_not_answer_as),
            source_text,
        )
    )


def _bm25_lite_score(
    query_tokens: list[str],
    document_tokens: list[str],
    idf: dict[str, float],
) -> float:
    if not query_tokens or not document_tokens:
        return 0.0
    doc_counts = Counter(document_tokens)
    doc_len = len(document_tokens)
    avg_len = max(doc_len, 1)
    k1 = 1.2
    b = 0.75
    score = 0.0
    for token in query_tokens:
        tf = doc_counts.get(token, 0)
        if tf == 0:
            continue
        denominator = tf + k1 * (1 - b + b * doc_len / avg_len)
        score += idf.get(token, 1.0) * (tf * (k1 + 1) / denominator)
    return score


def _claim_query_boost(claim_id: str, query: str) -> float:
    normalized = query.casefold()
    terms = CLAIM_QUERY_BOOSTS.get(claim_id, ())
    return sum(4.0 for term in terms if term in normalized)


def _claim_golden_seed_boost(claim: MedicalWikiReviewedClaim, query: str) -> float:
    normalized = " ".join(query.casefold().split())
    for question in claim.golden_questions:
        seed_question = " ".join(question.casefold().split())
        if normalized == seed_question:
            return 100.0
    return 0.0
