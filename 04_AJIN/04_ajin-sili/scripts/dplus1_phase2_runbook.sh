#!/usr/bin/env bash
# D+1 (2026-06-12) Phase 2 LongLLMLingua 활성 runbook.
# Goal 4: "LLMLINGUA_ENABLED=true 환경변수 적용 (D+1 = 2026-06-12 이후)"
# Goal 5: "A/B 비교 — 압축 전/후 응답 품질 + 토큰 절감률 측정"
#
# 본 스크립트는 D+1 이전 사전 실행 금지 — 본선 (2026-06-10~11) 시연 동안
# 환경 변경으로 인한 회귀 위험 회피.
#
# 사용:
#   bash scripts/dplus1_phase2_runbook.sh           # dry-run (명령만 표시)
#   bash scripts/dplus1_phase2_runbook.sh --apply   # 실제 실행

set -euo pipefail

PROJECT="ajin-cb"
REGION="asia-northeast3"
SERVICE="ajin-backend"
TODAY=$(date +%Y-%m-%d)
DPLUS1="2026-06-12"

cd "$(dirname "$0")/.."

if [[ "$TODAY" < "$DPLUS1" ]]; then
  echo "⚠️  현재 $TODAY — D+1 ($DPLUS1) 이전입니다."
  echo "   본선 종료 후 실행하세요. (사용자 §11 #5 확정)"
  if [[ "${1:-}" != "--force" ]]; then
    echo "   강제 진행은 --force 옵션 사용."
    exit 1
  fi
  echo "   --force 감지 — 진행합니다 (시연 환경 회귀 위험 인지)."
fi

DRY_RUN=1
if [[ "${1:-}" == "--apply" || "${2:-}" == "--apply" ]]; then
  DRY_RUN=0
fi

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY-RUN] $*"
  else
    echo "[APPLY] $*"
    "$@"
  fi
}

echo "============================================================"
echo "D+1 Phase 2 LongLLMLingua 활성 runbook ($TODAY)"
echo "============================================================"

# Step 1: Cloud Run env 활성
echo
echo "[Step 1/4] LLMLINGUA_ENABLED=true 환경변수 적용"
run gcloud run services update "$SERVICE" \
  --region="$REGION" --project="$PROJECT" \
  --update-env-vars="LLMLINGUA_ENABLED=true,LLMLINGUA_TARGET_RATIO=0.5,LLMLINGUA_THRESHOLD_CHARS=2000"

# Step 2: 새 revision traffic 이동
echo
echo "[Step 2/4] 새 revision 100% traffic"
run gcloud run services update-traffic "$SERVICE" \
  --region="$REGION" --project="$PROJECT" --to-latest

# Step 3: smoke 검증
echo
echo "[Step 3/4] smoke 검증 (health + chat 1회)"
URL="https://ajin-cb.web.app"
run curl -fsS "$URL/api/health" -o /dev/null
echo "  → /api/health 정상"
run curl -fsS "$URL/api/onboarding/health" -o /dev/null
echo "  → /api/onboarding/health 정상"

# Step 4: A/B 비교 시작
echo
echo "[Step 4/4] A/B 비교 (compression-only 모드, 즉시 실행 가능)"
run python3 scripts/compare_lingua_ab.py \
  --mode compression-only \
  --queries data/eval/golden_qa_kosha.jsonl \
  --output data/eval/lingua_ab_results_$(date +%Y%m%d).json

# D+7 measure script 안내
echo
echo "============================================================"
echo "✅ D+1 활성 완료. D+7 ($(date -j -v+6d -f %Y-%m-%d "$DPLUS1" +%Y-%m-%d 2>/dev/null || echo 2026-06-18)) 에 measure 스크립트 실행 권장:"
echo "============================================================"
cat <<EOF

# audit log 수집 (지난 7일)
gcloud logging read \\
  'resource.type=cloud_run_revision AND textPayload:"crag="' \\
  --limit 10000 \\
  --format='value(textPayload)' \\
  --project=$PROJECT \\
  > /tmp/audit_crag_dplus7.log

# verdict 분포 측정 + threshold 시뮬레이션
python3 scripts/measure_crag_verdict_distribution.py \\
  --log /tmp/audit_crag_dplus7.log \\
  --upper-candidates "0.55,0.60,0.65,0.70" \\
  --output data/eval/crag_distribution_dplus7.json

# 결과 분석 후 §12 의 upper threshold 0.60 검토
EOF
