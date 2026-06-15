#!/usr/bin/env bash
# AJIN AI Assistant — Demo Tunnel 컨테이너 entrypoint
# 1) Mac Ollama 보안 프록시 도달성 검증
# 2) Cloudflare Tunnel 시작 + URL 추출
# 3) Cloud Run env 업데이트 (Ollama primary + secret header)
# 4) cloudflared 를 foreground 유지 (컨테이너 alive)
# 5) SIGTERM 시 trap → Cloud Run env 원복

set -uo pipefail

PROJECT="${GCP_PROJECT:-ajin-cb}"
REGION="${GCP_REGION:-asia-northeast3}"
SERVICE="${GCP_SERVICE:-ajin-backend}"
HOSTING_BASE="${HOSTING_BASE:-https://ajin-cb.web.app}"
OLLAMA_HOST_INTERNAL="${OLLAMA_HOST_INTERNAL:-host.docker.internal:8434}"
AJIN_OLLAMA_SECRET_NAME="${AJIN_OLLAMA_SECRET_NAME:-ajin-ollama-secret}"

LOG_FILE="/tmp/cloudflared.log"
URL_FILE="/tmp/tunnel_url.txt"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$1"; }
step() { printf "\n\033[1m▶ [%s] %s\033[0m\n" "$1" "$2"; }

echo "═══════════════════════════════════════════════════════"
echo "  AJIN Demo Tunnel Container"
echo "═══════════════════════════════════════════════════════"
echo "  GCP_PROJECT=$PROJECT  REGION=$REGION  SERVICE=$SERVICE"
echo "  Secure Ollama proxy target: $OLLAMA_HOST_INTERNAL"

# ── 1) Mac Ollama 보안 프록시 도달성 ─────────────
step 1/5 "Mac Ollama secure proxy 도달성 검증"
if [ -z "${AJIN_OLLAMA_SECRET:-}" ]; then
    warn "AJIN_OLLAMA_SECRET env 미설정 — Secret Manager 에서 fallback fetch 시도"
    SECRET_FETCHED=$(gcloud secrets versions access latest --secret=ajin-ollama-secret --project="$PROJECT" 2>/dev/null || true)
    if [ -n "$SECRET_FETCHED" ]; then
        export AJIN_OLLAMA_SECRET="$SECRET_FETCHED"
        ok "Secret Manager 에서 AJIN_OLLAMA_SECRET fetch 완료"
    else
        fail "AJIN_OLLAMA_SECRET 미설정 — Secret Manager 에도 ajin-ollama-secret 없음"
        echo "    호스트에서 1회 실행:"
        echo "      bash scripts/demo/install_host_bridge.sh"
        exit 1
    fi
fi
if curl -sf -H "X-AJIN-Secret: $AJIN_OLLAMA_SECRET" "http://$OLLAMA_HOST_INTERNAL/api/tags" --max-time 5 > /dev/null 2>&1; then
    COUNT=$(curl -s -H "X-AJIN-Secret: $AJIN_OLLAMA_SECRET" "http://$OLLAMA_HOST_INTERNAL/api/tags" | jq '.models | length')
    ok "Secure proxy 도달 OK — ${COUNT}개 모델"
else
    fail "Secure proxy 응답 없음 ($OLLAMA_HOST_INTERNAL)"
    echo
    echo "    호스트 launchd 의 ollama-secure-proxy 가 정지된 것 같습니다."
    echo "    Mac terminal 에서 다음을 실행 후 컨테이너 ▶ Start 재시도:"
    echo "      launchctl kickstart -k gui/\$(id -u)/com.ajin.ollama-secure-proxy"
    echo "    첫 setup 미완료라면:"
    echo "      bash scripts/demo/install_host_bridge.sh"
    exit 1
fi

# ── 2) gcloud 인증 ──────────────────────────────
step 2/5 "gcloud 인증 검증"
# gcloud config get account 는 read-only — access token refresh 안 함.
# active account 만 확인하기 위해 사용 (gcloud auth list 보다 ro 마운트에서도 안전).
ACCT=$(gcloud config get account 2>/dev/null | tail -1)
if [ -z "$ACCT" ] || [ "$ACCT" = "(unset)" ]; then
    fail "gcloud active account 없음 — 호스트에서 'gcloud auth login' 후 재시도"
    exit 1
fi
ok "gcloud active account: $ACCT"

# ── 3) cleanup trap ─────────────────────────────
TUNNEL_URL=""
CF_PID=""
cleanup() {
    echo
    step "cleanup" "Cloud Run env 원복 + cloudflared 종료 + healthcheck marker 삭제"
    # healthcheck marker 즉시 삭제 — Docker Desktop UI 가 즉시 unhealthy 표시
    rm -f /tmp/cloudrun_applied /tmp/tunnel_url.txt 2>/dev/null || true
    if [ -n "$CF_PID" ] && kill -0 "$CF_PID" 2>/dev/null; then
        kill "$CF_PID" 2>/dev/null || true
        ok "cloudflared 종료 (PID=$CF_PID)"
    fi
    # gcloud token 만료 감지 — 만료 시 명확한 수동 복구 안내
    if ! gcloud auth print-access-token >/dev/null 2>&1; then
        warn "gcloud access token 만료 — Cloud Run env 원복 실패 가능"
        warn "  호스트에서 'gcloud auth login' 후 수동 실행:"
        warn "    gcloud run services update $SERVICE --region $REGION \\"
        warn "      --update-env-vars 'OLLAMA_BASE_URL=,LLM_ROUTER_PRIMARY=gemini,EMBEDDING_BACKEND=gemini,FEATURE_B_BLOCK_GEMINI=false' --quiet"
        return
    fi
    gcloud run services update "$SERVICE" \
        --region "$REGION" --project "$PROJECT" \
        --update-env-vars "OLLAMA_BASE_URL=,LLM_ROUTER_PRIMARY=gemini,EMBEDDING_BACKEND=gemini,FEATURE_B_BLOCK_GEMINI=false" \
        --quiet > /dev/null 2>&1 \
        && ok "OLLAMA_BASE_URL 비움 (Gemini 단독 모드)" \
        || warn "Cloud Run env 원복 실패 — 수동 확인 필요"
}
trap cleanup EXIT INT TERM

# ── 4) Cloudflare Tunnel ────────────────────────
step 3/5 "Cloudflare Tunnel 시작"
> "$LOG_FILE"
cloudflared tunnel --url "http://$OLLAMA_HOST_INTERNAL" --no-autoupdate \
    > "$LOG_FILE" 2>&1 &
CF_PID=$!
ok "cloudflared started (PID=$CF_PID)"

# URL 추출 (최대 30초)
for i in $(seq 1 30); do
    sleep 1
    TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_FILE" 2>/dev/null | head -1 || true)
    [ -n "$TUNNEL_URL" ] && break
done

if [ -z "$TUNNEL_URL" ]; then
    fail "Tunnel URL 발급 실패"
    tail -20 "$LOG_FILE"
    exit 1
fi
echo "$TUNNEL_URL" > "$URL_FILE"
ok "Tunnel URL: $TUNNEL_URL"

# 외부 접근 polling (60초)
TUNNEL_READY=false
for attempt in $(seq 1 12); do
    if curl -sf -H "X-AJIN-Secret: $AJIN_OLLAMA_SECRET" "$TUNNEL_URL/api/tags" --max-time 5 > /dev/null 2>&1; then
        TUNNEL_READY=true
        ok "authorized external access OK (시도 $attempt/12)"
        break
    fi
    sleep 5
done
[ "$TUNNEL_READY" = false ] && warn "Tunnel propagation 지연 — Cloud Run 측에서 정상 동작 가능"

# ── 5) Cloud Run env 업데이트 ────────────────────
step 4/5 "Cloud Run env 업데이트"
echo "  OLLAMA_BASE_URL=$TUNNEL_URL"
echo "  LLM_ROUTER_PRIMARY=ollama"
echo "  EMBEDDING_BACKEND=ollama"
echo "  FEATURE_B_BLOCK_GEMINI=true"
gcloud run services update "$SERVICE" \
    --region "$REGION" --project "$PROJECT" \
    --update-env-vars "OLLAMA_BASE_URL=$TUNNEL_URL,LLM_ROUTER_PRIMARY=ollama,EMBEDDING_BACKEND=ollama,FEATURE_B_BLOCK_GEMINI=true" \
    --update-secrets "AJIN_OLLAMA_SECRET=${AJIN_OLLAMA_SECRET_NAME}:latest" \
    --quiet > /dev/null 2>&1 \
    && { ok "Cloud Run env 적용 완료"; touch /tmp/cloudrun_applied; } \
    || { fail "gcloud run update 실패"; exit 1; }

# Cloud Run env 업데이트는 새 revision 만들지만, service 에 명시 traffic split
# (tag 별 pinning) 이 적용되어 있으면 새 revision 가 traffic 0% 받음 → 새
# OLLAMA_BASE_URL 미반영 → llm_connected=false. traffic 을 latest 로 강제
# 이동하여 새 tunnel URL 즉시 적용.
# (2026-05-28 — 이전 tunnel 재시작 후 traffic 가 옛 revision 에 고정되어
#  ollama 도달 fail 한 사례 재발 방지)
gcloud run services update-traffic "$SERVICE" \
    --to-latest \
    --region "$REGION" --project "$PROJECT" \
    --quiet > /dev/null 2>&1 \
    && ok "traffic → latest revision (새 OLLAMA_BASE_URL 활성)" \
    || warn "traffic shift 실패 — 수동: gcloud run services update-traffic $SERVICE --region $REGION --to-latest"

# ── 6) 통합 진단 (revision 활성 30초 대기) ──
# v3.3 Phase H — /api/health/llm-status 로 모든 기능(A~F) 의 LLM 도달 상태 확인.
# 기존 /api/draft/diagnose 는 B 만 검증 → llm-status 로 6 기능 통합 검증.
step 5/5 "Cloud Run revision 활성 대기 + 통합 진단"
sleep 30
DIAG=$(curl -s "$HOSTING_BASE/api/health/llm-status" --max-time 15)
if [ -n "$DIAG" ]; then
    OVERALL=$(echo "$DIAG" | jq -r '.status')
    TUNNEL_ACTIVE=$(echo "$DIAG" | jq -r '.tunnel_active')
    OLLAMA_OK=$(echo "$DIAG" | jq -r '.ollama.ok')
    OLLAMA_BASE=$(echo "$DIAG" | jq -r '.ollama.base_url')
    OLLAMA_MODELS=$(echo "$DIAG" | jq -r '.ollama.model_count')
    GEMINI_KEY=$(echo "$DIAG" | jq -r '.gemini.api_key_present')
    SUMMARY=$(echo "$DIAG" | jq -r '.summary')

    [ "$OVERALL" = "ok" ] && ok "overall status=ok" || warn "overall status=$OVERALL"
    [ "$TUNNEL_ACTIVE" = "true" ] && ok "tunnel_active=true (Cloud Run 이 Tunnel 사용 확인)" || warn "tunnel_active=$TUNNEL_ACTIVE — Cloud Run 이 아직 환경변수 반영 안 했을 수 있음"
    [ "$OLLAMA_OK" = "true" ] && ok "ollama.ok=true (모델 ${OLLAMA_MODELS}개)" || warn "ollama.ok=$OLLAMA_OK"
    [ "$GEMINI_KEY" = "true" ] && ok "gemini.api_key_present=true" || warn "gemini.api_key 부재 (Gemini 옵션 disabled)"

    # 6 기능별 상태 출력
    echo
    echo "  ┌─── 기능별 LLM 도달 상태 ──────────────────────"
    echo "$DIAG" | jq -r '.features[] | "  │ \(if .ok then "✓" else "✗" end) [\(.id)] \(.name) — uses=[\(.uses | join(","))] via=\(.via)"'
    echo "  └────────────────────────────────────────────"
    echo "  $SUMMARY"
else
    warn "llm-status 응답 없음 — Cloud Run revision 활성 지연 가능"
fi

# ── 완료 + foreground 대기 ──────────────────────
echo
echo "═══════════════════════════════════════════════════════"
echo "  ✅ 시연 환경 활성 — 모든 기능(A~F) 에 적용됨"
echo "═══════════════════════════════════════════════════════"
echo "  📡 Tunnel:    $TUNNEL_URL"
echo "  🌐 Frontend (전 기능 적용):"
echo "     - A 문서 검색:    $HOSTING_BASE/search"
echo "     - B 문서 작성:    $HOSTING_BASE/draft"
echo "     - C AI 도우미:    $HOSTING_BASE/chat"
echo "     - D 컴플라이언스: $HOSTING_BASE/compliance"
echo "     - E 인사 관리:    $HOSTING_BASE/admin"
echo "     - F 설비/공정:    $HOSTING_BASE/equipment"
echo "  🩺 통합 진단:  $HOSTING_BASE/api/health/llm-status"
echo "  ⏹ 종료:       Docker Desktop ▶ Stop 버튼 (또는 docker compose down)"
echo
echo "▶ cloudflared foreground 유지 — 컨테이너 alive"

# cloudflared 가 죽으면 컨테이너도 종료 → trap 동작 → cleanup
wait "$CF_PID"
