#!/usr/bin/env bash
# AJIN Demo Tunnel — Host bridge installer
#
# 목적: Mac 호스트의 ollama serve + ollama_secure_proxy.py 를 launchd 영구화 +
#       GCP Secret Manager 에 AJIN_OLLAMA_SECRET 1회 seed.
#       이후 docker/demo-tunnel 컨테이너의 ▶ Start 한 번으로 production frontend
#       (https://ajin-ai-assistant-frontend.vercel.app) 가 host ollama 모델 호출 가능.
#
# 사용: bash scripts/demo/install_host_bridge.sh
#
# idempotent — 이미 설치된 plist 도 unload+load 로 reload.

set -euo pipefail

# ── 변수 ─────────────────────────────────────────────────────────
PROJECT="${GCP_PROJECT:-ajin-cb}"
SECRET_NAME="${AJIN_OLLAMA_SECRET_NAME:-ajin-ollama-secret}"
PROXY_PORT="${PROXY_PORT:-8434}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECURE_PROXY="$REPO_ROOT/scripts/ollama_secure_proxy.py"
SECRETS_DIR="$REPO_ROOT/secrets"
ENV_FILE="$SECRETS_DIR/.demo-tunnel.env"
LA_DIR="$HOME/Library/LaunchAgents"
OLLAMA_PLIST="$LA_DIR/com.ajin.ollama.plist"
PROXY_PLIST="$LA_DIR/com.ajin.ollama-secure-proxy.plist"
UID_NUM="$(id -u)"

# ── 출력 helper ─────────────────────────────────────────────────
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$1"; }
step() { printf "\n\033[1m▶ %s\033[0m\n" "$1"; }

echo "═══════════════════════════════════════════════════════"
echo "  AJIN Demo Tunnel — Host Bridge Installer"
echo "═══════════════════════════════════════════════════════"
echo "  REPO_ROOT=$REPO_ROOT"
echo "  PROJECT=$PROJECT  SECRET=$SECRET_NAME"
echo "  PROXY_PORT=$PROXY_PORT  OLLAMA_PORT=$OLLAMA_PORT"

# ── (a) 필수 도구 검사 ────────────────────────────────────────
step "(a) 필수 도구 검사"
MISSING=()
for tool in ollama cloudflared jq gcloud python3; do
    if command -v "$tool" >/dev/null 2>&1; then
        ok "$tool 설치됨"
    else
        fail "$tool 누락"
        MISSING+=("$tool")
    fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo
    fail "다음 도구를 먼저 설치하세요:"
    for tool in "${MISSING[@]}"; do
        case "$tool" in
            ollama)        echo "  brew install ollama" ;;
            cloudflared)   echo "  brew install cloudflared" ;;
            jq)            echo "  brew install jq" ;;
            gcloud)        echo "  brew install --cask google-cloud-sdk" ;;
            python3)       echo "  brew install python3 (또는 Xcode CLT)" ;;
        esac
    done
    exit 1
fi

# ── (b) gcloud 인증 + 프로젝트 검증 ───────────────────────────
step "(b) gcloud 인증 검증"
ACCT="$(gcloud config get account 2>/dev/null | tail -1)"
if [ -z "$ACCT" ] || [ "$ACCT" = "(unset)" ]; then
    fail "gcloud active account 없음 — 다음 실행 후 재시도:"
    echo "  gcloud auth login"
    exit 1
fi
ok "gcloud active account: $ACCT"

CUR_PROJECT="$(gcloud config get project 2>/dev/null | tail -1)"
if [ "$CUR_PROJECT" != "$PROJECT" ]; then
    warn "gcloud project 가 $CUR_PROJECT — $PROJECT 로 변경"
    gcloud config set project "$PROJECT" --quiet
fi
ok "gcloud project: $PROJECT"

# ── (c) AJIN_OLLAMA_SECRET lifecycle ──────────────────────────
step "(c) AJIN_OLLAMA_SECRET — Secret Manager seed"
mkdir -p "$SECRETS_DIR"

if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" >/dev/null 2>&1; then
    ok "Secret Manager 에 $SECRET_NAME 존재 — fetch"
    SECRET_VALUE="$(gcloud secrets versions access latest --secret="$SECRET_NAME" --project="$PROJECT")"
else
    warn "Secret Manager 에 $SECRET_NAME 없음 — 32-byte random 생성 + upsert"
    SECRET_VALUE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    printf "%s" "$SECRET_VALUE" | gcloud secrets create "$SECRET_NAME" \
        --replication-policy=automatic \
        --data-file=- \
        --project="$PROJECT" >/dev/null
    ok "Secret Manager 에 $SECRET_NAME 생성 완료"
fi

# Cache 파일 작성 (docker-compose env_file 로 주입)
cat > "$ENV_FILE" <<EOF
# AJIN demo-tunnel — Secret Manager cache. install_host_bridge.sh 가 생성.
# Secret Manager 가 single source. 이 파일 분실 시 entrypoint 가 fallback fetch.
AJIN_OLLAMA_SECRET=$SECRET_VALUE
EOF
chmod 600 "$ENV_FILE"
ok "secrets/.demo-tunnel.env 작성 (chmod 600)"

# ── (d) Ollama launchd plist ──────────────────────────────────
step "(d) Ollama serve launchd 영구화 (com.ajin.ollama)"
OLLAMA_BIN="$(command -v ollama)"
mkdir -p "$LA_DIR"
cat > "$OLLAMA_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.ajin.ollama</string>
  <key>ProgramArguments</key>
  <array>
    <string>$OLLAMA_BIN</string>
    <string>serve</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OLLAMA_HOST</key><string>0.0.0.0:$OLLAMA_PORT</string>
    <key>OLLAMA_ORIGINS</key><string>*</string>
    <key>OLLAMA_NUM_PARALLEL</key><string>4</string>
    <key>OLLAMA_KEEP_ALIVE</key><string>30m</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/com.ajin.ollama.log</string>
  <key>StandardErrorPath</key><string>/tmp/com.ajin.ollama.err</string>
</dict>
</plist>
EOF
chmod 644 "$OLLAMA_PLIST"
launchctl bootout "gui/$UID_NUM/com.ajin.ollama" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$OLLAMA_PLIST"
ok "com.ajin.ollama plist 등록 + bootstrap (KeepAlive)"

# ── (e) Secure proxy launchd plist ────────────────────────────
step "(e) ollama_secure_proxy.py launchd 영구화 (com.ajin.ollama-secure-proxy)"

# Port 충돌 check — 다른 process (예: caddy) 가 PROXY_PORT 점유 중이면 plist 가
# 무한 재시작 loop 에 빠짐. 사용자에게 명시적으로 안내.
PORT_OWNER="$(lsof -nP -iTCP:"$PROXY_PORT" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $1, $2}' | sort -u || true)"
EXISTING_PROXY_PID="$(launchctl print "gui/$UID_NUM/com.ajin.ollama-secure-proxy" 2>/dev/null | awk '/^\tpid = / {print $3}' || true)"
if [ -n "$PORT_OWNER" ]; then
    # 이미 com.ajin.ollama-secure-proxy 가 점유 중이면 reload 정상 흐름
    if echo "$PORT_OWNER" | grep -qE "Python|python" && [ -n "$EXISTING_PROXY_PID" ]; then
        ok "이미 launchd com.ajin.ollama-secure-proxy (PID $EXISTING_PROXY_PID) 가 :$PROXY_PORT 사용 중 — reload 진행"
    else
        fail "다른 process 가 :$PROXY_PORT 사용 중 — plist 등록 시 충돌:"
        echo "$PORT_OWNER" | sed 's/^/    /'
        echo
        echo "    해결 옵션:"
        echo "      (1) 기존 process 정지: pkill caddy 또는 해당 service down"
        echo "      (2) 다른 port 사용: PROXY_PORT=8444 bash $0"
        echo "          (docker-compose.yml 의 OLLAMA_HOST_INTERNAL 도 host.docker.internal:8444 로 변경 필요)"
        exit 1
    fi
fi

PY_BIN="$(command -v python3)"
cat > "$PROXY_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.ajin.ollama-secure-proxy</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY_BIN</string>
    <string>$SECURE_PROXY</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>$PROXY_PORT</string>
    <string>--upstream</string><string>http://127.0.0.1:$OLLAMA_PORT</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>AJIN_OLLAMA_SECRET</key><string>$SECRET_VALUE</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/com.ajin.ollama-secure-proxy.log</string>
  <key>StandardErrorPath</key><string>/tmp/com.ajin.ollama-secure-proxy.err</string>
</dict>
</plist>
EOF
chmod 600 "$PROXY_PLIST"
launchctl bootout "gui/$UID_NUM/com.ajin.ollama-secure-proxy" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PROXY_PLIST"
ok "com.ajin.ollama-secure-proxy plist 등록 + bootstrap (KeepAlive, chmod 600)"

# ── (f) 헬스체크 ──────────────────────────────────────────────
step "(f) 헬스체크 — secure proxy 도달성"
for i in 1 2 3 4 5; do
    if curl -fsS -H "X-AJIN-Secret: $SECRET_VALUE" "http://127.0.0.1:$PROXY_PORT/api/tags" --max-time 5 >/dev/null 2>&1; then
        COUNT="$(curl -s -H "X-AJIN-Secret: $SECRET_VALUE" "http://127.0.0.1:$PROXY_PORT/api/tags" | jq '.models | length')"
        ok "Secure proxy 도달 OK — ${COUNT}개 모델 ($i 회 시도)"
        break
    fi
    if [ "$i" = 5 ]; then
        fail "Secure proxy 5회 시도 후에도 응답 없음"
        echo "    /tmp/com.ajin.ollama-secure-proxy.err 또는 .log 확인:"
        echo "      tail -50 /tmp/com.ajin.ollama-secure-proxy.err"
        echo "      tail -50 /tmp/com.ajin.ollama.err"
        exit 1
    fi
    sleep 2
done

# ── (g) 마지막 안내 ───────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Host bridge 설치 완료"
echo "═══════════════════════════════════════════════════════"
echo
echo "  다음 단계 — 컨테이너 1회 빌드 + create:"
echo "    cd docker/demo-tunnel"
echo "    docker compose build"
echo "    docker compose create"
echo
echo "  이후 시연:"
echo "    Docker Desktop → Containers → ajin-demo-tunnel → ▶ Start"
echo
echo "  Production frontend: https://ajin-ai-assistant-frontend.vercel.app"
echo
