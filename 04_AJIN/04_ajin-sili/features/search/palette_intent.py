"""v4.7 Sprint 2 P0 (축 ②) — Palette 카테고리 의도 분류기.

CommandPalette 의 10 카테고리(SearchCategory) 와 1:1 매핑되는 의도 분류기.
기존 `intent_router.py` 의 5 의도(employee_lookup / company_info / document_search /
document_compose / regulation_query)를 활용하면서, 10 카테고리(palette UI 와 일치)
로 확장한다.

전략:
  1. ML_05 LogisticRegression (ml_intent_classifier) 가 학습되어 있으면 5 의도 예측
  2. 5 → 10 카테고리 매핑 + 키워드 보강 신호로 세분류
  3. ML 미학습 시 키워드 룰만으로 분류 (TODO: ML 통합 — 액션 3 트랙 A 의 모델 재학습 흡수)

응답 스키마는 frontend/src/store/search.ts 의 IntentResult 와 일치.

PaletteCategory(SearchCategory) 키: page / person / doc / sop / regulation /
equipment_error / scenario / org_chart / draft / metric.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# 10 카테고리 (SearchCategory 와 1:1).
PaletteCategory = Literal[
    "page",
    "person",
    "doc",
    "sop",
    "regulation",
    "equipment_error",
    "scenario",
    "org_chart",
    "draft",
    "metric",
]

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        "page",
        "person",
        "doc",
        "sop",
        "regulation",
        "equipment_error",
        "scenario",
        "org_chart",
        "draft",
        "metric",
    }
)

# 5 ML intent → 10 카테고리 기본 매핑.
ML_INTENT_TO_CATEGORY: dict[str, PaletteCategory] = {
    "employee_lookup": "person",
    "company_info": "page",
    "document_search": "doc",
    "document_compose": "draft",
    "regulation_query": "regulation",
}

# 카테고리별 키워드 시그널 (10 카테고리 직접 분류용).
# Dict 삽입 순서가 동점 시 우선순위 결정 — 좁은 카테고리를 먼저 배치.
CATEGORY_KEYWORDS: dict[PaletteCategory, tuple[str, ...]] = {
    # org_chart 는 person 보다 먼저 — '조직도' 가 동시 매칭될 때 org_chart 우선.
    "org_chart": (
        "조직도", "조직 구조", "조직 현황", "부서 인원", "팀 구성",
        "팀 멤버",
    ),
    "person": (
        "사원", "직원", "팀원", "담당자", "책임자", "연락처", "전화번호",
        "이메일", "내선", "누구", "팀장", "부장", "대리", "과장",
    ),
    "doc": (
        "문서", "보고서", "report", "매뉴얼", "manual", "8d", "ecn",
        "회의록", "minutes", "발의서",
    ),
    "sop": (
        "sop", "절차", "프로세스", "process", "표준작업", "체크리스트",
        "checklist", "방법", "어떻게", "guideline", "지침",
    ),
    "regulation": (
        "규제", "법규", "regulation", "compliance", "컴플라이언스", "reach",
        "rohs", "iatf", "iso", "ira", "관세", "industrial safety", "산안법",
        "msds", "sds", "osha", "epa", "법령",
    ),
    "equipment_error": (
        "에러", "error", "오류", "고장", "fault", "alarm", "알람", "에러코드",
        "spc", "nelson", "관리도", "공정능력", "cpk", "ppk", "공정",
    ),
    "scenario": (
        "협업", "scenario", "시나리오", "8d 올려", "ecn 발행 요청",
        "ppap 제출 요청", "claim", "클레임 대응",
    ),
    "draft": (
        "작성", "써줘", "써 줘", "초안", "draft", "작성해", "만들어",
        "메일 보내", "메일 써", "보고서 작성", "통보문",
    ),
    "metric": (
        "지표", "kpi", "metric", "매출", "실적", "현황 대시보드", "그래프",
        "차트", "yoy", "qoq",
    ),
    "page": (
        "페이지", "이동", "go to", "open", "열어", "대시보드 페이지",
        "compliance 화면",
    ),
}


@dataclass
class IntentResult:
    """프론트엔드 IntentResult 와 1:1."""

    intent: str
    confidence: float                              # 0.0~1.0
    suggested_category: PaletteCategory | None
    alternatives: list[dict]                       # [{intent, confidence}, ...]


def _keyword_score(query: str) -> dict[PaletteCategory, float]:
    """카테고리별 키워드 매칭 점수 (0.0~1.0).

    각 카테고리는 매칭된 키워드 개수에 따라 0.55 ~ 1.0 의 신뢰도를 부여한다.
    동일 query 가 여러 카테고리에 매칭되는 경우 (예: '조직도' → org_chart + person)
    더 좁은 카테고리(org_chart)가 우선되도록 카테고리별 매칭 길이(평균) 가중치를 부여.
    """
    q = query.lower()
    scores: dict[PaletteCategory, float] = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        matched_lens = [len(kw) for kw in kws if kw in q]
        if not matched_lens:
            scores[cat] = 0.0
            continue
        hits = len(matched_lens)
        avg_len = sum(matched_lens) / hits
        # 더 긴 키워드(예: '조직도', '대시보드 페이지')는 더 강한 신호.
        length_bonus = min(0.20, 0.02 * avg_len)
        scores[cat] = min(1.0, 0.55 + 0.18 * min(hits, 3) + length_bonus)
    return scores


def _ml_categorize(query: str) -> tuple[str | None, float, list[dict]]:
    """ML_05 분류기 (있으면) 호출 → 5 intent.

    Returns: (intent, confidence_0_1, alternatives_top3)
    """
    try:
        from features.search.ml_intent_classifier import get_ml_classifier

        classifier = get_ml_classifier()
        if not classifier._is_trained:
            return None, 0.0, []
        pred = classifier.predict(query)
        # ml_intent_classifier 는 confidence 를 0~100 % 로 반환.
        conf = float(pred.confidence) / 100.0
        all_scores = pred.all_scores or {}
        sorted_alts = sorted(all_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
        alternatives = [{"intent": k, "confidence": float(v) / 100.0} for k, v in sorted_alts]
        return pred.intent, conf, alternatives
    except Exception:
        return None, 0.0, []


def classify_intent(query: str) -> IntentResult:
    """팔레트 카테고리 의도 분류.

    Args:
        query: 사용자 입력 (트림 전).

    Returns:
        IntentResult — confidence 가 0.7 이상이면 프론트가 자동 카테고리 적용.
    """
    q = (query or "").strip()
    if not q:
        return IntentResult(
            intent="unknown",
            confidence=0.0,
            suggested_category=None,
            alternatives=[],
        )

    # 1) ML 5-intent → 카테고리 매핑.
    ml_intent, ml_conf, ml_alts = _ml_categorize(q)

    # 2) 키워드 10-category 스코어.
    kw_scores = _keyword_score(q)
    top_kw_cat: PaletteCategory | None = None
    top_kw_score = 0.0
    for cat, score in kw_scores.items():
        if score > top_kw_score:
            top_kw_score = score
            top_kw_cat = cat

    # 3) 결정 로직.
    suggested: PaletteCategory | None = None
    confidence = 0.0
    intent_name = ml_intent or "unknown"

    if ml_intent and ml_conf >= 0.7:
        # ML 강한 신뢰 — 5→10 매핑 사용. 키워드 결과가 더 강하고 다른 카테고리를 지목하면
        # 키워드 시그널 우선 (Sprint 1 키워드 보강).
        ml_mapped = ML_INTENT_TO_CATEGORY.get(ml_intent)
        if top_kw_cat and top_kw_score >= 0.7 and top_kw_cat != ml_mapped:
            suggested = top_kw_cat
            confidence = top_kw_score
        else:
            suggested = ml_mapped
            confidence = ml_conf
    elif top_kw_cat and top_kw_score >= 0.7:
        suggested = top_kw_cat
        confidence = top_kw_score
        intent_name = f"keyword:{top_kw_cat}"
    elif ml_intent:
        # 약한 ML 결과만 있으면 그것을 후보로.
        suggested = ML_INTENT_TO_CATEGORY.get(ml_intent)
        confidence = ml_conf
    else:
        suggested = top_kw_cat
        confidence = top_kw_score
        intent_name = f"keyword:{top_kw_cat}" if top_kw_cat else "unknown"

    # alternatives — ML 우선, 비어 있으면 키워드 상위 3.
    alternatives: list[dict]
    if ml_alts:
        alternatives = ml_alts
    else:
        alts_sorted = sorted(kw_scores.items(), key=lambda kv: kv[1], reverse=True)
        alternatives = [
            {"intent": f"keyword:{cat}", "confidence": float(score)}
            for cat, score in alts_sorted[:3]
            if score > 0
        ]

    return IntentResult(
        intent=intent_name,
        confidence=round(float(confidence), 3),
        suggested_category=suggested if suggested in VALID_CATEGORIES else None,
        alternatives=alternatives,
    )


# 정규식 사전 — Sprint 1 + 2 의 협업 시나리오 트리거어 ("8D 절차 어떻게 시작?" 등).
_SOP_PATTERN = re.compile(r"(8d|ecn|ppap|fmea|msa)\s*(절차|어떻게|process)", re.IGNORECASE)


def classify_intent_with_overrides(query: str) -> IntentResult:
    """SOP 강제 매칭 등 special-case override 후 classify_intent 호출."""
    q = (query or "").strip()
    if _SOP_PATTERN.search(q):
        return IntentResult(
            intent="keyword:sop",
            confidence=0.85,
            suggested_category="sop",
            alternatives=[],
        )
    return classify_intent(q)
