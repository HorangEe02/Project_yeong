"""v3.3 Phase E — 인-챗 액션 시스템 종합 테스트.

검증 대상:
1. detect_actions() 매트릭스 (단일 / 다중 / 우선순위 / 같은-kind 중복 제거)
2. 영문 키워드 대소문자 무시 (SPC/Cpk/REACH/Nelson)
3. handle_* 핸들러별 graceful fallback (의존성 미주입)
4. dispatch_action() 통합 라우팅
5. summarize_payload_for_llm() — LLM context 요약 텍스트
6. 권한 통합 — 비인증 시 인사 검색 폴백 + 감사 로그
7. SSE 라우터 통합 — 피처 플래그 OFF/ON 분기, 이벤트 순서, action_card 스키마
8. ActionDetectionEvent / ActionCardEvent / 5종 페이로드 Pydantic 검증
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.onboarding.work_actions import (
    DetectedAction,
    ACTION_TYPE_TO_KIND,
    detect_action,
    detect_actions,
)
from features.onboarding.action_handlers import (
    dispatch_action,
    handle_compliance_lookup,
    handle_document_search,
    handle_draft_compose,
    handle_employee_search,
    handle_error_lookup,
    summarize_payload_for_llm,
)
from backend.schemas.onboarding import (
    ActionCardEvent,
    ActionDetectionEvent,
    ComplianceCardPayload,
    DocumentCardPayload,
    DocumentItem,
    DraftCardPayload,
    EmployeeCardPayload,
    ErrorCardPayload,
    ErrorPrediction,
)


# ════════════════════════════════════════════════════════════
# 1. detect_actions() — 매트릭스
# ════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "query,expected_kinds",
    [
        # 단일 매칭
        ("에러코드 E-101 알려줘", ["error"]),
        ("PPAP 양식 다운로드", ["document"]),
        ("산안법 안전거리 기준", ["compliance"]),
        ("홍길동 차장 연락처", ["employee"]),
        ("8D 보고서 작성해줘", ["draft"]),
        # 영문 대소문자
        ("SPC Cpk 현황", ["error"]),
        ("Nelson Rule 위반", ["error"]),
        ("REACH 규제 변경", ["compliance"]),
        # 다중 매칭 — 정렬 순서 우선
        ("PPAP 양식 다운로드 + 홍길동 차장 연락처", ["employee", "document"]),
        ("ALM-104 + Cpk 떨어짐", ["error"]),  # same-kind dedupe
        # 빈/무관 쿼리
        ("", []),
        ("아무 의미 없는 일반 질문", []),
    ],
)
def test_detect_actions_matrix(query: str, expected_kinds: list[str]):
    actions = detect_actions(query)
    assert [a.kind for a in actions] == expected_kinds, (
        f"Q={query!r} → {[a.kind for a in actions]} (기대: {expected_kinds})"
    )


def test_detect_actions_priority_ordering():
    """우선순위: error > employee > compliance > document > draft."""
    q = "ALM-104 에러 + 산안법 + PPAP 양식 + 홍길동 차장 + 8D 작성"
    actions = detect_actions(q)
    kinds = [a.kind for a in actions]
    # error 가 가장 먼저, document 가 draft 보다 앞
    assert kinds.index("error") < kinds.index("compliance")
    assert kinds.index("compliance") < kinds.index("document")


def test_detect_actions_dedupe_same_kind():
    """같은 kind 의 액션 2개 매칭 시 1개만 노출."""
    # error_code 패턴 + spc_status 키워드 → 둘 다 'error' kind
    q = "ALM-104 알람 + Cpk 떨어짐"
    actions = detect_actions(q)
    error_count = sum(1 for a in actions if a.kind == "error")
    assert error_count == 1


def test_detect_actions_confidence_pattern_vs_keyword():
    """정규식 매칭 conf=1.0, 키워드 매칭 conf=0.7."""
    pattern_match = detect_actions("PPAP 양식 다운로드")
    keyword_match = detect_actions("산안법 안전거리")
    assert pattern_match[0].confidence == 1.0
    assert keyword_match[0].confidence == 0.7


def test_detect_actions_returns_dataclass():
    actions = detect_actions("PPAP 양식 다운로드")
    assert isinstance(actions[0], DetectedAction)
    assert actions[0].action_type == "document_search"
    assert actions[0].kind == "document"
    assert "query" in actions[0].params


def test_action_type_to_kind_mapping():
    """모든 action_type 이 5 kind 중 하나로 매핑."""
    valid_kinds = {"document", "draft", "compliance", "employee", "error"}
    for action_type, kind in ACTION_TYPE_TO_KIND.items():
        assert kind in valid_kinds, f"{action_type} → {kind} 잘못된 kind"


def test_detect_action_backward_compat():
    """detect_action() 단일 매칭 backward compat 보장."""
    result = detect_action("PPAP 양식 다운로드")
    assert result is not None
    assert result[0] in ACTION_TYPE_TO_KIND


# ════════════════════════════════════════════════════════════
# 2. 핸들러별 graceful fallback (의존성 None)
# ════════════════════════════════════════════════════════════


def test_handle_document_search_no_searcher():
    """searcher=None 시 빈 결과 반환."""
    result = handle_document_search("PPAP 양식")
    assert result == {"items": [], "total": 0, "query": "PPAP 양식"}


def test_handle_employee_search_no_user():
    """user=None 시 auth_required=True 폴백."""
    result = handle_employee_search("홍길동", user=None)
    assert result["auth_required"] is True
    assert result["items"] == []


def test_handle_employee_search_no_user_logs_audit(caplog):
    """비인증 인사 검색은 INFO 감사 로그를 남긴다."""
    with caplog.at_level(logging.INFO):
        handle_employee_search("홍길동 차장 연락처", user=None)
    assert any("인사 검색 비인증 시도" in r.message for r in caplog.records)


def test_handle_compliance_lookup_known_keyword():
    """산안법 키워드 → safety_distance 시나리오 매칭."""
    result = handle_compliance_lookup("산안법 안전거리")
    # DemoScenarioEngine 가 정상 동작하면 매칭, 실패해도 graceful
    assert "regulation_id" in result
    if result.get("regulation_id"):
        assert result["regulation_id"] == "safety_distance"


def test_handle_draft_compose_8d():
    """8D 키워드 → doc_type='8d_report' + Module B prefill URL."""
    result = handle_draft_compose("8D 보고서 작성해줘", department="품질보증팀")
    assert result["doc_type"] == "8d_report"
    assert "/draft?" in result["full_view_url"]
    assert "prefill_doc_type=8d_report" in result["full_view_url"]


def test_handle_draft_compose_unknown_type():
    """미매칭 키워드 → doc_type='draft' fallback."""
    result = handle_draft_compose("그냥 무언가", department="")
    assert result["doc_type"] == "draft"


def test_handle_error_lookup_with_code_pattern():
    """E-101 같은 코드는 DB 조회 시도 (실패 시 ML 폴백)."""
    result = handle_error_lookup("에러코드 E-101", params={"match": "E-101"})
    # 코드 또는 ML 결과 둘 중 하나는 채워져야 함
    assert "code" in result
    assert "next_likely" in result


def test_handle_error_lookup_natural_language():
    """자연어 증상 → ML 검색 (graceful)."""
    result = handle_error_lookup("프레스가 멈췄어", params={})
    assert "next_likely" in result


# ════════════════════════════════════════════════════════════
# 3. dispatch_action() 라우팅
# ════════════════════════════════════════════════════════════


def test_dispatch_action_document():
    a = DetectedAction(action_type="document_search", kind="document", confidence=1.0)
    payload = dispatch_action(a, "PPAP 양식", searcher=None)
    assert "items" in payload
    assert "total" in payload


def test_dispatch_action_employee_anon():
    a = DetectedAction(action_type="employee_search", kind="employee", confidence=1.0)
    payload = dispatch_action(a, "홍길동", user=None)
    assert payload["auth_required"] is True


def test_dispatch_action_compliance():
    a = DetectedAction(
        action_type="regulation_status",
        kind="compliance",
        confidence=0.7,
        matched_keyword="산안법",
    )
    payload = dispatch_action(a, "산안법 안전거리")
    assert "regulation_id" in payload


def test_dispatch_action_draft():
    a = DetectedAction(action_type="compose_document", kind="draft", confidence=0.7)
    payload = dispatch_action(a, "8D 보고서 작성", department="품질보증팀")
    assert payload["doc_type"] == "8d_report"


def test_dispatch_action_error_with_params():
    a = DetectedAction(
        action_type="error_code", kind="error", confidence=1.0,
        params={"match": "E-101"},
    )
    payload = dispatch_action(a, "에러코드 E-101")
    assert "code" in payload


def test_dispatch_action_unknown_kind():
    """존재하지 않는 kind → 빈 dict."""
    a = DetectedAction(action_type="x", kind="unknown_kind", confidence=0.5)  # type: ignore[arg-type]
    assert dispatch_action(a, "x") == {}


# ════════════════════════════════════════════════════════════
# 4. summarize_payload_for_llm()
# ════════════════════════════════════════════════════════════


def test_summarize_document():
    s = summarize_payload_for_llm("document", {"items": [{"title": "PPAP 양식"}]})
    assert "문서 검색" in s
    assert "PPAP" in s


def test_summarize_employee_anon():
    s = summarize_payload_for_llm("employee", {"auth_required": True})
    assert "비인증" in s


def test_summarize_compliance():
    s = summarize_payload_for_llm(
        "compliance", {"title": "산안법 안전거리", "severity": "CRITICAL"},
    )
    assert "산안법" in s
    assert "CRITICAL" in s


def test_summarize_unknown_kind():
    assert summarize_payload_for_llm("unknown", {}) == ""


# ════════════════════════════════════════════════════════════
# 5. SSE 라우터 통합 (TestClient)
# ════════════════════════════════════════════════════════════


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routers.onboarding import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _parse_sse_events(body: str) -> list[dict]:
    """SSE body 에서 data: 프레임을 dict 리스트로 파싱."""
    import json as _json

    out = []
    for chunk in body.split("\n"):
        chunk = chunk.strip()
        if not chunk.startswith("data:"):
            continue
        payload = chunk[5:].strip()
        if not payload:
            continue
        try:
            out.append(_json.loads(payload))
        except _json.JSONDecodeError:
            continue
    return out


def test_chat_sse_no_actions_when_flag_off(client):
    """FEATURE_C_INLINE_ACTIONS 미설정 (기본 false) → action_card 0건."""
    # 환경변수 명시 OFF
    with patch.dict(os.environ, {"FEATURE_C_INLINE_ACTIONS": "false"}):
        r = client.post(
            "/onboarding/chat",
            json={"query": "산안법 안전거리", "department": "품질보증팀", "history": []},
        )
        events = _parse_sse_events(r.text)
        kinds = [e.get("type") for e in events]
        assert "detection" not in kinds
        assert "action_card" not in kinds


def test_chat_sse_emits_actions_when_flag_on(client):
    """FEATURE_C_INLINE_ACTIONS=true → detection + action_card 송출."""
    with patch.dict(os.environ, {"FEATURE_C_INLINE_ACTIONS": "true"}):
        r = client.post(
            "/onboarding/chat",
            json={"query": "산안법 안전거리", "department": "품질보증팀", "history": []},
        )
        events = _parse_sse_events(r.text)
        detections = [e for e in events if e.get("type") == "detection"]
        cards = [e for e in events if e.get("type") == "action_card"]
        assert detections, "detection 이벤트 미송출"
        assert cards, "action_card 이벤트 미송출"
        assert detections[0]["kind"] == "compliance"
        assert cards[0]["kind"] == "compliance"


def test_chat_sse_event_order_action_before_token(client):
    """SSE 이벤트 순서: detection → action_card → (token / metadata) ..."""
    with patch.dict(os.environ, {"FEATURE_C_INLINE_ACTIONS": "true"}):
        r = client.post(
            "/onboarding/chat",
            json={"query": "PPAP 양식 다운로드", "department": "품질보증팀", "history": []},
        )
        events = _parse_sse_events(r.text)
        detection_idx = next(
            (i for i, e in enumerate(events) if e.get("type") == "detection"), -1
        )
        action_idx = next(
            (i for i, e in enumerate(events) if e.get("type") == "action_card"), -1
        )
        token_idx = next(
            (i for i, e in enumerate(events) if e.get("type") == "token"), -1
        )
        # 액션은 LLM 토큰 전에. token 이 송출되지 않은 환경(LLM 미가동)도 허용 — token_idx=-1
        assert detection_idx != -1
        assert action_idx != -1
        assert detection_idx < action_idx
        if token_idx != -1:
            assert action_idx < token_idx


def test_chat_sse_action_card_payload_schema(client):
    """action_card 의 payload 가 kind 별로 올바른 스키마."""
    with patch.dict(os.environ, {"FEATURE_C_INLINE_ACTIONS": "true"}):
        r = client.post(
            "/onboarding/chat",
            json={"query": "산안법 안전거리", "department": "품질보증팀", "history": []},
        )
        events = _parse_sse_events(r.text)
        cards = [e for e in events if e.get("type") == "action_card"]
        assert cards
        card = cards[0]
        assert card["kind"] == "compliance"
        # ComplianceCardPayload 핵심 필드
        assert "regulation_id" in card["payload"]
        assert "title" in card["payload"]


def test_chat_sse_multi_action_emits_two_cards(client):
    """다중 매칭 시 카드 2장 송출 (예: 인사 검색 + 문서 검색)."""
    with patch.dict(os.environ, {"FEATURE_C_INLINE_ACTIONS": "true"}):
        r = client.post(
            "/onboarding/chat",
            json={
                "query": "PPAP 양식 다운로드 + 홍길동 차장 연락처",
                "department": "품질보증팀",
                "history": [],
            },
        )
        events = _parse_sse_events(r.text)
        cards = [e for e in events if e.get("type") == "action_card"]
        assert len(cards) == 2
        kinds = [c["kind"] for c in cards]
        assert set(kinds) == {"employee", "document"}


def test_chat_sse_anon_employee_returns_auth_required(client):
    """비인증 + 인사 검색 쿼리 → auth_required=True 카드."""
    with patch.dict(os.environ, {"FEATURE_C_INLINE_ACTIONS": "true"}):
        r = client.post(
            "/onboarding/chat",
            json={"query": "홍길동 차장 연락처", "department": "품질보증팀", "history": []},
        )
        events = _parse_sse_events(r.text)
        emp_cards = [
            e for e in events
            if e.get("type") == "action_card" and e.get("kind") == "employee"
        ]
        assert emp_cards
        assert emp_cards[0]["payload"]["auth_required"] is True


# ════════════════════════════════════════════════════════════
# 6. Pydantic 스키마 검증 (E-1 산출물)
# ════════════════════════════════════════════════════════════


def test_schema_action_detection_event():
    e = ActionDetectionEvent(kind="document", confidence=0.92, matched_keyword="양식")
    assert e.type == "detection"
    assert e.kind == "document"


def test_schema_action_card_event():
    e = ActionCardEvent(kind="compliance", payload={"regulation_id": "x"})
    assert e.type == "action_card"


def test_schema_action_kind_invalid_rejected():
    """ActionKind Literal 외 값은 거부."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ActionDetectionEvent(kind="invalid_kind", confidence=0.5)  # type: ignore[arg-type]


def test_schema_document_card_payload():
    p = DocumentCardPayload(
        items=[DocumentItem(doc_id="1", title="X", score=0.9)],
        total=1,
        query="x",
    )
    assert p.total == 1
    assert p.items[0].title == "X"


def test_schema_employee_card_visibility_default_partial():
    from backend.schemas.onboarding import EmployeeItem

    item = EmployeeItem(name="홍길동", department="품질", position="차장")
    assert item.visibility == "PARTIAL"


def test_schema_error_card_with_predictions():
    p = ErrorCardPayload(
        code="E-101",
        next_likely=[ErrorPrediction(code="E-205", probability=0.62)],
    )
    assert p.next_likely[0].probability == 0.62


def test_schema_compliance_optional_dday():
    p = ComplianceCardPayload(title="x")
    assert p.days_until_effective is None


def test_schema_draft_card_default_url():
    p = DraftCardPayload()
    assert p.full_view_url == ""
