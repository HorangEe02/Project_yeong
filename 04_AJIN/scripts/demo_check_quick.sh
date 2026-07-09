#!/usr/bin/env bash
# demo_check_quick.sh — 시연 D-Day T-120 빠른 인프라 점검 (영역 A)
#
# 사용:
#   bash scripts/demo_check_quick.sh
#   bash scripts/demo_check_quick.sh --no-vercel
#
# 종료 코드: 0=전체 PASS, 1=FAIL 있음

set -euo pipefail

# ---------------------------------------------------------------------------
# 색상
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; BOLD=''; NC=''
fi

PASS_ICON="✓"
FAIL_ICON="✗"
WARN_ICON="△"

# ---------------------------------------------------------------------------
# 옵션 파싱
# ---------------------------------------------------------------------------
NO_VERCEL=0
for arg in "$@"; do
    case "$arg" in
        --no-vercel) NO_VERCEL=1 ;;
    esac
done

OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
SSD_PATH="<EXTERNAL_DRIVE>/.ollama/models"
VERCEL_URL="https://ajin-ai-assistant-frontend.vercel.app/"

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------
pass() {
    echo -e "    ${GREEN}${PASS_ICON}${NC} $1  ${GREEN}$2${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo -e "    ${RED}${FAIL_ICON}${NC} $1  ${RED}$2${NC}"
    echo -e "       ${YELLOW}$3${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

warn() {
    echo -e "    ${YELLOW}${WARN_ICON}${NC} $1  ${YELLOW}$2${NC}"
    if [ -n "${3:-}" ]; then
        echo -e "       ${YELLOW}$3${NC}"
    fi
    WARN_COUNT=$((WARN_COUNT + 1))
}

# ---------------------------------------------------------------------------
# 헤더
# ---------------------------------------------------------------------------
TODAY=$(date +%F)
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  AJIN Demo Quick Check (Area A) — ${TODAY}${NC}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}▶ Area A: Infrastructure (5개 체크)${NC}"

# ---------------------------------------------------------------------------
# A1: 외장 SSD 마운트
# ---------------------------------------------------------------------------
if [ -d "$SSD_PATH" ]; then
    pass "A1" "외장 SSD 마운트 확인: $SSD_PATH"
else
    fail "A1" "외장 SSD 미마운트" "→ 해결: 외장 SSD를 USB 포트에 연결하세요"
fi

# ---------------------------------------------------------------------------
# A2: Ollama API + 모델 수
# ---------------------------------------------------------------------------
OLLAMA_RESP=$(curl -fsS --max-time 10 "${OLLAMA_URL}/api/tags" 2>/dev/null || echo "ERROR")
if [ "$OLLAMA_RESP" = "ERROR" ]; then
    fail "A2" "Ollama API 응답 없음 (${OLLAMA_URL})" "→ 해결: ollama serve (또는 Ollama 앱 실행)"
else
    # Python으로 모델 수 파싱 (jq 없이도 동작)
    MODEL_COUNT=$(python3 -c "
import json, sys
try:
    data = json.loads('''${OLLAMA_RESP}''')
    print(len(data.get('models', [])))
except Exception as e:
    print(0)
" 2>/dev/null || echo 0)
    if [ "$MODEL_COUNT" -ge 17 ] 2>/dev/null; then
        pass "A2" "Ollama API 응답 (${MODEL_COUNT}개 모델)"
    elif [ "$MODEL_COUNT" -gt 0 ] 2>/dev/null; then
        warn "A2" "Ollama 모델 수 부족: ${MODEL_COUNT}개 (기대 ≥17)" "→ 해결: ollama pull 로 추가 모델 다운로드"
    else
        warn "A2" "Ollama 모델 수 파싱 실패 (API는 응답)" "→ 해결: curl ${OLLAMA_URL}/api/tags 직접 확인"
    fi
fi

# ---------------------------------------------------------------------------
# A3: bge-m3 모델 확인
# ---------------------------------------------------------------------------
if echo "$OLLAMA_RESP" | grep -q "bge-m3" 2>/dev/null; then
    pass "A3" "bge-m3 모델 확인"
else
    OLLAMA_LIST=$(ollama list 2>/dev/null | grep "bge-m3" || echo "")
    if [ -n "$OLLAMA_LIST" ]; then
        pass "A3" "bge-m3 모델 확인 (ollama list)"
    else
        fail "A3" "bge-m3 모델 없음" "→ 해결: ollama pull bge-m3"
    fi
fi

# ---------------------------------------------------------------------------
# A4: Supabase 연결 (환경변수 기반)
# ---------------------------------------------------------------------------
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SECRET_KEY:-}" ]; then
    warn "A4" "Supabase 환경변수 미설정" "→ 해결: .env 파일에 SUPABASE_URL + SUPABASE_SECRET_KEY 설정"
else
    # 단순 HTTP 핑 (REST API)
    SUPA_PING=$(curl -fsS --max-time 10 \
        -H "apikey: ${SUPABASE_SECRET_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SECRET_KEY}" \
        "${SUPABASE_URL}/rest/v1/" 2>/dev/null && echo "OK" || echo "ERROR")
    if [ "$SUPA_PING" = "OK" ]; then
        pass "A4" "Supabase REST API 응답"
    else
        fail "A4" "Supabase 연결 실패" "→ 해결: Supabase 대시보드에서 프로젝트 상태 확인"
    fi
fi

# ---------------------------------------------------------------------------
# A5: Vercel 프론트엔드
# ---------------------------------------------------------------------------
if [ "$NO_VERCEL" = "1" ]; then
    echo -e "    ${NC}○${NC} A5  Vercel 프론트엔드 — ${YELLOW}생략 (--no-vercel)${NC}"
else
    VERCEL_HTTP=$(curl -fsS --max-time 15 -o /dev/null -w "%{http_code}" "$VERCEL_URL" 2>/dev/null || echo "000")
    if [ "$VERCEL_HTTP" = "200" ]; then
        pass "A5" "Vercel 프론트엔드 HTTP ${VERCEL_HTTP}"
    elif [ "$VERCEL_HTTP" = "000" ]; then
        warn "A5" "Vercel 접속 실패 (인터넷 연결 확인)" "→ 오프라인 시연 가능. --no-vercel 플래그 사용 가능"
    else
        warn "A5" "Vercel HTTP ${VERCEL_HTTP} (기대 200)" "→ Vercel 대시보드 확인"
    fi
fi

# ---------------------------------------------------------------------------
# 결과 요약
# ---------------------------------------------------------------------------
TOTAL=$((PASS_COUNT + FAIL_COUNT + WARN_COUNT))
echo ""
echo -e "  ${BOLD}──────────────────────────────────────────────────────────────${NC}"
if [ "$FAIL_COUNT" -eq 0 ]; then
    if [ "$WARN_COUNT" -eq 0 ]; then
        echo -e "  ${GREEN}${BOLD}✅  ${TOTAL}/${TOTAL} PASS — 인프라 점검 완료${NC}"
    else
        echo -e "  ${YELLOW}${BOLD}△   ${PASS_COUNT}/${TOTAL} PASS, ${WARN_COUNT} WARN — 시연 전 확인 권장${NC}"
    fi
else
    echo -e "  ${RED}${BOLD}❌  ${FAIL_COUNT} FAIL / ${WARN_COUNT} WARN / ${PASS_COUNT} PASS — 시연 전 수정 필요${NC}"
fi
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""

# 종료 코드
if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi
exit 0
