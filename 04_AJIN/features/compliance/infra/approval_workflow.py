"""P5 §7 — 자체 결재 워크플로 (Hancom e-Approval 무료 대안).

컴플라이언스 변경에 대한 다단 결재 (요청자 → 차장 → 팀장 → 임원).
- 외부 시스템 의존 X — sqlite + 우리 employees.db / Slack notify 재사용
- 멱등 — 동일 step 에 동일 결재자가 두 번 act 하면 두 번째는 거절
- 단계별 Slack DM (notify_slack 재사용)
- 거절 시 chain 즉시 종료 (rejected), 통과 시 다음 단계 활성

DB:
  approval_chains(id, change_id, name, requested_by, status, current_step, created_at)
  approval_steps(id, chain_id, step_order, approver_id, role_label, decision, comment, decided_at)

status: pending → approved | rejected
decision: pending | approved | rejected | delegated
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


VALID_DECISIONS = {"approved", "rejected", "delegated"}


def _conn() -> sqlite3.Connection:
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    c = sqlite3.connect(CHANGE_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ─────────────────────────────────────────────────────────────
# 시작 / 단계 활성화
# ─────────────────────────────────────────────────────────────


def start_chain(
    *,
    change_id: int,
    name: str,
    requested_by: str,
    steps: list[dict[str, Any]],
) -> int:
    """새 결재 chain 생성. steps 는 [{approver_id, role_label?}] 순서대로.

    Returns: chain_id
    Raises: ValueError — steps 비어있거나 approver_id 누락
    """
    if not steps:
        raise ValueError("steps 가 비어있습니다 — 최소 1단계 필요")
    if not requested_by:
        raise ValueError("requested_by 필요")
    for i, s in enumerate(steps):
        if not (s.get("approver_id") or "").strip():
            raise ValueError(f"step {i+1} 의 approver_id 누락")

    now = datetime.now().isoformat()
    c = _conn()
    cur = c.execute(
        """INSERT INTO approval_chains
           (change_id, name, requested_by, status, current_step, created_at)
           VALUES (?,?,?,?,?,?)""",
        (int(change_id), name[:200], requested_by[:100], "pending", 1, now),
    )
    chain_id = int(cur.lastrowid)
    for i, s in enumerate(steps):
        c.execute(
            """INSERT INTO approval_steps
               (chain_id, step_order, approver_id, role_label, decision)
               VALUES (?,?,?,?,?)""",
            (
                chain_id,
                i + 1,
                str(s["approver_id"]).strip()[:100],
                str(s.get("role_label") or "")[:50],
                "pending",
            ),
        )
    c.commit()
    c.close()
    _notify_step_active(chain_id, 1)
    return chain_id


def _notify_step_active(chain_id: int, step_order: int) -> None:
    """다음 단계 활성 시 결재자에게 Slack DM (실패 시 graceful skip)."""
    c = _conn()
    chain = c.execute(
        "SELECT * FROM approval_chains WHERE id = ?", (chain_id,),
    ).fetchone()
    step = c.execute(
        """SELECT * FROM approval_steps
           WHERE chain_id = ? AND step_order = ?""",
        (chain_id, step_order),
    ).fetchone()
    c.close()
    if not chain or not step:
        return
    try:
        from features.compliance.alerts.notify_slack import route as slack_route
        slack_route(
            {
                "grade": "INFO",
                "item_title": (
                    f"📝 [결재 요청 #{chain_id}] {chain['name']} · "
                    f"step {step_order} ({step['role_label'] or '결재자'})"
                ),
                "summary_ko": (
                    f"결재자: {step['approver_id']}, 요청자: {chain['requested_by']}. "
                    "10분 내 의사결정 권장."
                ),
                "change_type": "approval",
                "affected_departments": [],
            },
            change_id=int(chain["change_id"] or 0),
        )
    except Exception as e:
        logger.debug("approval Slack DM 실패: %s", e)


# ─────────────────────────────────────────────────────────────
# 결재 행위
# ─────────────────────────────────────────────────────────────


def act_on_step(
    step_id: int,
    decision: str,
    *,
    actor: str,
    comment: str = "",
) -> dict[str, Any]:
    """결재자가 step 에 결정. 다음 단계 활성 또는 chain 종료.

    Returns:
      {ok, chain_id, step_order, new_chain_status, next_step_order, error?}
    """
    if decision not in VALID_DECISIONS:
        return {"ok": False, "error": f"invalid decision (must be {sorted(VALID_DECISIONS)})"}
    if not actor:
        return {"ok": False, "error": "actor 필요"}

    c = _conn()
    step = c.execute(
        "SELECT * FROM approval_steps WHERE id = ?", (step_id,),
    ).fetchone()
    if step is None:
        c.close()
        return {"ok": False, "error": f"step_id={step_id} 미존재"}
    if step["decision"] != "pending":
        c.close()
        return {
            "ok": False,
            "error": f"already_decided:{step['decision']}",
            "chain_id": int(step["chain_id"]),
            "step_order": int(step["step_order"]),
        }
    if actor != step["approver_id"]:
        c.close()
        return {
            "ok": False,
            "error": f"not_assigned:{step['approver_id']}",
        }

    chain_id = int(step["chain_id"])
    chain = c.execute(
        "SELECT * FROM approval_chains WHERE id = ?", (chain_id,),
    ).fetchone()
    if chain is None or chain["status"] != "pending":
        c.close()
        return {"ok": False, "error": f"chain_status:{chain['status'] if chain else 'gone'}"}
    if int(chain["current_step"]) != int(step["step_order"]):
        c.close()
        return {
            "ok": False,
            "error": f"out_of_order: current_step={chain['current_step']}",
        }

    now = datetime.now().isoformat()
    c.execute(
        """UPDATE approval_steps
           SET decision = ?, comment = ?, decided_at = ? WHERE id = ?""",
        (decision, (comment or "")[:500], now, step_id),
    )

    new_chain_status = "pending"
    next_step_order = 0
    if decision == "rejected":
        c.execute(
            """UPDATE approval_chains SET status = 'rejected', completed_at = ?
               WHERE id = ?""",
            (now, chain_id),
        )
        new_chain_status = "rejected"
    else:
        # approved / delegated → 다음 단계 활성
        next_order = int(step["step_order"]) + 1
        next_row = c.execute(
            "SELECT id FROM approval_steps WHERE chain_id = ? AND step_order = ?",
            (chain_id, next_order),
        ).fetchone()
        if next_row is None:
            # 마지막 단계 → 전체 승인
            c.execute(
                """UPDATE approval_chains SET status = 'approved',
                   completed_at = ?, current_step = ? WHERE id = ?""",
                (now, int(step["step_order"]), chain_id),
            )
            new_chain_status = "approved"
        else:
            c.execute(
                """UPDATE approval_chains SET current_step = ? WHERE id = ?""",
                (next_order, chain_id),
            )
            next_step_order = next_order
    c.commit()
    c.close()

    if next_step_order > 0:
        _notify_step_active(chain_id, next_step_order)

    return {
        "ok": True,
        "chain_id": chain_id,
        "step_order": int(step["step_order"]),
        "new_chain_status": new_chain_status,
        "next_step_order": next_step_order,
    }


# ─────────────────────────────────────────────────────────────
# 조회
# ─────────────────────────────────────────────────────────────


def my_pending_steps(approver_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """본인이 결재할 차례인 step list (chain.current_step == step.step_order, decision=pending)."""
    if not approver_id:
        return []
    c = _conn()
    rows = c.execute(
        """SELECT s.*, ch.name AS chain_name, ch.change_id, ch.status AS chain_status,
                  ch.current_step
           FROM approval_steps s
           JOIN approval_chains ch ON ch.id = s.chain_id
           WHERE s.approver_id = ?
             AND s.decision = 'pending'
             AND ch.status = 'pending'
             AND ch.current_step = s.step_order
           ORDER BY ch.created_at DESC LIMIT ?""",
        (approver_id, max(1, min(limit, 200))),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_chain_detail(chain_id: int) -> dict[str, Any] | None:
    c = _conn()
    chain = c.execute(
        "SELECT * FROM approval_chains WHERE id = ?", (chain_id,),
    ).fetchone()
    if chain is None:
        c.close()
        return None
    steps = c.execute(
        "SELECT * FROM approval_steps WHERE chain_id = ? ORDER BY step_order",
        (chain_id,),
    ).fetchall()
    c.close()
    return {**dict(chain), "steps": [dict(s) for s in steps]}
