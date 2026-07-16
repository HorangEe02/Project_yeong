#!/usr/bin/env python3
"""Supabase Postgres 직접 연결 검증 (DATABASE_URL, psycopg).

사용법:
  1) local-worker/.env 의 DATABASE_URL 에서 [YOUR-PASSWORD] 를 본인 DB 비밀번호로 교체
     (특수문자는 percent-encode: ! -> %21 등)
  2) ./.venv/bin/python scripts/verify_supabase_db.py

성공하면 public 스키마 테이블 목록과 주요 행 수를 출력한다.
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# .env 로드 (stdlib)
env_file = BASE / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

url = os.getenv("DATABASE_URL", "").strip()
if not url:
    sys.exit("DATABASE_URL 이 .env 에 없습니다.")
if "[YOUR-PASSWORD]" in url or "<DB_PW>" in url:
    sys.exit("DATABASE_URL 의 [YOUR-PASSWORD] 를 본인 DB 비밀번호로 먼저 교체하세요 "
             "(특수문자는 percent-encode). 그 값은 .env 에만 두고 커밋하지 마세요.")

try:
    import psycopg
except ImportError:
    sys.exit("psycopg 미설치: ./.venv/bin/pip install 'psycopg[binary]'")

try:
    with psycopg.connect(url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database(), current_user, version()")
            db, user, ver = cur.fetchone()
            print(f"✅ 연결 성공: db={db} user={user}")
            print(f"   {ver.split(',')[0]}")
            cur.execute(
                "select table_name from information_schema.tables "
                "where table_schema='public' order by table_name")
            tables = [r[0] for r in cur.fetchall()]
            print(f"   public 테이블 {len(tables)}개: {', '.join(tables)}")
            for t in ("profiles", "meetings", "transcript_segments"):
                if t in tables:
                    cur.execute(f"select count(*) from {t}")
                    print(f"   - {t}: {cur.fetchone()[0]} rows")
    print("연결 검증 완료. (worker DB 백엔드를 Postgres 로 전환하는 것은 별도 구현 단계)")
except Exception as e:  # noqa: BLE001
    sys.exit(f"❌ 연결 실패: {e}\n"
             "- 비밀번호/percent-encoding 확인\n"
             "- Shared Pooler host/port(6543) 확인\n"
             "- 프로젝트가 ACTIVE 상태인지 확인")
