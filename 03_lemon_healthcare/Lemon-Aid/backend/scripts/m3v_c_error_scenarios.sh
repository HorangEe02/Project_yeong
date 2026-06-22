#!/usr/bin/env bash
#
# M-3-V.C — supplement/register e2e 오류 시나리오 자동 검증.
#
# 4 case 의 expected HTTP status 를 curl 로 확인하고 PASS/FAIL 출력.
# 모바일 측 `_mapDioError` 9 case 매핑 중 e2e 검증 가능한 4 케이스를 다룬다.
#
# !!!!! DEV 환경 전용 !!!!!
# docker compose stop/start, 강제 DB 정지를 포함하므로 운영/staging 에서 절대
# 실행하지 마라. ENVIRONMENT=development 가 .env 에 명시된 backend 에서만 호출.
#
# Usage:
#   export TOKEN=$(cat .test-jwt)               # 유효한 access JWT
#   export EXPIRED_TOKEN=$(cat .test-jwt-old)   # 만료된 access JWT (선택)
#   export FIXTURE=tests/fixtures/supplement_labels/local-multivitamin-0001.jpg
#   export BASE_URL=http://localhost:8000       # 기본값
#   bash scripts/m3v_c_error_scenarios.sh
#
# Reference:
#   docs/track-d/m3v-c-error-scenarios.md
#   /Users/yeong/.claude/plans/twinkly-splashing-hejlsberg.md Phase M-3-V.C

set -uo pipefail

# -----------------------------------------------------------------------------
# 환경 + 안전 가드
# -----------------------------------------------------------------------------
BASE_URL="${BASE_URL:-http://localhost:8000}"
FIXTURE="${FIXTURE:-tests/fixtures/supplement_labels/local-multivitamin-0001.jpg}"
TOKEN="${TOKEN:?ERROR: Set TOKEN env (유효한 access JWT) 후 재실행}"
RATE_LIMIT_BUFFER=2  # 분당 한도(10) + 여유 → 12회 시도

if [[ ! "$BASE_URL" =~ localhost|127\.0\.0\.1 ]]; then
    echo "ERROR: BASE_URL ($BASE_URL) 가 localhost 가 아님. dev 환경 전용 script."
    exit 1
fi

if [[ ! -f "$FIXTURE" ]]; then
    echo "ERROR: FIXTURE ($FIXTURE) 파일이 없음. tests/fixtures/supplement_labels/ 에 추가."
    exit 1
fi

REGISTER_URL="${BASE_URL}/api/v1/supplements/register"
ME_URL="${BASE_URL}/api/v1/users/me"
HEALTH_URL="${BASE_URL}/health"

PASS_COUNT=0
FAIL_COUNT=0

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "  ✓ PASS — $1"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "  ✗ FAIL — $1"
}

curl_status() {
    # $1 = method, $2 = URL, additional curl args follow
    local method="$1"
    local url="$2"
    shift 2
    curl -sS -o /dev/null -w "%{http_code}" -X "$method" "$@" "$url" 2>&1
}

# -----------------------------------------------------------------------------
# 사전 점검 — backend 가동중인지
# -----------------------------------------------------------------------------
echo "=== Pre-check: backend up? ==="
HEALTH_STATUS=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL" 2>&1 || echo "000")
if [[ "$HEALTH_STATUS" != "200" ]]; then
    echo "ERROR: $HEALTH_URL → $HEALTH_STATUS (200 기대). 먼저 uvicorn 실행."
    exit 1
fi
echo "  backend healthy → $HEALTH_STATUS"

# -----------------------------------------------------------------------------
# Case 1 — Rate limit 429
# (제일 먼저 — 다른 case 가 토큰을 소진하지 않도록)
# -----------------------------------------------------------------------------
echo ""
echo "=== Case 1: Rate limit 429 ==="
LIMIT=10
ATTEMPTS=$((LIMIT + RATE_LIMIT_BUFFER))  # 12회
LAST_STATUS=""
HIT_429=false

for i in $(seq 1 $ATTEMPTS); do
    STATUS=$(curl_status POST "$REGISTER_URL" \
        -H "Authorization: Bearer $TOKEN" \
        -F "image=@$FIXTURE")
    LAST_STATUS="$STATUS"
    if [[ "$STATUS" == "429" ]]; then
        HIT_429=true
        echo "  attempt $i → 429 (rate limit hit)"
        break
    elif [[ "$STATUS" != "200" && "$STATUS" != "422" ]]; then
        # 200 (정상) 또는 422 (OCR 인식 실패 — fixture 가 작은 이미지면 가능) 외는 경고
        echo "  WARN attempt $i → $STATUS"
    fi
done

if $HIT_429; then
    pass "Case 1 — 11회 안에 429 hit"
else
    fail "Case 1 — $ATTEMPTS 회 시도해도 429 미발생 (last=$LAST_STATUS). rate_limit_register_per_minute=$LIMIT 일치하는가?"
fi

# -----------------------------------------------------------------------------
# Case 2 — 401 만료/잘못된 토큰
# -----------------------------------------------------------------------------
echo ""
echo "=== Case 2: 401 invalid token ==="
INVALID_TOKEN="invalid.jwt.placeholder"
STATUS=$(curl_status GET "$ME_URL" -H "Authorization: Bearer $INVALID_TOKEN")
if [[ "$STATUS" == "401" ]]; then
    pass "Case 2 — invalid token → 401"
else
    fail "Case 2 — expected 401, got $STATUS"
fi

# (선택) 만료 토큰 — EXPIRED_TOKEN env 가 있을 때만
if [[ -n "${EXPIRED_TOKEN:-}" ]]; then
    STATUS=$(curl_status GET "$ME_URL" -H "Authorization: Bearer $EXPIRED_TOKEN")
    if [[ "$STATUS" == "401" ]]; then
        pass "Case 2b — expired token → 401"
    else
        fail "Case 2b — expired token expected 401, got $STATUS"
    fi
fi

# -----------------------------------------------------------------------------
# Case 3 — 500 서버 오류 (postgres stop)
# -----------------------------------------------------------------------------
echo ""
echo "=== Case 3: 500 server error (postgres stop) ==="
echo "  → docker compose stop postgres"
docker compose stop postgres > /dev/null 2>&1 || {
    fail "Case 3 — docker compose stop postgres 실패"
    SKIP_3=true
}

if [[ "${SKIP_3:-}" != "true" ]]; then
    sleep 1  # postgres 종료 대기
    STATUS=$(curl_status GET "$ME_URL" -H "Authorization: Bearer $TOKEN")
    if [[ "$STATUS" == "500" || "$STATUS" == "503" ]]; then
        pass "Case 3 — postgres down → $STATUS (DB 접근 endpoint 실패)"
    else
        fail "Case 3 — expected 500/503, got $STATUS"
    fi

    echo "  → docker compose start postgres (복구)"
    docker compose start postgres > /dev/null 2>&1
    # postgres healthy 까지 대기 (최대 30s)
    for i in $(seq 1 30); do
        sleep 1
        if curl -sS -o /dev/null --max-time 2 -H "Authorization: Bearer $TOKEN" "$ME_URL" | grep -q .; then
            break
        fi
        if [[ $(curl -sS -o /dev/null -w "%{http_code}" --max-time 2 -H "Authorization: Bearer $TOKEN" "$ME_URL") == "200" ]]; then
            echo "  postgres 복구 ($i s)"
            break
        fi
    done
fi

# -----------------------------------------------------------------------------
# Case 4 — connection refused (backend stop)
# (제일 마지막 — 다른 case 의 backend 의존성 파괴 방지)
# -----------------------------------------------------------------------------
echo ""
echo "=== Case 4: backend down → connection refused ==="
echo "  → 사용자가 직접 uvicorn 종료 + 재가동 필요 (script 가 backend 자체는 못 멈춤)"
echo "    1) Ctrl+C 로 uvicorn 종료 또는 \`pkill -f 'uvicorn src.main'\`"
echo "    2) curl $HEALTH_URL 시도 → connection refused 확인"
echo "    3) uvicorn 재시작 후 보고서에 결과 기입"
echo "  (자동 검증 미실행 — 수동 단계 안내만)"

# -----------------------------------------------------------------------------
# 결과 요약
# -----------------------------------------------------------------------------
echo ""
echo "================================================"
echo "  M-3-V.C 자동 오류 시나리오 결과"
echo "  PASS: $PASS_COUNT"
echo "  FAIL: $FAIL_COUNT"
echo "================================================"

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo "  → 모든 자동 case 통과. 매뉴얼 2 case 진행:"
    echo "      - 권한 거부 (sim)"
    echo "      - 동의 누락 (DB consent_records 삭제 후 sim 업로드)"
    echo "  → docs/track-d/m3v-c-error-scenarios.md 참조"
    exit 0
else
    echo "  → 실패 case 분석 필요. 보고서 §결과 갱신."
    exit 1
fi
