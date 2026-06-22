# 06. 기술 스택 (Tech Stack & Architecture)

> **문서 정보**
> 버전: v1.0 | 작성일: 2026-05-03 | 상태: 초안 | 작성자: 경북대학교 AI/빅데이터 전문가 양성 과정 — TBD팀

---

## 📋 한 줄 요약

> **Flutter (모바일) + FastAPI (백엔드) + OCR adapter 계약 + Ollama 로컬 LLM + PostgreSQL/TimescaleDB (DB)** 의 5개 핵심 스택을 중심으로, 환자 개인정보를 외부 LLM으로 보내지 않는 의료 헬스케어 앱을 구현할 수 있도록 설계된 하이브리드 아키텍처.

> 현행 구현 상태(2026-05-13): OCR은 `src.ocr.base.OCRAdapter` 계약과 `NoopOCRAdapter`만 코드에 있으며, 외부 OCR provider는 아직 연결되지 않았다. provider별 정확도·비용 수치는 공식 문서와 자체 테스트셋으로 재검증하기 전까지 운영 근거로 사용하지 않는다.

---

## 목차
- [1. 전체 아키텍처](#1-전체-아키텍처)
- [2. 기술 스택 일람](#2-기술-스택-일람)
- [3. 영역별 상세 — 선택 근거와 대안](#3-영역별-상세--선택-근거와-대안)
- [4. 데이터 흐름 — 영양제 사진에서 결과까지](#4-데이터-흐름--영양제-사진에서-결과까지)
- [5. 비용 추정 (학생 팀 기준)](#5-비용-추정-학생-팀-기준)
- [6. 의사결정 매트릭스 — 왜 이 스택인가](#6-의사결정-매트릭스--왜-이-스택인가)
- [7. 학습 자료](#7-학습-자료)
- [8. 확장·마이그레이션 가능성](#8-확장마이그레이션-가능성)

---

## 1. 전체 아키텍처

### 1.1 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                       👤 사용자 (페르소나 B/A)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (UI/UX)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  📱 Flutter Mobile App                            │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ 영양제    │  │ 식단     │  │ 활동·체중 │  │ 5종 출력     │  │
│  │ 사진 입력 │  │ 입력     │  │ 추적     │  │ 대시보드     │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
│                                                                   │
│  📦 health 패키지 → HealthKit (iOS) + Health Connect (Android)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS / REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  🐍 FastAPI Backend (Python)                      │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 알고리즘     │  │ OCR 파이프  │  │ 영양 분석    │            │
│  │ (v1~v4,     │  │ 라인        │  │ (KDRIs 룩업) │            │
│  │  7-step)    │  │             │  │             │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
        │                  │                  │
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌────────────────┐  ┌────────────────┐
│ 🗄️ PostgreSQL │  │ OCR Adapter     │  │ 🤖 Ollama Local│
│ + TimescaleDB │  │ 계약/Provider   │  │   (localhost)   │
│ + Redis       │  │ 후보            │  │   (텍스트→JSON │
│              │  │                 │  │   구조화)       │
└──────────────┘  └────────────────┘  └────────────────┘
        │
        │
        ▼
┌─────────────────────────────────────────────┐
│     📊 외부 데이터 소스                       │
│   • 식약처 식품영양성분 Open API              │
│   • 식약처 건강기능식품 원료 DB              │
│   • 한국영양학회 KDRIs 2020 (룩업)            │
│   • AI Hub 한국 음식 이미지 (Phase 3)         │
└─────────────────────────────────────────────┘
```

### 1.2 핵심 설계 원칙

| 원칙 | 의미 |
|------|------|
| **로컬 LLM 우선** | 환자 개인정보·민감 건강정보가 LLM 처리 과정에서 외부로 나가지 않도록 Ollama를 기본값으로 둔다 |
| **온디바이스 헬스 데이터** | 걸음수·심박수는 HealthKit/Health Connect로 직접 수집 → 백엔드 부하 ↓ |
| **백엔드 중심 비즈니스 로직** | 알고리즘은 모두 Python → 단위 테스트·디버깅 용이 |
| **API 키·로컬 모델 보호** | 모바일에서 외부 API 직접 호출 금지, LLM 호출은 백엔드의 Adapter 경유 |
| **수평 확장 가능 구조** | Stateless FastAPI + DB/Redis 분리 → 사용자 증가 시 수평 확장 |

---

## 2. 기술 스택 일람

### 2.1 핵심 5개 스택

| 영역 | 기술 | 버전 | 용도 |
|------|------|------|------|
| **모바일** | Flutter | 3.24+ (stable) | iOS + Android 동시 배포 |
| **백엔드** | FastAPI (Python 3.13+) | 0.110+ | REST API 서버 |
| **OCR** | `OCRAdapter` + provider 후보 | 현행: no-op | 영양제 라벨 텍스트 추출 확장 지점 |
| **LLM** | Ollama Local API | qwen3.5 / gemma4 | 텍스트 → 영양 성분 JSON 구조화 |
| **DB** | PostgreSQL + TimescaleDB | PG 16 / TS 2.x | 관계형 + 시계열 통합 |

### 2.2 부가 스택

| 영역 | 기술 | 용도 |
|------|------|------|
| **캐싱** | Redis 7+ | OCR 결과·KDRIs 룩업·세션 캐싱 |
| **헬스 데이터** | health 패키지 (Flutter) | HealthKit + Health Connect 통합 |
| **컨테이너** | Docker + Docker Compose | 로컬 개발·배포 환경 통일 |
| **인프라** | NCP / AWS / GCP (택1) | 백엔드 호스팅 |
| **이미지 저장** | NCP Object Storage / AWS S3 | 영양제·식단 사진 저장 |
| **모니터링** | Python logging + Sentry (선택) | 에러 추적 |
| **CI/CD** | GitHub Actions | 자동 테스트·빌드 |
| **API 테스트** | Pytest + httpx | 백엔드 통합 테스트 |
| **API 문서** | FastAPI 자동 Swagger UI | `/docs` 엔드포인트 |

### 2.3 백엔드 주요 라이브러리 (`requirements.txt` 골격)

기본 의존성 (모든 환경 공통):

```
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.6
sqlalchemy>=2.0
asyncpg>=0.29
alembic>=1.13              # DB 마이그레이션
redis>=5.0
httpx>=0.27                # 외부 API 호출
google-cloud-vision>=3.7
ollama>=0.6.0              # Ollama Local API
pillow>=10.2               # 이미지 처리
python-multipart>=0.0.9    # 파일 업로드
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=4.1
black>=24.4
ruff>=0.4
mypy>=1.10
```

선택 의존성 — `backend/pyproject.toml` 의 `[project.optional-dependencies]` 에 정식 분리. MVP 기본 설치(`pip install -e backend`)에는 포함되지 않음:

```toml
[project.optional-dependencies]
# pip install ".[vision]" — Phase 3 비전 게이트 통과 후에만 설치
vision = [
    "torch>=2.2",
    "ultralytics>=8.1",
]
# pip install ".[learning]" — Phase 4 학습 적재 게이트 통과 후에만 설치
learning = [
    "boto3>=1.34",
    "pgvector>=0.2",
    "sentence-transformers>=2.5",
]
```

extras 사용 원칙:

- `[vision]`은 `enable_vision_classifier=true` 환경에서만 설치(기본 OFF)
- `[learning]`은 `enable_image_learning_pipeline=true` 환경에서만 설치(기본 OFF)
- 기본 빌드/CI 는 두 extras 를 설치하지 않아 MVP 영향을 최소화한다.
- 운영 활성화 조건은 [docs/17 §9](./17-image-collection-consent-plan.md)의 게이트 플래그 매핑을 따른다. production 환경에서 게이트 플래그가 활성화된 채 extras 미설치면 `ImportError` 가 즉시 발생하도록 구현체 측에서 가드한다.

### 2.4 모바일 주요 패키지 (`pubspec.yaml` 골격)

```yaml
dependencies:
  flutter:
    sdk: flutter

  # 상태 관리
  flutter_riverpod: ^2.5.1   # 또는 provider/bloc

  # API 통신
  dio: ^5.4.0
  retrofit: ^4.1.0

  # 헬스 데이터
  health: ^10.2.0            # HealthKit + Health Connect
  permission_handler: ^11.3.0

  # 이미지 처리
  image_picker: ^1.0.7       # 카메라·갤러리
  image_cropper: ^5.0.1

  # UI
  flutter_screenutil: ^5.9.0  # 반응형
  fl_chart: ^0.66.0          # 차트

  # 라우팅
  go_router: ^13.2.0

  # 로컬 저장
  shared_preferences: ^2.2.2
  flutter_secure_storage: ^9.0.0  # 토큰 등 민감정보

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
  build_runner: ^2.4.0
```

---

## 3. 영역별 상세 — 선택 근거와 대안

각 기술별로 **왜 선택했는가(Why)**, **대안은 무엇인가(Alternatives)**, **트레이드오프(Tradeoffs)** 를 정리한다.

### 3.1 모바일 — **Flutter**

#### 선택 근거
1. **단일 코드베이스로 iOS + Android 동시 배포** — 학생 팀의 인력 부담 ↓
2. **Dart 학습 곡선이 완만** — Python 경험자에게 친숙한 문법
3. **`health` 패키지 검증됨** — HealthKit + Health Connect를 동시 래핑
4. **Hot Reload** — 빠른 개발 사이클
5. **풍부한 UI 라이브러리** — Material + Cupertino 동시 지원

#### 대안 비교

| 옵션 | 장점 | 단점 | 결론 |
|------|------|------|------|
| **Flutter** ⭐ | 단일 코드 양대 OS, Hot Reload, Dart 친숙 | 네이티브 대비 약간 무거움 | ✅ 채택 |
| React Native | JS 생태계, 인기 ↑ | 헬스 패키지 두 개 필요 (RN-Health + RN-Health-Connect) | ❌ |
| Native (Swift + Kotlin) | 최고 성능 | 두 개 스택 학습·유지 부담 | ❌ |
| Xcode 단독 | iOS 네이티브 | Android 배포 불가 | ❌ |

#### 트레이드오프
- ⚠️ 앱 크기 커짐 (Flutter 엔진 ~10MB)
- ⚠️ 일부 네이티브 SDK는 채널 통신 코드 필요

### 3.2 백엔드 — **Python 3.13+ + FastAPI**

#### 선택 근거
1. **팀이 Python에 익숙** — 학습 비용 0
2. **FastAPI = Type Hint 기반 자동 문서화** — Pydantic 스키마 → Swagger UI 자동 생성
3. **비동기 (async/await)** — OCR API와 로컬 Ollama 호출은 I/O 바운드라 비동기가 큰 이점
4. **AI/ML 라이브러리 풍부** — pandas, numpy, scikit-learn 등 즉시 활용
5. **알고리즘 검증 용이** — pytest + 단위 테스트 자연스러움

#### 대안 비교

| 옵션 | 장점 | 단점 | 결론 |
|------|------|------|------|
| **FastAPI** ⭐ | 비동기, 자동 문서, 타입 안전 | 신규 프레임워크 (3년+) | ✅ 채택 |
| Django REST Framework | 성숙, 어드민 자동 | 무거움, 비동기 약함 | ❌ |
| Flask | 가벼움, 자유도 ↑ | 표준 부재, 타입 검증 수동 | ❌ |
| Node.js (Express/NestJS) | JS 단일 언어 | 팀 학습 비용 | ❌ |
| Spring Boot (Java) | 엔터프라이즈 표준 | 학습 곡선 ↑↑ | ❌ |

#### 트레이드오프
- ⚠️ Python GIL → CPU 바운드 작업은 Worker 프로세스 분리 필요 (uvicorn workers)
- ⚠️ 타입 시스템이 런타임 검증 — Pydantic으로 보완

### 3.3 데이터베이스 — **PostgreSQL 16 + TimescaleDB**

#### 선택 근거
1. **PostgreSQL = 사실상 표준** — JSON 지원, 확장성, 무료
2. **TimescaleDB 확장**으로 시계열 데이터(걸음수·체중) 효율 처리
3. **JSON/JSONB 컬럼** — 영양제 성분 등 동적 스키마 저장
4. **GIN 인덱스** — 식품 검색 성능
5. **AES-256 컬럼 암호화** 가능 — 의료 데이터 보안
6. **`pgvector` 확장(선택)** — 영양제 이미지 임베딩 학습 적재용. Phase 4 게이트가 통과되어 `enable_pgvector_storage=true`로 설정된 경우에만 활성화한다. 자세한 적용 절차는 [docs/17](./17-image-collection-consent-plan.md) 참조.

#### 데이터 모델 개요

```
관계형 (PG):
  users          (사용자 정보)
  supplements    (영양제 마스터)
  foods          (식품 마스터, KDRIs/식약처)
  user_supplements (사용자가 등록한 영양제)
  meals          (식단 기록)
  diagnoses      (만성질환 정보)

시계열 (TimescaleDB Hypertable):
  step_counts          (걸음수, hour 단위 집계)
  weight_logs          (체중 측정, 일 단위)
  heart_rate_samples   (심박수, 분 단위)

벡터 (pgvector, Phase 4 게이트 통과 시에만):
  labeled_supplement_images (가명화 이미지 + CLIP 임베딩, docs/17 §3 4번 동의 한정)
```

#### 대안 비교

| 옵션 | 장점 | 단점 | 결론 |
|------|------|------|------|
| **PostgreSQL + TimescaleDB** ⭐ | 표준 + 시계열 통합 | 시계열만 본다면 over-engineering | ✅ 채택 |
| MongoDB | 동적 스키마 | 트랜잭션 약함, 의료 데이터엔 부족 | ❌ |
| MySQL | 친숙 | JSON 지원 약함, 확장성 ↓ | ❌ |
| Firebase Firestore | 모바일 통합 ↑ | 비용 폭증 우려, 복잡 쿼리 어려움 | ❌ |

#### 트레이드오프
- ⚠️ 운영 부담 (인덱스, VACUUM, 백업) — 학생 단계에서는 매니지드 서비스 활용 권장 (NCP DB Manager / AWS RDS)

### 3.4 캐싱 — **Redis 7+**

#### 선택 근거
1. **OCR 결과 캐싱** — 같은 영양제 라벨 재인식 비용 ↓
2. **KDRIs 룩업 캐싱** — 자주 조회되는 영양 기준값
3. **세션·토큰 저장**
4. **Rate Limiting** — 외부 OCR provider 연결 시 비용 폭주 방지

#### 트레이드오프
- ⚠️ 메모리 제한 — TTL 정책 필수 (예: OCR 결과 30일 캐싱 후 만료)

### 3.5 OCR — **Adapter 계약 + Provider 후보**

#### 선택 근거
1. **현행 코드 안전성** — 기본 API는 외부 OCR 호출 없이 이미지 intake preview까지만 수행한다.
2. **Adapter 경계** — provider 교체는 `OCRAdapter.extract_text` 구현체 주입으로 제한한다.
3. **개인정보 통제** — 외부 provider 전송 전 동의, 보유 기간, 감사 로그, 비식별 정책을 먼저 검증한다.
4. **검증 가능성** — provider별 정확도와 비용은 공식 문서와 프로젝트 테스트셋으로 재측정한 뒤 채택한다.

#### 대안 비교

| 옵션 | 현재 코드 상태 | 채택 전 확인할 것 |
|------|------|------|
| 외부 OCR provider | 미구현 | 공식 API, 데이터 처리 위치, 비용, 장애 정책, 테스트셋 성능 |
| 자체 호스팅 OCR | 미구현 | 모델 라이선스, 배포 리소스, 한국어 라벨 성능, 운영 복잡도 |
| no-op provider | 구현됨 | intake-only 환경에서만 사용 |

#### 권고
- **현행 기본값**: no-op 또는 provider 미주입 상태로 intake-only 운영
- **후속 구현**: provider별 adapter를 별도 파일로 추가하고 공식 문서 URL과 자체 테스트 결과를 PR에 첨부
- **외부 전송**: 민감정보와 이미지 전송 정책 승인 전에는 비활성 유지

### 3.6 LLM — **Ollama 로컬 LLM**

#### 선택 근거
1. **환자 개인정보 보호** — OCR 텍스트와 건강 관련 문장이 외부 LLM 서버로 전송되지 않음
2. **로컬 API 단순성** — Ollama 설치 후 기본 API가 `http://localhost:11434/api`에서 제공됨
3. **구조화 출력 지원** — `format`에 JSON 또는 JSON Schema를 전달해 Pydantic 검증과 연결 가능
4. **모델 교체 용이** — `qwen3.5`, `gemma4`, 향후 `qwen3.6` 등 모델 태그만 교체
5. **MacBook Pro M4 Pro 24GB 활용** — Apple Silicon에서 Metal GPU 가속을 활용할 수 있음

#### 사용 예시 (의사 코드)

```python
from ollama import AsyncClient

from src.llm.schemas import ParsedSupplement

client = AsyncClient(host="http://127.0.0.1:11434")

# OCR 결과 텍스트
ocr_text = """
Supplement Facts
Vitamin C  1000 mg  1111% DV
Vitamin D3  25 mcg (1000 IU)  125% DV
...
"""

response = await client.chat(
    model="qwen3.5:9b",
    format=ParsedSupplement.model_json_schema(),
    stream=False,
    messages=[{
        "role": "user",
        "content": f"다음 OCR 텍스트를 영양 성분 JSON으로만 구조화하세요.\n\n{ocr_text}",
    }],
    options={"temperature": 0},
)
```

#### 대안 비교

| 옵션 | 개인정보 보호 | 로컬 실행 | JSON 응답 | 결론 |
|------|---------------|-----------|----------|------|
| **Ollama + Qwen 3.5** ⭐ | 높음 | 가능 | JSON Schema | ✅ 기본 |
| **Ollama + Gemma 4** | 높음 | 가능 | JSON Schema | ✅ 대안 |
| Ollama + Qwen 3.6 | 높음 | 24GB 장비에서는 모델 크기별 검증 필요 | JSON Schema | △ 향후 |
| DeepSeek V4 Pro `:cloud` | 낮음 | 클라우드 | 지원 가능 | ❌ 식별 가능 환자 데이터 금지 |
| Claude/OpenAI API | 낮음 | 외부 API | Tool/Function Calling | ❌ 기본 경로 제외 |

#### 권고
- **주력**: `qwen3.5:9b` 또는 `qwen3.5:latest`를 먼저 검증
- **대안**: `gemma4:e4b` 또는 `gemma4:latest`를 같은 테스트셋으로 비교
- **성능 실험**: `qwen3.5:27b`, `gemma4:26b`는 MacBook Pro M4 Pro 24GB에서 응답 시간·메모리 사용량 측정 후 제한 적용
- **보류**: `deepseek-v4-pro:cloud`는 클라우드 모델이므로 민감정보 처리에 사용하지 않음

### 3.7 헬스 데이터 — **health 패키지 (Flutter)**

#### 선택 근거
1. **HealthKit + Health Connect 동시 래핑** — 단일 코드로 양대 OS 지원
2. **걸음수 / 심박수 / 활동에너지 / 운동 / 체중 / 키** 등 50+ 데이터 타입
3. **백그라운드 동기화** 가능 (HKObserverQuery 등)
4. **권한 관리 통합 API**

#### 주의사항
- ⚠️ Health Connect는 사용자가 별도 앱 설치 필요 (Android 13 이하)
- ⚠️ Galaxy Watch는 Samsung Health → Health Connect 경유로 데이터 흐름
- ⚠️ 백그라운드 권한은 Apple/Google 심사 까다로움

### 3.8 인프라 — **Docker + 클라우드 (NCP/AWS/GCP)**

#### 권장 구성

| 환경 | 도구 |
|------|------|
| **로컬 개발** | Docker Compose (FastAPI + PostgreSQL + Redis) |
| **CI/CD** | GitHub Actions |
| **이미지 레지스트리** | Docker Hub (무료 1개 private) 또는 GitHub Container Registry |
| **클라우드** | NCP / AWS / GCP 중 택 1 (학생 크레딧 활용) |

#### 클라우드 옵션 비교

| 옵션 | 학생 혜택 | 한국 위치 | 추천 시나리오 |
|------|---------|---------|------------|
| **NCP (Naver Cloud)** | 학생 크레딧 (정부 사업) | ✅ 한국 | ⭐ 한국 사용자 + 의료 데이터 보호 |
| AWS | AWS Educate (제한적) | △ Tokyo / Seoul | 글로벌 확장 시 |
| GCP | 무료 크레딧 정책 확인 필요 | △ Seoul | GCP 서비스 통합 시 |
| Azure | Azure for Students | △ | Microsoft 생태계 시 |

#### Docker Compose 골격 (`docker-compose.yml`)

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    depends_on: [postgres, redis]

  postgres:
    image: timescale/timescaledb:latest-pg16
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: lemon
      POSTGRES_USER: lemon
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

### 3.9 모니터링 — **로깅 + Sentry (선택)**

| 도구 | 용도 | 무료 티어 |
|------|------|---------|
| **Python logging** | 애플리케이션 로그 | 무한 |
| **Sentry** (선택) | 에러 자동 추적·알림 | 5,000 events/month 무료 |
| **Uptime Robot** (선택) | 서비스 가용성 모니터링 | 50개 모니터 무료 |

---

## 4. 데이터 흐름 — 영양제 사진에서 결과까지

### 4.1 시퀀스 다이어그램

```text
[사용자]    [Flutter App]    [FastAPI]    [OCR Adapter]   [Ollama Local]  [PostgreSQL]    [Redis]
   │             │              │              │                 │               │             │
   │ 사진 촬영   │              │              │                 │               │             │
   ├────────────►│              │              │                 │               │             │
   │             │              │              │                 │               │             │
   │             │ POST /api/v1/supplements/analyze              │               │             │
   │             ├─────────────►│              │                 │               │             │
   │             │              │              │                 │               │             │
   │             │              │ 이미지 검증  │                 │               │             │
   │             │              │ preview 저장 │                 │               │             │
   │             │              ├──────────────────────────────────────────────►│              │
   │             │              │                                                                │
   │             │              │              OCR adapter가 주입된 경우에만 실행                │
   │             │              ├─────────────►│                                                 │
   │             │              │              │                                                 │
   │             │              │ OCR 텍스트   │                                                 │
   │             │              │◄─────────────┤                                                 │
   │             │              │                                                                │
   │             │              │ JSON 구조화 요청                                                │
   │             │              ├─────────────────────────────────►│                              │
   │             │              │                                  │                              │
   │             │              │ {supplements: [...]}             │                              │
   │             │              │◄─────────────────────────────────┤                              │
   │             │              │                                                                │
   │             │              │ 사용자 확인 후 등록 저장                                       │
   │             │              ├──────────────────────────────────────────────►│                │
   │             │              │                                                                │
   │             │ 202 Accepted │                                                                │
   │             │ {preview}    │                                                                │
   │             │◄─────────────┤                                                                │
   │             │              │                                                                │
   │ UI 갱신     │              │                                                                │
   │◄────────────┤              │                                                                │
```

### 4.2 단계별 처리

| 단계 | 작업 | 현재 구현 상태 |
|------|------|--------------|
| 1. 사용자 촬영 | Flutter camera/image picker 연동 | 모바일 화면 문서 단계 |
| 2. 백엔드 업로드 | `POST /api/v1/supplements/analyze` multipart/form-data | 구현됨 |
| 3. 이미지 검증 | 크기, MIME type, pixel 제한 | 구현됨 |
| 4. preview 저장 | SHA-256 image hash와 metadata 저장 | 구현됨 |
| 5. OCR | `OCRAdapter`가 주입된 경우만 실행 | provider 미연결 |
| 6. LLM 구조화 | OCR text가 있을 때 `OllamaSupplementParser` 실행 | 텍스트 parser 구현됨 |
| 7. 사용자 확인 등록 | `POST /api/v1/supplements` | 구현됨 |
| 8. 결과 조회/삭제 | 목록, 상세, soft delete | 구현됨 |

---

## 5. 비용 추정 (학생 팀 기준)

### 5.1 PoC ~ MVP 단계 (10주, 베타 사용자 50명 가정)

| 항목 | 사용량 | 단가 | 월 비용 (USD) |
|------|--------|------|------------|
| **OCR provider** | 현행 미연결 | provider 선정 후 공식 과금표 확인 | 미산정 |
| **Ollama 로컬 LLM** | 호출량 미측정 | MacBook 로컬 실행 | 장비·전기 비용 별도 |
| **NCP 백엔드** | 1 vCPU, 2GB RAM 인스턴스 | 학생 크레딧 활용 | **$0** (크레딧 사용 시) |
| **NCP DB Manager** | PostgreSQL 1GB | 학생 크레딧 | **$0** |
| **NCP Object Storage** | 10GB 사진 저장 | $0.02/GB | **약 $0.20** |
| **도메인** (선택) | .com 1년 | $12/년 | **약 $1** |
| **합계** | | | **OCR provider 선정 전 미산정** |

### 5.2 정식 출시 시 (월 1만 활성 사용자 가정)

| 항목 | 월 비용 (USD) |
|------|------------|
| OCR provider | 공식 과금표와 자체 사용량 추정 후 산정 |
| Ollama 로컬/사내 LLM 서버 | 장비·운영 방식에 따라 산정 |
| 인프라 (NCP) | $200~500 |
| 합계 | **외부 LLM 비용 제외, 서버 운영비 별도 산정** |

> 💡 **비용 절감 전략**:
> 1. provider 연결 후 OCR 결과 캐싱 정책 검토
> 2. KDRIs 룩업은 PostgreSQL에 저장, LLM 호출 최소화
> 3. 외부 OCR provider 간 비용·정확도·데이터 처리 위치 비교
> 4. 사용량 임계치 도달 시 알림 (NCP/AWS Cloud Watch)

---

## 6. 의사결정 매트릭스 — 왜 이 스택인가

10주 학생 팀 + 발표 + 양대 스토어 배포라는 제약 조건에서 각 후보를 평가:

| 평가 기준 (가중치) | Flutter | FastAPI | PostgreSQL | OCR Adapter | Ollama | 합계 |
|-------------------|:-------:|:-------:|:----------:|:------------:|:------:|:----:|
| **학습 곡선** (25%) | 8/10 | 9/10 | 8/10 | 9/10 | 9/10 | 8.6 |
| **개발 속도** (20%) | 9/10 | 9/10 | 8/10 | 10/10 | 9/10 | 9.0 |
| **비용 효율** (15%) | 10/10 | 10/10 | 10/10 | 8/10 | 10/10 | 9.5 |
| **확장성** (15%) | 8/10 | 9/10 | 10/10 | 9/10 | 9/10 | 9.0 |
| **커뮤니티·문서** (10%) | 9/10 | 9/10 | 10/10 | 10/10 | 9/10 | 9.4 |
| **유지보수성** (10%) | 8/10 | 9/10 | 10/10 | 10/10 | 9/10 | 9.2 |
| **발표 어필** (5%) | 9/10 | 8/10 | 7/10 | 9/10 | 9/10 | 8.4 |
| **종합** | **8.7** | **9.0** | **8.9** | **9.2** | **8.8** | **8.9/10** |

> 💡 기존 점수표는 설계 단계 평가다. 실제 운영 채택 전에는 OCR provider별 공식 조건과 자체 테스트셋 결과로 재산정해야 한다.

---

## 7. 학습 자료

팀원이 빠르게 익힐 수 있도록 권장 자료를 정리:

### Flutter
- 공식 튜토리얼: https://docs.flutter.dev/get-started/codelab
- 한국어: 인프런 *"Flutter 만들기"* (저자: 코드팩토리)
- `health` 패키지 예제: https://pub.dev/packages/health

### FastAPI
- 공식 튜토리얼 (한국어 번역 있음): https://fastapi.tiangolo.com/ko/
- 책: *"FastAPI를 사용한 견고한 파이썬 웹 API 개발"* (한빛미디어)

### OCR Adapter
- 현행 계약: `backend/src/ocr/base.py`
- 현행 no-op provider: `backend/src/ocr/providers/noop.py`
- 외부 provider 연결 시 해당 provider의 최신 공식 문서를 확인하고 PR에 URL을 첨부한다.

### Ollama
- API Introduction: https://docs.ollama.com/api/introduction
- Chat API: https://docs.ollama.com/api/chat
- Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Python Library: https://github.com/ollama/ollama-python
- macOS requirements: https://docs.ollama.com/macos

### PostgreSQL + TimescaleDB
- TimescaleDB 5분 시작: https://docs.tigerdata.com/getting-started/latest/
- PostgreSQL Tutorial: https://www.postgresqltutorial.com/

---

## 8. 확장·마이그레이션 가능성

향후 사용자·기능 증가 시 어떻게 확장할 수 있는가.

### 8.1 단기 (Year 1)

- 모바일: Flutter 그대로 유지, 웹 버전(Flutter Web) 추가 가능
- 백엔드: Uvicorn workers 수직 확장
- DB: Read Replica 추가

### 8.2 중기 (Year 2~3)

- **마이크로서비스 분리** (필요 시): 알고리즘 / OCR / 사용자 / 추천을 별도 서비스로
- **비동기 작업 큐** 도입: Celery + RabbitMQ (대량 OCR 배치)
- **CDN 도입**: 정적 자원 + 이미지
- **카프카 도입**: 실시간 헬스 데이터 스트리밍

### 8.3 장기 — LDB 통합

레몬헬스케어의 LDB 의료 데이터 플랫폼과 연동 시:
- **HL7 FHIR KR Core** 표준 적용
- **마이데이터 채널** 통합 (보건복지부 사업)
- **AES-256 컬럼 암호화**, **ISMS-P 인증** 필수

> 🔍 **법규·표준 상세**: [10-compliance-checklist.md](./10-compliance-checklist.md)

### 8.4 마이그레이션 가능성

| 영역 | 마이그레이션 시 영향 |
|------|--------------------|
| Flutter → React Native | 전체 재작성 (높은 비용) |
| FastAPI → Django | 알고리즘 코드는 재사용 가능, 라우터·미들웨어만 |
| PostgreSQL → MySQL | SQL 미세 조정 (대부분 호환) |
| OCR provider 교체 | `OCRAdapter` 구현체 주입 지점만 교체 |
| Ollama 모델 교체 | `OLLAMA_MODEL` 설정만 교체하되, 테스트셋 기준 품질·속도 재측정 |

> 💡 **설계 원칙**: OCR·LLM은 **Adapter 패턴**으로 추상화한다. LLM은 Ollama 로컬을 기본값으로 두고, 외부 LLM은 비식별·승인 환경에서만 선택적으로 연결한다.

```python
# 현행 구현: src.ocr.base.OCRAdapter 계약과 no-op provider
from src.ocr.base import OCRAdapter, OCRImageInput
from src.ocr.providers.noop import NoopOCRAdapter

ocr: OCRAdapter = NoopOCRAdapter()
result = await ocr.extract_text(OCRImageInput(image_bytes=image, mime_type="image/png"))
```

---

## 📝 변경 이력

| 버전 | 날짜 | 변경 사항 | 작성자 |
|-----|------|---------|-------|
| v1.0 | 2026-05-03 | 초안 작성. 5개 핵심 + 부가 스택, 의사결정 매트릭스 포함 | TBD |

## 🔗 관련 문서

- [01. 프로젝트 개요](./01-project-overview.md)
- [05. GitHub 협업 규칙](../05-github-guidelines.md)
- [07. 핵심 알고리즘](./07-core-algorithm.md)
- [08. 구현 계획](./08-implementation-plan.md)
- [09. 데이터·API 카탈로그](./09-data-catalog.md)
- [10. 컴플라이언스 체크리스트](./10-compliance-checklist.md)
