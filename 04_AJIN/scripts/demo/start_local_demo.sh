#!/usr/bin/env bash
# AJIN AI Assistant — 시연 환경 1-클릭 활성화
#
# 동작:
#   1. Ollama 외부 접근 활성 + 재시작 (CLI 모드)
#   2. Cloudflare Tunnel 백그라운드 실행 → URL 자동 추출
#   3. Cloud Run 환경변수 업데이트 (OLLAMA_BASE_URL + Gemini fallback ON)
#   4. caffeinate 로 Mac sleep 방지
#   5. /api/draft/diagnose 검증
#
# 사용:
#   bash scripts/demo/start_local_demo.sh
#
# 종료:
#   bash scripts/demo/stop_local_demo.sh
#
# 상태:
#   bash scripts/demo/status_demo.sh

set -uo pipefail

# ── 설정 ──────────────────────────────────────────
PROJECT="${PROJECT:-ajin-cb}"
REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-ajin-backend}"
HOSTING_BASE="${HOSTING_BASE:-https://ajin-cb.web.app}"
TUNNEL_LOG="/tmp/ajin_cloudflared.log"
TUNNEL_PID_FILE="/tmp/ajin_cloudflared.pid"
TUNNEL_URL_FILE="/tmp/ajin_tunnel_url.txt"
OLLAMA_LOG="/tmp/ajin_ollama_demo.log"
OLLAMA_PID_FILE="/tmp/ajin_ollama.pid"
CAFFEINATE_PID_FILE="/tmp/ajin_caffeinate.pid"

# ── 헬퍼 ──────────────────────────────────────────
ok()    { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn()  { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
fail()  { printf "  \033[31m✗\033[0m %s\n" "$1"; }
step()  { printf "\n\033[1m▶ [%s] %s\033[0m\n" "$1" "$2"; }
need()  { command -v "$1" >/dev/null 2>&1 || { fail "$1 미설치 — '$2' 로 설치하세요"; exit 1; }; }

echo "═══════════════════════════════════════════════════════"
echo "  AJIN AI Assistant — 시연 환경 활성화"
echo "═══════════════════════════════════════════════════════"
echo "  PROJECT=$PROJECT  REGION=$REGION  SERVICE=$SERVICE"

# ── 사전 도구 점검 ────────────────────────────────
need ollama "brew install ollama"
need cloudflared "brew install cloudflared"
need gcloud "brew install --cask gcloud-cli"
need jq "brew install jq"
need curl "(시스템 기본)"

# ── 1) Ollama 외부 접근 ───────────────────────────
step 1/5 "Ollama 외부 접근 활성"
launchctl setenv OLLAMA_HOST "0.0.0.0:11434"
launchctl setenv OLLAMA_ORIGINS "*"
launchctl setenv OLLAMA_NUM_PARALLEL "4"
launchctl setenv OLLAMA_KEEP_ALIVE "30m"
ok "launchctl env vars 적용"

# Ollama 가 0.0.0.0 으로 바인딩되었는지 확인 — 아니면 재시작
NEED_RESTART=true
if lsof -nP -iTCP:11434 -sTCP:LISTEN 2>/dev/null | grep -qE "(\*|0\.0\.0\.0):11434"; then
    NEED_RESTART=false
fi

if [ "$NEED_RESTART" = true ]; then
    ok "Ollama 재시작 (현재 127.0.0.1 만 바인딩)"
    pkill -x Ollama 2>/dev/null || true
    pkill -x ollama 2>/dev/null || true
    sleep 3
    OLLAMA_HOST="0.0.0.0:11434" OLLAMA_ORIGINS="*" OLLAMA_NUM_PARALLEL=4 OLLAMA_KEEP_ALIVE=30m \
        nohup ollama serve > "$OLLAMA_LOG" 2>&1 &
    echo $! > "$OLLAMA_PID_FILE"
    sleep 5
fi

if ! curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    fail "Ollama 응답 없음 — '$OLLAMA_LOG' 확인"
    exit 1
fi

MODEL_COUNT=$(curl -s http://127.0.0.1:11434/api/tags | jq '.models | length')
ok "Ollama 가동 — ${MODEL_COUNT}개 모델"

# ── 2) Sleep 방지 ────────────────────────────────
step 2/5 "Sleep 방지 (caffeinate)"
if [ -f "$CAFFEINATE_PID_FILE" ] && kill -0 "$(cat $CAFFEINATE_PID_FILE)" 2>/dev/null; then
    ok "이미 가동 중 (PID=$(cat $CAFFEINATE_PID_FILE))"
else
    caffeinate -dimsu &
    echo $! > "$CAFFEINATE_PID_FILE"
    ok "caffeinate PID=$(cat $CAFFEINATE_PID_FILE)"
fi

# ── 3) Cloudflare Tunnel ─────────────────────────
step 3/5 "Cloudflare Tunnel 시작"
if [ -f "$TUNNEL_PID_FILE" ] && kill -0 "$(cat $TUNNEL_PID_FILE)" 2>/dev/null; then
    warn "기존 tunnel 종료 (PID=$(cat $TUNNEL_PID_FILE))"
    kill "$(cat $TUNNEL_PID_FILE)" 2>/dev/null || true
    sleep 2
fi
> "$TUNNEL_LOG"
nohup cloudflared tunnel --url http://localhost:11434 --no-autoupdate \
    > "$TUNNEL_LOG" 2>&1 &
echo $! > "$TUNNEL_PID_FILE"
ok "cloudflared PID=$(cat $TUNNEL_PID_FILE)"

URL=""
for _ in $(seq 1 30); do
    sleep 1
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    [ -n "$URL" ] && break
done

if [ -z "$URL" ]; then
    fail "Tunnel URL 발급 실패 — 'tail $TUNNEL_LOG' 확인"
    exit 1
fi
echo "$URL" > "$TUNNEL_URL_FILE"
ok "Tunnel URL: $URL"

# 외부 접근 검증 — Cloudflare DNS propagation 까지 최대 60초 polling (5초 간격)
TUNNEL_READY=false
for attempt in $(seq 1 12); do
    if curl -sf "$URL/api/tags" --max-time 5 > /dev/null 2>&1; then
        TUNNEL_READY=true
        ok "외부 접근 OK (시도 $attempt/12)"
        break
    fi
    sleep 5
done

if [ "$TUNNEL_READY" = false ]; then
    warn "Tunnel 외부 접근이 60초 내 활성화되지 않음 — Cloud Run 검증 시 다시 점검"
    warn "Tunnel URL 자체는 발급됨: $URL — 계속 진행"
fi

# ── 4) Cloud Run 환경변수 ────────────────────────
step 4/5 "Cloud Run env 업데이트"
echo "  OLLAMA_BASE_URL=$URL"
echo "  FEATURE_B_BLOCK_GEMINI=false  (Mac 끊김 시 Gemini fallback)"
gcloud run services update "$SERVICE" \
    --region "$REGION" \
    --project "$PROJECT" \
    --update-env-vars "OLLAMA_BASE_URL=$URL,FEATURE_B_BLOCK_GEMINI=false" \
    --quiet > /dev/null 2>&1 || { fail "gcloud run update 실패"; exit 1; }
ok "Cloud Run env 적용 완료"

# ── 5) /api/draft/diagnose ────────────────────────
step 5/5 "백엔드 진단 (revision 활성 대기 30s)"
sleep 30

DIAG=$(curl -s "$HOSTING_BASE/api/draft/diagnose" --max-time 15)
if [ -z "$DIAG" ]; then
    warn "/diagnose 응답 없음 — 시연 시작 후 화면에서 직접 확인 필요"
else
    OLLAMA_OK=$(echo "$DIAG" | jq -r '.ollama.ok')
    PIPELINE_OK=$(echo "$DIAG" | jq -r '.pipeline.ok')
    TPL_OK=$(echo "$DIAG" | jq -r '.templates.ok')
    PROMPTS_OK=$(echo "$DIAG" | jq -r '.prompts.ok')
    [ "$OLLAMA_OK" = "true" ]   && ok "Ollama"    || warn "Ollama 미감지 (revision 활성 추가 대기 가능)"
    [ "$PIPELINE_OK" = "true" ] && ok "Pipeline"  || warn "Pipeline"
    [ "$TPL_OK" = "true" ]      && ok "Templates" || warn "Templates"
    [ "$PROMPTS_OK" = "true" ]  && ok "Prompts"   || warn "Prompts"
fi

# ── 완료 ─────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════════"
echo "  ✅ 시연 환경 활성 완료"
echo "═══════════════════════════════════════════════════════"
echo "  🌐 Frontend:  $HOSTING_BASE/draft"
echo "  📡 Tunnel:    $URL"
echo "  💾 Tunnel log: $TUNNEL_LOG"
echo "  🔥 Tunnel PID: $(cat $TUNNEL_PID_FILE)"
echo
echo "  종료:  bash scripts/demo/stop_local_demo.sh"
echo "  상태:  bash scripts/demo/status_demo.sh"
echo
