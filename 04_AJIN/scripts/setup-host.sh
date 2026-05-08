#!/usr/bin/env bash
# AJIN AI Assistant — 호스트 1-클릭 셋업
# 사용:
#   bash scripts/setup-host.sh
#
# 수행:
#   1. 필수 toolchain 버전 검증 + 부족 시 안내
#   2. .env / secrets/ placeholder 생성
#   3. Python venv + pip install
#   4. frontend npm install
#   5. Ollama 모델 5개 pull
#   6. ~/.config/ajin/ + Caddyfile + launchd plist 설치 (사용자 동의 시)
#   7. setup-demo-data.py 실행 (가짜 사내 데이터 생성)
set -uo pipefail

ok()    { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn()  { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
fail()  { printf "  \033[31m✗\033[0m %s\n" "$1"; }
step()  { printf "\n\033[1m▶ [%s] %s\033[0m\n" "$1" "$2"; }
ask()   { read -r -p "  $1 [y/N] " a; [[ "$a" =~ ^[Yy]$ ]]; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "═══════════════════════════════════════════════════════"
echo "  AJIN AI Assistant — 호스트 셋업"
echo "═══════════════════════════════════════════════════════"
echo "  REPO=$REPO_ROOT"
echo "  USER=$USER  HOME=$HOME"

# ───────── Step 1: toolchain 검증 ─────────
step 1/7 "필수 toolchain 검증"

check_tool() {
  local cmd="$1" min="$2" install="$3"
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd 설치됨 ($($cmd --version 2>/dev/null | head -1 | head -c 60))"
  else
    fail "$cmd 미설치 — '$install' 실행"
  fi
}

check_tool node      "≥20"     "brew install node"
check_tool npm       "≥10"     "(node 와 함께)"
check_tool python3   "≥3.11"   "brew install python@3.11"
check_tool docker    "≥24"     "https://docker.com/desktop"
check_tool firebase  "≥13"     "npm install -g firebase-tools"
check_tool gcloud    "latest"  "brew install --cask google-cloud-sdk"
check_tool ollama    "≥0.18"   "brew install ollama"
check_tool caddy     "≥2.10"   "brew install caddy"
check_tool cloudflared "latest" "brew install cloudflared"
check_tool jq        "latest"  "brew install jq"

# ───────── Step 2: .env + secrets placeholder ─────────
step 2/7 ".env / secrets/ placeholder 생성"

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  ok ".env 생성 — GEMINI_API_KEY, AJIN_JWT_SECRET 등 직접 채우세요"
else
  warn ".env 이미 존재 — 그대로 유지"
fi

mkdir -p secrets
if [ ! -f secrets/meili_master_key ]; then
  openssl rand -base64 32 > secrets/meili_master_key
  chmod 600 secrets/meili_master_key
  ok "secrets/meili_master_key 자동 생성"
fi
if [ ! -f secrets/smtp_password ]; then
  : > secrets/smtp_password
  chmod 600 secrets/smtp_password
  ok "secrets/smtp_password placeholder (빈 파일) 생성"
fi

# ───────── Step 3: Python venv + pip ─────────
step 3/7 "Python venv + 의존성 설치"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ok "venv 생성 (.venv/)"
fi
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Python 의존성 설치 완료"

# ───────── Step 4: frontend npm ─────────
step 4/7 "Frontend 의존성 설치 (npm install)"
( cd frontend && npm install --silent ) && ok "npm 의존성 설치 완료" || fail "npm install 실패"

# ───────── Step 5: Ollama 모델 ─────────
step 5/7 "Ollama 모델 5개 다운로드 (~14 GB, 첫 실행 시 시간 소요)"
if ask "지금 다운로드할까요?"; then
  for m in qwen3.5:9b qwen3.5:4b gemma4:e4b gemma4:e2b bge-m3; do
    if ollama list 2>/dev/null | awk '{print $1}' | grep -q "^${m}$"; then
      ok "$m 이미 설치됨"
    else
      echo "  pull $m ..."
      ollama pull "$m" && ok "$m" || warn "$m 다운로드 실패 — 나중에 재시도"
    fi
  done
else
  warn "Ollama 모델 다운로드 skip — 'ollama pull qwen3.5:9b' 등 수동 실행"
fi

# ───────── Step 6: Caddy + Watchdog (운영 연동) ─────────
step 6/7 "Caddy + Tunnel Watchdog 설치 (운영 시 Mac Ollama × Cloud Run 연동)"
if ask "Caddy + cloudflared watchdog 영속화 설치할까요? (시연·운영용)"; then
  AJIN_CFG="$HOME/.config/ajin"
  mkdir -p "$AJIN_CFG"

  # Caddyfile
  cp infra/caddy/Caddyfile.example "$AJIN_CFG/Caddyfile"
  ok "Caddyfile → $AJIN_CFG/Caddyfile"

  # ollama-secret 자동 생성
  if [ ! -f "$AJIN_CFG/ollama-secret" ]; then
    openssl rand -hex 32 > "$AJIN_CFG/ollama-secret"
    chmod 600 "$AJIN_CFG/ollama-secret"
    ok "ollama-secret 자동 생성 (32-byte hex)"
  fi

  # launchctl env 등록
  SECRET=$(cat "$AJIN_CFG/ollama-secret")
  launchctl setenv AJIN_OLLAMA_SECRET "$SECRET"
  launchctl setenv OLLAMA_HOST "0.0.0.0:11434"

  # tunnel-watchdog.sh 복사 + placeholder 치환
  sed "s|__USER_HOME__|$HOME|g" infra/tunnel-watchdog.sh.example > "$AJIN_CFG/tunnel-watchdog.sh"
  chmod +x "$AJIN_CFG/tunnel-watchdog.sh"
  ok "tunnel-watchdog.sh → $AJIN_CFG/"

  # launchd plist 복사 + placeholder 치환
  for plist in com.ajin.caddy.plist com.ajin.tunnel-watchdog.plist; do
    sed "s|__USER_HOME__|$HOME|g" "infra/launchd/${plist}.example" \
      > "$HOME/Library/LaunchAgents/$plist"
    ok "$plist → ~/Library/LaunchAgents/"
  done

  if ask "지금 Caddy 만 launchd 로 기동할까요? (Watchdog 은 GCP 로그인 후 별도)"; then
    launchctl unload "$HOME/Library/LaunchAgents/com.ajin.caddy.plist" 2>/dev/null
    launchctl load   "$HOME/Library/LaunchAgents/com.ajin.caddy.plist"
    ok "com.ajin.caddy 기동"
  fi
fi

# ───────── Step 7: 데모 데이터 생성 ─────────
step 7/7 "데모 데이터 생성 (가짜 직원 30명 + 법규 5건 + 시나리오 5종)"
if ask "지금 데모 데이터를 생성할까요?"; then
  python3 scripts/setup-demo-data.py && ok "데모 데이터 생성 완료" || warn "데모 데이터 생성 실패"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  셋업 완료. 다음 단계:"
echo "    - .env 의 GEMINI_API_KEY 등 직접 채우기"
echo "    - 'bash scripts/demo/start_local_demo.sh' 로 시연 환경 활성화"
echo "    - 'cd frontend && npm run dev' 로 프론트엔드 dev 서버"
echo "    - 'uvicorn backend.main:app --reload' 로 백엔드 dev 서버"
echo "═══════════════════════════════════════════════════════"
