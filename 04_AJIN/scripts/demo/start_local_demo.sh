#!/usr/bin/env bash
# AJIN AI Assistant — secure local Ollama demo bridge.
#
# Flow:
#   1. Prepare host Ollama on the external SSD model root.
#   2. Start a loopback-only secret-gated proxy on 127.0.0.1:8434.
#   3. Expose the proxy through Cloudflare Tunnel.
#   4. Update Cloud Run to use Ollama primary through the tunnel.
#   5. Verify /api/health/llm-status.

set -uo pipefail

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
PROJECT="${PROJECT:-ajin-cb}"
REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-ajin-backend}"
HOSTING_BASE="${HOSTING_BASE:-https://ajin-cb.web.app}"
# MODEL_ROOT 자동 탐지: 환경변수 우선 → <EXTERNAL_DRIVE>/.ollama/models glob →
# ~/.ollama/models (system default). 외장 SSD 모델명이 바뀌어도 (EX300U → EX400U 등)
# 자동 적응. 한 군데도 못 찾으면 빈 문자열 — Step 1 에서 graceful skip.
_resolve_model_root() {
    if [[ -n "${OLLAMA_MODELS_ROOT:-}" && -d "${OLLAMA_MODELS_ROOT}" ]]; then
        printf '%s\n' "${OLLAMA_MODELS_ROOT}"
        return
    fi
    # Corsair 외장 SSD glob (Corsair EX300U / EX400U / 그 외 변형 모두 매칭)
    for candidate in <EXTERNAL_DRIVE>/.ollama/models; do
        if [[ -d "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return
        fi
    done
    # 내장 SSD system default
    if [[ -d "$HOME/.ollama/models" ]]; then
        printf '%s\n' "$HOME/.ollama/models"
        return
    fi
    printf '\n'
}
MODEL_ROOT="$(_resolve_model_root)"
PROXY_PORT="${OLLAMA_PROXY_PORT:-8434}"
SECRET_NAME="${AJIN_OLLAMA_SECRET_NAME:-ajin-ollama-secret}"
SECRET_FILE="${AJIN_OLLAMA_SECRET_FILE:-$PROJECT_ROOT/secrets/ajin-ollama-secret.txt}"
TUNNEL_LOG="/tmp/ajin_cloudflared.log"
TUNNEL_PID_FILE="/tmp/ajin_cloudflared.pid"
TUNNEL_URL_FILE="/tmp/ajin_tunnel_url.txt"
PROXY_LOG="/tmp/ajin_ollama_proxy.log"
PROXY_PID_FILE="/tmp/ajin_ollama_proxy.pid"
CAFFEINATE_PID_FILE="/tmp/ajin_caffeinate.pid"

ok()    { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn()  { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
fail()  { printf "  \033[31m✗\033[0m %s\n" "$1"; }
step()  { printf "\n\033[1m▶ [%s] %s\033[0m\n" "$1" "$2"; }
need()  { command -v "$1" >/dev/null 2>&1 || { fail "$1 미설치 — '$2' 로 설치하세요"; exit 1; }; }

python_bin() {
    if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
        printf '%s\n' "$PROJECT_ROOT/.venv/bin/python"
    else
        command -v python3
    fi
}

ensure_secret() {
    mkdir -p "$(dirname "$SECRET_FILE")"
    if [[ ! -s "$SECRET_FILE" ]]; then
        umask 077
        if command -v openssl >/dev/null 2>&1; then
            openssl rand -base64 32 > "$SECRET_FILE"
        else
            "$(python_bin)" -c "import secrets; print(secrets.token_urlsafe(32))" > "$SECRET_FILE"
        fi
        ok "local proxy secret generated: $SECRET_FILE"
    else
        ok "local proxy secret exists: $SECRET_FILE"
    fi
}

upsert_secret_manager() {
    local secret_value="$1"
    if gcloud secrets describe "$SECRET_NAME" --project "$PROJECT" >/dev/null 2>&1; then
        printf '%s' "$secret_value" | gcloud secrets versions add "$SECRET_NAME" \
            --project "$PROJECT" \
            --data-file=- >/dev/null 2>&1
    else
        printf '%s' "$secret_value" | gcloud secrets create "$SECRET_NAME" \
            --project "$PROJECT" \
            --replication-policy=automatic \
            --data-file=- >/dev/null 2>&1
    fi
}

echo "═══════════════════════════════════════════════════════"
echo "  AJIN AI Assistant — Ollama secure bridge start"
echo "═══════════════════════════════════════════════════════"
echo "  PROJECT=$PROJECT  REGION=$REGION  SERVICE=$SERVICE"
echo "  MODEL_ROOT=$MODEL_ROOT"

need ollama "brew install ollama"
need cloudflared "brew install cloudflared"
need gcloud "brew install --cask gcloud-cli"
need jq "brew install jq"
need curl "(system default)"

step 1/6 "Host Ollama setup"
# 이미 가동 중인 Ollama 가 있으면 그대로 사용 (외장 SSD 마운트 여부 무관).
# 아니면 MODEL_ROOT 가 확인된 경우에만 setup_host_ollama.sh 호출.
if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama already running on 127.0.0.1:11434 — skipping host setup"
elif [[ -n "$MODEL_ROOT" && -d "$MODEL_ROOT" ]]; then
    bash "$PROJECT_ROOT/scripts/setup_host_ollama.sh" \
        --models-root "$MODEL_ROOT" \
        --skip-pull || { fail "Host Ollama setup failed"; exit 1; }
else
    fail "Ollama 가 가동 중이지 않고 모델 디렉토리도 찾을 수 없음"
    echo "    옵션:"
    echo "      1) 'ollama serve' 직접 실행"
    echo "      2) OLLAMA_MODELS_ROOT=<경로> 환경변수 명시"
    echo "      3) <EXTERNAL_DRIVE>/.ollama/models 외장 SSD 마운트"
    exit 1
fi

MODEL_COUNT=$(curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | jq '.models | length' 2>/dev/null || echo "?")
ok "Ollama ready on loopback — ${MODEL_COUNT} models"

step 2/6 "Sleep prevention"
if [[ -f "$CAFFEINATE_PID_FILE" ]] && kill -0 "$(cat "$CAFFEINATE_PID_FILE")" 2>/dev/null; then
    ok "caffeinate already active (PID=$(cat "$CAFFEINATE_PID_FILE"))"
else
    caffeinate -dimsu &
    echo $! > "$CAFFEINATE_PID_FILE"
    ok "caffeinate PID=$(cat "$CAFFEINATE_PID_FILE")"
fi

step 3/6 "Secret-gated Ollama proxy"
ensure_secret
AJIN_OLLAMA_SECRET="$(cat "$SECRET_FILE")"
if lsof -nP -iTCP:"$PROXY_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    if curl -sf -H "X-AJIN-Secret: $AJIN_OLLAMA_SECRET" "http://127.0.0.1:${PROXY_PORT}/api/tags" >/dev/null 2>&1; then
        ok "existing secure proxy already accepts configured secret on 127.0.0.1:${PROXY_PORT}"
    else
        fail "port ${PROXY_PORT} is already in use but does not accept the configured secret"
        echo "    Stop the existing listener or set OLLAMA_PROXY_PORT to a free loopback port."
        lsof -nP -iTCP:"$PROXY_PORT" -sTCP:LISTEN || true
        exit 1
    fi
else
if [[ -f "$PROXY_PID_FILE" ]] && kill -0 "$(cat "$PROXY_PID_FILE")" 2>/dev/null; then
    warn "stopping previous proxy (PID=$(cat "$PROXY_PID_FILE"))"
    kill "$(cat "$PROXY_PID_FILE")" 2>/dev/null || true
    sleep 1
fi
> "$PROXY_LOG"
AJIN_OLLAMA_SECRET="$AJIN_OLLAMA_SECRET" \
OLLAMA_PROXY_UPSTREAM="http://127.0.0.1:11434" \
OLLAMA_PROXY_PORT="$PROXY_PORT" \
nohup "$(python_bin)" "$PROJECT_ROOT/scripts/ollama_secure_proxy.py" \
    > "$PROXY_LOG" 2>&1 &
echo $! > "$PROXY_PID_FILE"
fi

for _ in $(seq 1 10); do
    if curl -sf -H "X-AJIN-Secret: $AJIN_OLLAMA_SECRET" "http://127.0.0.1:${PROXY_PORT}/api/tags" >/dev/null 2>&1; then
        ok "secure proxy ready on 127.0.0.1:${PROXY_PORT}"
        break
    fi
    sleep 1
done
if ! curl -sf -H "X-AJIN-Secret: $AJIN_OLLAMA_SECRET" "http://127.0.0.1:${PROXY_PORT}/api/tags" >/dev/null 2>&1; then
    fail "secure proxy did not become ready — $PROXY_LOG"
    exit 1
fi

step 4/6 "Cloudflare Tunnel to secure proxy"
if [[ -f "$TUNNEL_PID_FILE" ]] && kill -0 "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null; then
    warn "stopping previous tunnel (PID=$(cat "$TUNNEL_PID_FILE"))"
    kill "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null || true
    sleep 2
fi
> "$TUNNEL_LOG"
nohup cloudflared tunnel --url "http://127.0.0.1:${PROXY_PORT}" --no-autoupdate \
    > "$TUNNEL_LOG" 2>&1 &
echo $! > "$TUNNEL_PID_FILE"
ok "cloudflared PID=$(cat "$TUNNEL_PID_FILE")"

URL=""
for _ in $(seq 1 30); do
    sleep 1
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    [[ -n "$URL" ]] && break
done

if [[ -z "$URL" ]]; then
    fail "Tunnel URL not issued — tail $TUNNEL_LOG"
    exit 1
fi
echo "$URL" > "$TUNNEL_URL_FILE"
ok "Tunnel URL: $URL"

TUNNEL_READY=false
for attempt in $(seq 1 12); do
    if curl -sf -H "X-AJIN-Secret: $AJIN_OLLAMA_SECRET" "$URL/api/tags" --max-time 5 >/dev/null 2>&1; then
        TUNNEL_READY=true
        ok "authorized tunnel probe OK (attempt $attempt/12)"
        break
    fi
    sleep 5
done
if [[ "$TUNNEL_READY" = false ]]; then
    warn "authorized tunnel probe not ready within 60s; continuing with issued URL"
fi

step 5/6 "Cloud Run env and secret update"
upsert_secret_manager "$AJIN_OLLAMA_SECRET" || { fail "Secret Manager update failed"; exit 1; }
echo "  OLLAMA_BASE_URL=$URL"
echo "  LLM_ROUTER_PRIMARY=ollama"
echo "  EMBEDDING_BACKEND=ollama"
echo "  FEATURE_B_BLOCK_GEMINI=true"
gcloud run services update "$SERVICE" \
    --region "$REGION" \
    --project "$PROJECT" \
    --update-env-vars "OLLAMA_BASE_URL=$URL,LLM_ROUTER_PRIMARY=ollama,EMBEDDING_BACKEND=ollama,FEATURE_B_BLOCK_GEMINI=true" \
    --update-secrets "AJIN_OLLAMA_SECRET=${SECRET_NAME}:latest" \
    --quiet >/dev/null 2>&1 || { fail "gcloud run update failed"; exit 1; }
ok "Cloud Run env applied"

step 6/6 "Backend LLM status"
sleep 30
STATUS=$(curl -s "$HOSTING_BASE/api/health/llm-status" --max-time 15)
if [[ -z "$STATUS" ]]; then
    warn "/health/llm-status no response; verify from browser after revision activation"
else
    PRIMARY=$(echo "$STATUS" | jq -r '.routing.primary_provider // "unknown"')
    OLLAMA_OK=$(echo "$STATUS" | jq -r '.ollama.ok')
    TUNNEL=$(echo "$STATUS" | jq -r '.tunnel_active')
    [[ "$PRIMARY" = "ollama" ]] && ok "primary=ollama" || warn "primary=$PRIMARY"
    [[ "$OLLAMA_OK" = "true" ]] && ok "ollama.ok=true" || warn "ollama.ok=$OLLAMA_OK"
    [[ "$TUNNEL" = "true" ]] && ok "tunnel_active=true" || warn "tunnel_active=$TUNNEL"
fi

echo
echo "═══════════════════════════════════════════════════════"
echo "  Secure Ollama bridge active"
echo "═══════════════════════════════════════════════════════"
echo "  Frontend:   $HOSTING_BASE"
echo "  Tunnel:     $URL"
echo "  Proxy log:  $PROXY_LOG"
echo "  Tunnel log: $TUNNEL_LOG"
echo
echo "  Stop:   bash scripts/demo/stop_local_demo.sh"
echo "  Status: bash scripts/demo/status_demo.sh"
echo
