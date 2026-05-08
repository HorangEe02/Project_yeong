#!/usr/bin/env bash
# AJIN AI Assistant — 시연 환경 상태 점검
#
# 사용:
#   bash scripts/demo/status_demo.sh

set -uo pipefail

PROJECT="${PROJECT:-ajin-cb}"
REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-ajin-backend}"
HOSTING_BASE="${HOSTING_BASE:-https://ajin-cb.web.app}"
TUNNEL_LOG="/tmp/ajin_cloudflared.log"
TUNNEL_PID_FILE="/tmp/ajin_cloudflared.pid"
TUNNEL_URL_FILE="/tmp/ajin_tunnel_url.txt"
CAFFEINATE_PID_FILE="/tmp/ajin_caffeinate.pid"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$1"; }

echo "═══════════════════════════════════════════════════════"
echo "  AJIN Demo 환경 상태"
echo "═══════════════════════════════════════════════════════"

# Ollama
echo
echo "▶ Ollama (Mac local)"
if curl -sf http://127.0.0.1:11434/api/tags --max-time 3 > /dev/null 2>&1; then
    COUNT=$(curl -s http://127.0.0.1:11434/api/tags | jq '.models | length')
    BIND=$(lsof -nP -iTCP:11434 -sTCP:LISTEN 2>/dev/null | tail -n 1 | awk '{print $9}')
    ok "가동 — ${COUNT}개 모델 / 바인딩 $BIND"
else
    fail "응답 없음"
fi

# Cloudflared
echo
echo "▶ Cloudflare Tunnel"
if [ -f "$TUNNEL_PID_FILE" ] && kill -0 "$(cat $TUNNEL_PID_FILE)" 2>/dev/null; then
    URL=""
    [ -f "$TUNNEL_URL_FILE" ] && URL=$(cat "$TUNNEL_URL_FILE")
    [ -z "$URL" ] && URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    ok "프로세스 가동 — PID=$(cat $TUNNEL_PID_FILE)"
    if [ -n "$URL" ]; then
        echo "    URL: $URL"
        if curl -sf "$URL/api/tags" --max-time 5 > /dev/null 2>&1; then
            ok "외부 응답 OK"
        else
            fail "외부 응답 실패"
        fi
    else
        warn "URL 미확보 — '$TUNNEL_LOG' 확인"
    fi
else
    fail "미가동"
fi

# Sleep 방지
echo
echo "▶ Sleep 방지 (caffeinate)"
if [ -f "$CAFFEINATE_PID_FILE" ] && kill -0 "$(cat $CAFFEINATE_PID_FILE)" 2>/dev/null; then
    ok "활성 — PID=$(cat $CAFFEINATE_PID_FILE)"
else
    warn "비활성 — Mac 이 sleep 으로 들어갈 수 있음"
fi

# Cloud Run env
echo
echo "▶ Cloud Run ($SERVICE)"
ENVS=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" \
    --format='value(spec.template.spec.containers[0].env[].name,spec.template.spec.containers[0].env[].value)' 2>/dev/null)
OLLAMA_URL=$(echo "$ENVS" | tr ';' '\n' | grep -E "^OLLAMA_BASE_URL=" | head -1 | cut -d= -f2-)
BLOCK=$(echo "$ENVS" | tr ';' '\n' | grep -E "^FEATURE_B_BLOCK_GEMINI=" | head -1 | cut -d= -f2-)

if [ -n "${OLLAMA_URL:-}" ]; then
    ok "OLLAMA_BASE_URL=$OLLAMA_URL"
else
    warn "OLLAMA_BASE_URL=(빈값) — Gemini 단독 모드"
fi
echo "    FEATURE_B_BLOCK_GEMINI=${BLOCK:-(미설정/기본 true)}"

# Diagnose
echo
echo "▶ /api/draft/diagnose ($HOSTING_BASE)"
DIAG=$(curl -s "$HOSTING_BASE/api/draft/diagnose" --max-time 10)
if [ -n "$DIAG" ]; then
    for k in ollama gemini pipeline templates prompts; do
        OK=$(echo "$DIAG" | jq -r ".$k.ok")
        DT=$(echo "$DIAG" | jq -r ".$k.detail")
        if [ "$OK" = "true" ]; then
            ok "$(printf '%-10s — %s' "$k" "$DT")"
        else
            warn "$(printf '%-10s — %s' "$k" "$DT")"
        fi
    done
else
    fail "응답 없음"
fi

echo
