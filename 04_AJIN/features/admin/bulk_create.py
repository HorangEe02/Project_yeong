"""features/admin/bulk_create.py — v4.8 F 트랙.

사용자 CSV 일괄 생성 / 권한 일괄 변경 모듈.
v4.3 inspection_etl 패턴(IngestResult / IngestErrorRow) 을 재사용한다.

CSV 컬럼: username,email,name,department,position,role_level,phone
- username : 자연키. 중복 시 SKIP (단, email/department/position 등 컬럼이 다르면 UPDATE).
- role_level : 1~5 정수.
- department : core/auth/department_config.DEPARTMENT_CATEGORIES 에 존재해야 함.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Iterable

from backend.schemas.inspection_etl import IngestErrorRow, IngestResult
from core.data_lineage import lineage_values

logger = logging.getLogger(__name__)


CSV_COLUMNS = ["username", "email", "name", "department", "position", "role_level", "phone"]


_ROLE_LEVEL_TO_NAME = {
    1: "EMPLOYEE",
    2: "MANAGER",
    3: "TEAM_LEAD",
    4: "HR_ADMIN",
    5: "SYS_ADMIN",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_row(raw: dict) -> dict:
    """헤더 대소문자 / 공백을 정규화한다."""
    out: dict[str, str] = {}
    for k, v in raw.items():
        if k is None:
            continue
        key = str(k).strip().lower()
        val = "" if v is None else str(v).strip()
        out[key] = val
    return out


def _validate_row(row: dict, valid_depts: set[str]) -> tuple[bool, str]:
    """단일 행 유효성 검사. (ok, msg)."""
    for col in ("username", "email", "department", "position", "role_level"):
        if not row.get(col):
            return False, f"필수 컬럼 누락: {col}"

    try:
        rl = int(row["role_level"])
    except (TypeError, ValueError):
        return False, f"role_level 정수 아님: {row['role_level']!r}"

    if rl < 1 or rl > 5:
        return False, f"role_level 범위 위반 (1~5): {rl}"

    if "@" not in row["email"]:
        return False, f"이메일 형식 오류: {row['email']!r}"

    if row["department"] not in valid_depts:
        return False, f"유효하지 않은 부서: {row['department']!r}"

    return True, ""


def parse_csv(content: bytes | str) -> list[dict]:
    """CSV bytes / str → 정규화된 dict 리스트."""
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content
    reader = csv.DictReader(io.StringIO(text))
    out: list[dict] = []
    for raw in reader:
        out.append(_normalize_row(raw))
    return out


def ingest_users_csv(
    content: bytes | str,
    *,
    dry_run: bool = True,
    actor_employee_id: str = "",
) -> IngestResult:
    """CSV 본문을 받아 사용자 일괄 생성/업데이트.

    dry_run=True: validate only, DB write 없음.
    """
    started_at = _now_iso()

    from core.auth.department_config import (
        DEPARTMENT_CATEGORIES,
        generate_employee_id,
        get_dept_prefix,
    )
    from core.auth.password import generate_initial_password, hash_password

    valid_depts: set[str] = set()
    for depts in DEPARTMENT_CATEGORIES.values():
        valid_depts.update(depts.keys())

    try:
        rows = parse_csv(content)
    except Exception as e:  # noqa: BLE001
        return IngestResult(
            rows_total=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            rows_error=1,
            dry_run=dry_run,
            source="csv_upload",
            started_at=started_at,
            finished_at=_now_iso(),
            error_payload=[
                IngestErrorRow(
                    row_index=0,
                    error_code="parse_error",
                    error_msg=f"CSV 파싱 실패: {e}",
                ),
            ],
        )

    inserted = updated = skipped = errored = 0
    errors: list[IngestErrorRow] = []

    if dry_run:
        for idx, row in enumerate(rows, start=1):
            ok, msg = _validate_row(row, valid_depts)
            if not ok:
                errored += 1
                errors.append(
                    IngestErrorRow(
                        row_index=idx,
                        error_code="validation",
                        error_msg=msg,
                        raw_payload=row,
                    ),
                )
        return IngestResult(
            rows_total=len(rows),
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            rows_error=errored,
            dry_run=True,
            source="csv_upload",
            started_at=started_at,
            finished_at=_now_iso(),
            error_payload=errors,
        )

    # ── 실제 INSERT/UPDATE 단계 ─────────────────────────────────
    from core.auth.database import get_auth_db

    conn = get_auth_db()
    lineage = lineage_values(
        "real",
        "bulk_csv",
        f"bulk_csv:{actor_employee_id or 'unknown'}",
    )

    role_by_level: dict[int, dict] = {}
    for level, name in _ROLE_LEVEL_TO_NAME.items():
        rrow = conn.execute(
            "SELECT role_id, role_level, role_name FROM roles WHERE role_name = ?",
            (name,),
        ).fetchone()
        if rrow:
            role_by_level[level] = {
                "role_id": rrow["role_id"],
                "role_level": rrow["role_level"],
            }

    for idx, row in enumerate(rows, start=1):
        ok, msg = _validate_row(row, valid_depts)
        if not ok:
            errored += 1
            errors.append(
                IngestErrorRow(
                    row_index=idx,
                    error_code="validation",
                    error_msg=msg,
                    raw_payload=row,
                ),
            )
            continue

        rl = int(row["role_level"])
        role_meta = role_by_level.get(rl)
        if not role_meta:
            errored += 1
            errors.append(
                IngestErrorRow(
                    row_index=idx,
                    error_code="role_lookup",
                    error_msg=f"roles 테이블에 role_level={rl} 매핑 없음",
                    raw_payload=row,
                ),
            )
            continue

        existing = conn.execute(
            "SELECT user_id, employee_id, email, department, position, role_id FROM users WHERE username = ?",
            (row["username"],),
        ).fetchone()

        if existing is not None:
            # 자연키 충돌 — 다른 컬럼이 다르면 UPDATE, 동일하면 SKIP.
            differs = (
                (existing["email"] or "") != row["email"]
                or (existing["department"] or "") != row["department"]
                or (existing["position"] or "") != row["position"]
                or int(existing["role_id"] or 0) != int(role_meta["role_id"])
            )
            if differs:
                try:
                    conn.execute(
                        """UPDATE users
                              SET email = ?, department = ?, position = ?, phone = ?,
                                  role_id = ?, updated_at = datetime('now'),
                                  data_class = ?, source_system = ?,
                                  source_label = ?, source_updated_at = ?
                            WHERE user_id = ?""",
                        (
                            row["email"],
                            row["department"],
                            row["position"],
                            row.get("phone", ""),
                            role_meta["role_id"],
                            lineage["data_class"],
                            lineage["source_system"],
                            lineage["source_label"],
                            lineage["source_updated_at"],
                            existing["user_id"],
                        ),
                    )
                    updated += 1
                except Exception as e:  # noqa: BLE001
                    errored += 1
                    errors.append(
                        IngestErrorRow(
                            row_index=idx,
                            error_code="update_error",
                            error_msg=f"UPDATE 실패: {e}",
                            raw_payload=row,
                        ),
                    )
            else:
                skipped += 1
            continue

        # 신규 INSERT.
        prefix = get_dept_prefix(row["department"])
        existing_for_prefix = conn.execute(
            "SELECT employee_id FROM users WHERE employee_id LIKE ?",
            (f"{prefix}-%",),
        ).fetchall()
        max_n = 0
        for r in existing_for_prefix:
            try:
                tail = (r["employee_id"] or "").split("-", 1)[1]
                max_n = max(max_n, int(tail))
            except (IndexError, ValueError):
                continue
        seq = max_n + 1
        emp_id = generate_employee_id(row["department"], seq)
        initial_pw = generate_initial_password(emp_id)
        pw_hash = hash_password(initial_pw)

        try:
            conn.execute(
                """INSERT INTO users
                     (employee_id, username, password_hash, role_id, is_active, must_change_pw,
                      email, phone, department, position, hire_date,
                      data_class, source_system, source_label, source_updated_at)
                   VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?, ?, '', ?, ?, ?, ?)""",
                (
                    emp_id,
                    row["username"],
                    pw_hash,
                    role_meta["role_id"],
                    row["email"],
                    row.get("phone", ""),
                    row["department"],
                    row["position"],
                    lineage["data_class"],
                    lineage["source_system"],
                    lineage["source_label"],
                    lineage["source_updated_at"],
                ),
            )
            inserted += 1
        except Exception as e:  # noqa: BLE001
            errored += 1
            errors.append(
                IngestErrorRow(
                    row_index=idx,
                    error_code="insert_error",
                    error_msg=f"INSERT 실패: {e}",
                    raw_payload=row,
                ),
            )

    conn.commit()
    conn.close()

    logger.info(
        "[bulk_create] actor=%s total=%d inserted=%d updated=%d skipped=%d error=%d",
        actor_employee_id,
        len(rows),
        inserted,
        updated,
        skipped,
        errored,
    )

    return IngestResult(
        rows_total=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        rows_error=errored,
        dry_run=False,
        source="csv_upload",
        started_at=started_at,
        finished_at=_now_iso(),
        error_payload=errors,
    )


def apply_bulk_role_change(
    employee_ids: Iterable[str],
    target_role_level: int,
    *,
    reason: str = "",
    actor_employee_id: str = "",
) -> dict:
    """선택된 employee_id 집합에 대해 role_level 일괄 변경.

    audit log 는 호출 측(라우터)에서 log_api_access 로 1건 + 본 함수가
    각 user_id 마다 1건씩 추가 기록한다.
    """
    from backend.auth_middleware import log_api_access
    from core.auth.database import get_auth_db

    if target_role_level < 1 or target_role_level > 5:
        raise ValueError(f"target_role_level 범위 위반 (1~5): {target_role_level}")

    role_name = _ROLE_LEVEL_TO_NAME[target_role_level]

    conn = get_auth_db()
    role_row = conn.execute(
        "SELECT role_id FROM roles WHERE role_name = ?",
        (role_name,),
    ).fetchone()
    if not role_row:
        conn.close()
        raise RuntimeError(f"roles 테이블에 {role_name} 없음")
    new_role_id = role_row["role_id"]

    changed: list[dict] = []
    not_found: list[str] = []
    for eid in employee_ids:
        before = conn.execute(
            """SELECT u.user_id, u.username, u.role_id, r.role_name, r.role_level
                 FROM users u JOIN roles r ON u.role_id=r.role_id
                WHERE u.employee_id = ?""",
            (eid,),
        ).fetchone()
        if not before:
            not_found.append(eid)
            continue
        conn.execute(
            "UPDATE users SET role_id = ?, updated_at = datetime('now') WHERE user_id = ?",
            (new_role_id, before["user_id"]),
        )
        changed.append({
            "employee_id": eid,
            "username": before["username"],
            "before_role": before["role_name"],
            "before_level": before["role_level"],
            "after_role": role_name,
            "after_level": target_role_level,
        })

    conn.commit()
    conn.close()

    for entry in changed:
        log_api_access(
            endpoint="/api/admin/users/bulk-role",
            method="POST",
            user=None,
            detail=(
                f"actor={actor_employee_id} target={entry['employee_id']} "
                f"{entry['before_role']}(L{entry['before_level']}) → "
                f"{entry['after_role']}(L{entry['after_level']}) reason={reason[:80]}"
            ),
        )

    return {
        "changed_count": len(changed),
        "not_found": not_found,
        "changes": changed,
        "target_role": role_name,
        "target_role_level": target_role_level,
    }
