#!/usr/bin/env bash
# v4.1 + v4.2 + v4.3 자동 검증 (Docker 환경) — v4.3 B1.
#
# 자동 가능한 항목 (curl 응답 채취):
#   - Endpoint 응답 + status code
#   - SSE 5초 sample
#   - 401 처리
#   - scope=mine 부서 필터
#
# 사람 손이 필요한 시나리오 4종 (오프라인 / DB DELETE 후 시각 확인 / UI 인터랙션) 은
# MANUAL_CHECKS.md 참조.
#
# 사용:
#   export AJIN_BASE_URL=http://localhost:8080
#   export JWT=$(cat /tmp/jwt)             # 사전에 로그인 endpoint 로 토큰 확보
#   bash scripts/verify_v41_p41.sh [--out OUT_DIR]
#
# 산출물: update_log/v4.3_followups/verify_run_<ts>/ 디렉토리
#   - run.log
#   - responses/*.json | *.txt
#   - SUMMARY.md

set -euo pipefail

# ─── 인자 ──────────────────────────────────────────────
OUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/update_log/v4.3_followups/verify_run_$TS}"
mkdir -p "$OUT_DIR/responses"

BASE="${AJIN_BASE_URL:-http://localhost:8080}"
JWT="${JWT:-}"

log() { printf '[%s] %s\n' "$(date +%T)" "$*" | tee -a "$OUT_DIR/run.log"; }

# ─── PASS/FAIL 카운터 ──────────────────────────────────
PASS=0
FAIL=0

record() {
  # usage: record SCENARIO_NAME http_code expected_code
  local name="$1" actual="$2" expected="$3"
  if [[ "$actual" == "$expected" ]]; then
    log "  ✅ $name  → HTTP $actual"
    PASS=$((PASS+1))
  else
    log "  ❌ $name  → HTTP $actual (expected $expected)"
    FAIL=$((FAIL+1))
  fi
}

curl_auth() {
  # usage: curl_auth METHOD PATH [extra_curl_args...]
  local method="$1" path="$2"; shift 2
  if [[ -n "$JWT" ]]; then
    curl -sS -X "$method" -H "Authorization: Bearer $JWT" "$@" "$BASE$path"
  else
    curl -sS -X "$method" "$@" "$BASE$path"
  fi
}

# ─── 시작 ──────────────────────────────────────────────
log "verify_v41_p41 start"
log "BASE=$BASE   JWT_set=$([[ -n $JWT ]] && echo yes || echo no)"

# 0. /healthz (인증 불필요)
log "[0] healthz"
code=$(curl -sS -o "$OUT_DIR/responses/healthz.json" -w "%{http_code}" "$BASE/healthz" || echo 000)
record "healthz" "$code" "200"

# 1. equipment/dashboard/overview (Happy Path)
log "[1] equipment overview"
code=$(curl_auth GET "/api/equipment/dashboard/overview" \
  -o "$OUT_DIR/responses/overview.json" -w "%{http_code}" || echo 000)
record "1·equipment/overview" "$code" "200"

# 2. equipment health (v4.1 신설)
log "[2] equipment health"
code=$(curl_auth GET "/api/equipment/health" \
  -o "$OUT_DIR/responses/equipment_health.json" -w "%{http_code}" || echo 000)
record "2·equipment/health" "$code" "200"

# 3. compliance alarms recent (M1)
log "[3] compliance alarms"
code=$(curl_auth GET "/api/compliance/alarms/recent?limit=50" \
  -o "$OUT_DIR/responses/alarms_recent.json" -w "%{http_code}" || echo 000)
record "3·compliance/alarms/recent" "$code" "200"

# 4. compliance alarms scope=mine (P5)
log "[4] alarms scope=mine"
code=$(curl_auth GET "/api/compliance/alarms/recent?scope=mine" \
  -o "$OUT_DIR/responses/alarms_mine.json" -w "%{http_code}" || echo 000)
record "4·alarms scope=mine" "$code" "200"

# 5. SSE stream — 5초 sample
log "[5] SSE stream 5s sample"
if [[ -n "$JWT" ]]; then
  timeout 5 curl -sN -H "Authorization: Bearer $JWT" \
    "$BASE/api/compliance/alarms/stream?interval=2" \
    > "$OUT_DIR/responses/stream_5s.txt" || true
fi
n_events=$(grep -c '^data:' "$OUT_DIR/responses/stream_5s.txt" 2>/dev/null || echo 0)
if [[ $n_events -ge 1 ]]; then
  log "  ✅ 5·SSE stream  → $n_events events captured"; PASS=$((PASS+1))
else
  log "  ❌ 5·SSE stream  → $n_events events (need ≥ 1)"; FAIL=$((FAIL+1))
fi

# 6. 401 — 잘못된 토큰
log "[6] 401 invalid token"
code=$(curl -sS -o "$OUT_DIR/responses/401.json" -w "%{http_code}" \
  -H "Authorization: Bearer invalid_token" \
  "$BASE/api/equipment/dashboard/overview" || echo 000)
record "6·401 invalid token" "$code" "401"

# 7. inspection upload-csv (v4.3) — dry-run 빈 파일 422
log "[7] inspection upload dry-run (빈 페이로드 → 400)"
code=$(curl_auth POST "/api/equipment/inspection/upload-csv?dry_run=true" \
  -F "file=@/dev/null" \
  -o "$OUT_DIR/responses/inspection_upload_empty.json" -w "%{http_code}" || echo 000)
# 빈 파일은 400 거부 기대 (또는 422). 둘 다 허용.
if [[ "$code" == "400" || "$code" == "422" ]]; then
  log "  ✅ 7·inspection upload empty file → HTTP $code (400/422 허용)"; PASS=$((PASS+1))
else
  log "  ❌ 7·inspection upload empty file → HTTP $code (400/422 기대)"; FAIL=$((FAIL+1))
fi

# 8. ingest-log/recent (v4.3)
log "[8] ingest-log recent"
code=$(curl_auth GET "/api/equipment/inspection/ingest-log/recent?limit=10" \
  -o "$OUT_DIR/responses/ingest_log.json" -w "%{http_code}" || echo 000)
# role_level<3 면 403, 충분하면 200
if [[ "$code" == "200" || "$code" == "403" ]]; then
  log "  ✅ 8·ingest-log/recent → HTTP $code"; PASS=$((PASS+1))
else
  log "  ❌ 8·ingest-log/recent → HTTP $code"; FAIL=$((FAIL+1))
fi

# ─── SUMMARY ───────────────────────────────────────────
SUMMARY="$OUT_DIR/SUMMARY.md"
{
  echo "# verify_v41_p41 — $TS"
  echo ""
  echo "Base: $BASE"
  echo ""
  echo "| 결과 | 카운트 |"
  echo "|---|---|"
  echo "| PASS | $PASS |"
  echo "| FAIL | $FAIL |"
  echo ""
  echo "## 자동 검증 항목"
  echo ""
  echo "응답 본문: \`responses/\` 디렉토리"
  echo ""
  echo "## 수동 시나리오"
  echo ""
  echo "- VERIFICATION_GUIDE.md 시나리오 2 (Backend 다운 ErrorState)"
  echo "- 시나리오 3 (오프라인 토스트)"
  echo "- 시나리오 4 (DB DELETE 후 빈 상태)"
  echo "- 시나리오 9 (Deep-link 하이라이트)"
  echo ""
  echo "→ MANUAL_CHECKS.md 절차 따라 screenshots/ 보존"
} > "$SUMMARY"

log "verify_v41_p41 done  PASS=$PASS FAIL=$FAIL  →  $OUT_DIR"
exit $([[ $FAIL -eq 0 ]] && echo 0 || echo 1)
