# AJIN Compliance — Docker 운영 가이드 (Phase 1)

Phase 1 통합 docker-compose 구성. Mac (Apple Silicon Metal) → 클라우드 (NVIDIA / Cloud Run) 호환 설계.

## 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│ Mac Host (M4 Pro 24GB / Metal GPU)                           │
│                                                              │
│  Ollama (host install — brew)                                │
│    :11434  ← Metal GPU 가속                                  │
│    models root: <EXTERNAL_DRIVE>/.ollama/models │
│    models: qwen3.5:9b, qwen3.5:4b, gemma4:e4b, bge-m3        │
│                                                              │
│  Docker Desktop (8~12 GB allocated)                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ network: ajin_net                                       │  │
│  │                                                         │  │
│  │  rp (nginx :8080) ──► backend :8080 ──┐                 │  │
│  │      │                  │              │                │  │
│  │      └─► frontend :80   ▼              ▼                │  │
│  │                   host.docker         redis :6379        │  │
│  │                   .internal:11434                        │  │
│  │                         ↓                                │  │
│  │                   Ollama (호스트)                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

외부 접근: `http://localhost:8080` (rp 가 frontend / `/api` 분기)

## 빠른 시작 (4 단계)

```bash
# 1. 호스트 Ollama 셋업 (.env 작성 후)
make setup

# 2. 컨테이너 시작
make up

# 3. 헬스 검증
make health

# 4. (선택) 호스트 .venv 회귀 테스트
make backend-venv
make test
```

## 사전 요건

- macOS (Apple Silicon 또는 Intel) 또는 Linux
- **Docker Desktop ≥ 4.30** (compose v2.24+ — `env_file required:false` 지원)
- **Homebrew** (Mac, Ollama 설치용)
- 디스크 ≥ 30 GB (모델 + 이미지)
- RAM ≥ 16 GB (Docker Desktop 8 GB 할당 + Ollama 6 GB)

## 명령 한눈에

| 명령 | 용도 |
|---|---|
| `make setup` | Mac 호스트 Ollama 설치 + 모델 pull + .env.docker 복사 |
| `make up` | 컨테이너 빌드 + 시작 (background) |
| `make logs` | 전체 로그 tail |
| `make ps` | service 상태 |
| `make health` | `/healthz` + `/api/health` curl |
| `make backend-venv` | 호스트 `.venv` 생성 + requirements 설치 |
| `make test-collect` | 호스트 `.venv` 기준 pytest collection 재현 |
| `make test` | 호스트 `.venv` 기준 pytest |
| `make test-docker` | 컨테이너 안 pytest |
| `make shell` | backend bash |
| `make down` | 정지 (data 보존) |
| `make clean` | 정지 + volume 제거 (host bind mount 의 data/ 는 보존) |
| `make rebuild` | --no-cache 빌드 |

## 자격증명 / .env

`.env` 가 root 에 있어야 함 — 기존 P5 까지의 키들 그대로:

```bash
# .env (gitignored)
DART_API_KEY=...
JIRA_API_TOKEN=...
JIRA_BASE_URL=...
SLACK_WEBHOOK_URL=...
GEMINI_API_KEY=...
# ...
```

`.env.docker` 는 컨테이너 전용 override (`.env.docker.example` 참고):

```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434  # Mac 호스트 Ollama
LLM_ROUTER_PRIMARY=ollama
EMBEDDING_BACKEND=ollama
FEATURE_B_BLOCK_GEMINI=true
OLLAMA_MODEL_CHAT_LARGE=qwen3.5:9b
OLLAMA_MODEL_CHAT_SMALL=qwen3.5:4b
OLLAMA_MODEL_GEMMA_LARGE=gemma4:e4b
OLLAMA_MODEL_GEMMA_SMALL=gemma4:e2b
OLLAMA_MODEL_EMBEDDING=bge-m3
REDIS_URL=redis://redis:6379/0
PORT=8080
```

호스트 Ollama 모델 루트는 컨테이너 env가 아니라 호스트 셋업 단계에서 고정한다. 올바른 값은 `blobs/`와 `manifests/`를 둘 다 포함하는 `<EXTERNAL_DRIVE>/.ollama/models`이며, `.../manifests/registry.ollama.ai/library` 같은 leaf 경로를 `OLLAMA_MODELS`로 지정하면 안 된다.

### 원격 Supabase Docker 실행

Supabase 원격 프로젝트에 붙는 Docker 실행은 기본 compose와 분리된 override를 사용한다. `.env.supabase.local`은 gitignored secret 파일이며, `SUPABASE_SECRET_KEY`는 backend에만 주입한다.

```bash
make supabase-env
# .env.supabase.local에 SUPABASE_ACCESS_TOKEN, SUPABASE_SECRET_KEY를 직접 채운 뒤:
make supabase-cutover-preflight SUPABASE_CUTOVER_ARGS="--env-file .env.supabase.local"
make supabase-docker-config
make supabase-docker-up
make supabase-docker-health
```

## 트러블슈팅

### `make health` 가 ollama: error

원인: Mac 호스트 Ollama 가 동작 안 함, 또는 컨테이너가 host.docker.internal 도달 실패.

```bash
# 호스트에서 직접 확인
curl http://localhost:11434/api/tags

# 외장 SSD 모델 루트 검증
scripts/setup_host_ollama.sh --check-only --models-root "<EXTERNAL_DRIVE>/.ollama/models"

# 컨테이너 안에서 확인 (Mac/Windows Docker Desktop 자동 / Linux 는 host-gateway)
docker compose exec backend curl http://host.docker.internal:11434/api/tags
```

해결: `make setup` 재실행 → `brew services start ollama`

Cloud Run 시연은 raw Ollama를 직접 터널링하지 않는다. `scripts/demo/start_local_demo.sh`가 `127.0.0.1:8434` 보안 프록시를 띄우고, Cloudflare Tunnel은 이 프록시만 노출한다. Cloud Run에는 `OLLAMA_BASE_URL`과 Secret Manager 기반 `AJIN_OLLAMA_SECRET`만 주입한다.

### Linux 에서 host.docker.internal 도달 안 됨

`docker-compose.yml` 의 `extra_hosts: ["host.docker.internal:host-gateway"]` 를 명시해 둠 — Docker ≥ 20.10 자동 동작. 그래도 안 되면 `--network host` 모드로 backend 만 실행 (compose 와 호환 안 됨, dev only).

### 모델 pull 너무 느림

qwen3.5:9b 는 ~5GB. WiFi 보다 유선 추천. 부분 다운 후 끊겨도 `ollama pull` 재실행하면 이어받음.

### Docker Desktop RAM 부족

설정 → Resources → Memory 12GB 권장. 8GB 도 동작하지만 backend + redis + nginx 동시 운영 시 swap.

### `data/*.db` 가 컨테이너 안에서 안 보임

bind mount 확인:
```bash
docker compose exec backend ls -la /app/data
```
호스트 `./data` 의 권한이 컨테이너 안 user (root) 와 호환되어야 함. 일반적으로 Mac/Linux 모두 OK.

### Frontend 빌드 시 메모리 OOM

```bash
docker compose build frontend --build-arg NODE_OPTIONS="--max-old-space-size=2048"
```

### 호스트 Ollama 0.18.2 + gemma4 — 500 Internal Server Error

```
{"error":"unable to load model: .../blobs/sha256-..."}
```
gemma4 아키텍처 (e2b/e4b) 는 Ollama runtime ≥0.20.0 필요. 호스트가 0.18.2 면 로드 실패.

**임시 우회:** `.env.docker` 의 `LLM_MODEL_QUIZ=qwen3.5:4b` 로 swap 후 `docker compose up -d --force-recreate backend` (code rebuild 불필요, env reload 만).

**근본 해결:** `brew upgrade ollama && brew services restart ollama` → 0.20+ 검증 후 `LLM_MODEL_QUIZ=gemma4:e2b` 로 원복. 7 모델 재로드 + `OLLAMA_KEEP_ALIVE` 캐시 초기화 부수 효과 있으니 maintenance window 권장.

### qwen3 응답이 비어있음 (`done_reason: length`)

qwen3 류 thinking 모델은 chain-of-thought 토큰을 응답 본문 전에 출력. `num_predict` 가 작으면 thinking 만 채우고 답변 0.

**해결:** `_call_ollama` 의 `think=False` (default) 로 thinking 비활성. opt-in 필요한 호출만 `think=True`.

## Phase 2 / 3 마이그 가이드

### Phase 1.5 — NVIDIA 서버 / Cloud Run for GPU 이전

`docker-compose.cloud.yml` (override) 작성 후:
```bash
docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d
```
- `ollama` service 활성화 (NVIDIA GPU 자원 reservation)
- backend 의 `OLLAMA_BASE_URL=http://ollama:11434` 로 swap

### Phase 2 — LLM 풀 모델별 분리 (구현·검증 완료)

What-if 자연어 라우팅 같은 큰 모델 호출과 quiz/grade 같은 작은 모델 호출을 별도 endpoint 로 분리. 향후 NVIDIA 서버에서 GPU 자원 차별화 가능.

#### 코드 라우팅 (구현 완료)

`regulation_qa._call_ollama(..., feature=...)` 가 `config.LLM_FEATURE_ROUTES` 매핑으로 base URL + 모델 선택. 4 feature 등록:

| Feature | Tier | 기본 모델 | 호출처 |
|---|---|---|---|
| `whatif_nl_route` | LARGE | qwen3.5:9b | `whatif_engine._llm_extract` (자연어 → 시나리오 JSON) |
| `rag_answer` | FAST | qwen3.5:4b | `regulation_qa.answer_question` (RAG 답변) |
| `quiz_gen` | FAST | gemma4:e2b\* | `learning_path._generate_quiz_llm` |
| `short_answer_grade` | FAST | qwen3.5:4b | `learning_path._grade_short_answer_llm` |

\* Stage 1 hotfix 로 임시 `qwen3.5:4b` (트러블슈팅 §"호스트 Ollama 0.18.2 + gemma4" 참조).

`feature` 미지정 호출 → `OLLAMA_BASE_URL` + `LLM_MODEL` 폴백 (Phase 1 동작 그대로 — backward-compat).

#### thinking 토큰 차단 (`think` kwarg)

qwen3 류 thinking 모델은 chain-of-thought 토큰을 응답 본문 전에 생성. `_call_ollama(..., think=False)` (default) 로 차단해 latency·token 절감 — 실측 RAG 호출에서 **5.32s → 0.96s (5.5x)** 개선. 깊은 추론이 필요한 호출만 `think=True` opt-in.

#### env 활성화

`.env.docker` 에 LARGE/FAST URL + 모델 override (없으면 `OLLAMA_BASE_URL` 단일 폴백):

```
OLLAMA_BASE_URL_LARGE=http://host.docker.internal:11434  # Stage 1: 호스트 단일
OLLAMA_BASE_URL_FAST=http://host.docker.internal:11434
LLM_MODEL_WHATIF=qwen3.5:9b
LLM_MODEL_QUIZ=qwen3.5:4b   # Stage 1 hotfix; Ollama 0.20+ 이후 gemma4:e2b 로 원복
LLM_MODEL_RAG=qwen3.5:4b
LLM_MODEL_GRADE=qwen3.5:4b
```

#### Stage 1 dry-run (Mac 단일 호스트 — LARGE=FAST)

같은 endpoint 지만 feature 별 라우팅 코드 경로를 운영 트래픽으로 검증. 부작용 0, env 만 추가.

**검증 명령 (in-container):**
```bash
docker compose exec backend python3 -c "
import logging,sys; logging.basicConfig(level=logging.INFO,stream=sys.stdout)
from features.compliance.regulation_qa import _call_ollama
for f in ['rag_answer','quiz_gen','short_answer_grade','whatif_nl_route']:
    kw={'feature':f,'num_predict':30,'timeout':60.0}
    if f=='whatif_nl_route': kw.update(format='json',temperature=0.1)
    print(f, _call_ollama('Reply with the digit only: 1+1=', **kw))
"
```
기대: 4 feature 모두 200 OK + `INFO ollama_call feature=<f> model=<m> base=<url>` 4건.

**관측 운용 (1주):**
```bash
# 일일 feature별 라우팅 카운트
docker compose logs --since=24h backend | grep "ollama_call feature=" \
  | awk '{for(i=1;i<=NF;i++) if($i~/feature=/) print $i}' | sort | uniq -c

# 실패율 (룰 폴백 발생)
docker compose logs --since=24h backend | grep "Ollama 호출 실패" | wc -l
```

**rollback 트리거:** 실패율 baseline 2x 이상 또는 p95 latency 1.5x 이상 → `.env.docker` 에서 `OLLAMA_BASE_URL_LARGE`/`_FAST` 라인 주석처리 + `docker compose up -d --force-recreate backend` (코드는 그대로, Phase 1 단일 endpoint 동작).

#### Stage 2 진입 (NVIDIA 서버 / Cloud Run for GPU)

`docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d` — `ollama-large` (qwen3.5:9b) + `ollama-fast` (qwen3.5:4b 등) 두 service 자동 기동. 모델 pull 은 `ollama-large-init` / `ollama-fast-init` 가 1회 수행 후 종료.

진입 조건 (Stage 1 1주 관측 충족):
- 4 feature 라우팅 적중 100% (룰 폴백 0건 — gemma4 hotfix 적용 상태)
- 응답 latency p95 baseline ±20%
- 회귀 (`make test`, 필요 시 `make test-docker`) 무회귀

Stage 1 → Stage 2 변경 표면적: `.env.docker` 의 `OLLAMA_BASE_URL_FAST` URL 만 사내 서버 IP 로 swap (1줄).

### Phase 3 — Feature 마이크로서비스

추출 순서: D11 industry_trend → D17 financial_baseline → D6 supplier ETL → D9 collab/Jira → D14/D15 핵심.

각 추출 시:
1. `features/compliance/<feature>.py` → 별도 FastAPI app + Dockerfile
2. `docker-compose.yml` 에 service 추가
3. `nginx/rp.conf` 의 해당 path 를 새 service 로 reverse_proxy
4. backend 의 import 를 HTTP 호출로 swap (httpx)

DB 분리: sqlite → PostgreSQL 마이그 (alembic 또는 단순 SQL dump → restore).

## 보안

- `.env` / `.env.docker` 는 gitignored — chmod 600 권장
- 운영 진입 시 `JIRA_API_TOKEN` / `DART_API_KEY` 등은 docker secrets 또는 SOPS 활용
- nginx-rp 는 plain HTTP (port 8080) — 외부 노출 시 Caddy 추가 또는 ALB/Cloud Load Balancer TLS 종단

## 검증 체크리스트

- [ ] `make setup` 성공 (호스트 Ollama + 모델 pull)
- [ ] `make up` 후 `make ps` 모든 service `running` / `healthy`
- [ ] `curl http://localhost:8080/healthz` → 200
- [ ] `curl http://localhost:8080/api/health` → `{"status":"ok",...}`
- [ ] `curl http://localhost:8080/api/compliance/changes/recent?limit=3` → JSON 응답
- [ ] `make test-collect` → collection/import 오류 없이 완료
- [ ] `make test` → 호스트 `.venv` 기준 pytest 재현. 일부 baseline fail 은 Phase 2 와 무관 (jira_sync, phase_a_models, phase_e_inline_actions 등)
- [ ] Phase 2 활성 시: `docker compose exec backend python3 -c "from config import resolve_llm_route; print(resolve_llm_route('rag_answer'))"` → `(<FAST URL>, 'qwen3.5:4b')`
- [ ] `http://localhost:8080/` 브라우저 → SPA 로드

## Cloud 배포 (참고)

### AWS ECS Fargate
- compose → `ecs-cli compose convert` 또는 `copilot init`
- Ollama 는 ECS GPU instance (g5/g6) 사용 — Fargate GPU 미지원
- DB: RDS PostgreSQL (Phase 3)
- Cache: ElastiCache Redis

### GCP Cloud Run for GPU
- backend / frontend / nginx-rp → Cloud Run (CPU)
- Ollama → Cloud Run for GPU (NVIDIA L4) — 별도 region/quota 필요
- DB: Cloud SQL (Phase 3) 또는 Firestore (이미 일부 사용 중)
- Cache: Memorystore Redis

## 자주 묻는 질문

**Q. Mac 호스트 Ollama 대신 컨테이너 안 Ollama 도 가능?**
A. 가능하지만 Apple Silicon Metal GPU 가속 없음 (CPU only) → ~10x 느림. dev 검증 시에만 권장.

**Q. data/ 는 어떻게 백업?**
A. host bind mount (`./data:/app/data`) 라 호스트 `./data` 만 백업.

**Q. compose 파일 여러 개 병행 실행?**
A. `make up` 으로 시작한 stack 은 `name: ajin-compliance`. 다른 stack 은 다른 name 으로 격리됨.

**Q. 로그 영속?**
A. `./logs:/app/logs` bind mount. `docker compose logs` 는 별도로 stdout 수집.

---

운영 중 이슈 발생 시: `make logs` 출력 + `make ps` 결과 첨부해 보고.
