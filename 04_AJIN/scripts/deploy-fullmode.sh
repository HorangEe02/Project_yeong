#!/usr/bin/env bash
# AJIN Backend — 풀 모드 배포 (DEPRECATED → deploy-backend.sh 위임)
#
# v3.6.1 부터 Dockerfile 이 단일화되고 deploy 흐름이 canary + smoke test 가드를
# 포함하는 deploy-backend.sh 로 통합됨. 본 스크립트는 BC (역호환) 차원에서 유지.
#
# 권장:
#   bash scripts/deploy-backend.sh --mode full
#
# 추가 서비스 설정 (메모리/scaling/secrets/env) 변경이 필요하면 deploy 후 별도로:
#   gcloud run services update ajin-backend --region=asia-northeast3 \
#     --memory=4Gi --cpu=2 --min-instances=1 --max-instances=3 \
#     --update-env-vars=EMBEDDING_BACKEND=gemini,AUTH_BACKEND=firestore \
#     --set-secrets=AJIN_JWT_SECRET=AJIN_JWT_SECRET:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[deploy-fullmode.sh] DEPRECATED — deploy-backend.sh --mode full 로 위임합니다."
exec bash "${SCRIPT_DIR}/deploy-backend.sh" --mode full "$@"
