"""v3.3 Phase E-3 — 인-챗 액션 핸들러 5종 + 디스패처.

각 핸들러는 사용자 질문을 받아 해당 카드 payload(dict) 를 반환한다.
- 의존 모듈 import 실패 / 데이터 부재 시 빈 페이로드 또는 안내 메시지로 graceful fallback.
- 인사 검색만 user 객체 필요 (가시성 매트릭스 적용).

라우터 통합 (E-4): backend/routers/onboarding.py 의 event_stream() 가
detect_actions() 결과 → dispatch_action() → SSE action_card 이벤트로 송출.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from features.onboarding.work_actions import DetectedAction

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# document_search — Module A (BM25 + Vector 검색)
# ──────────────────────────────────────────────


def handle_document_search(query: str, searcher=None) -> dict:
    """문서 검색 결과 5건 반환. Module A 의 searcher 를 의존성 주입으로 받는다.

    Args:
        query: 검색어
        searcher: app.state.searcher (HybridSearcher) — 라우터에서 주입.
                  None 이면 빈 결과 (graceful — 검색기 미초기화 환경 호환).
    """
    payload: dict[str, Any] = {"items": [], "total": 0, "query": query}
    if searcher is None:
        logger.debug("handle_document_search: searcher 미주입 — 빈 결과")
        return payload
    try:
        results = searcher.search(query, k=5)
        items: list[dict] = []
        for r in results[:5]:
            items.append({
                "doc_id": getattr(r, "doc_id", "") or "",
                "title": getattr(r, "title", "") or "",
                "doc_type": getattr(r, "doc_type", "") or "",
                "snippet": (getattr(r, "content", "") or "")[:160],
                "score": float(getattr(r, "score", 0.0) or 0.0),
                "download_url": (
                    f"/api/onboarding/download?doc_id={getattr(r, 'doc_id', '')}"
                    if getattr(r, "doc_id", "")
                    else ""
                ),
            })
        payload["items"] = items
        payload["total"] = len(items)
    except Exception as e:
        logger.exception("handle_document_search 실패: %s", e)
    return payload


# ──────────────────────────────────────────────
# employee_search — Module E (인사 검색 + 가시성)
# ──────────────────────────────────────────────


def handle_employee_search(query: str, user, engine=None) -> dict:
    """인사 검색 결과 — 가시성 매트릭스 적용. 비인증 시 auth_required=True 폴백.

    Args:
        query: 검색어
        user: 인증 사용자 (None 이면 auth_required=True 로 폴백)
        engine: app.state.employee_engine — 라우터에서 주입.
                None 이면 stand-alone 인스턴스 생성 (테스트/스크립트 용).
    """
    payload: dict[str, Any] = {
        "items": [],
        "total": 0,
        "query": query,
        "auth_required": False,
    }

    # 비인증 — 프런트가 로그인 안내 카드로 폴백.
    # 보안 감사: 비인증 인사 검색 시도는 잠재적 프로빙이므로 INFO 로그 (경보는 X).
    if user is None:
        logger.info("인사 검색 비인증 시도 — query 길이=%d, 폴백 카드 노출", len(query or ""))
        payload["auth_required"] = True
        return payload

    # 검색어 정제 — 흔한 prefix/suffix 제거
    search_term = re.sub(
        r"(연락처|전화번호|내선|이메일|누구|찾아|검색|알려줘)", "", query
    ).strip()
    if not search_term:
        return payload

    try:
        from core.auth.visibility import (
            VisibilityLevel,
            determine_visibility,
            filter_employee_fields,
        )

        # engine 주입 우선 — 미주입 시 stand-alone (성능 떨어짐, 호환성 유지)
        owns_db = False
        db = None
        if engine is None:
            from features.search.employee.database import EmployeeDatabase
            from features.search.employee.search import EmployeeSearchEngine

            db = EmployeeDatabase()
            engine = EmployeeSearchEngine(db)
            owns_db = True

        result = engine.search(search_term)
        if owns_db and db is not None:
            db.close()

        raw = result.get("results", [])
        # v3.6 — Feature A 와 동일하게 visible 인원 전체 노출.
        # 이전에는 raw[:5] 로 잘라 17명 중 5명만 채팅 카드에 표기 → 사용자 혼동.
        # 이제 HIDDEN 필터링 후 모든 인원을 items 에 담고 total 도 실제 수치로 반영.
        DISPLAY_CAP = 30  # LLM 컨텍스트 보호용 안전한 상한 (부서 단위 평균 < 20)
        items: list[dict] = []
        visible_total = 0
        for r in raw:
            if not isinstance(r, dict):
                continue
            emp_dept = r.get("department", "")
            emp_role = r.get("role", "EMPLOYEE")

            vis = determine_visibility(user, emp_dept, emp_role)
            if vis == VisibilityLevel.HIDDEN:
                continue
            visible_total += 1

            if len(items) >= DISPLAY_CAP:
                continue  # 카운트는 계속 — 표시만 cap

            filtered = filter_employee_fields(r, vis) if vis == VisibilityLevel.PARTIAL else r
            vis_label = "FULL" if vis == VisibilityLevel.FULL else "PARTIAL"

            items.append({
                "name": filtered.get("name", ""),
                "department": filtered.get("department", ""),
                "position": filtered.get("position", ""),
                "visibility": vis_label,
                "contact": {
                    "extension": filtered.get("extension"),
                    "email": filtered.get("email"),
                    "phone": filtered.get("phone"),
                },
            })
        payload["items"] = items
        payload["total"] = visible_total
        if visible_total > len(items):
            payload["truncated"] = True
    except Exception as e:
        logger.exception("handle_employee_search 실패: %s", e)
    return payload


# ──────────────────────────────────────────────
# regulation_status / compliance — Module D
# ──────────────────────────────────────────────


_COMPLIANCE_KEYWORD_TO_SCENARIO = {
    "safety_distance": ["안전거리", "산안법", "프레스 안전", "안전 거리"],
    "us_tariff_25": ["관세", "HMGMA", "트럼프", "25%"],
    "reach_svhc_update": ["REACH", "SVHC", "크롬", "화학물질"],
}


def handle_compliance_lookup(query: str) -> dict:
    """규제·컴플라이언스 조회 — DemoScenarioEngine 재사용."""
    payload: dict[str, Any] = {
        "regulation_id": "",
        "title": "",
        "severity": "",
        "effective_date": "",
        "days_until_effective": None,
        "excerpt": "",
        "affected_departments": [],
        "full_view_url": "/compliance",
    }
    try:
        from features.compliance.demo_scenario_engine import DemoScenarioEngine

        engine = DemoScenarioEngine()
        q_lower = query.lower()

        matched = None
        for sid, keywords in _COMPLIANCE_KEYWORD_TO_SCENARIO.items():
            if any(kw.lower() in q_lower for kw in keywords):
                matched = engine.get_scenario(sid)
                break

        if matched:
            payload["regulation_id"] = matched.id
            payload["title"] = matched.title
            payload["severity"] = matched.severity
            payload["effective_date"] = matched.effective_date
            payload["days_until_effective"] = matched.days_until_effective
            payload["excerpt"] = (matched.summary or "")[:300]
            payload["affected_departments"] = list(matched.affected_departments)[:5]
            payload["full_view_url"] = f"/compliance?scenario={matched.id}"
        else:
            # 미매칭 — 전체 요약 안내
            summary = engine.get_summary_for_dashboard()
            payload["title"] = f"규제 모니터링 ({summary.get('total_scenarios', 0)}건)"
            payload["excerpt"] = "구체적인 규제명을 명시하세요. (예: 산안법, REACH, 관세)"
    except Exception as e:
        logger.exception("handle_compliance_lookup 실패: %s", e)
    return payload


# ──────────────────────────────────────────────
# compose_document / compose_email — Module B (Draft)
# ──────────────────────────────────────────────


_DOC_TYPE_KEYWORDS = {
    "8d_report": ["8D"],
    "ecn": ["ECN"],
    "ppap": ["PPAP"],
    "email_internal": ["이메일", "메일"],
    "report": ["보고서"],
}


def handle_draft_compose(query: str, department: str = "") -> dict:
    """초안 작성 카드 — 첫 줄 요약만 반환, 전체 화면은 Module B 라우트."""
    payload: dict[str, Any] = {
        "title": "초안 작성",
        "doc_type": "draft",
        "markdown_preview": "",
        "full_view_url": "/draft",
    }

    # 문서 유형 추정
    q_lower = query.lower()
    doc_type = "draft"
    for dt, kws in _DOC_TYPE_KEYWORDS.items():
        if any(kw.lower() in q_lower for kw in kws):
            doc_type = dt
            break

    type_label = {
        "8d_report": "8D Report",
        "ecn": "ECN (설계 변경 통지)",
        "ppap": "PPAP 패키지",
        "email_internal": "사내 이메일",
        "report": "보고서",
    }.get(doc_type, "초안")

    payload["title"] = f"{type_label} 초안"
    payload["doc_type"] = doc_type
    payload["markdown_preview"] = (
        f"_{type_label}_ 의 초안을 Module B (문서 작성) 화면에서 생성합니다.\n"
        f"부서 컨텍스트: **{department or '미지정'}**\n\n"
        f"입력하신 요청: \"{query[:100]}\""
    )
    # prefill — Module B 가 query string 으로 받음
    from urllib.parse import urlencode
    qs = urlencode({"prefill_doc_type": doc_type, "prefill_user_input": query[:200]})
    payload["full_view_url"] = f"/draft?{qs}"
    return payload


# ──────────────────────────────────────────────
# error_code / spc_status — Module F (설비)
# ──────────────────────────────────────────────


def handle_error_lookup(query: str, params: dict | None = None) -> dict:
    """에러코드 조회 + Markov 후속. 코드 미매칭 시 ML 증상 검색 결과로 폴백."""
    payload: dict[str, Any] = {
        "code": "",
        "error_name": "",
        "severity": "",
        "cause": "",
        "action": "",
        "avg_recovery_min": None,
        "history_count": None,
        "next_likely": [],
        "full_view_url": "/equipment",
    }
    params = params or {}

    # 1) 코드 패턴 매칭 — DB 직접 조회
    code = params.get("match", "")
    if not code:
        m = re.search(r"([A-Za-z]+-?\d+)", query)
        code = m.group(1) if m else ""

    try:
        if code and re.match(r"^[A-Za-z]+-?\d+$", code):
            from features.equipment.error_code_db import lookup_error

            results = lookup_error(code)
            if results:
                err = results[0]
                payload["code"] = err.get("error_code", code) or code
                payload["error_name"] = err.get("error_name", "") or ""
                payload["severity"] = err.get("severity", "") or ""
                payload["cause"] = err.get("cause", "") or ""
                payload["action"] = err.get("action", "") or ""
                payload["full_view_url"] = f"/equipment?code={payload['code']}"
                return payload

        # 2) 자연어 증상 검색 (ML)
        from features.equipment.ml_error_search import ml_search_with_context

        results = ml_search_with_context(query, top_k=1)
        if results:
            top = results[0]
            payload["code"] = top.get("code", "") or ""
            payload["error_name"] = top.get("description", "") or ""
            payload["severity"] = top.get("severity", "") or ""
            payload["cause"] = top.get("cause", "") or ""
            payload["action"] = top.get("action", "") or ""

            hs = top.get("history_summary") or {}
            payload["avg_recovery_min"] = hs.get("avg_resolution_min")
            payload["history_count"] = hs.get("total_count")

            cascade = top.get("cascade_warning") or {}
            preds = cascade.get("predictions", []) or []
            payload["next_likely"] = [
                {
                    "code": p.get("code", "") or "",
                    "probability": float(p.get("probability", 0)) / 100.0
                    if p.get("probability", 0) > 1
                    else float(p.get("probability", 0)),
                    "description": p.get("description", "") or "",
                }
                for p in preds[:3]
            ]
            payload["full_view_url"] = f"/equipment?query={query[:100]}"
    except Exception as e:
        logger.exception("handle_error_lookup 실패: %s", e)
    return payload


# ──────────────────────────────────────────────
# Dispatcher — DetectedAction → payload dict
# ──────────────────────────────────────────────


def dispatch_action(
    action: DetectedAction,
    query: str,
    user=None,
    department: str = "",
    searcher=None,
    employee_engine=None,
) -> dict:
    """5종 kind 별 핸들러 라우팅.

    Args:
        action: detect_actions() 가 반환한 DetectedAction
        query: 원문 쿼리
        user: 인증 사용자 (인사 검색에 가시성 적용)
        department: Phase B _resolve_effective_department() 결과 (draft prefill 에 활용)
        searcher: app.state.searcher — 라우터에서 주입 (document_search 용)
        employee_engine: app.state.employee_engine — 라우터에서 주입 (employee_search 용)

    Returns:
        카드 payload dict (kind 에 맞는 *CardPayload 형식)
    """
    kind = action.kind

    if kind == "document":
        return handle_document_search(query, searcher=searcher)
    if kind == "employee":
        return handle_employee_search(query, user, engine=employee_engine)
    if kind == "compliance":
        return handle_compliance_lookup(query)
    if kind == "draft":
        return handle_draft_compose(query, department=department)
    if kind == "error":
        return handle_error_lookup(query, action.params)

    # unknown kind — 빈 payload (라우터에서 이벤트 발행 자체를 스킵해야 함)
    return {}


def summarize_payload_for_llm(kind: str, payload: dict) -> str:
    """LLM 후속 답변용 — 액션 결과를 system context 에 짧게 주입할 요약 텍스트."""
    if kind == "document":
        items = payload.get("items", [])
        return (
            f"[방금 실행된 액션 — 문서 검색] {len(items)}건 발견."
            + (f" 첫 결과: {items[0].get('title', '')}." if items else "")
        )
    if kind == "employee":
        if payload.get("auth_required"):
            return (
                "[액션:인사검색] 비인증 — 로그인 안내 카드 노출. "
                "사용자에게 '로그인 후 이용 가능' 만 안내. **가짜 연락처 생성 금지**."
            )
        items = payload.get("items", [])
        q = payload.get("query", "")
        if not items:
            return (
                f"[액션:인사검색] '{q}' 검색 결과 0건. "
                "**중요**: 사내 인사 DB에 등록되지 않은 인물입니다. "
                "**가짜 전화번호/이메일 생성 절대 금지**. "
                "사용자에게 '인사 DB 미등록 — 부서장 또는 총무인사팀에 문의' 라고만 답하시오."
            )
        # N건 — 실제 데이터를 LLM 컨텍스트로 전달 (온프레미스 사내 환경)
        # v3.6 — total = visible 전체, items = 표시 cap (DISPLAY_CAP=30) 분리.
        total = payload.get("total", len(items))
        header = f"[액션:인사검색] '{q}' 검색 결과 총 {total}건"
        if total > len(items):
            header += f" (LLM 컨텍스트 보호용 상위 {len(items)}건만 본문 노출)"
        header += " — 사내 직원 정보 (업무 목적 공유 가능):"
        lines = [header]
        for i, it in enumerate(items, 1):
            c = it.get("contact", {}) or {}
            contact_parts = []
            if c.get("extension"):
                contact_parts.append(f"내선 {c['extension']}")
            if c.get("email"):
                contact_parts.append(f"이메일 {c['email']}")
            if c.get("phone"):
                contact_parts.append(f"휴대폰 {c['phone']}")
            contact_str = " · ".join(contact_parts) or "연락처 비공개"
            vis = it.get("visibility", "PARTIAL")
            lines.append(
                f"  {i}. {it.get('name','')} "
                f"({it.get('department','')} {it.get('position','')}) "
                f"[{vis}] — {contact_str}"
            )
        lines.append(
            "위 결과를 정확히 사용해 답변하시오. "
            "**결과에 없는 정보(가짜 번호/이메일) 추가 금지**."
        )
        return "\n".join(lines)
    if kind == "compliance":
        title = payload.get("title", "")
        sev = payload.get("severity", "")
        return f"[방금 실행된 액션 — 규제 조회] {title} (심각도: {sev or '미지정'})."
    if kind == "draft":
        return f"[방금 실행된 액션 — 초안 작성] doc_type={payload.get('doc_type', '')}, Module B 진입 링크 생성됨."
    if kind == "error":
        code = payload.get("code", "")
        sev = payload.get("severity", "")
        return f"[방금 실행된 액션 — 에러/SPC 조회] code={code}, severity={sev}."
    return ""
