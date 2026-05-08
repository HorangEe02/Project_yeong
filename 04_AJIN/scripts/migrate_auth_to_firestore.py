"""auth.db (SQLite) → Firestore 마이그레이션 (1회성).

매핑:
  roles 테이블 → auth_roles/{role_name} 컬렉션
  users 테이블 → auth_users/{employee_id} 컬렉션 (password_hash 그대로 보존)

전제: gcloud auth application-default login + Firestore API enabled.

실행: python scripts/migrate_auth_to_firestore.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
AUTH_DB = PROJECT_ROOT / "data" / "auth.db"


def export_sqlite_rows() -> tuple[list[dict], list[dict]]:
    """auth.db 에서 roles/users 데이터를 dict 리스트로 export."""
    conn = sqlite3.connect(str(AUTH_DB))
    conn.row_factory = sqlite3.Row

    roles = [dict(r) for r in conn.execute(
        "SELECT role_id, role_name, role_level, description FROM roles"
    ).fetchall()]

    users = [dict(r) for r in conn.execute(
        "SELECT user_id, employee_id, username, password_hash, role_id, is_active, "
        "must_change_pw, failed_attempts, locked_until, last_login, "
        "created_at, updated_at, email, phone, department, position, hire_date "
        "FROM users"
    ).fetchall()]

    conn.close()
    return roles, users


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Firestore 쓰기 없이 통계만")
    parser.add_argument("--project", default="ajin-cb")
    args = parser.parse_args()

    roles, users = export_sqlite_rows()
    print(f"📦 export 완료: roles={len(roles)}건, users={len(users)}건")

    if args.dry_run:
        print("--dry-run: Firestore 쓰기 스킵")
        return

    from google.cloud import firestore  # type: ignore

    db = firestore.Client(project=args.project)

    # role_id → role_name 매핑
    role_id_to_name = {r["role_id"]: r["role_name"] for r in roles}

    # auth_roles 컬렉션
    print(f"🔥 auth_roles 쓰기 중...")
    role_batch = db.batch()
    for r in roles:
        ref = db.collection("auth_roles").document(r["role_name"])
        role_batch.set(ref, {
            "role_id": r["role_id"],
            "role_name": r["role_name"],
            "role_level": r["role_level"],
            "description": r.get("description") or "",
        })
    role_batch.commit()
    print(f"  ✓ {len(roles)} roles")

    # auth_users 컬렉션 (employee_id 가 doc id)
    print(f"🔥 auth_users 쓰기 중...")
    written = 0
    user_batch = db.batch()
    BATCH_LIMIT = 400  # Firestore batch 한도 500

    for u in users:
        ref = db.collection("auth_users").document(u["employee_id"])
        doc = {
            "employee_id": u["employee_id"],
            "username": u["username"],
            "password_hash": u["password_hash"],
            "role_name": role_id_to_name.get(u["role_id"], "EMPLOYEE"),
            "role_id": u["role_id"],
            "is_active": bool(u.get("is_active", 1)),
            "must_change_pw": bool(u.get("must_change_pw", 0)),
            "failed_attempts": int(u.get("failed_attempts") or 0),
            "locked_until": u.get("locked_until") or None,
            "last_login": u.get("last_login") or None,
            "created_at": u.get("created_at") or "",
            "updated_at": u.get("updated_at") or "",
            "email": u.get("email") or "",
            "phone": u.get("phone") or "",
            "department": u.get("department") or "",
            "position": u.get("position") or "",
            "hire_date": u.get("hire_date") or "",
        }
        user_batch.set(ref, doc)
        written += 1
        if written % BATCH_LIMIT == 0:
            user_batch.commit()
            user_batch = db.batch()

    if written % BATCH_LIMIT != 0:
        user_batch.commit()
    print(f"  ✓ {written} users")

    # 검증: admin doc 다시 읽어보기
    snap = db.collection("auth_users").document("admin").get()
    if snap.exists:
        d = snap.to_dict()
        print(f"\n검증 — admin doc:")
        print(f"  username={d.get('username')} role={d.get('role_name')}({d.get('role_id')}) lv={d.get('role_id')}")
        print(f"  password_hash 길이={len(d.get('password_hash',''))} (bcrypt OK)")
    else:
        print("⚠ admin doc 못 찾음")
        sys.exit(1)


if __name__ == "__main__":
    main()
