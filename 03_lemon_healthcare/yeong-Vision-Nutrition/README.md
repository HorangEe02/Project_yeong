<!-- 
  README.md
  Lemon Healthcare Project — 건강의신 AI 모델
  최종 작성일: 2026-05-03
-->

<div align="center">

# 🍋 Lemon Healthcare — 건강의신 AI 모델

### 영양제·식단·활동을 통합 분석하여 만성질환자 중심의 맞춤형 건강 관리를 제공하는 AI 헬스케어 플랫폼

[![Status](https://img.shields.io/badge/status-in%20development-yellow)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Phase](https://img.shields.io/badge/phase-0%20%7C%201%20%7C%202%20%7C%203%20%7C%204-orange)]()

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)]()
[![Flutter](https://img.shields.io/badge/Flutter-3.24+-02569B?logo=flutter&logoColor=white)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)]()
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2.x-FDB515?logo=timescale&logoColor=white)]()
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)]()
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)]()

[![Cloud Vision](https://img.shields.io/badge/Google_Cloud_Vision-OCR-4285F4?logo=googlecloud&logoColor=white)]()
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-000000?logo=ollama&logoColor=white)]()
[![HealthKit](https://img.shields.io/badge/Apple-HealthKit-000000?logo=apple&logoColor=white)]()
[![Health Connect](https://img.shields.io/badge/Google-Health_Connect-4285F4?logo=google&logoColor=white)]()

[![Backend CI](https://img.shields.io/badge/Backend_CI-not%20yet-lightgrey)]()
[![Mobile CI](https://img.shields.io/badge/Mobile_CI-not%20yet-lightgrey)]()
[![Coverage](https://img.shields.io/badge/coverage-pending-lightgrey)]()

---

**[📖 문서](#-문서-허브) · [🚀 빠른 시작](#-빠른-시작-quick-start) · [🏗 아키텍처](#-아키텍처) · [🛠 기술 스택](#-기술-스택) · [🗺 로드맵](#-로드맵)**

</div>

---

## 📋 한 줄 정의

> 영양제 라벨 사진 한 장과 식단 정보로, **부족 영양소 추천 · 영양 권장량 · 체중 변화 예측 · 운동 권고 · 목적별(눈/간/피로) 분석** 5가지를 한 번에 제공하는 AI 헬스케어 플랫폼.  
> *(주)레몬헬스케어 발주, 경북대학교 AI/빅데이터 전문가 양성 과정 협업 프로젝트.*

## 🎯 누구를 위한 서비스인가

```
🩺 1차 핵심 페르소나 — 김건강 (52세, 만성질환 관리자)
   고혈압·당뇨 전단계 진단 받음. 영양제 4종 동시 복용 중.
   "약과 영양제가 충돌하지 않을까?", 
   "내 만성질환에 맞는 운동·영양은?" 같은 질문을 매일 한다.

📊 2차 확장 페르소나 — 박직장 (38세, 예방 단계 직장인)  
   정기 검진에서 콜레스테롤·체중 경고. 시간이 없다.
   "최소 시간으로 만성질환을 예방하고 싶다."
```

> 🔍 **상세 페르소나·차별화 전략**: [`docs/03-project-intent.md`](./docs/03-project-intent.md)

## ✨ 핵심 차별점 (vs 필라이즈·CalZen 등 선행 주자)

| 차별 무기 | 본 프로젝트 | 경쟁 서비스 |
|----------|-----------|-----------|
| 🏥 **의료기관 네트워크 연계 가능성** | ✅ LDB (130여 의료기관) | ❌ |
| 🧬 **만성질환 v4 가중 알고리즘** | ✅ 임상적 정교함 | ❌ |
| 👥 **검증된 사용자 베이스** | ✅ 770만+ (청구의신) | △ |
| 📊 **5종 출력 한 번에** | ✅ 통합 | △ (단편) |
| ⚖️ **공식 데이터 기반** | ✅ KDRIs·식약처 | △ |

> 🔍 **상세 시장·경쟁 분석**: [`docs/04-market-research.md`](./docs/04-market-research.md)

---

## 🏗 아키텍처

```
┌────────────────────────────────────────────────────────────┐
│                   👤 사용자 (페르소나 B/A)                  │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│                📱 Flutter App (iOS + Android)                │
│   영양제 카메라 · 식단 입력 · 5종 출력 대시보드               │
│   📦 health 패키지 → HealthKit + Health Connect 자동 연동    │
└────────────────────────────────────────────────────────────┘
                              │ HTTPS / REST
                              ▼
┌────────────────────────────────────────────────────────────┐
│              🐍 FastAPI Backend (Python 3.11+)              │
│   알고리즘 (v1~v4 · BMR/TDEE · 7-step) · API · 인증         │
└────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
   │PostgreSQL│   │ Cloud   │    │ Claude  │    │  Redis  │
   │   +      │   │ Vision  │    │   API   │    │  Cache  │
   │TimescaleDB│  │  (OCR)  │    │  (LLM)  │    │         │
   └─────────┘    └─────────┘    └─────────┘    └─────────┘
                              │
                              ▼
        🌐 외부 데이터: KDRIs · 식약처 · 농진청 · AI Hub
```

### 🔄 영양제 사진 → 결과 (예상 응답 시간 2.5~6초)

```
📸 사용자 촬영
   ↓
📤 Flutter → FastAPI 업로드 (multipart)
   ↓
🔑 SHA-256 해시 → Redis 캐시 조회
   ↓ (캐시 미스)
👁 Google Cloud Vision OCR (~1초)
   ↓
🤖 Ollama 로컬 LLM 구조화 (모델별 측정)
   ↓
📚 식약처 DB 매칭 (~0.2초)
   ↓
💾 PostgreSQL 저장 + Redis 캐싱
   ↓
📦 결과 JSON 반환 → 5종 출력 대시보드
```

> 🔍 **상세 아키텍처·기술 의사결정**: [`docs/06-tech-stack.md`](./docs/06-tech-stack.md)

---

## 🛠 기술 스택

### 백엔드
- **언어·프레임워크**: Python 3.11+ · FastAPI 0.110+ · Pydantic v2
- **데이터베이스**: PostgreSQL 16 · TimescaleDB 2.x (시계열) · Redis 7
- **테스트**: pytest · pytest-cov · httpx (50+ 단위 테스트)
- **품질**: Black · Ruff · mypy · pre-commit hooks

### 모바일
- **프레임워크**: Flutter 3.24+ · Dart 3.x
- **상태 관리**: Riverpod (또는 Provider)
- **헬스 데이터**: `health` 패키지 (HealthKit + Health Connect 통합)
- **API 통신**: Dio + Retrofit

### AI / 외부 API
- **OCR**: Google Cloud Vision API (주력) · Naver CLOVA OCR (백업)
- **LLM**: Ollama 로컬 LLM (qwen3.5 / gemma4) · 외부 LLM은 비식별·승인 환경 전용
- **데이터셋**: AI Hub 한국 음식 이미지 (Phase 3)

### 인프라 · DevOps
- **컨테이너**: Docker + Docker Compose
- **CI/CD**: GitHub Actions (3개 워크플로 — backend/mobile/docs)
- **클라우드**: NCP / AWS / GCP (택 1, 학생 크레딧 활용)
- **모니터링**: Python logging + Sentry (선택)

### 데이터 출처 (모두 공공)
- 한국영양학회 KDRIs 2020 · 식약처 식품영양성분 Open API
- 식약처 건강기능식품 원료 DB · 농진청 국가표준식품성분표

> 🔍 **각 기술 의사결정 근거·대안 비교**: [`docs/06-tech-stack.md`](./docs/06-tech-stack.md)  
> 🔍 **데이터·API 카탈로그**: [`docs/09-data-catalog.md`](./docs/09-data-catalog.md)

---

## 🚀 빠른 시작 (Quick Start)

### 사전 요구사항

| 도구 | 버전 | 확인 명령 |
|------|------|---------|
| Python | 3.11+ | `python --version` |
| Flutter | 3.24+ | `flutter --version` |
| Docker | 최신 | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| Git | 최신 | `git --version` |

### 1️⃣ 저장소 클론

```bash
git clone https://github.com/<team>/lemon-healthcare-project.git
cd lemon-healthcare-project
```

### 2️⃣ 백엔드 셋업 (Docker Compose 권장)

```bash
# 환경 변수 설정
cd backend
cp .env.example .env
# .env 파일 열어 API 키 입력 (아래 '환경 변수' 섹션 참조)

# Docker Compose로 한 번에 시작
cd ..
docker compose up -d

# 또는 로컬에서 직접 실행
cd backend
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

#### 동작 확인

```bash
# Swagger UI 확인
open http://localhost:8000/docs

# 헬스 체크 API
curl http://localhost:8000/health
# {"status": "ok"}
```

### 3️⃣ 모바일 셋업

```bash
cd mobile
flutter doctor                 # 환경 확인
flutter pub get                # 의존성 설치
flutter run                    # 시뮬레이터/실기기 실행
```

#### iOS (Mac 환경)

```bash
cd ios
pod install
cd ..
flutter run -d "iPhone 15"     # 시뮬레이터 지정
```

#### Android

```bash
flutter run -d <device_id>     # adb devices로 확인
```

### 4️⃣ 환경 변수 (`backend/.env`)

```bash
# 데이터베이스
DATABASE_URL=postgresql+asyncpg://lemon:lemon@localhost:5432/lemon
REDIS_URL=redis://localhost:6379/0

# 로컬 LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
ALLOW_EXTERNAL_LLM=false

# 외부 API 키
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
MFDS_API_KEY=...                  # 식약처 식품영양성분 API
CLOVA_OCR_API_KEY=...             # (선택) 백업 OCR

# 보안
JWT_SECRET=...                    # openssl rand -hex 32
ENCRYPTION_KEY=...                # AES-256 컬럼 암호화 키

# 환경
ENVIRONMENT=development           # development/staging/production
LOG_LEVEL=DEBUG
```

> ⚠️ **절대 `.env` 파일을 커밋하지 마세요.** `.gitignore`에 등록되어 있습니다.

### 5️⃣ Pre-commit Hooks 설치 (권장)

```bash
pip install pre-commit
pre-commit install
```

이후 모든 `git commit`이 자동 린트·포매팅 검증.

---

## 📂 폴더 구조

```
lemon-healthcare-project/
├── 📄 README.md                    # 이 문서
│
├── 📁 docs/                        # 기획·설계 문서 (10개)
│   ├── 01-project-overview.md      # 프로젝트 개요
│   ├── 02-background-problem.md    # 배경 및 문제 정의
│   ├── 03-project-intent.md        # 기획 의도·차별화
│   ├── 04-market-research.md       # 시장·경쟁사 분석
│   ├── 05-github-guidelines.md     # GitHub 협업 규칙
│   ├── 06-tech-stack.md            # 기술 스택
│   ├── 07-core-algorithm.md        # 핵심 알고리즘
│   ├── 08-implementation-plan.md   # 구현 계획
│   ├── 09-data-catalog.md          # 데이터·API 카탈로그
│   └── 10-compliance-checklist.md  # 컴플라이언스 체크리스트
│
├── 📁 backend/                     # Python 백엔드 (FastAPI)
│   ├── src/
│   │   ├── algorithms/             # v1~v4, 7-step 산출식
│   │   ├── ocr/                    # 영양제 OCR 파이프라인
│   │   ├── nutrition/              # KDRIs 룩업 + 결핍 진단
│   │   ├── prediction/             # 체중 예측
│   │   ├── activity/               # 활동점수
│   │   ├── api/                    # FastAPI 라우터
│   │   ├── models/                 # Pydantic 스키마, DB 모델
│   │   └── utils/
│   ├── tests/                      # pytest 50+
│   ├── requirements.txt
│   └── pyproject.toml              # Black·Ruff·mypy 설정
│
├── 📁 mobile/                      # Flutter 모바일 앱
│   ├── lib/
│   │   ├── screens/                # UI 화면
│   │   ├── widgets/                # 재사용 위젯
│   │   ├── services/               # API · HealthKit · Health Connect
│   │   ├── models/
│   │   └── utils/
│   ├── ios/                        # iOS 빌드 설정
│   ├── android/                    # Android 빌드 설정
│   ├── test/
│   ├── pubspec.yaml
│   └── analysis_options.yaml
│
├── 📁 data/                        # 정적 데이터
│   ├── kdris_2020.csv              # KDRIs 룩업 테이블
│   └── README.md                   # 출처·라이선스
│
├── 📁 notebooks/                   # 실험·EDA
├── 📁 scripts/                     # 보조 스크립트
│
├── 📁 .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/
│   ├── CODEOWNERS
│   └── workflows/                  # CI 워크플로 3개
│
├── 🔧 .gitignore
├── 🔧 .pre-commit-config.yaml
├── 🔧 .editorconfig
└── 🔧 docker-compose.yml
```

---

## 📖 문서 허브

본 프로젝트는 **10개의 핵심 문서**로 구성되어 있습니다. 어떤 질문이 있는지에 따라 적합한 문서로 바로 이동하세요.

### 🟢 1단계 — 비전·합의 (What·Why·Who)

| 질문 | 문서 |
|------|------|
| 이 프로젝트가 무엇인가? | [`01-project-overview.md`](./docs/01-project-overview.md) |
| 왜 만드는가? 어떤 문제를 해결하는가? | [`02-background-problem.md`](./docs/02-background-problem.md) |
| 누구를 위한 것이고, 어떻게 차별화되는가? | [`03-project-intent.md`](./docs/03-project-intent.md) |
| 시장과 경쟁사는 어떤가? | [`04-market-research.md`](./docs/04-market-research.md) |

### 🟡 2단계 — 협업 시스템 (How to Collaborate)

| 질문 | 문서 |
|------|------|
| 팀이 어떻게 함께 코딩할 것인가? | [`05-github-guidelines.md`](./docs/05-github-guidelines.md) |

### 🔵 3단계 — 실행 설계 (How to Build)

| 질문 | 문서 |
|------|------|
| 어떤 기술 스택을 쓰는가? 왜? | [`06-tech-stack.md`](./docs/06-tech-stack.md) |
| 알고리즘은 어떻게 동작하는가? | [`07-core-algorithm.md`](./docs/07-core-algorithm.md) |
| 언제·누가·어떻게 만드는가? | [`08-implementation-plan.md`](./docs/08-implementation-plan.md) |

### 🟣 추가 — 데이터·법규 (Data & Compliance)

| 질문 | 문서 |
|------|------|
| 어떤 데이터·API를 쓰고, 비용은 얼마인가? | [`09-data-catalog.md`](./docs/09-data-catalog.md) |
| 의료법·약사법·개인정보보호법은? | [`10-compliance-checklist.md`](./docs/10-compliance-checklist.md) |

> 💡 **처음 보시는 분이라면**: `01 → 02 → 03 → 04` 순서로 1단계 4개 문서만 읽으셔도 프로젝트의 전체 그림이 보입니다.

---

## 🛠 명령어 레퍼런스

### 백엔드 (Python)

```bash
# 개발 서버 실행 (Hot Reload)
uvicorn src.main:app --reload --port 8000

# 코드 포매팅
black src tests --line-length=100

# 린트
ruff check src tests
ruff check src tests --fix          # 자동 수정

# 타입 체크
mypy src --ignore-missing-imports

# 테스트
pytest                              # 전체
pytest -v                           # 상세
pytest --cov=src                    # 커버리지
pytest tests/unit/test_algorithms.py::test_v4_50f_example  # 특정 테스트

# 데이터베이스 마이그레이션 (Alembic)
alembic upgrade head                # 최신 적용
alembic revision -m "add user table" --autogenerate

# 의존성 추가
pip install <package>
pip freeze > requirements.txt
```

### 모바일 (Flutter)

```bash
# 환경 확인
flutter doctor -v

# 의존성
flutter pub get
flutter pub upgrade
flutter pub outdated

# 코드 포매팅
dart format lib test

# 정적 분석
flutter analyze

# 테스트
flutter test
flutter test --coverage

# 실행
flutter run                         # 기본 디바이스
flutter run -d <device_id>          # 특정 디바이스
flutter devices                     # 디바이스 목록

# 빌드
flutter build apk --debug           # Android Debug APK
flutter build apk --release         # Android Release APK
flutter build appbundle             # Google Play 업로드용
flutter build ios --debug --no-codesign  # iOS 빌드 검증
flutter build ipa                   # App Store 업로드용 (Mac만)

# 코드 생성 (build_runner)
dart run build_runner build --delete-conflicting-outputs
dart run build_runner watch         # 변경 감시
```

### Docker

```bash
# 전체 스택 시작
docker compose up -d

# 특정 서비스만
docker compose up -d postgres redis

# 로그 보기
docker compose logs -f backend
docker compose logs -f --tail=100 backend

# 종료
docker compose down                 # 볼륨 유지
docker compose down -v              # 볼륨 삭제 (DB 초기화)

# 재빌드
docker compose up -d --build

# 컨테이너 내부 진입
docker compose exec backend bash
docker compose exec postgres psql -U lemon -d lemon
```

### Git (Conventional Commits)

```bash
# 새 기능
git commit -m "feat(algo): add v1 step score calculation"

# 버그 수정
git commit -m "fix(ocr): handle empty supplement label edge case"

# 문서
git commit -m "docs(readme): update setup instructions"

# 리팩토링
git commit -m "refactor(api): split nutrition router"

# 테스트
git commit -m "test(algo): add edge cases for BMI categories"
```

> 🔍 **상세 컨벤션**: [`docs/05-github-guidelines.md`](./docs/05-github-guidelines.md)

---

## 🗺 로드맵

10주 학생 프로젝트 일정 (5-Phase 구조).

```
Week:    1     2-4         5-7              8-9          10
        ┌───┬───────────┬────────────────┬────────────┬──────┐
Phase:  │ 0 │     1     │       2        │     3      │  4   │
        │기획│ 핵심산출식 │ 영양제OCR MVP  │ 식단·고도화 │ 발표 │
        │조사│   PoC     │   + 모바일     │            │      │
        └───┴───────────┴────────────────┴────────────┴──────┘
         1주     3주          3주             2주        1주
```

### Phase 마일스톤

- ⬜ **Phase 0** (W1) — 환경 세팅, API 키 발급, 데이터 수급 계획
- ⬜ **Phase 1** (W2-W4) — v1~v4 + 7-step 산출식 PoC, 50+ 단위 테스트
- ⬜ **Phase 2** (W5-W7) — 영양제 OCR + 모바일 앱 + HealthKit 연동
- ⬜ **Phase 3** (W8-W9) — 식단 분석 + 5종 출력 통합 + 의료자문위 검토
- ⬜ **Phase 4** (W10) — 발표·시연

### 향후 계획 (Year 2~3)

- ⬜ ISMS-P 인증 추진
- ⬜ LDB-E 마이데이터 연계 (의료기관 진료 기록 통합)
- ⬜ FHIR KR Core 표준 적용
- ⬜ DTx (디지털치료기기) 진입 검토
- ⬜ 글로벌 확장 (일본·동남아)

> 🔍 **상세 일정·역할 분담·리스크 관리**: [`docs/08-implementation-plan.md`](./docs/08-implementation-plan.md)

---

## 🤝 기여하기 (Contributing)

본 프로젝트는 학생 팀 + 발주처 협업 프로젝트입니다.

### 기여 흐름

1. Issue 생성 (Bug Report / Feature Request 템플릿 사용)
2. `develop` 브랜치에서 `feature/<scope>-<description>` 분기
3. 작업 + Conventional Commits 형식의 커밋
4. PR 생성 (`docs/05-github-guidelines.md`의 PR 템플릿 자동 적용)
5. CI 통과 + 1명 이상 리뷰 → Squash & Merge

### 행동 강령

- 사람이 아니라 코드를 비판합니다.
- 의료법 표현 가이드를 준수합니다 (진단·처방 표현 금지).
- 민감 정보(API 키·개인정보)를 절대 커밋하지 않습니다.

> 🔍 **상세 협업 규칙**: [`docs/05-github-guidelines.md`](./docs/05-github-guidelines.md)

---

## ⚖️ 컴플라이언스 고지

> ⚠️ **본 서비스에서 제공하는 정보는 일반적인 건강 관리를 위한 참고 자료이며, 의사·약사·영양사의 전문적 진단이나 처방을 대체하지 않습니다.**  
> 증상이 있거나 만성질환을 앓고 계신 경우, 반드시 전문가와 상담하시기 바랍니다.

본 프로젝트는 다음 법령·표준을 준수합니다:

- 의료법 · 약사법 · 건강기능식품법
- 개인정보보호법 (민감정보 별도 동의)
- 정보통신망법
- 보건복지부 「비의료 건강관리서비스 가이드라인 (2차)」
- KISA ISMS-P 인증 기준 (정식 출시 전 추진)

> 🔍 **상세 컴플라이언스 체크리스트**: [`docs/10-compliance-checklist.md`](./docs/10-compliance-checklist.md)

---

## 👥 팀

```
경북대학교 AI/빅데이터 전문가 양성 과정 — TBD팀

🔧 Backend Engineer  : TBD
📱 Mobile Engineer   : TBD
🤖 AI/ML Engineer    : TBD
📊 Data / Domain     : TBD
📋 Project Manager   : TBD
```

> 한 명이 여러 역할을 겸할 수 있습니다. 팀원 수에 따른 매핑 가이드는 [`docs/08-implementation-plan.md`](./docs/08-implementation-plan.md) 참조.

### 발주처

**(주)레몬헬스케어** — 코스닥 상장 예정 디지털 헬스케어 인프라 기업
- 핵심 기술: LDB(Lemon Digital Bridge) 의료데이터 중계 플랫폼
- 누적 사용자: 770만+ (청구의신 → 건강의신)
- 의료기관 네트워크: 상급종합병원 80% (37개), 종합병원 포함 130여 곳
- 공식 사이트: https://www.lemonhealthcare.com

---

## 🙏 감사의 말

본 프로젝트는 다음 공공 자원과 외부 도구의 도움으로 만들어집니다:

### 공공 데이터·기관
- **한국영양학회** · 보건복지부 — KDRIs 2020
- **식품의약품안전처** — 식품영양성분 Open API, 건강기능식품 원료 DB
- **농촌진흥청 국립농업과학원** — 국가표준식품성분표
- **NIA AI Hub** — 한국 음식 이미지 데이터셋
- **한국인터넷진흥원 (KISA)** — ISMS-P 인증 기준
- **개인정보보호위원회** — 가명정보 처리 가이드라인

### 외부 도구·서비스
- **Google Cloud Platform** — Cloud Vision API
- **Ollama** — Local LLM runtime
- **Apple** — HealthKit
- **Google** — Health Connect
- **Naver Cloud** — CLOVA OCR

### 오픈소스 프로젝트
FastAPI · Flutter · PostgreSQL · TimescaleDB · Redis · Docker · pytest · Black · Ruff · 그 외 의존성에 명시된 모든 패키지의 기여자분들께 감사드립니다.

---

## 📜 라이선스

본 프로젝트는 [MIT License](./LICENSE) 하에 배포됩니다.

```
MIT License

Copyright (c) 2026 경북대학교 AI/빅데이터 전문가 양성 과정 — TBD팀

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. ...
```

> ⚠️ **데이터 라이선스 주의**: AI Hub 데이터셋은 활용 신청 동의에 따라 **재배포 금지**입니다. 본 코드는 MIT지만, 학습 데이터는 원 라이선스를 따릅니다.

---

<div align="center">

### 🍋 Lemon Healthcare — 건강의신 AI 모델

*"필라이즈가 못하는 영역, 만성질환자를 위한 의료 데이터 통합 플랫폼"*

**[📖 1단계 문서부터 시작하기](./docs/01-project-overview.md)**

Made with 💛 by 경북대학교 AI/빅데이터 전문가 양성 과정 TBD팀  
in collaboration with **(주)레몬헬스케어**

</div>
