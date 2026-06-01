# AJIN AI Assistant — 로컬 LLM 시연 자동화

Mac 의 Ollama 를 보안 프록시(`127.0.0.1:8434`) 뒤에 두고, Cloudflare Tunnel 로 프록시만 노출시켜 Cloud Run 백엔드(`ajin-backend`)가 호출하도록 자동화한 스크립트 모음.

## 구성

| 스크립트 | 용도 |
|---|---|
| `start_local_demo.sh` | 시연 직전 1-클릭 활성화 (외장 SSD Ollama → 보안 프록시 → Tunnel → Cloud Run env update) |
| `stop_local_demo.sh`  | 시연 종료 1-클릭 정리 (Tunnel 종료 + Cloud Run env 원복 → Gemini 모드) |
| `status_demo.sh`      | 현재 활성 상태 점검 (Ollama / 보안 프록시 / Tunnel / Cloud Run env / llm-status) |

## 사전 준비 (1회만)

```bash
brew install ollama cloudflared jq
brew install --cask gcloud-cli
gcloud auth login
gcloud config set project ajin-cb
```

Ollama 모델 루트 검증. `OLLAMA_MODELS`는 manifest leaf가 아니라 `blobs/`와 `manifests/`를 포함하는 models 루트여야 한다.
```bash
scripts/setup_host_ollama.sh --check-only --models-root "/Volumes/Corsair EX300U Media/.ollama/models"
```

Ollama 모델 설치 (최소 권장):
```bash
ollama pull qwen3.5:4b   # 빠른 응답
ollama pull qwen3.5:9b   # 메인 시연 모델
ollama pull gemma4:e4b   # Gemini 대체 비전 모델
```

## 시연 SOP

### 시연 1시간 전 — 모델 사전 로드 (cold start 방지)
```bash
ollama run qwen3.5:9b "warmup" --verbose=false
ollama run gemma4:e4b  "warmup" --verbose=false
```

### 시연 직전 — 활성화
```bash
bash scripts/demo/start_local_demo.sh
```
약 40-60초 소요. 완료 시 다음 정보 출력:
- Tunnel URL (예: `https://printed-latinas-bracket-unwrap.trycloudflare.com`)
- `/api/health/llm-status`에서 `primary=ollama`, `ollama.ok=true`, `tunnel_active=true`

### 시연 중 — 상태 확인
```bash
bash scripts/demo/status_demo.sh
```

### 시연 종료
```bash
bash scripts/demo/stop_local_demo.sh
```
Cloud Run env 가 자동으로 Gemini 모드로 복귀 → 사용자가 `https://ajin-cb.web.app/draft` 접속해도 무중단으로 Gemini 동작.

## 옵션

```bash
# Ollama 프로세스를 죽이지 않고 종료 (다른 작업이 계속 사용 중)
bash scripts/demo/stop_local_demo.sh --keep-ollama

# Cloud Run 을 Gemini 모드로 바꾸지 않고 종료 (시연 직후에도 Mac LLM 유지)
bash scripts/demo/stop_local_demo.sh --keep-gemini
```

## 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `Ollama 미설치` | `brew install ollama` |
| `cloudflared 미설치` | `brew install cloudflared` |
| Tunnel URL 발급 실패 | Mac 인터넷 점검 → 재실행 |
| /health/llm-status ollama=false (start 직후) | revision 활성 대기 — 30s 후 다시 status 호출 |
| 시연 중 응답 매우 느림 | `caffeinate` 종료 가능성 — start 재실행 |
| 모델 OOM | 더 작은 모델 사용 (`qwen3.5:4b`, `gemma4:e2b`) |

## 위험 / 보안

- **Raw Ollama quick tunnel 금지** — Tunnel 은 `X-AJIN-Secret`을 검증하는 보안 프록시만 노출
- **Mac sleep 시 응답 끊김** — caffeinate 가 자동 적용되지만 화면 보호기 설정도 점검
- **인터넷 끊김 시** — strict 시연 기본은 `FEATURE_B_BLOCK_GEMINI=true`라서 Ollama 경로가 release blocker로 드러남. 종료 스크립트는 Cloud Run 을 Gemini 단독 모드로 원복한다.

## 영구 URL 이 필요한 경우 (Named Tunnel)

```bash
cloudflared tunnel login                                 # Cloudflare 인증
cloudflared tunnel create ajin-mac-ollama                # Named tunnel 생성
cloudflared tunnel route dns ajin-mac-ollama ollama.example.com
# ~/.cloudflared/config.yml 작성 후
sudo cloudflared service install
```
이 경우에도 raw Ollama 가 아니라 보안 프록시를 origin 으로 두고, Cloud Run 에는 `OLLAMA_BASE_URL=https://ollama.example.com` 과 Secret Manager 기반 `AJIN_OLLAMA_SECRET`을 함께 설정한다.
