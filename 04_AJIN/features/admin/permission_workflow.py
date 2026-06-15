"""v4.7 PR-E7 — 2단계 결재 워크플로우.

흐름
----
1. 요청자 (HR_ADMIN+) 가 권한 변경 요청 생성 (status='pending')
2. IT보안 (SYS_ADMIN) 1차 승인 → status='security_approved'
3. 임원 (role_level >= 5 + EXECUTIVE) 최종 승인
   → permissions table UPDATE + status='applied'
4. 어느 단계에서든 거부 가능 → status='rejected'

escalation
----------
24h+ pending 또는 24h+ security_approved 요청은
``escalate_overdue()`` 가 식별 (Celery beat 매 4 시간 호출).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.auth.permissions_db import (
    get_change_request,
    get_permission,
    init_permissions_db,
    insert_audit,
    insert_change_request,
    list_change_requests,
    update_change_request_status,
    upsert_permission,
)

# 상태 상수 ───────────────────────────────────────────────────────────────────

STATUS_PENDING = "pending"
STATUS_SECURITY_APPROVED = "security_approved"
STATUS_EXECUTIVE_APPROVED = "executive_approved"
STATUS_APPLIED = "applied"
STATUS_REJECTED = "rejected"

_ACTIVE_STATUSES = {STATUS_PENDING, STATUS_SECURITY_APPROVED}
_TERMINAL_STATUSES = {STATUS_APPLIED, STATUS_REJECTED}


class WorkflowError(RuntimeError):
    """워크플로우 전이 규칙 위반."""


# ── 요청 생성 ───────────────────────────────────────────────────────────────


def create_change_request(
    permission_key: str,
    new_value: dict,
    reason: str,
    actor: str,
) -> int:
    """요청자가 권한 변경 요청 생성. status='pending', request_id 반환.

    Args:
        permission_key: 변경 대상 permission key (없으면 신규 권한 생성 요청).
        new_value: 신규 권한 정의 (description/min_role/departments/...).
        reason: 변경 사유 (필수, 빈 문자열 거부).
        actor: 요청자 employee_id.
    """
    if not reason or not reason.strip():
        raise WorkflowError("reason 은 비어 있을 수 없습니다.")
    init_permissions_db()

    old_value = get_permission(permission_key)  # None 이면 신규 권한
    return insert_change_request(
        permission_key=permission_key,
        requested_by=actor,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    )


# ── 승인/거부 ───────────────────────────────────────────────────────────────


def approve_by_security(request_id: int, approver: str) -> dict:
    """IT 보안 1차 승인. status='pending' → 'security_approved'."""
    req = _require_request(request_id)
    if req["status"] != STATUS_PENDING:
        raise WorkflowError(
            f"security approve 는 status='pending' 에서만 가능 "
            f"(현재: {req['status']})"
        )
    updated = update_change_request_status(
        request_id,
        STATUS_SECURITY_APPROVED,
        security_approver=approver,
    )
    insert_audit(
        req["permission_key"], approver, "approve_security",
        {"request_id": request_id},
    )
    return updated


def approve_by_executive(request_id: int, approver: str) -> dict:
    """임원 최종 승인 + 자동 applied.

    transition: 'security_approved' → 'executive_approved' → 'applied'.
    permissions table UPDATE + permission_audit INSERT (upsert_permission 내부).
    """
    req = _require_request(request_id)
    if req["status"] != STATUS_SECURITY_APPROVED:
        raise WorkflowError(
            f"executive approve 는 status='security_approved' 에서만 가능 "
            f"(현재: {req['status']})"
        )

    # 1) executive_approver 기록
    update_change_request_status(
        request_id,
        STATUS_EXECUTIVE_APPROVED,
        executive_approver=approver,
    )
    insert_audit(
        req["permission_key"], approver, "approve_executive",
        {"request_id": request_id},
    )

    # 2) permissions table 적용
    new_value = dict(req["new_value"] or {})
    new_value.setdefault("key", req["permission_key"])
    new_value.setdefault("description", "")
    new_value.setdefault("min_role", "EMPLOYEE")
    upsert_permission(new_value, actor=approver)

    # 3) status='applied'
    now = datetime.now(timezone.utc).isoformat()
    applied = update_change_request_status(
        request_id, STATUS_APPLIED, applied_at=now,
    )
    insert_audit(
        req["permission_key"], approver, "apply",
        {"request_id": request_id, "applied_at": now},
    )
    return applied


def reject(request_id: int, approver: str, reason: str) -> dict:
    """반려. pending / security_approved 에서만 가능. terminal 상태는 거부."""
    if not reason or not reason.strip():
        raise WorkflowError("reject reason 은 비어 있을 수 없습니다.")

    req = _require_request(request_id)
    if req["status"] in _TERMINAL_STATUSES:
        raise WorkflowError(
            f"이미 terminal 상태입니다: {req['status']}"
        )

    # stage 정보를 audit 에 기록
    stage = req["status"]
    updated = update_change_request_status(request_id, STATUS_REJECTED)
    insert_audit(
        req["permission_key"], approver, "reject",
        {"request_id": request_id, "stage": stage, "reason": reason},
    )
    return updated


# ── 조회 ────────────────────────────────────────────────────────────────────


def get_queue(status_filter: str = STATUS_PENDING) -> list[dict]:
    """대기열 조회. status_filter 는 pending / security_approved 권장."""
    return list_change_requests(status_filter=status_filter)


def get_history(limit: int = 50) -> list[dict]:
    """변경 이력 — applied + rejected 만. requested_at DESC. limit 적용."""
    applied = list_change_requests(status_filter=STATUS_APPLIED)
    rejected = list_change_requests(status_filter=STATUS_REJECTED)
    merged = sorted(
        applied + rejected,
        key=lambda r: r.get("requested_at") or "",
        reverse=True,
    )
    return merged[:limit]


# ── escalation ──────────────────────────────────────────────────────────────


def escalate_overdue(threshold_hours: int = 24) -> list[dict]:
    """threshold_hours 이상 pending / security_approved 인 요청 식별.

    Celery beat (매 4 시간) 가 호출. 외부 알림 (Slack/메일) 은 호출자가 처리.

    Returns:
        list of {request_id, permission_key, status, requested_by,
                 hours_pending, requested_at}.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
    overdue: list[dict] = []
    for status in (STATUS_PENDING, STATUS_SECURITY_APPROVED):
        for r in list_change_requests(status_filter=status):
            requested_at = _parse_iso(r.get("requested_at"))
            if requested_at is None:
                continue
            if requested_at <= cutoff:
                age = datetime.now(timezone.utc) - requested_at
                overdue.append({
                    "request_id": r["request_id"],
                    "permission_key": r["permission_key"],
                    "status": r["status"],
                    "requested_by": r["requested_by"],
                    "hours_pending": int(age.total_seconds() // 3600),
                    "requested_at": r["requested_at"],
                })
    overdue.sort(key=lambda x: x["hours_pending"], reverse=True)
    return overdue


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────


def _require_request(request_id: int) -> dict:
    req = get_change_request(request_id)
    if req is None:
        raise WorkflowError(f"request_id={request_id} 가 존재하지 않습니다.")
    return req


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
