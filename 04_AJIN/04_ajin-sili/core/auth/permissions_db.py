"""v4.7 PR-E7 — Permission DB CRUD.

기존 코드 dict (COMPLIANCE_PERMISSIONS 등) → SQLite 영속.
v4.7: DB-first lookup, dict 는 first-run seed only.
v4.8+: dict 제거, DB 가 단일 source.

스키마
------
permissions
    key (PK), description, min_role, departments (JSON nullable),
    allow_same_division (int), min_position_level (int),
    created_at, updated_at, updated_by

permission_change_requests
    request_id (PK auto), permission_key (FK), requested_by,
    old_value (JSON), new_value (JSON),
    status, security_approver, executive_approver,
    requested_at, applied_at, reason

permission_audit
    id (PK auto), permission_key, actor, action,
    diff (JSON), ts

모든 timestamp 는 ISO 8601 UTC. JSON 컬럼 (departments / old_value /
new_value / diff) 은 ``json.dumps`` 직렬화.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PERMISSIONS_DB_PATH = (
    Path(__file__).parent.parent.parent / "data" / "permissions.db"
)


# ── 내부 유틸 ────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    """sqlite3 connect — row_factory + foreign_keys ON."""
    PERMISSIONS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PERMISSIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _dumps_departments(value: Any) -> str | None:
    """departments 컬럼 직렬화. None / set / list / tuple 지원."""
    if value is None:
        return None
    if isinstance(value, (set, frozenset)):
        return json.dumps(sorted(value), ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return json.dumps(sorted(set(value)), ensure_ascii=False)
    if isinstance(value, str):
        # 이미 JSON 문자열이라고 가정
        return value
    raise TypeError(f"departments must be None/set/list/str: {type(value)!r}")


def _loads_departments(raw: str | None) -> set[str] | None:
    if raw is None or raw == "":
        return None
    return set(json.loads(raw))


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """permissions row → public dict (departments → set)."""
    return {
        "key": row["key"],
        "description": row["description"],
        "min_role": row["min_role"],
        "departments": _loads_departments(row["departments"]),
        "allow_same_division": bool(row["allow_same_division"]),
        "min_position_level": int(row["min_position_level"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }


# ── 스키마 init ──────────────────────────────────────────────────────────────


def init_permissions_db() -> None:
    """3 테이블 init (멱등). 본 함수 호출은 backend/main.py startup 또는 별도 migration."""
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                key TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                min_role TEXT NOT NULL,
                departments TEXT,
                allow_same_division INTEGER DEFAULT 0,
                min_position_level INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS permission_change_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_key TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                old_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                status TEXT NOT NULL,
                security_approver TEXT,
                executive_approver TEXT,
                requested_at TEXT NOT NULL,
                applied_at TEXT,
                reason TEXT NOT NULL
                -- NOTE: FK 없음. 신규 권한 생성 요청 시 permission_key 가
                --       아직 permissions table 에 존재하지 않을 수 있음.
                --       executive_approve 시점에 upsert_permission 으로 실체화.
            );
            CREATE TABLE IF NOT EXISTS permission_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_key TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                diff TEXT NOT NULL,
                ts TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_perm_req_status
                ON permission_change_requests(status);
            CREATE INDEX IF NOT EXISTS idx_perm_audit_ts
                ON permission_audit(ts);
            """
        )
        conn.commit()
    finally:
        conn.close()


# ── permissions CRUD ────────────────────────────────────────────────────────


def get_permission(key: str) -> dict | None:
    """key 로 단일 permission 조회. 없으면 None."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM permissions WHERE key = ?", (key,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_permissions() -> list[dict]:
    """전체 permissions 목록 (key ASC)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM permissions ORDER BY key ASC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def upsert_permission(perm_dict: dict, actor: str) -> None:
    """permission INSERT OR UPDATE. permission_audit INSERT 자동.

    perm_dict 필수 키: key, description, min_role.
    선택 키: departments, allow_same_division, min_position_level.
    """
    key = perm_dict["key"]
    description = perm_dict["description"]
    min_role = perm_dict["min_role"]
    departments_raw = _dumps_departments(perm_dict.get("departments"))
    allow_same_division = int(bool(perm_dict.get("allow_same_division", False)))
    min_position_level = int(perm_dict.get("min_position_level", 0))
    now = _utcnow_iso()

    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT * FROM permissions WHERE key = ?", (key,)
        ).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO permissions
                       (key, description, min_role, departments,
                        allow_same_division, min_position_level,
                        created_at, updated_at, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    key, description, min_role, departments_raw,
                    allow_same_division, min_position_level,
                    now, now, actor,
                ),
            )
            diff = {
                "before": None,
                "after": {
                    "description": description,
                    "min_role": min_role,
                    "departments": _loads_departments(departments_raw),
                    "allow_same_division": bool(allow_same_division),
                    "min_position_level": min_position_level,
                },
            }
            action = "create"
        else:
            before = _row_to_dict(existing)
            conn.execute(
                """UPDATE permissions
                      SET description = ?, min_role = ?, departments = ?,
                          allow_same_division = ?, min_position_level = ?,
                          updated_at = ?, updated_by = ?
                    WHERE key = ?""",
                (
                    description, min_role, departments_raw,
                    allow_same_division, min_position_level,
                    now, actor, key,
                ),
            )
            diff = {
                "before": {
                    "description": before["description"],
                    "min_role": before["min_role"],
                    "departments": before["departments"],
                    "allow_same_division": before["allow_same_division"],
                    "min_position_level": before["min_position_level"],
                },
                "after": {
                    "description": description,
                    "min_role": min_role,
                    "departments": _loads_departments(departments_raw),
                    "allow_same_division": bool(allow_same_division),
                    "min_position_level": min_position_level,
                },
            }
            action = "update"

        conn.execute(
            """INSERT INTO permission_audit
                   (permission_key, actor, action, diff, ts)
               VALUES (?, ?, ?, ?, ?)""",
            (key, actor, action, _json_default_dumps(diff), now),
        )
        conn.commit()
    finally:
        conn.close()


def delete_permission(key: str, actor: str) -> bool:
    """permission DELETE. permission_audit INSERT 자동. 없으면 False."""
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT * FROM permissions WHERE key = ?", (key,)
        ).fetchone()
        if existing is None:
            return False

        before = _row_to_dict(existing)
        conn.execute("DELETE FROM permissions WHERE key = ?", (key,))
        conn.execute(
            """INSERT INTO permission_audit
                   (permission_key, actor, action, diff, ts)
               VALUES (?, ?, ?, ?, ?)""",
            (
                key, actor, "delete",
                _json_default_dumps({"before": {
                    "description": before["description"],
                    "min_role": before["min_role"],
                    "departments": before["departments"],
                    "allow_same_division": before["allow_same_division"],
                    "min_position_level": before["min_position_level"],
                }, "after": None}),
                _utcnow_iso(),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def _json_default_dumps(payload: Any) -> str:
    """set 포함 dict 도 직렬화."""

    def _default(o: Any):
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        raise TypeError(f"not JSON serializable: {type(o)!r}")

    return json.dumps(payload, ensure_ascii=False, default=_default)


# ── change requests CRUD ────────────────────────────────────────────────────


def insert_change_request(
    permission_key: str,
    requested_by: str,
    old_value: dict | None,
    new_value: dict,
    reason: str,
) -> int:
    """permission_change_requests INSERT. status='pending'. request_id 반환."""
    conn = _connect()
    try:
        now = _utcnow_iso()
        cur = conn.execute(
            """INSERT INTO permission_change_requests
                   (permission_key, requested_by, old_value, new_value,
                    status, requested_at, reason)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (
                permission_key,
                requested_by,
                _json_default_dumps(old_value),
                _json_default_dumps(new_value),
                now,
                reason,
            ),
        )
        request_id = int(cur.lastrowid)
        # 별도 audit 도 기록 — workflow transition 추적
        conn.execute(
            """INSERT INTO permission_audit
                   (permission_key, actor, action, diff, ts)
               VALUES (?, ?, 'request_create', ?, ?)""",
            (
                permission_key, requested_by,
                _json_default_dumps({
                    "request_id": request_id,
                    "before": old_value, "after": new_value, "reason": reason,
                }),
                now,
            ),
        )
        conn.commit()
        return request_id
    finally:
        conn.close()


def get_change_request(request_id: int) -> dict | None:
    """request_id 로 단일 change request 조회."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM permission_change_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return _change_request_row_to_dict(row) if row else None
    finally:
        conn.close()


def list_change_requests(status_filter: str | None = None) -> list[dict]:
    """status filter (None 이면 전체). requested_at DESC."""
    conn = _connect()
    try:
        if status_filter:
            rows = conn.execute(
                """SELECT * FROM permission_change_requests
                    WHERE status = ?
                    ORDER BY requested_at DESC""",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM permission_change_requests
                    ORDER BY requested_at DESC"""
            ).fetchall()
        return [_change_request_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_change_request_status(
    request_id: int,
    new_status: str,
    *,
    security_approver: str | None = None,
    executive_approver: str | None = None,
    applied_at: str | None = None,
) -> dict:
    """change request status 전이. 변경된 row 반환.

    transition 은 호출자 (permission_workflow) 가 검증.
    """
    conn = _connect()
    try:
        sets: list[str] = ["status = ?"]
        params: list[Any] = [new_status]
        if security_approver is not None:
            sets.append("security_approver = ?")
            params.append(security_approver)
        if executive_approver is not None:
            sets.append("executive_approver = ?")
            params.append(executive_approver)
        if applied_at is not None:
            sets.append("applied_at = ?")
            params.append(applied_at)
        params.append(request_id)
        conn.execute(
            f"UPDATE permission_change_requests SET {', '.join(sets)} "
            "WHERE request_id = ?",
            params,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM permission_change_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return _change_request_row_to_dict(row) if row else {}
    finally:
        conn.close()


def _change_request_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "request_id": row["request_id"],
        "permission_key": row["permission_key"],
        "requested_by": row["requested_by"],
        "old_value": json.loads(row["old_value"]) if row["old_value"] else None,
        "new_value": json.loads(row["new_value"]) if row["new_value"] else None,
        "status": row["status"],
        "security_approver": row["security_approver"],
        "executive_approver": row["executive_approver"],
        "requested_at": row["requested_at"],
        "applied_at": row["applied_at"],
        "reason": row["reason"],
    }


# ── audit CRUD (직접 호출용 — workflow 에서 transition 기록) ────────────────


def insert_audit(
    permission_key: str, actor: str, action: str, diff: dict | None = None
) -> None:
    """permission_audit 단일 INSERT. workflow transition / 임의 이벤트 기록용."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO permission_audit
                   (permission_key, actor, action, diff, ts)
               VALUES (?, ?, ?, ?, ?)""",
            (
                permission_key, actor, action,
                _json_default_dumps(diff or {}),
                _utcnow_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_audit(
    permission_key: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """permission_audit 조회. ts DESC. limit 제한."""
    conn = _connect()
    try:
        if permission_key:
            rows = conn.execute(
                """SELECT * FROM permission_audit
                    WHERE permission_key = ?
                    ORDER BY ts DESC LIMIT ?""",
                (permission_key, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM permission_audit
                    ORDER BY ts DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "permission_key": r["permission_key"],
                "actor": r["actor"],
                "action": r["action"],
                "diff": json.loads(r["diff"]) if r["diff"] else {},
                "ts": r["ts"],
            }
            for r in rows
        ]
    finally:
        conn.close()
