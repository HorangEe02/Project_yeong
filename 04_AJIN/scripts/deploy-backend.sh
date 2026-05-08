#!/usr/bin/env bash
# AJIN Backend — Cloud Run canary 배포 (smoke test 가드 포함)
#
# 두 인시던트 (00102~00105 sync 누락 / `rank_bm25` ImportError) 직후 도입.
# 배포 → smoke test → canary 10% → 모니터링 → 100% 의 흐름을 단일 명령으로 묶고,
# 어느 단계든 실패 시 자동 rollback.
#
# 사용법:
#   bash scripts/deploy-backend.sh                            # slim, canary, 자동 promote
#   bash scripts/deploy-backend.sh --mode full                # 풀 모드
#   bash scripts/deploy-backend.sh --skip-canary              # 새 리비전만 띄우고 사용자가 수동 promote
#   bash scripts/deploy-backend.sh --rollback                 # 이전 안정 리비전(LKG) 으로 트래픽 100% 환원
#
# 옵션:
#   --mode {slim|full}   (default: slim)
#   --tag <name>         새 리비전 tag (default: deploy-YYYYMMDD-HHMMSS)
#   --canary-pct <N>     canary % (default: 10)
#   --canary-wait <sec>  canary 모니터링 시간 (default: 180)
#   --skip-canary        canary 단계 skip — 새 리비전만 no-traffic 으로 배포
#   --rollback           이전 안정 리비전으로 즉시 환원
#   --lkg <revision>     known good 리비전 명시 (default: 자동 추론)
#   -h, --help

set -euo pipefail

# ───────────────────────── 기본값
PROJECT="${PROJECT:-ajin-cb}"
REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-ajin-backend}"
MODE="slim"
TAG="deploy-$(date +%Y%m%d-%H%M%S)"
CANARY_PCT=10
CANARY_WAIT=180
SKIP_CANARY=0
ROLLBACK=0
LKG=""

# ───────────────────────── 인자 파싱
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)         MODE="$2"; shift 2 ;;
        --tag)          TAG="$2"; shift 2 ;;
        --canary-pct)   CANARY_PCT="$2"; shift 2 ;;
        --canary-wait)  CANARY_WAIT="$2"; shift 2 ;;
        --skip-canary)  SKIP_CANARY=1; shift ;;
        --rollback)     ROLLBACK=1; shift ;;
        --lkg)          LKG="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,30p' "$0"; exit 0 ;;
        *)
            echo "Unknown arg: $1" >&2; exit 4 ;;
    esac
done

if [[ "$MODE" != "slim" && "$MODE" != "full" ]]; then
    echo "✗ --mode must be slim or full" >&2; exit 4
fi

# ───────────────────────── 컬러
if [[ -t 1 ]]; then
    G=$'\e[32m'; R=$'\e[31m'; Y=$'\e[33m'; B=$'\e[36m'; X=$'\e[0m'
else
    G=''; R=''; Y=''; B=''; X=''
fi
log()  { echo "${B}▶${X} $*"; }
ok()   { echo "${G}✓${X} $*"; }
err()  { echo "${R}✗${X} $*"; }
warn() { echo "${Y}⚠${X} $*"; }

# 작업 로그 — incident 회고용
LOG_DIR="${LOG_DIR:-/tmp/ajin-deploy-logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1
log "Log: $LOG_FILE"

# ───────────────────────── 헬퍼
current_traffic() {
    gcloud run services describe "$SERVICE" \
        --region="$REGION" --project="$PROJECT" \
        --format="value(status.traffic[].revisionName,status.traffic[].percent)" 2>/dev/null
}

resolve_lkg() {
    # 가장 최근에 100% traffic 받았던 리비전 추론.
    if [[ -n "$LKG" ]]; then echo "$LKG"; return; fi
    gcloud run services describe "$SERVICE" \
        --region="$REGION" --project="$PROJECT" \
        --format='value(status.traffic[].revisionName,status.traffic[].percent)' 2>/dev/null \
        | awk '{n=split($1,r,";"); split($2,p,";"); for(i=1;i<=n;i++) if(p[i]=="100") print r[i]}' \
        | head -1
}

# ───────────────────────── ROLLBACK 모드
if [[ $ROLLBACK -eq 1 ]]; then
    TARGET=$(resolve_lkg)
    if [[ -z "$TARGET" ]]; then
        err "이전 안정 리비전을 찾지 못함 — --lkg <revision> 명시 필요"
        exit 5
    fi
    log "Rollback target: $TARGET"
    read -r -p "Promote ${TARGET} to 100%? [y/N] " ans
    [[ "$ans" =~ ^[yY]$ ]] || { warn "취소"; exit 0; }
    gcloud run services update-traffic "$SERVICE" \
        --region="$REGION" --project="$PROJECT" \
        --to-revisions="${TARGET}=100" \
        --quiet
    ok "Rolled back to $TARGET"
    exit 0
fi

# ───────────────────────── 1. Pre-flight
log "Pre-flight 점검"
gcloud config get-value account 1>/dev/null || { err "gcloud auth 안 됨"; exit 5; }
[[ -f Dockerfile ]] || { err "Dockerfile 없음 — 프로젝트 루트에서 실행하세요"; exit 5; }
[[ -f scripts/smoke-test.sh ]] || { err "scripts/smoke-test.sh 없음"; exit 5; }
ok "PROJECT=$PROJECT REGION=$REGION SERVICE=$SERVICE MODE=$MODE TAG=$TAG"

# 현재 traffic snapshot — rollback 시 LKG 후보
PREV_LKG=$(resolve_lkg || true)
if [[ -n "$PREV_LKG" ]]; then
    ok "Last-known-good: $PREV_LKG"
fi

# ───────────────────────── 2. Cloud Build + deploy --no-traffic --tag
log "Cloud Build + Cloud Run deploy (--no-traffic --tag $TAG, mode=$MODE)"
if [[ "$MODE" == "full" ]]; then
    # full mode 빌드는 Cloud Build 의 explicit `--target full` 이 필요 → cloudbuild.yaml 사용.
    if [[ ! -f cloudbuild.yaml ]]; then
        err "cloudbuild.yaml 없음 — full 모드는 Cloud Build 단계에서 --target full 필요"
        exit 5
    fi
    gcloud builds submit \
        --config=cloudbuild.yaml \
        --substitutions=_MODE=full,_TAG="$TAG" \
        --project="$PROJECT" \
        --quiet
else
    # slim 모드는 Dockerfile 의 default stage(=slim) 가 자동 빌드됨
    gcloud run deploy "$SERVICE" \
        --source=. \
        --region="$REGION" --project="$PROJECT" \
        --no-traffic --tag="$TAG" \
        --quiet
fi
ok "Deployed (no-traffic, tag=$TAG)"

NEW_REV=$(gcloud run services describe "$SERVICE" \
    --region="$REGION" --project="$PROJECT" \
    --format='value(status.latestCreatedRevisionName)')
TAG_URL="https://${TAG}---${SERVICE}-ncsnraqdaa-du.a.run.app"
ok "New revision: $NEW_REV   tag URL: $TAG_URL"

# ───────────────────────── 3. Smoke test on tag URL
log "Smoke test (tag URL)"
if ! bash scripts/smoke-test.sh "$TAG_URL" "$NEW_REV"; then
    err "Smoke test 실패 — 트래픽 promote 안 함. tag URL ($TAG_URL) 만 남김."
    err "수동 점검 후 재시도하거나 이전 리비전 그대로 둘 것."
    exit 1
fi
ok "Tag URL smoke test 통과"

# ───────────────────────── 4. (옵션) Canary 10%
if [[ $SKIP_CANARY -eq 1 ]]; then
    warn "--skip-canary — 새 리비전 $NEW_REV 만 띄우고 종료."
    warn "트래픽 promote 는 수동: gcloud run services update-traffic $SERVICE --to-revisions=$NEW_REV=100 ..."
    exit 0
fi

if [[ -z "$PREV_LKG" ]]; then
    warn "PREV_LKG 추론 실패 → canary 단계 skip 하고 100% 직행"
    SKIP_CANARY=1
else
    log "Canary $CANARY_PCT% (현재: $PREV_LKG=$((100-CANARY_PCT))% / 새: $NEW_REV=$CANARY_PCT%)"
    gcloud run services update-traffic "$SERVICE" \
        --region="$REGION" --project="$PROJECT" \
        --to-revisions="${NEW_REV}=${CANARY_PCT},${PREV_LKG}=$((100-CANARY_PCT))" \
        --quiet
    ok "Canary applied — ${CANARY_WAIT}s 모니터링 시작"

    # 모니터링: 5xx rate 추적
    SLEEP_INC=30
    elapsed=0
    while [[ $elapsed -lt $CANARY_WAIT ]]; do
        sleep "$SLEEP_INC"
        elapsed=$((elapsed+SLEEP_INC))
        FIVES=$(gcloud logging read \
            "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE\" AND httpRequest.status>=500" \
            --limit=20 --freshness=1m \
            --format='value(timestamp)' \
            --project="$PROJECT" 2>/dev/null | wc -l | tr -d ' ')
        log "  [+${elapsed}s] last 1m 5xx count: $FIVES"
        if [[ "$FIVES" -gt 0 ]]; then
            err "Canary 모니터링 중 5xx 감지 — 자동 rollback"
            gcloud run services update-traffic "$SERVICE" \
                --region="$REGION" --project="$PROJECT" \
                --to-revisions="${PREV_LKG}=100" \
                --quiet
            err "Rollback to $PREV_LKG 완료"
            exit 1
        fi
    done
    ok "Canary ${CANARY_WAIT}s 통과 — 5xx 0건"
fi

# ───────────────────────── 5. Promote 100%
log "Promote 100% to $NEW_REV"
gcloud run services update-traffic "$SERVICE" \
    --region="$REGION" --project="$PROJECT" \
    --to-revisions="${NEW_REV}=100" \
    --quiet

ok "Promoted. Final smoke test on production URL..."
PROD_URL=$(gcloud run services describe "$SERVICE" \
    --region="$REGION" --project="$PROJECT" \
    --format='value(status.url)')
if ! bash scripts/smoke-test.sh "$PROD_URL" "$NEW_REV"; then
    err "Production URL 에서 smoke test 실패 — rollback 진행"
    gcloud run services update-traffic "$SERVICE" \
        --region="$REGION" --project="$PROJECT" \
        --to-revisions="${PREV_LKG}=100" \
        --quiet
    err "Rolled back to $PREV_LKG"
    exit 1
fi

ok "Deploy 완료: $NEW_REV (mode=$MODE)"
ok "URL: $PROD_URL"
ok "Log: $LOG_FILE"
