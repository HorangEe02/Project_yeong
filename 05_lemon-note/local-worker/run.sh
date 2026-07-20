#!/usr/bin/env bash
# 로컬 데모 Worker 실행 스크립트 (비용 0, 모델 다운로드 없음)
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[setup] 가상환경 생성..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[setup] 의존성 설치..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

export PORT="${PORT:-8710}"
echo "[run] http://localhost:${PORT} 에서 실행합니다."
exec uvicorn app.main:app --host 127.0.0.1 --port "${PORT}" --reload
