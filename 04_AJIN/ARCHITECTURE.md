# 시스템 아키텍처

> Plan A 변형 — Mac Ollama × Cloud Run × Firebase Hosting 운영급 연동.

## 1. 전체 다이어그램

```
┌──────────────────────────────────────────────────────────────┐
│                         사용자 (Web)                          │
└─────────────────────────────┬────────────────────────────────┘
                              │ HTTPS
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Firebase Hosting — https://ajin-cb.web.app                  │
│  - frontend/dist 정적 파일                                    │
│  - SPA 라우팅 + immutable cache                               │
└─────────────────────────────┬────────────────────────────────┘
                              │ /api/** rewrite
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Cloud Run — ajin-backend (asia-northeast3)                  │
│  - FastAPI + uvicorn (CPU 2 / Mem 2 GiB)                     │
│  - LLMRouter (provider chain)                                │
│  - OllamaHealthMiddleware (Mac off 시 503)                    │
│  - Firestore mirror (사용자 인증)                              │
└─────────────┬────────────────────────────┬───────────────────┘
              │                            │
   ┌──────────▼─────────┐        ┌─────────▼──────────┐
   │ Gemini 2.5 Pro API │        │ Mac Ollama         │
   │ (text-embedding-004│        │ via Cloudflare     │
   │  + chat fallback)  │        │ Tunnel (자가호스팅) │
   └────────────────────┘        └────────────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │ Mac (M4 Pro, 24GB RAM)  │
                              ├─────────────────────────┤
                              │ launchd 3 daemons:      │
                              │  • ollama serve         │
                              │  • caddy :8434 (auth)   │
                              │  • tunnel-watchdog      │
                              │     ├─ cloudflared      │
                              │     └─ env auto-update  │
                              └─────────────────────────┘
```

## 2. LLM Router (`core/llm_router.py`)

모든 LLM 요청은 mode + provider chain 으로 라우팅:

| Mode | Chain (LLM_ROUTER_PRIMARY=ollama) | 사용 endpoint |
|---|---|---|
| `CHAT_KOREAN` | ollama qwen3.5:9b → gemma4:e4b → gemini → lm_studio | `/api/onboarding/chat` |
| `DRAFT` | ollama qwen3.5:9b → gemma4:e4b → gemini | `/api/draft/*` |
| `SUMMARY` | ollama qwen3.5:4b → gemma4:e2b → gemini | 요약 |
| `JSON` | ollama qwen3.5:9b → gemini | 구조화 응답 |
| `INTENT` | gemini → ollama (always Gemini 1순위 — 빠른 분류) | 의도 분류 |
| `VISION` | gemini → gemma4:e4b (qwen vision 미지원) | 이미지 첨부 |
| `EMBEDDING` | ollama bge-m3 only (또는 gemini text-embedding-004) | 검색·색인 |

**환경변수 토글**: `LLM_ROUTER_PRIMARY=gemini` 로 1줄 변경 시 즉시 Gemini-only 환원 (사고 시 빠른 fallback).

## 3. Mac 호스트 인프라

### 3.1 Caddy (`:8434` reverse proxy + secret 검증)
```caddyfile
:8434 {
    @authorized header X-AJIN-Secret {env.AJIN_OLLAMA_SECRET}
    handle @authorized {
        reverse_proxy 127.0.0.1:11434
    }
    handle {
        respond "Forbidden" 403
    }
    log {
        format filter {
            wrap json
            fields {
                request>headers>X-Ajin-Secret delete
                request>headers>Authorization delete
            }
        }
    }
}
```

### 3.2 cloudflared 임시 tunnel
- `cloudflared tunnel --url http://127.0.0.1:8434`
- 시작 시마다 `random-name-1234.trycloudflare.com` 발급
- Watchdog 가 stdout 에서 URL 추출 → Cloud Run env 자동 갱신

### 3.3 Tunnel Watchdog (`infra/tunnel-watchdog.sh`)
- launchd `KeepAlive` 로 영속화
- cloudflared 죽으면 30s 후 자동 재시작
- 새 URL 추출 시 `gcloud run services update --update-env-vars OLLAMA_BASE_URL=...`
- gcloud ADC 자격증명 자동 사용

## 4. Frontend (`frontend/`)

- React 19 + Vite + TypeScript + Tailwind v4 (Liquid Glass)
- Zustand 상태 관리 (auth, theme, ui, chat, maintenance)
- axios interceptor:
  - 401 → refresh token / Firebase exchange / login redirect
  - 503 + `AI_UNAVAILABLE` → maintenance store activate
- `MaintenanceBanner` — Mac off 시 자동 표시
- `TopBar` LLM 라벨 — `/api/draft/diagnose` polling 으로 동적 (`🐳 DOCKER` / `LOCAL · OLLAMA` / `GEMINI · CLOUD` / `OFFLINE`)

## 5. 보안 계층

| 계층 | 인증 |
|---|---|
| **Frontend ↔ Cloud Run** | Firebase Auth (Google SSO) → JWT (1h access + refresh) |
| **Cloud Run ↔ Cloudflare Tunnel** | URL 비공개 (~16자 랜덤) + X-AJIN-Secret 헤더 |
| **Cloudflare Tunnel ↔ Caddy** | TLS (Cloudflare 측 자동) |
| **Caddy ↔ Ollama** | localhost loopback only (`127.0.0.1:11434`) |
| **Cloud Run secret** | GCP Secret Manager (`GEMINI_API_KEY`, `AJIN_JWT_SECRET`) |

## 6. 데이터 흐름 (예: Module C 채팅)

```
1. 사용자가 frontend 채팅창에 메시지 입력
2. axios → POST /api/onboarding/chat (JWT 헤더)
3. Cloud Run OllamaHealthMiddleware 가 Mac 도달성 확인 (5s 캐시)
   - Mac off → 503 + AI_UNAVAILABLE → frontend banner
   - Mac on → 통과
4. LLMRouter → mode=CHAT_KOREAN → chain[0] = ollama qwen3.5:9b
5. OllamaProvider 가 X-AJIN-Secret 헤더 부착해 Cloudflare Tunnel 호출
6. trycloudflare.com → Cloudflare Edge → cloudflared (Mac)
7. Caddy 가 X-AJIN-Secret 검증 → :11434 으로 forward
8. Ollama 가 SSE 스트림으로 토큰 반환
9. Cloud Run 이 같은 SSE 로 frontend 까지 전달
10. frontend 가 토큰 단위로 채팅 UI 에 표시
```

평균 응답 시간:
- First token: ~1.5s (cold) / ~0.5s (warm)
- 평균 stream 속도: 20~40 tokens/s (qwen3.5:9b on M4 Pro)

## 7. 운영 토글 (Cloud Run env)

| Env | 효과 |
|---|---|
| `OLLAMA_BASE_URL=` (빈값) | 즉시 Gemini-only 모드 (Caddy 우회) |
| `LLM_ROUTER_PRIMARY=gemini` | chain 1순위 Gemini 로 환원 |
| `LLM_ROUTER_FALLBACK_ENABLED=true` | Ollama 실패 시 자동 Gemini fallback |
| `EMBEDDING_BACKEND=gemini` | 임베딩만 Gemini, 채팅은 Ollama (혼합) |
| `AJIN_OLLAMA_SECRET=<NEW>` | secret rotation (Caddy 도 동시 갱신 필요) |

## 8. Plan B 이행 경로 (미래 GPU 서버 도입)

같은 Caddy + secret + watchdog 패턴 그대로 GPU 서버에 복제:
1. `~/.config/ajin/` 통째로 SCP
2. Linux launchd 대신 systemd 사용
3. Cloud Run env 변경 불요 — 같은 watchdog 가 새 URL 추출
4. Mac 측 `launchctl unload com.ajin.tunnel-watchdog` (이중 가동 방지)
5. 다운타임 < 5분, 백엔드 코드 변경 0
