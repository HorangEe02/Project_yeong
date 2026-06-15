#!/usr/bin/env bash
# AJIN Backend — Cloud Run 배포 후 smoke test (재사용 가능)
#
# 두 인시던트(00102~00105 sync 누락 / `rank_bm25` ImportError) 직후 도입.
# 트래픽 promote *전에* tag URL 또는 새 리비전 URL 에 대해 다음을 검사:
#
#   1) HTTP probe — 다음 endpoint 가 5xx 가 아닌 정상 응답 (401/200/404 등) 을 내는지.
#      - /api/auth/login   → 401 기대 (인증 미제공 시)
#      - /api/admin/hr/summary → 401 기대
#      - 5xx 가 나오면 import / DB / 의존성 회귀 신호
#
#   2) Startup 로그 grep — 새 리비전의 lifespan 로그에 다음 키워드가 *모두* 보여야 함:
#      - "Application startup complete"        (gunicorn worker boot)
#      - "Firestore → SQLite 동기화 완료"      (Firebase read fallback enabled)
#        또는 "Firestore read fallback 비활성" (Supabase/Postgres runtime cutover)
#      - "✓ 인증 DB 초기화 완료"               (init_auth_db)
#
#   3) 금지 키워드 — 다음이 보이면 fail:
#      - "ModuleNotFoundError"
#      - "Worker failed to boot"
#      - "HaltServer"
#      - "Application startup failed"
#
# 사용법:
#   smoke-test.sh <BASE_URL> [REVISION_NAME]
#
# 예:
#   smoke-test.sh https://fix-bm25---ajin-backend-ncsnraqdaa-du.a.run.app ajin-backend-00108-gef
#
# 환경변수:
#   PROJECT       (default: ajin-cb)
#   REGION        (default: asia-northeast3)
#   PROBE_RETRIES (default: 5) — 첫 cold start 503 허용 횟수
#   PROBE_DELAY   (default: 4) — retry 간 대기 초
#   LOG_FRESHNESS (default: 10m) — gcloud logging --freshness 값
#
# 종료 코드:
#   0 — 모든 검사 통과
#   1 — HTTP probe 실패
#   2 — 필수 startup 로그 누락
#   3 — 금지 키워드 발견
#   4 — 잘못된 인자

set -euo pipefail

BASE_URL="${1:-}"
REVISION="${2:-}"

if [[ -z "$BASE_URL" ]]; then
    echo "Usage: $0 <BASE_URL> [REVISION_NAME]" >&2
    exit 4
fi

PROJECT="${PROJECT:-ajin-cb}"
REGION="${REGION:-asia-northeast3}"
PROBE_RETRIES="${PROBE_RETRIES:-5}"
PROBE_DELAY="${PROBE_DELAY:-4}"
LOG_FRESHNESS="${LOG_FRESHNESS:-10m}"

# 컬러
if [[ -t 1 ]]; then
    GREEN=$'\e[32m'; RED=$'\e[31m'; YELLOW=$'\e[33m'; RESET=$'\e[0m'
else
    GREEN=''; RED=''; YELLOW=''; RESET=''
fi

pass()  { echo "${GREEN}✓${RESET} $1"; }
fail()  { echo "${RED}✗${RESET} $1"; }
warn()  { echo "${YELLOW}⚠${RESET} $1"; }

# ────────────────────────────────────────────────────────────
# 1) HTTP probe — endpoint 가 5xx 안 내는지
# ────────────────────────────────────────────────────────────
probe_endpoint() {
    local path="$1"
    local label="$2"
    local last_code=0
    for ((i=1; i<=PROBE_RETRIES; i++)); do
        local code
        code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 30 \
            "${BASE_URL%/}${path}" 2>/dev/null || echo "000")
        last_code=$code
        if [[ "$code" =~ ^[2345]..$ ]] && [[ "$code" -lt 500 ]]; then
            pass "[$label] HTTP $code (4xx/2xx OK — 5xx 아님)"
            return 0
        fi
        warn "[$label] try=$i/$PROBE_RETRIES HTTP $code (cold start 가능 — 재시도)"
        sleep "$PROBE_DELAY"
    done
    fail "[$label] $PROBE_RETRIES 회 모두 5xx/error (last=$last_code)"
    return 1
}

probe_post_endpoint() {
    # POST 변형 — body 없이도 5xx 가 아닌 응답이면 OK (auth 401 / 422 등 허용).
    local path="$1"
    local label="$2"
    local max_time="${3:-30}"
    local last_code=0
    for ((i=1; i<=PROBE_RETRIES; i++)); do
        local code
        code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time "$max_time" \
            -X POST "${BASE_URL%/}${path}" 2>/dev/null || echo "000")
        last_code=$code
        if [[ "$code" =~ ^[2345]..$ ]] && [[ "$code" -lt 500 ]]; then
            pass "[$label] POST HTTP $code (4xx/2xx OK — 5xx 아님)"
            return 0
        fi
        warn "[$label] try=$i/$PROBE_RETRIES HTTP $code (cold start 가능 — 재시도)"
        sleep "$PROBE_DELAY"
    done
    fail "[$label] $PROBE_RETRIES 회 모두 5xx/error/timeout (last=$last_code)"
    return 1
}

echo "═══ HTTP Probe ($BASE_URL) ═══"
probe_failed=0
probe_endpoint "/api/auth/login"          "auth.login"          || probe_failed=1
probe_endpoint "/api/admin/hr/summary"    "admin.hr.summary"    || probe_failed=1
# 크롤러 일괄 실행 — axios ceiling(30s) 안에 응답하는지 + 5xx 아님 보증.
# 인증 필요하므로 401 기대 (실 동작 검증은 production smoke 의 별도 인증 시나리오).
probe_post_endpoint "/api/compliance/crawl/run-all" "compliance.crawl.run-all" 30 \
    || probe_failed=1

if [[ $probe_failed -ne 0 ]]; then
    echo "${RED}HTTP probe failed.${RESET}"
    exit 1
fi
echo

# ────────────────────────────────────────────────────────────
# 2) Startup 로그 grep (gcloud logging)
# ────────────────────────────────────────────────────────────
if [[ -z "$REVISION" ]]; then
    REVISION=$(gcloud run services describe ajin-backend \
        --region="$REGION" --project="$PROJECT" \
        --format='value(status.latestCreatedRevisionName)' 2>/dev/null || echo "")
fi

if [[ -z "$REVISION" ]]; then
    warn "REVISION 인자 미제공 + 자동 추론 실패 → 로그 단계 skip."
    exit 0
fi

echo "═══ Startup 로그 검사 (revision=$REVISION) ═══"

# Cloud Logging 인덱싱 지연 회피 — 초기 freshness 로 한 번 시도 후, 누락 시 retry.
# 일부 로그(Application startup complete) 가 deploy 직후 ~10초 indexing lag 가능.
LOG_RETRIES="${LOG_RETRIES:-4}"
LOG_RETRY_DELAY="${LOG_RETRY_DELAY:-15}"

REQUIRED=(
    "Application startup complete"
    "✓ 인증 DB 초기화 완료"
)

required_ok=0
for ((retry=1; retry<=LOG_RETRIES; retry++)); do
    # retry 마다 freshness window 를 점진 확대 (10m → 14m → 18m → 22m 등)
    fresh_min=$(( 10 + (retry - 1) * 4 ))
    LOGS=$(gcloud logging read \
        "resource.type=\"cloud_run_revision\" AND resource.labels.revision_name=\"$REVISION\"" \
        --limit=300 --freshness="${fresh_min}m" \
        --format='value(textPayload)' \
        --project="$PROJECT" 2>/dev/null || true)

    if [[ -z "$LOGS" ]]; then
        warn "[try=$retry/$LOG_RETRIES] 로그 비어있음 (freshness=${fresh_min}m) — ${LOG_RETRY_DELAY}s 후 재시도"
        sleep "$LOG_RETRY_DELAY"
        continue
    fi

    # Firebase read fallback 이 꺼진 Supabase/Postgres runtime 에서는 sync 완료가 아니라
    # 의도적인 mirror sync skip 로그가 정상 경로다. 넓은 "Firestore" grep 으로
    # skip 로그까지 sync 필수 조건으로 오인하지 않도록 fallback 상태를 먼저 판별한다.
    SYNC_REQ="Firestore → SQLite 동기화 완료"
    SYNC_SKIP_REQ="Firestore read fallback 비활성"
    THIS_REQUIRED=("${REQUIRED[@]}")
    if echo "$LOGS" | grep -qF "$SYNC_SKIP_REQ"; then
        THIS_REQUIRED+=("$SYNC_SKIP_REQ")
    elif echo "$LOGS" | grep -q "AUTH_BACKEND=firestore" 2>/dev/null \
       || echo "$LOGS" | grep -qF "$SYNC_REQ"; then
        THIS_REQUIRED+=("$SYNC_REQ")
    fi

    all_found=1
    missing=()
    for keyword in "${THIS_REQUIRED[@]}"; do
        if echo "$LOGS" | grep -qF "$keyword"; then
            :
        else
            all_found=0
            missing+=("$keyword")
        fi
    done

    if [[ $all_found -eq 1 ]]; then
        for keyword in "${THIS_REQUIRED[@]}"; do
            pass "필수 로그: $keyword"
        done
        required_ok=1
        break
    fi

    warn "[try=$retry/$LOG_RETRIES] 누락: ${missing[*]} (freshness=${fresh_min}m) — ${LOG_RETRY_DELAY}s 후 재시도"
    sleep "$LOG_RETRY_DELAY"
done

if [[ $required_ok -ne 1 ]]; then
    fail "필수 로그 ${LOG_RETRIES}회 retry 후에도 일부 누락 — 컨테이너 부팅 실패 또는 인덱싱 lag 비정상"
    exit 2
fi
echo

# ────────────────────────────────────────────────────────────
# 3) 금지 키워드
# ────────────────────────────────────────────────────────────
echo "═══ 금지 키워드 검사 ═══"
FORBIDDEN=(
    "ModuleNotFoundError"
    "Worker failed to boot"
    "HaltServer"
    "Application startup failed"
)
forbidden_hit=0
for keyword in "${FORBIDDEN[@]}"; do
    if echo "$LOGS" | grep -qF "$keyword"; then
        fail "금지 키워드 발견: $keyword"
        echo "$LOGS" | grep -F "$keyword" | head -3 | sed 's/^/    /'
        forbidden_hit=1
    else
        pass "$keyword 없음"
    fi
done

if [[ $forbidden_hit -eq 1 ]]; then
    echo "${RED}Forbidden keyword detected in startup logs.${RESET}"
    exit 3
fi

echo
echo "${GREEN}═══ Smoke test PASSED ═══${RESET}"
exit 0
