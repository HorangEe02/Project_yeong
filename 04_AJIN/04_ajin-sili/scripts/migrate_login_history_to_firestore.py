"""I-3 — auth.db login_history 일회성 마이그레이션 → Firestore audit_logs.

사용:
  $ gcloud auth application-default login
  $ python scripts/migrate_login_history_to_firestore.py --dry-run --limit 10
  $ python scripts/migrate_login_history_to_firestore.py  # 실 실행

Idempotent: doc id = sha256(user_id|employee_id|timestamp)[:24] → 동일 row
재실행 시 .exists() 체크로 skip. Firestore batch 400건씩 commit.

전제:
  - Local 에서 실행 (Cloud Run 휘발성이라 의미 없음)
  - gcloud Application Default Credentials 가 ajin-cb 프로젝트에 권한 있음
  - Firestore audit_logs 컬렉션 + TTL(expires_at, 180d) 적용 완료
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ID = "ajin-cb"
COLLECTION = "audit_logs"
TTL_DAYS = 180


def _doc_id(user_id, employee_id: str, timestamp: str) -> str:
    """Deterministic id — 동일 SQLite row 재실행 시 충돌 → skip."""
    key = f"{user_id}|{employee_id}|{timestamp}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def _parse_timestamp(ts_str: str) -> datetime:
    """ISO format with Z 또는 timezone-naive SQLite default 처리."""
    if not ts_str:
        return datetime.now(timezone.utc)
    s = ts_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth-db", default="data/auth.db", help="SQLite auth.db 경로")
    parser.add_argument("--dry-run", action="store_true", help="실제 write 없이 카운트만")
    parser.add_argument("--limit", type=int, default=0, help="0 = 전체")
    parser.add_argument("--batch-size", type=int, default=400, help="Firestore batch commit 단위")
    args = parser.parse_args()

    db_path = Path(args.auth_db)
    if not db_path.exists():
        print(f"❌ auth.db not found: {db_path}", file=sys.stderr)
        return 1

    # Firebase Admin 초기화 (ADC 사용)
    import firebase_admin  # type: ignore
    from firebase_admin import firestore  # type: ignore
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT_ID})
    fs = firestore.client()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    sql = """
      SELECT lh.user_id, lh.employee_id, lh.action, lh.success,
             lh.ip_address, lh.user_agent, lh.timestamp,
             u.department, u.role_id
      FROM login_history lh
      LEFT JOIN users u ON lh.user_id = u.user_id
      ORDER BY lh.timestamp ASC
    """
    if args.limit:
        sql += f" LIMIT {args.limit}"

    rows = conn.execute(sql).fetchall()
    total = len(rows)
    print(f"📦 Found {total} rows in login_history "
          f"(dry-run={args.dry_run}, limit={args.limit or 'all'}).")

    written = skipped = errors = 0
    batch = fs.batch()
    batch_size = 0

    for i, r in enumerate(rows, 1):
        doc_id = _doc_id(r["user_id"], r["employee_id"], r["timestamp"])
        doc_ref = fs.collection(COLLECTION).document(doc_id)
        ts_dt = _parse_timestamp(r["timestamp"])

        # Idempotent check (dry-run 에서도 동작)
        try:
            if doc_ref.get().exists:
                skipped += 1
                continue
        except Exception as e:
            print(f"  ⚠ exists check 실패 ({doc_id}): {e}")
            errors += 1
            continue

        data = {
            "user_id": r["user_id"],
            "employee_id": r["employee_id"],
            "action": r["action"] or "login",
            "success": bool(r["success"]),
            "ip_address": r["ip_address"] or "",
            "user_agent": r["user_agent"] or "",
            "department": r["department"] or "",
            "role_level": 0,  # SQLite users 에 role_level 직접 없음 — role_id 만. 0 으로 보존.
            "timestamp": ts_dt,
            "expires_at": ts_dt + timedelta(days=TTL_DAYS),
            "_migrated_from": "auth.db.login_history",
        }

        if args.dry_run:
            written += 1
            if i <= 5:
                print(f"  [dry-run] would write {doc_id} — user={r['user_id']}, ts={r['timestamp']}")
            continue

        batch.set(doc_ref, data)
        batch_size += 1

        if batch_size >= args.batch_size:
            batch.commit()
            written += batch_size
            print(f"  ✓ flushed {written}/{total} ...")
            batch = fs.batch()
            batch_size = 0

    if batch_size and not args.dry_run:
        batch.commit()
        written += batch_size

    conn.close()
    print(f"\n✅ migration done — written: {written}, skipped: {skipped}, errors: {errors}")
    if args.dry_run:
        print("ℹ️  dry-run 종료. 실제 실행하려면 --dry-run 없이 재실행.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
