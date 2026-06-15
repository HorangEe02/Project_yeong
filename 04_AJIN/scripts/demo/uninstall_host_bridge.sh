#!/usr/bin/env bash
# AJIN Demo Tunnel — Host bridge uninstaller
#
# 목적: install_host_bridge.sh 가 설치한 launchd plist 2개 (ollama + secure_proxy)
#       를 bootout + 파일 삭제. Secret Manager 의 ajin-ollama-secret 은 보존
#       (다음 install 시 재사용). --purge flag 사용 시 secrets/.demo-tunnel.env 도 삭제.
#
# 사용:
#   bash scripts/demo/uninstall_host_bridge.sh           # plist 만 제거
#   bash scripts/demo/uninstall_host_bridge.sh --purge   # 위 + cache env 삭제

set -euo pipefail

PURGE=false
for arg in "$@"; do
    case "$arg" in
        --purge) PURGE=true ;;
        *) echo "unknown arg: $arg" >&2; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/secrets/.demo-tunnel.env"
LA_DIR="$HOME/Library/LaunchAgents"
OLLAMA_PLIST="$LA_DIR/com.ajin.ollama.plist"
PROXY_PLIST="$LA_DIR/com.ajin.ollama-secure-proxy.plist"
UID_NUM="$(id -u)"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$1"; }
step() { printf "\n\033[1m▶ %s\033[0m\n" "$1"; }

echo "═══════════════════════════════════════════════════════"
echo "  AJIN Demo Tunnel — Host Bridge Uninstaller"
echo "═══════════════════════════════════════════════════════"
echo "  PURGE=$PURGE"

step "(1) launchd bootout + plist 삭제"
for label in com.ajin.ollama com.ajin.ollama-secure-proxy; do
    if launchctl print "gui/$UID_NUM/$label" >/dev/null 2>&1; then
        launchctl bootout "gui/$UID_NUM/$label" || warn "$label bootout 실패 (이미 정지일 수 있음)"
        ok "$label bootout 완료"
    else
        warn "$label 등록 안 되어 있음 — skip"
    fi
done

for plist in "$OLLAMA_PLIST" "$PROXY_PLIST"; do
    if [ -f "$plist" ]; then
        rm -f "$plist"
        ok "삭제: $plist"
    fi
done

step "(2) secret cache 처리"
if [ -f "$ENV_FILE" ]; then
    if [ "$PURGE" = true ]; then
        rm -f "$ENV_FILE"
        ok "삭제: $ENV_FILE (--purge)"
    else
        ok "보존: $ENV_FILE (재설치 시 재사용. --purge 로 삭제 가능)"
    fi
fi

step "(3) Secret Manager 상태"
ok "GCP Secret Manager 의 ajin-ollama-secret 은 변경 없음 (안전)"
echo "    명시적 삭제가 필요하면:"
echo "      gcloud secrets delete ajin-ollama-secret --project=ajin-cb --quiet"

echo
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Host bridge 가동 해제 완료"
echo "═══════════════════════════════════════════════════════"
echo
echo "  ollama 와 ollama_secure_proxy.py 는 다음 Mac 부팅 시 자동 가동되지 않음."
echo "  재설치: bash scripts/demo/install_host_bridge.sh"
echo
