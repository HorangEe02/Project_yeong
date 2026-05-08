# AJIN AI Assistant — Demo Tunnel Container
# Plan v3.0: cloudflared + gcloud SDK + entrypoint script
# Mac 호스트의 Ollama (host.docker.internal:11434) → Cloudflare Tunnel → Cloud Run
#
# 빌드: docker compose build
# 실행: Docker Desktop "Containers" 탭에서 ▶ Start

FROM google/cloud-sdk:slim

# cloudflared + 기본 도구 설치 (multi-arch 지원: amd64 / arm64 자동 분기)
# v3.6 — procps 추가 (pgrep/ps 제공) — 헬스체크 도구 누락으로 119회 unhealthy 발생.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl jq ca-certificates procps \
    && ARCH=$(dpkg --print-architecture) \
    && case "$ARCH" in \
        amd64)  CFD_ARCH="amd64" ;; \
        arm64)  CFD_ARCH="arm64" ;; \
        *)      echo "지원하지 않는 아키텍처: $ARCH" && exit 1 ;; \
       esac \
    && curl -fsSL --output /usr/local/bin/cloudflared \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CFD_ARCH}" \
    && chmod +x /usr/local/bin/cloudflared \
    && cloudflared --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 컨테이너 health: cloudflared 가 살아있고 tunnel URL 이 있는지
# v3.6 — pidof 우선 사용 (procps 없는 base image 호환). 둘 다 미설치면 마지막 fallback 으로 /proc 직접 검사.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ( pidof cloudflared > /dev/null 2>&1 || pgrep -x cloudflared > /dev/null 2>&1 || ls /proc/*/comm 2>/dev/null | xargs -I{} sh -c 'grep -q ^cloudflared$ "{}"' ) \
        && [ -f /tmp/tunnel_url.txt ] || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
