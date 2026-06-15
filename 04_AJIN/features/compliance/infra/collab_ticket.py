"""P3 D9 — 협업 티켓 (다중 부서 영향 변경의 책임자 자동 매핑).

영향 부서가 2개 이상이면:
  1. 각 부서의 팀장+ 책임자를 employees.db 또는 dept_owners.json 에서 추출
  2. collab_tickets 테이블에 row 적재
  3. 책임자에게 Slack DM (이미 있는 notify_slack 활용)
  4. (옵션) Jira/Asana webhook 발행
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# dept_owners.json — 명시 매핑 우선 (없으면 employees.db 자동 추출)
DEPT_OWNERS_PATH = Path(__file__).parent.parent.parent / "data" / "dept_owners.json"


# ─────────────────────────────────────────────────────────────
# 부서 책임자 매칭
# ─────────────────────────────────────────────────────────────


def find_dept_owners(departments: list[str]) -> dict[str, dict[str, str]]:
    """부서명 list → {dept: {employee_id, name, email, position}}.

    1차: data/dept_owners.json (명시 매핑)
    2차: employees.db 의 position_level >= 5 (팀장+) 자동 추출
    """
    owners: dict[str, dict[str, str]] = {}

    # 1차 — JSON 명시 매핑
    if DEPT_OWNERS_PATH.exists():
        try:
            data = json.loads(DEPT_OWNERS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for d in departments:
                    if d in data and isinstance(data[d], dict):
                        owners[d] = data[d]
        except json.JSONDecodeError:
            pass

    # 2차 — employees.db 자동 추출 (위에서 못 잡은 부서)
    missing = [d for d in departments if d not in owners]
    if missing:
        try:
            from features.search.employee.database import EmployeeDatabase
            db = EmployeeDatabase()
            try:
                # position_level >= 5 (팀장 이상). 우선순위: is_team_leader=1
                conn = db.get_connection() if hasattr(db, "get_connection") else None
                if conn is None:
                    # EmployeeDatabase 내부 세부 API 미지원 시 직접 sqlite
                    import sqlite3 as _sqlite
                    conn = _sqlite.connect(str(db.db_path) if hasattr(db, "db_path") else "data/employees.db")
                    conn.row_factory = _sqlite.Row
                for d in missing:
                    rows = conn.execute(
                        """SELECT employee_id, name, email, position
                           FROM employees
                           WHERE department = ?
                             AND (position_level >= 5 OR is_team_leader = 1)
                             AND is_active = 1
                           ORDER BY is_team_leader DESC, position_level DESC LIMIT 1""",
                        (d,),
                    ).fetchall()
                    if rows:
                        r = rows[0]
                        owners[d] = {
                            "employee_id": r["employee_id"],
                            "name": r["name"],
                            "email": r["email"] or "",
                            "position": r["position"] or "",
                        }
            finally:
                if conn is not None:
                    conn.close()
        except Exception as e:
            logger.debug("employees.db 자동 책임자 추출 실패: %s", e)

    return owners


# ─────────────────────────────────────────────────────────────
# 티켓 생성
# ─────────────────────────────────────────────────────────────


def create_ticket(change: dict[str, Any], change_id: int) -> dict[str, Any]:
    """변경 → 협업 티켓 자동 생성 + Slack DM + (옵션) 외부 webhook.

    부서 1개 이하면 티켓 생성 안 함.

    Returns:
        {ok, ticket_id, departments, owners, slack_sent, external_url, error?}
    """
    departments = change.get("affected_departments") or []
    if isinstance(departments, str):
        try:
            departments = json.loads(departments)
        except json.JSONDecodeError:
            departments = []

    if len(departments) < 2:
        return {
            "ok": False,
            "error": "협업 티켓은 다중 부서(2개 이상) 영향 변경에만 생성됩니다",
            "ticket_id": 0,
        }

    owners = find_dept_owners(departments)
    owner_ids = [o.get("employee_id", "") for o in owners.values() if o.get("employee_id")]

    title = (
        change.get("item_title")
        or change.get("summary_ko")
        or "(제목 없음)"
    )

    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO collab_tickets
           (change_id, title, departments, owners, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            change_id,
            title[:200],
            json.dumps(departments, ensure_ascii=False),
            json.dumps(owner_ids, ensure_ascii=False),
            "created",
            now,
        ),
    )
    ticket_id = int(cur.lastrowid)
    conn.commit()
    conn.close()

    # Slack DM — notify_slack 의 webhook 재사용
    slack_sent = False
    try:
        from features.compliance.alerts.notify_slack import route as slack_route
        slack_sent = slack_route({
            "grade": change.get("grade", "MEDIUM"),
            "item_title": f"🤝 [협업 티켓 #{ticket_id}] {title}",
            "summary_ko": (
                f"다중 부서 영향: {', '.join(departments[:5])}.\n"
                f"책임자 자동 매핑 — {', '.join([o.get('name') or '?' for o in owners.values()])}"
            ),
            "change_type": "collab",
            "affected_departments": departments,
        }, change_id=change_id)
    except Exception as e:
        logger.warning("Slack 협업 티켓 발송 실패 ticket_id=%s: %s", ticket_id, e)

    # 외부 webhook — Jira/Asana (선택)
    external_url = ""
    try:
        external_url = _send_external_webhook(ticket_id, title, departments, change_id)
        if external_url:
            conn = sqlite3.connect(CHANGE_DB_PATH)
            conn.execute(
                "UPDATE collab_tickets SET external_url = ? WHERE id = ?",
                (external_url, ticket_id),
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.debug("외부 webhook 미설정/실패: %s", e)

    # P5 §6 — Jira REST API 양방향 sync (자격 미설정 시 graceful skip)
    external_id = ""
    try:
        from features.compliance.infra import jira_sync
        if jira_sync.jira_enabled():
            description = (
                f"[AJIN Compliance] 변경 #{change_id}\n"
                f"부서: {', '.join(departments[:5])}\n"
                f"등급: {change.get('grade', 'MEDIUM')}\n"
                f"요약: {change.get('summary_ko', '')[:300]}"
            )
            jira_out = jira_sync.create_issue(title=title, description=description)
            if jira_out.get("ok"):
                external_id = jira_out["issue_key"]
                external_url = jira_out["issue_url"]
                conn = sqlite3.connect(CHANGE_DB_PATH)
                conn.execute(
                    """UPDATE collab_tickets
                       SET external_id = ?, external_url = ?, jira_last_sync_at = ?
                       WHERE id = ?""",
                    (external_id, external_url, datetime.now().isoformat(), ticket_id),
                )
                conn.commit()
                conn.close()
            else:
                logger.warning(
                    "Jira issue 생성 실패 ticket_id=%s reason=%s",
                    ticket_id, jira_out.get("error"),
                )
    except Exception as e:
        logger.warning("Jira sync 호출 예외 ticket_id=%s: %s", ticket_id, type(e).__name__)

    return {
        "ok": True,
        "ticket_id": ticket_id,
        "departments": departments,
        "owners": list(owners.values()),
        "slack_sent": slack_sent,
        "external_url": external_url,
        "external_id": external_id,
    }


def _send_external_webhook(ticket_id: int, title: str, departments: list[str],
                            change_id: int) -> str:
    """Jira/Asana webhook 발행. URL env 미설정 시 빈 string 반환."""
    import os
    import httpx

    jira_url = (os.environ.get("JIRA_WEBHOOK_URL") or "").strip()
    asana_url = (os.environ.get("ASANA_WEBHOOK_URL") or "").strip()

    target = jira_url or asana_url
    if not target:
        return ""

    payload = {
        "ticket_id": ticket_id,
        "title": title,
        "departments": departments,
        "change_id": change_id,
        "source": "AJIN_compliance",
    }
    try:
        r = httpx.post(target, json=payload, timeout=5.0)
        r.raise_for_status()
        # webhook 응답에서 외부 URL 추출 (provider 마다 다름 — 단순 graceful)
        try:
            body = r.json()
            return str(body.get("url") or body.get("self") or "")
        except Exception:
            return target  # webhook URL 자체를 placeholder 로
    except httpx.HTTPError as e:
        logger.warning("외부 webhook %s 실패: %s", target, e)
        return ""


# ─────────────────────────────────────────────────────────────
# 조회 + 상태 전환
# ─────────────────────────────────────────────────────────────


def list_tickets(status: str | None = None,
                  department: str | None = None,
                  limit: int = 50) -> list[dict[str, Any]]:
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row

    where: list[str] = []
    params: list[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if department:
        where.append("departments LIKE ?")
        params.append(f"%{department}%")
    where_sql = " WHERE " + " AND ".join(where) if where else ""

    rows = conn.execute(
        f"""SELECT * FROM collab_tickets{where_sql}
           ORDER BY created_at DESC LIMIT ?""",
        [*params, max(1, min(limit, 200))],
    ).fetchall()
    conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["departments"] = json.loads(d.get("departments") or "[]")
        except json.JSONDecodeError:
            d["departments"] = []
        try:
            d["owners"] = json.loads(d.get("owners") or "[]")
        except json.JSONDecodeError:
            d["owners"] = []
        out.append(d)
    return out


_VALID_TICKET_STATUS = {"created", "acknowledged", "in_progress", "resolved"}


def ensure_kanban_columns() -> None:
    """D5 — collab_tickets 에 assignee/deadline/progress_pct 컬럼 보강 (idempotent)."""
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(collab_tickets)").fetchall()}
        if "assignee" not in cols:
            conn.execute("ALTER TABLE collab_tickets ADD COLUMN assignee TEXT DEFAULT ''")
        if "deadline" not in cols:
            conn.execute("ALTER TABLE collab_tickets ADD COLUMN deadline TEXT DEFAULT ''")
        if "progress_pct" not in cols:
            conn.execute("ALTER TABLE collab_tickets ADD COLUMN progress_pct INTEGER DEFAULT 0")
        conn.commit()
    finally:
        conn.close()


def patch_ticket(ticket_id: int, patch: dict[str, Any]) -> bool:
    """D5 — assignee/deadline/progress_pct 패치."""
    ensure_kanban_columns()
    allowed = {"assignee", "deadline", "progress_pct"}
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        return False

    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    try:
        sets = ", ".join(f"{k} = ?" for k in fields)
        cur = conn.execute(
            f"UPDATE collab_tickets SET {sets} WHERE id = ?",
            [*fields.values(), ticket_id],
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_ticket_status(ticket_id: int, new_status: str, user_id: str = "") -> bool:
    if new_status not in _VALID_TICKET_STATUS:
        return False

    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    row = conn.execute(
        "SELECT status FROM collab_tickets WHERE id = ?", (ticket_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return False

    resolved_at = datetime.now().isoformat() if new_status == "resolved" else ""
    conn.execute(
        "UPDATE collab_tickets SET status = ?, resolved_at = ? WHERE id = ?",
        (new_status, resolved_at, ticket_id),
    )
    conn.commit()
    conn.close()
    return True
