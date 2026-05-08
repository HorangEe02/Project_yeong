# 로컬 셋업 가이드

## 1. 필수 toolchain

| 도구 | 검증 버전 | 최소 요구 | 설치 (macOS) |
|---|---|---|---|
| Node.js | v22.17.0 | ≥ 20 | `brew install node@22` |
| npm | 10.9.2 | ≥ 10 | (Node 와 함께) |
| Python | 3.11+ (Docker), 3.13 (host OK) | ≥ 3.11 | `brew install python@3.11` |
| Docker Desktop | 29.4.2 | ≥ 24 | https://docker.com/desktop |
| Firebase CLI | 15.15.0 | ≥ 13 | `npm install -g firebase-tools` |
| gcloud SDK | 565.0.0 | latest | `brew install --cask google-cloud-sdk` |
| Ollama | 0.18.2 | ≥ 0.18 (NEW_ENGINE) | `brew install ollama` |
| Caddy | 2.11.2 | ≥ 2.10 | `brew install caddy` |
| cloudflared | 2026.3.0 | latest | `brew install cloudflared` |
| jq | latest | latest | `brew install jq` |

Linux/WSL 의 경우 같은 도구의 패키지 매니저 명령(`apt`, `dnf`, `pacman`)으로 대체.

## 2. 1-클릭 셋업

```bash
git clone https://github.com/HorangEe02/Project_yeong.git
cd Project_yeong/04_AJIN
bash scripts/setup-host.sh
```

`setup-host.sh` 가 수행하는 것:

1. toolchain 버전 검증 (부족 시 안내)
2. `.env.example` → `.env` 복사 (chmod 600)
3. `secrets/meili_master_key`, `secrets/smtp_password` placeholder 자동 생성
4. Python venv (`.venv/`) + `pip install -r requirements.txt`
5. `frontend/` 의 `npm install`
6. (선택) Ollama 모델 5개 pull — `qwen3.5:9b/4b`, `gemma4:e4b/e2b`, `bge-m3` (~14 GB)
7. (선택) `~/.config/ajin/` 디렉토리 + Caddyfile + launchd plist 설치
8. (선택) `python scripts/setup-demo-data.py` 실행 — 가짜 직원 30명 + 법규 5건 + 시나리오 5종

## 3. 환경변수 설정 (`.env`)

`.env.example` 의 모든 항목 중 다음만 본인 값으로 채우면 됩니다:

```bash
GEMINI_API_KEY=AIzaSy...                 # https://aistudio.google.com 에서 발급
AJIN_JWT_SECRET=$(openssl rand -hex 32)  # 32-byte hex
```

나머지는 default 그대로 OK (로컬 dev 시):
- `OLLAMA_BASE_URL=http://localhost:11434` — Mac/Linux 호스트의 Ollama 직접 호출
- `LLM_ROUTER_PRIMARY=ollama` — Ollama 1순위, 실패 시 Gemini fallback
- `EMBEDDING_BACKEND=auto` — Ollama 살아있으면 ollama, 아니면 gemini
- `AJIN_OLLAMA_SECRET=` — 빈값 (로컬은 인증 불요)

## 4. 백엔드 dev 서버

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
# → http://localhost:8000/docs (Swagger UI)
```

## 5. 프론트엔드 dev 서버

```bash
cd frontend
npm run dev
# → http://localhost:5173
```

frontend 가 `/api/**` 요청을 자동으로 `http://localhost:8000/api/` 로 프록시 (Vite proxy).

## 6. Docker 통합 환경 (선택)

```bash
docker compose -f docker-compose.yml up -d
```

기동되는 서비스:
- `meilisearch` (포트 7700) — 법규 전문검색
- `redis` (포트 6379) — Celery broker
- `mailhog` (포트 1025/8025) — SMTP 발송 테스트
- `flower` (포트 5555) — Celery 모니터

## 7. 시연 환경 활성화 (Cloud Run 연동)

운영 사이트(`ajin-cb.web.app`)와 Mac Ollama 를 임시 URL 로 연결:

```bash
bash scripts/demo/start_local_demo.sh
```

수행:
1. Ollama `0.0.0.0:11434` 외부 바인딩 (재시작)
2. cloudflared 임시 tunnel 발급
3. Cloud Run env 의 `OLLAMA_BASE_URL` 자동 갱신
4. caffeinate 로 Mac sleep 방지

종료:
```bash
bash scripts/demo/stop_local_demo.sh
```

상태 확인:
```bash
bash scripts/demo/status_demo.sh
```

## 8. Ollama 모델 추가 다운로드

`setup-host.sh` 에서 skip 한 경우 또는 추가 모델 필요 시:

```bash
ollama pull qwen3.5:9b      # ~6.6 GB (메인 채팅)
ollama pull qwen3.5:4b      # ~3.4 GB (빠른 응답)
ollama pull gemma4:e4b      # ~9.6 GB (보조)
ollama pull gemma4:e2b      # ~7.2 GB (보조 small)
ollama pull bge-m3          # ~1.2 GB (임베딩)
```

총 ~28 GB. SSD 여유 공간 확인 필수.

## 9. 벡터스토어 재빌드

`vectorstore/` 가 비어있으면 임베딩 검색이 동작하지 않습니다. 재빌드:

```bash
source .venv/bin/activate
python scripts/reindex_v16.py             # 전체 문서 인덱스
python scripts/reindex_fewshot_rag.py     # Module B 의 few-shot 예제
python scripts/reindex_equipment_manuals.py  # Module F 의 설비 매뉴얼
```

## 10. 빠른 검증

```bash
# 백엔드 헬스체크
curl http://localhost:8000/api/health

# 채팅 endpoint smoke
curl -X POST http://localhost:8000/api/onboarding/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"테스트","conversation_id":"local-1"}'

# Ollama 직접 검증
ollama list
curl http://localhost:11434/api/version
```

문제 발생 시 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) 참고.
