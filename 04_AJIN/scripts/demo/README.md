# AJIN AI Assistant — 로컬 LLM 시연 자동화

Mac 의 Ollama 를 Cloudflare Tunnel 로 외부에 노출시켜 Cloud Run 백엔드(`ajin-backend`)가 호출하도록 자동화한 스크립트 모음.

## 구성

| 스크립트 | 용도 |
|---|---|
| `start_local_demo.sh` | 시연 직전 1-클릭 활성화 (Ollama → Tunnel → Cloud Run env update) |
| `stop_local_demo.sh`  | 시연 종료 1-클릭 정리 (Tunnel 종료 + Cloud Run env 원복 → Gemini 모드) |
| `status_demo.sh`      | 현재 활성 상태 점검 (Ollama / Tunnel / Cloud Run env / diagnose) |

## 사전 준비 (1회만)

```bash
brew install ollama cloudflared jq
brew install --cask gcloud-cli
gcloud auth login
gcloud config set project ajin-cb
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
- 진단 칩 4-5개 ✓

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
| /diagnose ollama=false (start 직후) | revision 활성 대기 — 30s 후 다시 status 호출 |
| 시연 중 응답 매우 느림 | `caffeinate` 종료 가능성 — start 재실행 |
| 모델 OOM | 더 작은 모델 사용 (`qwen3.5:4b`, `gemma4:e2b`) |

## 위험 / 보안

- **Quick Tunnel URL 은 인증 없음** — 시연 외 시간엔 반드시 stop 실행
- **Mac sleep 시 응답 끊김** — caffeinate 가 자동 적용되지만 화면 보호기 설정도 점검
- **인터넷 끊김 시** — Cloud Run 의 `FEATURE_B_BLOCK_GEMINI=false` 덕분에 자동으로 Gemini fallback 동작 (Plan v1.0 §3.1)

## 영구 URL 이 필요한 경우 (Named Tunnel)

```bash
cloudflared tunnel login                                 # Cloudflare 인증
cloudflared tunnel create ajin-mac-ollama                # Named tunnel 생성
cloudflared tunnel route dns ajin-mac-ollama ollama.example.com
# ~/.cloudflared/config.yml 작성 후
sudo cloudflared service install
```
이 경우 `OLLAMA_BASE_URL=https://ollama.example.com` 으로 영구 고정.
