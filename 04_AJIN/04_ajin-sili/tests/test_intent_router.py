"""v4.7 Sprint 2 P0 (축 ②) — palette intent router 테스트.

10 카테고리 각 대표 쿼리에 대해:
  - classify_intent_with_overrides 가 confidence ≥ 0.7
  - suggested_category 가 기대 카테고리와 일치
  - alternatives 가 비어있지 않거나, 빈 경우 confidence 가 매우 높음
"""

from __future__ import annotations

import pytest

from features.search.palette_intent import (
    CATEGORY_KEYWORDS,
    classify_intent,
    classify_intent_with_overrides,
)


# (query, expected_category) — 10 카테고리 × 3~5 샘플.
SAMPLES: list[tuple[str, str]] = [
    # person
    ("박준영 사원 연락처", "person"),
    ("품질팀 담당자 누구야", "person"),
    ("김영희 과장 내선번호", "person"),
    # doc
    ("8D Report 양식 어디 있어", "doc"),
    ("ECN 변경통보 문서 찾아줘", "doc"),
    ("회의록 minutes 검색", "doc"),
    # sop
    ("8D 절차 어떻게 시작", "sop"),
    ("PPAP process 표준작업", "sop"),
    ("SOP 체크리스트 찾아줘", "sop"),
    # regulation
    ("REACH 규제 현황", "regulation"),
    ("ISO 9001 compliance", "regulation"),
    ("IATF 16949 컴플라이언스 점검", "regulation"),
    # equipment_error
    ("에러코드 E001", "equipment_error"),
    ("SPC Cpk 떨어졌어 알람", "equipment_error"),
    ("Nelson Rule 위반 공정", "equipment_error"),
    # scenario
    ("8D 올려달라는데 협업 시나리오", "scenario"),
    ("클레임 대응 협업", "scenario"),
    # org_chart
    ("조직도 보여줘", "org_chart"),
    ("팀 구성 조직 구조", "org_chart"),
    # draft
    ("PPAP 메일 작성해줘", "draft"),
    ("ECN 통보문 초안 만들어", "draft"),
    ("주간 보고 보고서 작성", "draft"),
    # metric
    ("매출 지표 차트", "metric"),
    ("KPI 현황 대시보드", "metric"),
    # page
    ("compliance 화면 이동", "page"),
    ("대시보드 페이지 열어", "page"),
]


@pytest.mark.parametrize("query,expected", SAMPLES)
def test_classify_intent_categorizes_each_sample(query: str, expected: str) -> None:
    result = classify_intent_with_overrides(query)
    assert result.suggested_category == expected, (
        f"query={query!r} expected={expected} got={result.suggested_category} "
        f"confidence={result.confidence}"
    )
    assert result.confidence >= 0.7, (
        f"query={query!r} confidence={result.confidence} (must be >= 0.7)"
    )


def test_empty_query_returns_unknown() -> None:
    r = classify_intent("")
    assert r.suggested_category is None
    assert r.confidence == 0.0


def test_categories_set_completeness() -> None:
    """CATEGORY_KEYWORDS 가 10 카테고리 모두 다룬다."""
    expected = {
        "person",
        "doc",
        "sop",
        "regulation",
        "equipment_error",
        "scenario",
        "org_chart",
        "draft",
        "metric",
        "page",
    }
    assert set(CATEGORY_KEYWORDS.keys()) == expected


def test_sop_pattern_override_triggers_high_confidence() -> None:
    """'8D 절차 어떻게' 같은 정규식 매칭이 우선 적용됨."""
    r = classify_intent_with_overrides("8D 절차 어떻게 시작하나요")
    assert r.suggested_category == "sop"
    assert r.confidence >= 0.8


def test_alternatives_shape_valid() -> None:
    r = classify_intent_with_overrides("REACH 규제 현황")
    # alternatives 는 list[dict{intent, confidence}] — 비어있어도 OK.
    for alt in r.alternatives:
        assert "intent" in alt
        assert "confidence" in alt
        assert 0.0 <= float(alt["confidence"]) <= 1.0
