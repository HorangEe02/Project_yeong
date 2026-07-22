"""Vercel 서버리스 진입점 (무료 티어).

로컬 모델(faster-whisper/Ollama)은 서버리스에서 못 돌리므로 stub 으로 고정한다 → 요금 0.
상태는 Supabase(Postgres + Storage)에 저장하므로 함수가 매번 새로 떠도 데이터가 유지된다.

Vercel 프로젝트 환경변수로는 Supabase 4개만 넣으면 된다:
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL
나머지 실행 모드는 아래 기본값으로 고정한다(대시보드에서 덮어쓰면 그 값이 우선).
"""
import os
import sys

# app.config 가 import 시점에 환경변수를 읽으므로 반드시 그 전에 설정한다.
os.environ.setdefault("DB_BACKEND", "postgres")
os.environ.setdefault("STORAGE_PROVIDER", "supabase")
os.environ.setdefault("ASR_PROVIDER", "stub")
os.environ.setdefault("SUMMARY_PROVIDER", "stub")
os.environ.setdefault("STUB_STAGE_DELAY", "0")
# 서버리스는 응답을 보낸 뒤 백그라운드 태스크 실행이 보장되지 않는다 → 요청 안에서 처리.
os.environ.setdefault("SYNC_PIPELINE", "1")
# 서버리스 파일시스템은 /tmp 외 읽기 전용이다(config 가 부팅 시 mkdir 함).
os.environ.setdefault("LOCAL_STORAGE_ROOT", "/tmp/data")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402  (ASGI 앱 — Vercel 이 이 이름을 찾는다)
