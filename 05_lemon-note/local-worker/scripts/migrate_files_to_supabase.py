#!/usr/bin/env python3
"""기존 로컬 파일(음성·내보내기)을 Supabase Storage 로 이전하고 DB의 storage_path 를 갱신한다.

  ./.venv/bin/python scripts/migrate_files_to_supabase.py            # dry-run(기본)
  ./.venv/bin/python scripts/migrate_files_to_supabase.py --apply    # 실제 이전
  ./.venv/bin/python scripts/migrate_files_to_supabase.py --self-check

DB 는 DB_BACKEND(sqlite|postgres) 설정을 그대로 따른다. 업로드 key 는 신규 업로드와 동일 규칙이라
이전 후에는 STORAGE_PROVIDER=supabase 로 바로 읽힌다. 로컬 원본 파일은 지우지 않는다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db                                  # noqa: E402
from app.providers.storage import SupabaseStorage   # noqa: E402

APPLY = "--apply" in sys.argv

# (라벨, 조회 SQL, 갱신 테이블, key 만드는 함수)
JOBS = [
    ("음성", "SELECT r.id, r.storage_path, r.meeting_id, m.user_id "
             "FROM recording_files r JOIN meetings m ON m.id=r.meeting_id",
     "recording_files",
     lambda sb, r: sb._key(r["user_id"], r["meeting_id"], os.path.basename(r["storage_path"]))),
    ("내보내기", "SELECT e.id, e.storage_path, e.format, e.meeting_id, m.user_id "
                 "FROM exports e JOIN meetings m ON m.id=e.meeting_id",
     "exports",
     lambda sb, r: sb._key(r["user_id"], r["meeting_id"], "exports",
                           f"{r['id']}.{r['format']}")),
]


def main() -> int:
    sb = SupabaseStorage()
    conn = db.connect()
    moved = skipped = missing = 0
    try:
        for label, sql, table, mkkey in JOBS:
            for r in conn.execute(sql).fetchall():
                path = r["storage_path"]
                if not path or not os.path.isabs(str(path)):
                    skipped += 1                       # 이미 이전됨(=object key)
                    continue
                if not os.path.exists(path):
                    print(f"  [{label}] 원본 없음: {path}")
                    missing += 1
                    continue
                key = mkkey(sb, r)
                print(f"  [{label}] {os.path.basename(path)} → {key}")
                if APPLY:
                    with open(path, "rb") as f:
                        sb._upload(key, f.read(), "application/octet-stream")
                    conn.execute(f"UPDATE {table} SET storage_path=? WHERE id=?",
                                 (key, r["id"]))
                moved += 1
            if APPLY:
                conn.commit()
    finally:
        conn.close()

    print(f"\n{'이전 완료' if APPLY else 'DRY-RUN'}: 대상 {moved} · 이미이전 {skipped} · 원본없음 {missing}")
    if not APPLY and moved:
        print("실제 이전하려면 --apply 를 붙여 다시 실행하세요.")
    if APPLY and moved:
        print("이제 STORAGE_PROVIDER=supabase 로 실행하면 이전된 파일을 읽습니다.")
    return 0


def self_check() -> int:
    """네트워크 없이 key 규칙·idempotency 판정만 검증."""
    sb = SupabaseStorage.__new__(SupabaseStorage)      # __init__(자격증명) 우회
    u, m = "00000000-0000-0000-0000-000000000001", "abc"
    assert sb._key(u, m, "original.webm") == f"users/{u}/meetings/{m}/original.webm"
    assert sb._key(u, m, "exports", "e1.md") == f"users/{u}/meetings/{m}/exports/e1.md"
    # 절대경로 = 로컬(이전 대상), 상대 key = 이미 이전됨(건너뜀)
    assert os.path.isabs("/data/users/u/meetings/m/original.webm")
    assert not os.path.isabs(f"users/{u}/meetings/{m}/original.webm")
    print("self-check OK")
    return 0


if __name__ == "__main__":
    sys.exit(self_check() if "--self-check" in sys.argv else main())
