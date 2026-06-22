<!--
  README.md
  Lemon Healthcare Project — 건강의신 AI 모델
  최종 수정일: 2026-05-15
-->

<div align="center">

# 🍋 Lemon Healthcare — 건강의신 AI 모델

### 영양제·식단·활동 데이터를 바탕으로 만성질환자 중심의 건강관리 보조 흐름을 검증하는 Lemon Aid 팀 프로젝트

[![Status](https://img.shields.io/badge/status-team%20branch%20workspace-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-Pydantic%20v2-009688?logo=fastapi&logoColor=white)]()
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM%20default-000000)]()
[![OCR](https://img.shields.io/badge/OCR-fail--closed%20by%20default-4285F4)]()
[![Tests](https://img.shields.io/badge/latest%20local%20pytest-390%20passed%2C%202%20skipped-brightgreen)]()

**[현재 상태](#-현재-구현-상태) · [빠른 시작](#-빠른-시작) · [폴더 구조](#-폴더-구조) · [검증 명령](#-검증-명령) · [문서 허브](#-문서-허브) · [협업 규칙](#-협업-규칙)**

</div>

---

## ⚠️ 이 브랜치 주의 — DB 연결이 `lemon_app`(FORCE RLS Stage-2)로 바뀌었습니다

> **이 브랜치(`feat/ai-agent-chat-import`)를 받아 로컬에서 실행하기 전에 꼭 읽어주세요.**
> `docker-compose.yml`의 백엔드 DB 연결이 슈퍼유저 `lemon` → **비-슈퍼유저 요청 역할 `lemon_app`** 으로 전환되었습니다(FORCE RLS Stage-2 flip, 커밋 `a957d1a4`). 준비가 안 된 로컬 DB에서는 **백엔드가 DB 연결에 실패하거나(인증) owner write가 막힐(fail-closed) 수 있습니다.** 아래 1회 설정만 하면 됩니다.

### 무엇이 / 왜 바뀌었나
- 지금까지 앱은 모든 테이블을 소유한 **슈퍼유저 `lemon`** 으로 접속했습니다. 슈퍼유저는 Row-Level Security(RLS)를 **우회**하므로, 행 단위 소유자 격리 정책이 실제로는 적용되지 않았습니다.
- 이제 일반 요청은 **`lemon_app`(NOSUPERUSER·NOBYPASSRLS)** 으로 접속합니다. 그러면 사용자 데이터 read/write가 요청별 GUC(`is_local` owner-subject)를 통해 **`0023b`/`0023c`/`0041` RLS 정책을 강제로 따르게** 됩니다 — "내 데이터만" 보고 쓰는 것을 **DB 레벨에서 보장**합니다.
- 단, **out-of-band 감사 로그 기록**과 **post-commit 학습 쓰기**는 슈퍼유저 권한이 필요하므로, 이 둘만 별도의 **privileged 엔진(`lemon`)** 으로 분리했습니다(`AUDIT_DATABASE_URL`, `LEARNING_DATABASE_URL`).
- 백엔드는 기동 시 `verify_stage2_privileged_database_urls`(`backend/Nutrition-backend/src/main.py`) 가드로 **"DATABASE_URL이 `lemon_app`인데 AUDIT/LEARNING이 privileged가 아니면 즉시 기동 실패"** 하도록 fail-fast 합니다.

### 현재 `docker-compose.yml`(backend) 설정 요약
```yaml
DATABASE_URL:          postgresql+asyncpg://lemon_app:lemon_app@db:5432/lemon   # 요청 역할 → RLS 적용
AUDIT_DATABASE_URL:    postgresql+asyncpg://lemon:lemon@db:5432/lemon           # privileged(감사)
LEARNING_DATABASE_URL: postgresql+asyncpg://lemon:lemon@db:5432/lemon           # privileged(학습)
# 마이그레이션은 DDL 권한이 필요하므로 privileged lemon으로 실행한다(lemon_app은 alembic_version 권한 없음):
#   DATABASE_URL='postgresql+asyncpg://lemon:lemon@db:5432/lemon' alembic upgrade head
```

### 로컬에서 실행하려면 (필수 1회 설정)
`lemon_app` 역할은 마이그레이션 `0023a`가 **LOGIN 권한은 주지만 비밀번호는 만들지 않습니다**(비밀번호를 마이그레이션에 넣으면 시크릿이 커밋되므로). 따라서 앱이 `lemon_app:lemon_app`으로 접속하려면 **로컬 DB에서 비밀번호를 직접 설정**해야 합니다.

```bash
# 1) 마이그레이션 최신화(역할·권한·RLS 정책 생성) — compose가 기동 시 privileged URL로 자동 실행합니다.
# 2) lemon_app 비밀번호를 compose 기본값과 동일하게 설정:
docker exec -i lemon-aid-db-1 psql -U lemon -d lemon \
  -c "ALTER ROLE lemon_app LOGIN PASSWORD 'lemon_app';"
# 3) 백엔드 재기동:
docker compose up -d backend
```

> 운영(production)에서는 `lemon_app` 비밀번호를 **시크릿에서 주입**하고 `DATABASE_URL`도 그 시크릿을 사용하세요. `'lemon_app'`은 로컬 개발 편의값일 뿐입니다.

### 잘 됐는지 확인
- 백엔드 health 200, `GET /me/privacy/consents` 200(감사 이벤트가 `audit_logs`에 기록되면 privileged 엔진이 정상 동작하는 것).
- 요청 연결은 `lemon_app`, 감사/학습 연결은 `lemon`으로 분리되어 보이면 정상:
  ```bash
  docker exec -i lemon-aid-db-1 psql -U lemon -d lemon \
    -c "SELECT usename, count(*) FROM pg_stat_activity WHERE datname='lemon' GROUP BY usename;"
  ```
- `permission denied` / RLS 관련 에러가 **0** 이어야 합니다.

### 증상별 대처
| 증상 | 원인 | 해결 |
|---|---|---|
| 기동 직후 DB 연결 실패(auth) | `lemon_app` 비밀번호 미설정 | 위 2단계 `ALTER ROLE … PASSWORD 'lemon_app'` 실행 |
| 기동은 되는데 owner write가 막힘(fail-closed) | 마이그레이션 미적용(역할·정책 없음) 또는 옛 컨테이너 재사용 | privileged URL로 `alembic upgrade head` 재적용 후 재기동 |
| 기동 가드에서 즉시 실패 | AUDIT/LEARNING이 privileged 아님 | compose의 `AUDIT_DATABASE_URL`/`LEARNING_DATABASE_URL`을 `lemon`으로 |
| 코드 변경이 반영 안 됨 | 소스가 이미지에 baked(바인드마운트 아님) | `docker compose build backend` 후 재기동 |

### 원래대로(슈퍼유저 `lemon`) 롤백
`docker-compose.yml`에서 `DATABASE_URL`을 `lemon:lemon@db`로 되돌리고, `AUDIT_DATABASE_URL`/`LEARNING_DATABASE_URL`과 alembic의 privileged override를 제거한 뒤, 필요하면 `ALTER ROLE lemon_app PASSWORD NULL;`로 로그인을 닫고 컨테이너를 재기동하세요.

---

## 📋 프로젝트 정의

Lemon Aid는 (주)레몬헬스케어 기업 프로젝트 맥락에서 진행하는 AI 헬스케어 팀 프로젝트입니다. 현재 저장소는 건강의신 직접 연동 완성본이 아니라, 영양제 분석을 중심으로 음식 사진 분석, AI agent chat, 모바일/프론트엔드 파트를 통합하기 위한 참조 구현 작업 공간입니다.

서비스 방향은 진단·처방·치료가 아닌 건강관리 보조입니다. 처방전·검사표 같은 민감 문서는 OCR intake와 사용자 확인 흐름으로 제한하고, 복용량 변경을 직접 안내하지 않는 안전 정책을 기본값으로 둡니다.

---

## ✅ 현재 구현 상태

| 영역 | 상태 | 주요 경로 | 설명 |
|------|------|-----------|------|
| Nutrition backend | 구현·검증 진행 중 | `backend/Nutrition-backend/` | FastAPI 런타임, 영양제 OCR/파싱, KDRIs 룩업, 체중 예측, 개인정보/동의, regulated OCR intake, 테스트가 이 폴더에 모여 있습니다. |
| Food image analysis | 구조 준비 | `backend/food_image_analysis/`, `data/food_images/` | 음식 사진 분석 담당 폴더와 데이터 표준 구조가 준비되어 있고, 실제 모델/서비스 구현은 다음 단계입니다. |
| AI agent chat | 구조 준비 | `backend/ai_agent_chat/`, `docs/Chat-docs/` | AI agent chat 담당 폴더가 준비되어 있고, 대화 런타임 구현은 후속 작업입니다. |
| Frontend | 구조 준비 | `frontend/` | 팀 통합용 프론트엔드 위치만 정의된 상태입니다. |
| Mobile | 구조 준비 | `mobile/` | Flutter/Xcode 기반 UI/UX 작업을 위한 위치가 정의되어 있습니다. |
| Data | 일부 구현 | `data/nutrition_reference/`, `data/supplement_images/`, `data/food_images/` | KDRIs 2025 파생 CSV와 taxonomy/manifests/splits 구조를 포함합니다. 원본 이미지·PDF·ZIP은 Git에 올리지 않습니다. |
| Docs | 정리 완료 | `docs/`, `docs/Nutrition-docs/`, `docs/Integration-docs/` | 공통 문서와 Nutrition 담당 상세 문서를 분리했습니다. |
| CI/GitHub templates | 현재 브랜치에는 없음 | `docs/05-github-guidelines.md` | `.github/` 워크플로와 템플릿은 현재 푸시 트리에 포함하지 않았습니다. 협업 규칙은 문서 기준으로 관리합니다. |

최근 로컬 검증 기준:

- KDRIS 2025 데이터셋 검증: `1795` rows 통과
- `black --check .` 통과
- `ruff check .` 통과
- 핵심 backend mypy 통과
- `pytest -q --no-cov`: `390 passed, 2 skipped`

---

## 🏗 아키텍처

```text
사용자 입력
  ├─ 영양제 라벨 이미지 또는 OCR 텍스트
  ├─ 음식 이미지/식단 정보 (후속 구현)
  └─ AI agent chat 입력 (후속 구현)
        │
        ▼
FastAPI Backend
  ├─ backend/Nutrition-backend/src/api/v1/
  ├─ backend/Nutrition-backend/src/services/
  ├─ backend/Nutrition-backend/src/nutrition/
  ├─ backend/Nutrition-backend/src/prediction/
  ├─ backend/Nutrition-backend/src/ocr/
  ├─ backend/Nutrition-backend/src/llm/
  ├─ backend/Nutrition-backend/src/regulated/
  └─ backend/Nutrition-backend/src/learning/
        │
        ├─ PostgreSQL / Redis 설정값 보유
        ├─ KDRIs 2025 / nutrient reference data
        ├─ Ollama local LLM 기본 경로
        └─ Google Vision / CLOVA / PaddleOCR optional OCR adapters
```

### 영양제 분석 흐름

```text
이미지 또는 OCR 텍스트 입력
  → 이미지 크기·파일 제한 검증
  → OCR provider 선택
      기본값: OCR_PRIMARY_PROVIDER=none, ALLOW_EXTERNAL_OCR=false
      opt-in: Google Vision, CLOVA, PaddleOCR, YOLO ROI, Ollama vision assist
  → OCR 텍스트 정리
  → Ollama 기반 구조화 parser
  → 성분·함량·섭취 방법 후보 추출
  → KDRIs / 영양 기준 / 주의 성분 규칙과 매칭
  → 사용자 확인 후 저장 또는 폐기
```

Google Vision 관련 코드와 설정은 존재하지만 기본 운영 자세는 fail-closed입니다. 외부 OCR로 이미지 바이트를 보내려면 `ALLOW_EXTERNAL_OCR=true`와 provider별 인증 설정을 명시해야 합니다.

---

## 🛠 기술 스택

### Backend

- Python `>=3.13`
- FastAPI, Pydantic v2, SQLAlchemy, Alembic
- pytest, pytest-cov, httpx
- Black, Ruff, mypy strict
- PostgreSQL/Redis 설정값 보유

### AI / OCR

- Local LLM 기본값: Ollama
- Text model 기본 예시: `qwen3.5:9b`
- Vision model 기본 예시: `gemma4:e4b`
- OCR 기본값: disabled
- Optional OCR: Google Vision API key/ADC, NAVER CLOVA OCR, PaddleOCR
- Optional ROI: YOLO 기반 label region helper

### Frontend / Mobile

- `frontend/`: 팀 통합용 프론트엔드 작업 위치
- `mobile/`: Flutter + Xcode 기반 UI/UX 및 모바일 구현 위치

---

## 🚀 빠른 시작

로컬 smoke는 두 가지 방식으로 실행할 수 있습니다.

- 빠른 코드 반복: 로컬 Python venv에서 FastAPI 실행
- 컨테이너 재현: `docker-compose.yml`로 pgvector PostgreSQL, Redis, FastAPI backend 실행

### 1. 저장소 준비

```bash
git clone https://github.com/Lemon-Aid-KDT/Lemon-sin.git
cd Lemon-sin
git switch feat/db-internal-learning-pipeline
```

로컬 작업 경로에서 바로 실행하는 경우:

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid
```

### 2. Backend 환경 구성

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env
```

`Settings`는 프로젝트 루트 `.env`와 `backend/.env`를 모두 읽습니다. 실제 키는 `.env`에만 넣고, `.env`는 Git에 커밋하지 않습니다.

### 3. Backend 실행

로컬 Python으로 실행:

```bash
cd backend
source .venv/bin/activate
python -m uvicorn src.main:app --app-dir Nutrition-backend --reload --port 8000
```

Docker Compose로 실행:

```bash
docker compose build backend
docker compose up -d db redis backend
```

Compose backend는 Docker Desktop 개발 환경에서 로컬 Ollama로 접근할 수 있도록
`OLLAMA_BASE_URL=http://host.docker.internal:11434`를 기본값으로 사용합니다. 이 alias는
`ENVIRONMENT=development`에서만 local LLM guard를 통과합니다.

동작 확인:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## 🔐 환경 변수 기준

기본 템플릿은 `backend/.env.example`입니다. 실제 로컬 키는 루트 `.env` 또는 `backend/.env`에 둡니다.

핵심 기본값:

```dotenv
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/lemon
REDIS_URL=redis://localhost:6379/0

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_VISION_MODEL=gemma4:e4b
ALLOW_EXTERNAL_LLM=false

OCR_PRIMARY_PROVIDER=none
ALLOW_EXTERNAL_OCR=false
GOOGLE_VISION_AUTH_MODE=api_key
GOOGLE_CLOUD_API_KEY=

FEATURE_PRESCRIPTION_OCR_INTAKE=false
FEATURE_LAB_RESULT_OCR_INTAKE=false
FEATURE_DOSAGE_CHANGE_RECOMMENDATION=false
FEATURE_MEDICATION_SAFETY_ALERT=false
```

운영 환경에서는 외부 LLM 사용을 금지하고, Google Vision 운영 사용 시 `GOOGLE_VISION_AUTH_MODE=adc`, `GOOGLE_CLOUD_PROJECT`, attached service account, 별도 승인 게이트가 필요합니다.

Google Vision local smoke에서 `status 401`이 나오면 endpoint 연결 문제가 아니라
`GOOGLE_CLOUD_API_KEY` 또는 ADC 권한 문제입니다. CLOVA/PaddleOCR/Ollama 경로와 분리해서
키 재발급, Cloud Vision API 사용 설정, API key restriction을 먼저 확인합니다.

공식 참고:

- Docker Compose CLI: <https://docs.docker.com/reference/cli/docker/compose/>
- Docker Compose services: <https://docs.docker.com/compose/compose-file/05-services/>
- Docker Desktop host networking: <https://docs.docker.com/desktop/features/networking/>

---

## 📂 폴더 구조

```text
Lemon-Aid/
├── README.md
├── PROJECT_GUIDE.md
├── guide.html
├── config/
│   ├── implementation-readiness.settings.json
│   └── service-segmentation.settings.json
├── backend/
│   ├── Nutrition-backend/
│   │   ├── src/
│   │   │   ├── api/v1/
│   │   │   ├── algorithms/
│   │   │   ├── db/
│   │   │   ├── learning/
│   │   │   ├── llm/
│   │   │   ├── models/
│   │   │   ├── nutrition/
│   │   │   ├── ocr/
│   │   │   ├── prediction/
│   │   │   ├── regulated/
│   │   │   ├── security/
│   │   │   ├── services/
│   │   │   └── vision/
│   │   └── tests/
│   ├── food_image_analysis/
│   ├── ai_agent_chat/
│   ├── alembic/
│   ├── scripts/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pyproject.toml
├── data/
│   ├── nutrition_reference/
│   │   ├── kdris/
│   │   ├── mfds/
│   │   └── nutrient/
│   ├── supplement_images/
│   │   ├── raw/
│   │   ├── interim/
│   │   ├── processed/
│   │   ├── splits/
│   │   ├── manifests/
│   │   ├── quarantine/
│   │   └── scripts/
│   └── food_images/
│       ├── raw/
│       ├── interim/
│       ├── processed/
│       ├── splits/
│       ├── manifests/
│       ├── quarantine/
│       └── scripts/
├── docs/
│   ├── 01-project-overview.md
│   ├── 03-project-intent.md
│   ├── 05-github-guidelines.md
│   ├── 06-tech-stack.md
│   ├── 10-compliance-checklist.md
│   ├── Integration-docs/
│   ├── Nutrition-docs/
│   ├── Food-docs/
│   └── Chat-docs/
├── frontend/
├── mobile/
├── outputs/
└── records/
```

### Git에 올리지 않는 항목

- `.env`, `.env.local`, API key 원본 폴더
- `.venv`, cache, `__pycache__`, coverage/htmlcov
- 원본 이미지 데이터, AI Hub 원본, 친구 제공 원본
- KDRI 원본 PDF/ZIP/HWPX, 발표용 PDF/PPTX/DOCX
- 대용량 모델 weight/checkpoint

원본 데이터는 로컬 또는 외부 저장소에 보존하고, Git에는 taxonomy, manifest, split CSV, review CSV, 파생된 작은 reference 파일만 올리는 기준입니다.

---

## 🧪 검증 명령

Backend 기준:

```bash
cd backend
source .venv/bin/activate

python -m json.tool ../config/implementation-readiness.settings.json
python -m json.tool ../config/service-segmentation.settings.json
python scripts/validate_kdris_dataset.py

python -m black --check .
python -m ruff check .
python -m mypy \
  Nutrition-backend/src Nutrition-backend/tests \
  food_image_analysis/src food_image_analysis/tests \
  ai_agent_chat/src ai_agent_chat/tests
python -m pytest -q --no-cov
```

주의: `backend/scripts/digitize_kdris_2025_summary.py`는 KDRI 원본 PDF 디지털화 보조 스크립트라 선택 의존성 `pdfplumber`가 필요합니다. 일반 backend 검증 범위에서는 핵심 패키지와 테스트 경로 mypy를 기준으로 봅니다.

---

## 📖 문서 허브

### 공통 문서

| 목적 | 문서 |
|------|------|
| 프로젝트 개요 | [`docs/01-project-overview.md`](./docs/01-project-overview.md) |
| 프로젝트 의도 | [`docs/03-project-intent.md`](./docs/03-project-intent.md) |
| GitHub 협업 규칙 | [`docs/05-github-guidelines.md`](./docs/05-github-guidelines.md) |
| 기술 스택 요약 | [`docs/06-tech-stack.md`](./docs/06-tech-stack.md) |
| 컴플라이언스 체크리스트 | [`docs/10-compliance-checklist.md`](./docs/10-compliance-checklist.md) |
| CI/PR/통합 운영 | [`docs/Integration-docs/01-ci-pr-integration-operations.md`](./docs/Integration-docs/01-ci-pr-integration-operations.md) |

### 파트별 문서

| 파트 | 문서 경로 |
|------|-----------|
| Nutrition | [`docs/Nutrition-docs/`](./docs/Nutrition-docs/) |
| Food | [`docs/Food-docs/`](./docs/Food-docs/) |
| Chat | [`docs/Chat-docs/`](./docs/Chat-docs/) |
| Backend structure | [`backend/README.md`](./backend/README.md) |
| Nutrition backend | [`backend/Nutrition-backend/README.md`](./backend/Nutrition-backend/README.md) |

---

## 🤝 협업 규칙

브랜치는 기능 단위로 분리하고, 이름은 `<type>/<scope>-<kebab-subject>` 형식을 사용합니다.

기본 흐름:

```bash
git switch feat/db-internal-learning-pipeline
git fetch origin
git merge origin/develop
# 작업
git add -A
git commit
git push origin feat/db-internal-learning-pipeline
```

커밋 메시지는 Conventional Commits를 기본으로 합니다. 현재 hook은 Lore format과
`Co-authored-by: OmX <omx@oh-my-codex.dev>` trailer를 요구할 수 있습니다.

---

## 🗺 다음 작업 우선순위

1. 최상위 README와 실제 브랜치 구조를 계속 동기화
2. `food_image_analysis` 실제 모델/API 스켈레톤 확장
3. `ai_agent_chat` 대화 런타임 계약 정의
4. `frontend`/`mobile` 초기 앱 구조 생성
5. 팀 통합용 `.github` CI/PR 템플릿을 별도 합의 후 복원
6. OCR fixture 기반 Google Vision, CLOVA, PaddleOCR 비교 리포트 작성
7. 원본 이미지/문서 데이터의 외부 저장소 정책 확정

---

## ⚖️ 컴플라이언스 고지

본 프로젝트의 결과는 건강관리 참고 정보 제공을 목표로 하며, 진단·처방·치료를 대체하지 않습니다.

금지 기본값:

- 질병 진단 또는 치료 판단
- 약물 중단·대체·증량·감량 직접 지시
- 검사 수치만으로 질환 확정 표현
- 의료 전문가 상담을 대체하는 문구
- 식별 가능한 건강정보의 외부 LLM 전송

처방전·검사표 OCR은 intake와 사용자 확인 흐름으로 제한합니다. 실제 복용 변경이나 임상 판단이 필요한 경우 의사 또는 약사 상담으로 연결하는 것이 기본 정책입니다.

---

## 🙏 참고 자원

- 한국영양학회 / 보건복지부 KDRIs
- 식품의약품안전처 식품영양성분 및 건강기능식품 데이터
- 농촌진흥청 국가표준식품성분표
- AI Hub 음식 이미지 데이터셋
- Ollama local runtime
- Google Vision, NAVER CLOVA OCR, PaddleOCR
- FastAPI, Pydantic, SQLAlchemy, pytest, Black, Ruff, mypy

---

<div align="center">

### 🍋 Lemon Aid

만성질환자 중심의 영양제·식단·활동 분석을 안전하게 검증하기 위한 팀 프로젝트 작업 공간

</div>
