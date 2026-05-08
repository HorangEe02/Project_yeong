#!/usr/bin/env bash
# AJIN AI Assistant — 시연 환경 1-클릭 종료
#
# 동작:
#   1. Cloudflare Tunnel 종료
#   2. caffeinate 종료
#   3. Cloud Run env 원복 (Gemini 단독 모드)
#   4. (선택) ollama serve 백그라운드 종료
#
# 사용:
#   bash scripts/demo/stop_local_demo.sh
#
# 옵션:
#   --keep-ollama  : ollama serve 프로세스는 종료하지 않음
#   --keep-gemini  : Cloud Run env 를 원복하지 않음 (계속 Gemini 사용)

set -uo pipefail

PROJECT="${PROJECT:-ajin-cb}"
REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-ajin-backend}"
TUNNEL_PID_FILE="/tmp/ajin_cloudflared.pid"
TUNNEL_URL_FILE="/tmp/ajin_tunnel_url.txt"
OLLAMA_PID_FILE="/tmp/ajin_ollama.pid"
CAFFEINATE_PID_FILE="/tmp/ajin_caffeinate.pid"

KEEP_OLLAMA=false
KEEP_GEMINI=false
for arg in "$@"; do
    case "$arg" in
        --keep-ollama) KEEP_OLLAMA=true ;;
        --keep-gemini) KEEP_GEMINI=true ;;
    esac
done

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
step() { printf "\n\033[1m▶ [%s] %s\033[0m\n" "$1" "$2"; }

echo "═══════════════════════════════════════════════════════"
echo "  AJIN AI Assistant — 시연 환경 종료"
echo "═══════════════════════════════════════════════════════"

step 1/4 "Cloudflare Tunnel 종료"
if [ -f "$TUNNEL_PID_FILE" ]; then
    PID=$(cat "$TUNNEL_PID_FILE")
    if kill "$PID" 2>/dev/null; then
        ok "tunnel 종료 (PID=$PID)"
    else
        warn "tunnel 이미 종료됨"
    fi
    rm -f "$TUNNEL_PID_FILE" "$TUNNEL_URL_FILE"
fi
pkill -f "cloudflared tunnel --url" 2>/dev/null || true

step 2/4 "Sleep 방지 해제"
if [ -f "$CAFFEINATE_PID_FILE" ]; then
    PID=$(cat "$CAFFEINATE_PID_FILE")
    kill "$PID" 2>/dev/null && ok "caffeinate 종료 (PID=$PID)" || warn "이미 종료됨"
    rm -f "$CAFFEINATE_PID_FILE"
fi

step 3/4 "Cloud Run env 원복"
if [ "$KEEP_GEMINI" = true ]; then
    warn "--keep-gemini 옵션 — Cloud Run env 변경 안 함"
else
    gcloud run services update "$SERVICE" \
        --region "$REGION" \
        --project "$PROJECT" \
        --update-env-vars "OLLAMA_BASE_URL=,FEATURE_B_BLOCK_GEMINI=false" \
        --quiet > /dev/null 2>&1 \
        && ok "OLLAMA_BASE_URL 비움 (Gemini 단독 모드)" \
        || warn "gcloud run update 실패 — 수동 확인 필요"
fi

step 4/4 "Ollama 정리"
if [ "$KEEP_OLLAMA" = true ]; then
    warn "--keep-ollama 옵션 — ollama 프로세스 유지"
elif [ -f "$OLLAMA_PID_FILE" ]; then
    PID=$(cat "$OLLAMA_PID_FILE")
    kill "$PID" 2>/dev/null && ok "ollama serve 종료 (PID=$PID)" || warn "이미 종료됨"
    rm -f "$OLLAMA_PID_FILE"
else
    warn "스크립트가 시작한 ollama 가 없음 — 기존 GUI/CLI 그대로 둠"
fi

echo
echo "═══════════════════════════════════════════════════════"
echo "  ✅ 시연 환경 종료 완료"
echo "═══════════════════════════════════════════════════════"
echo "  Frontend (https://ajin-cb.web.app/draft) 는 자동으로"
echo "  Gemini 모드로 동작합니다."
echo
