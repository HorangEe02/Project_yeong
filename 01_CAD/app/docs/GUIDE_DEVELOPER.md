# CAD Vision v5.6 — 개발자 가이드

> 이 문서는 CAD Vision 시스템을 **개발·운영**하는 사용자를 위한 기술 가이드입니다.
> 로컬 개발 환경 구성, Docker 배포, 테스트, 트러블슈팅 등을 다룹니다.
>
> **v5.6**: React 프론트엔드 (`web/`) 추가. AI 언어 선택, IGES 2D 감지 개선.
> React: `cd web && npm run dev` (port 3000) | Streamlit: `streamlit run app/streamlit_app.py` (port 8501)

---

## 목차

0. [빠른 실행](#0-빠른-실행)
1. [시스템 아키텍처](#1-시스템-아키텍처)
2. [전제조건](#2-전제조건)
3. [로컬 개발 환경 구성](#3-로컬-개발-환경-구성)
4. [Docker 환경 구성](#4-docker-환경-구성)
5. [프로젝트 구조](#5-프로젝트-구조)
6. [환경변수 설정](#6-환경변수-설정)
7. [테스트](#7-테스트)
8. [핵심 모듈 상세](#8-핵심-모듈-상세)
9. [데이터 관리](#9-데이터-관리)
10. [트러블슈팅](#10-트러블슈팅)
11. [보안 설계](#11-보안-설계)
12. [유용한 명령어 모음](#12-유용한-명령어-모음)

---

## 0. 빠른 실행

### Docker (권장, 원클릭)

```bash
cd "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/app"
./docker-start.sh              # 빌드 + 시작
./docker-start.sh --build      # 강제 재빌드
./docker-start.sh --down       # 중지
./docker-start.sh --reset      # 데이터 초기화 + 재시작
```

### 로컬 개발 (v5.0+: API + UI 분리)

```bash
cd "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/app"

# 동시 실행 (API + Streamlit)
python run_api.py &                                        # API → http://localhost:8000/docs
streamlit run app/streamlit_app.py --server.port 8501 &    # UI  → http://localhost:8501

# 전체 종료
kill $(lsof -t -i:8000) $(lsof -t -i:8501) 2>/dev/null && echo "종료 완료"

# 개별 종료
kill $(lsof -t -i:8000)    # API만 종료
kill $(lsof -t -i:8501)    # Streamlit만 종료
```

**접속 URL:**

| 서비스 | URL | 설명 |
|--------|-----|------|
| API Swagger | http://localhost:8000/docs | REST API 문서 (대화형 테스트) |
| API ReDoc | http://localhost:8000/redoc | API 문서 (읽기 전용) |
| Streamlit UI | http://localhost:8501 | 웹 인터페이스 |
| Health Check | http://localhost:8000/health | 서버 상태 확인 |

브라우저에서 **http://localhost:8501** 로 접속합니다.

---

## 1. 시스템 아키텍처

```
┌───────────────────────────────────────────────────────────────────┐
│                    CAD Vision v5.3                                  │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│   ┌──────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│   │  Streamlit    │    │  Ollama      │    │  ChromaDB          │  │
│   │  (UI)         │───▶│  (VLM)       │    │  (VectorDB)        │  │
│   │  :8501        │    │  :11434      │    │  Persistent        │  │
│   └──────┬───────┘    └──────┬───────┘    └────────┬───────────┘  │
│          │                   │                      │              │
│   ┌──────▼───────────────────▼──────────────────────▼───────────┐ │
│   │              Python ML Pipeline                               │ │
│   │  ┌────────┐  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │ │
│   │  │OpenCLIP│  │E5-small │  │PaddleOCR │  │ YOLO-cls    │  │ │
│   │  │ViT-L/14│  │ 384d    │  │ Korean   │  │ 81cat 93.87%  │  │ │
│   │  └────────┘  └─────────┘  └──────────┘  └───────────────┘  │ │
│   │  ┌──────────┐  ┌────────────────────┐  ┌────────────────┐  │ │
│   │  │YOLO-det│  │AnalysisContext     │  │Hallucination   │  │ │
│   │  │영역 탐지 │  │YOLO+OCR→LLM 주입  │  │Detector        │  │ │
│   │  └──────────┘  └────────────────────┘  └────────────────┘  │ │
│   └────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

| 컴포넌트 | 역할 | 포트 |
|---|---|---|
| **Streamlit** | 웹 UI (4페이지: 대시보드, 등록, 검색, 분석) | 8501 |
| **Ollama** | VLM 서버 (qwen3.5:9b, 도면 분석 + 컨텍스트 주입) | 11434 |
| **ChromaDB** | 벡터 데이터베이스 (임베딩 저장/검색, 68,647건) | 내장 |
| **OpenCLIP** | 이미지 임베딩 (ViT-L/14, 768차원) | — |
| **E5-small** | 텍스트 임베딩 (multilingual-e5-small, 384차원) | — |
| **PaddleOCR** | 한국어 OCR (도면 텍스트 추출, 패턴 매칭) | — |
| **YOLO-cls v2** | 도면 분류 (81 카테고리, 정확도 93.87%) | — |
| **YOLO-det** | 객체 탐지 (표제란, 부품표, 치수 영역, mAP50=0.552) | — |

---

## 2. 전제조건

### 로컬 개발 시

| 항목 | 최소 버전 | 확인 명령어 |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | 최신 | `pip --version` |
| Ollama | 최신 | `ollama --version` |
| Git | 최신 | `git --version` |
| poppler-utils | — | `pdftoppm -v` |

### Docker 배포 시

| 항목 | 최소 버전 | 확인 명령어 |
|---|---|---|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | v2 | `docker compose version` |

### 권장 하드웨어

| 항목 | 최소 | 권장 |
|---|---|---|
| RAM | 8GB | 16GB+ |
| 디스크 | 20GB 여유 | 50GB+ |
| GPU | 불필요 (CPU 가능) | NVIDIA GPU (Ollama 가속) |

---

## 3. 로컬 개발 환경 구성

### 3-1. 프로젝트 위치

프로젝트는 **외장 드라이브**에 저장되어 있습니다:

```
<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/drawing-llm
```

> **주의**: 외장 드라이브가 연결된 상태에서만 개발/실행이 가능합니다.
> 경로에 공백이 포함되어 있으므로, 터미널에서 사용 시 **반드시 큰따옴표로 감싸세요**.

### 3-2. 자동 설치 (setup.sh)

```bash
cd "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/drawing-llm"

# 자동 설치 (venv 생성 + 의존성 + 디렉토리 + .env)
chmod +x setup.sh
./setup.sh
```

### 3-3. 수동 설치

```bash
cd "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/drawing-llm"

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install --upgrade pip
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# 필요 시 .env 편집

# 디렉토리 생성
mkdir -p data/sample_drawings data/vector_store
```

### 3-4. Ollama 설정

```bash
# Ollama 설치 (macOS)
brew install ollama

# Ollama 서버 시작 (백그라운드)
ollama serve &

# VLM 모델 다운로드 (~5GB, 최초 1회)
ollama pull qwen3.5:9b

# 모델 확인
ollama list
```

### 3-5. 앱 실행

```bash
# 가상환경 활성화 상태에서
source venv/bin/activate

# Streamlit 실행
streamlit run app/streamlit_app.py

# 브라우저에서 접속 → http://localhost:8501
```

---

## 4. Docker 환경 구성

### 4-1. 빠른 시작

```bash
# 프로젝트 폴더로 이동 (외장 드라이브)
cd "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/drawing-llm"

# 빌드 + 시작
docker compose up -d --build

# Ollama 모델 다운로드 (최초 1회, ~5GB)
docker compose exec ollama ollama pull qwen3.5:9b

# 접속 → http://localhost:8501
```

> **외장 드라이브 주의**: Docker의 `./data` 바인드 마운트는 상대 경로이므로,
> 반드시 **프로젝트 디렉토리에서** `docker compose` 명령어를 실행해야 합니다.

### 4-2. Docker 아키텍처

```
docker-compose (2 서비스)
┌───────────────────────┐     ┌────────────────────────┐
│  app (cad-vision-app)  │────▶│  ollama                │
│  Streamlit :8501       │     │  (cad-vision-ollama)   │
│  Python 3.11-slim      │     │  :11434                │
│  CLIP + E5 프리로드     │     │  qwen3.5:9b           │
└──────────┬────────────┘     └────────────┬───────────┘
           │                                │
    ./data/ (bind mount)          ollama_data (named volume)
    ├── sample_drawings/          └── /root/.ollama/
    └── vector_store/                 └── models/
```

### 4-3. 볼륨 전략

| 볼륨 | 타입 | 용도 | 영속성 |
|---|---|---|---|
| `./data` | Bind Mount | 도면 파일 + ChromaDB | `docker compose down` 후에도 유지 |
| `ollama_data` | Named Volume | Ollama 모델 파일 (6GB+) | `docker compose down` 후에도 유지 |
| `./.streamlit` | Bind Mount | Streamlit 테마 설정 | 호스트에서 직접 편집 가능 |

### 4-4. 주요 Docker 명령어

```bash
# === 기본 운영 ===
docker compose up -d              # 백그라운드 시작
docker compose down               # 중지 (데이터 유지)
docker compose restart             # 재시작
docker compose ps                  # 상태 확인

# === 로그 ===
docker compose logs -f             # 전체 로그 (실시간)
docker compose logs app --tail 50  # 앱 로그 최근 50줄
docker compose logs ollama         # Ollama 로그

# === 빌드 ===
docker compose build               # 이미지 재빌드
docker compose up -d --build       # 재빌드 + 시작
docker compose build --no-cache    # 캐시 없이 전체 재빌드

# === 디버깅 ===
docker compose exec app bash       # 앱 컨테이너 셸 접속
docker compose exec ollama bash    # Ollama 컨테이너 셸 접속

# === 정리 ===
docker compose down -v             # 중지 + 볼륨 삭제 (⚠️ 모델 재다운로드 필요)
docker image prune                 # 미사용 이미지 정리
```

### 4-5. 환경변수 오버라이드

`docker-compose.yml`의 `environment` 섹션이 `.env` 파일보다 우선합니다.
`pydantic_settings.BaseSettings` 가 환경변수를 자동 주입하므로 **코드 수정 없이** 설정 변경이 가능합니다.

```yaml
# docker-compose.yml 에서 직접 변경
environment:
  - OLLAMA_BASE_URL=http://ollama:11434   # Docker 내부 네트워크
  - OLLAMA_MODEL=qwen3.5:9b
  - SEARCH_TOP_K=20                        # 검색 결과 수 변경
```

### 4-6. 외부 도면 이미지 마운트

도면 이미지가 프로젝트 폴더 외부(외장 드라이브, NAS 등)에 있는 경우, Docker 컨테이너에서 접근할 수 있도록 **볼륨 마운트**와 **경로 매핑**을 설정해야 합니다.

**배경**: `records.json`에 저장된 파일 경로가 호스트의 절대 경로(예: `/Volumes/ExtDrive/data/MiSUMi_png/...`)인 경우, 컨테이너 내부에서는 해당 경로가 존재하지 않아 이미지가 표시되지 않습니다.

**설정 방법**: `docker-compose.yml`에서 아래 주석을 해제하고 경로를 수정합니다:

```yaml
services:
  app:
    volumes:
      - ./data:/app/data
      - ./.streamlit:/app/.streamlit
      # ⬇️ 아래 줄의 주석을 해제하고 경로를 수정
      - /Volumes/ExtDrive/data:/app/data/external_drawings
    environment:
      # ⬇️ 아래 두 줄의 주석을 해제하고 경로를 수정
      - DRAWING_PATH_REMAP_FROM=/Volumes/ExtDrive/data
      - DRAWING_PATH_REMAP_TO=/app/data/external_drawings
```

**동작 원리**: Streamlit UI의 `_resolve_file_path()` 함수가 3단계로 파일을 찾습니다:
1. 저장된 원본 경로 그대로 시도
2. `DRAWING_PATH_REMAP_FROM` 접두사를 `DRAWING_PATH_REMAP_TO`로 치환하여 시도
3. 파일명으로 `UPLOAD_DIR` 하위를 재귀 검색 (5분 캐싱)

**확인 방법**:
```bash
# 컨테이너 내부에서 도면 파일 접근 확인
docker compose exec app ls /app/data/external_drawings/
```

---

## 5. 프로젝트 구조

```
drawing-llm/
├── app/
│   ├── __init__.py
│   └── streamlit_app.py          # Streamlit UI (4페이지, 경로 리매핑)
├── config/
│   ├── __init__.py
│   └── settings.py               # pydantic_settings 전역 설정 (보안+경로매핑)
├── core/
│   ├── __init__.py
│   ├── embeddings.py             # CLIP + E5 임베딩 엔진
│   ├── llm.py                    # Ollama VLM + AnalysisContext + HallucinationDetector
│   ├── ocr.py                    # PaddleOCR 한국어 OCR (패턴 매칭)
│   ├── classifier.py             # YOLO-cls 도면 분류기 (81cat, 93.87%)
│   ├── detector.py               # YOLO-det 객체 탐지기 (영역 탐지)
│   ├── pipeline.py               # 등록/검색/분석 파이프라인 (컨텍스트 주입)
│   ├── vector_store.py           # ChromaDB 벡터 DB 래퍼
│   ├── benchmark.py              # 성능 벤치마크 (YOLO/OCR/LLM)
│   ├── evaluation.py             # 검색 품질 평가
│   └── weight_tuner.py           # 하이브리드 검색 가중치 튜닝
├── models/
│   ├── yolo_cls_v2_best.pt       # YOLO-cls v2 학습 모델 (81cls, 10MB)
│   ├── yolo_cls_best.pt          # YOLO-cls v1 학습 모델 (73cls, legacy)
│   ├── clip_finetuned.pt         # CLIP Fine-tuned 모델 (577MB)
│   └── yolo_det_best.pt          # YOLO-det 학습 모델
├── data/
│   ├── sample_drawings/          # 도면 이미지 파일 (68,647건)
│   ├── vector_store/             # ChromaDB 영속 데이터 (441MB)
│   ├── category_keywords.json    # 카테고리별 검색 키워드
│   ├── metadata/                 # 평가/튜닝 결과 JSON
│   └── ground_truth_misumi.json  # Ground truth (평가용)
├── scripts/
│   ├── docker-start.sh           # 비개발자용 원클릭 실행
│   └── preload_models.py         # Docker 빌드 시 모델 다운로드
├── tests/                        # pytest 412개 테스트
│   ├── conftest.py               # pytest 픽스처 (모의 객체, sample_analysis_context)
│   ├── test_embeddings.py        # 임베딩 테스트
│   ├── test_llm.py               # LLM 기본 테스트
│   ├── test_llm_context.py       # 컨텍스트 주입 + 환각 검증 테스트
│   ├── test_classifier.py        # YOLO-cls 분류기 테스트
│   ├── test_detector.py          # YOLO-det 탐지기 테스트
│   ├── test_ocr.py               # OCR 테스트
│   ├── test_pipeline.py          # 파이프라인 통합 테스트
│   ├── test_security.py          # 보안 테스트 (SSRF, 인젝션, 레이트리밋)
│   └── test_vector_store.py      # 벡터 DB 테스트
├── .streamlit/
│   └── config.toml               # Streamlit 테마 (CAD Vision 다크)
├── Dockerfile                    # Python 앱 이미지 (비루트 실행)
├── docker-compose.yml            # app + ollama 오케스트레이션
├── .dockerignore                 # 빌드 컨텍스트 최적화
├── .env.example                  # 환경변수 템플릿
├── requirements.txt              # Python 의존성 (버전 상한 핀닝)
├── setup.sh                      # 로컬 자동 설치 스크립트
└── pytest.ini                    # pytest 설정
```

---

## 6. 환경변수 설정

모든 설정은 `config/settings.py` 의 `Settings` 클래스로 관리됩니다.

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 서버 주소 (Docker: `http://ollama:11434`) |
| `OLLAMA_MODEL` | `qwen3.5:9b` | VLM 모델명 |
| `CHROMA_PERSIST_DIR` | `./data/vector_store` | ChromaDB 데이터 경로 |
| `CHROMA_COLLECTION_NAME` | `drawings` | 컬렉션 이름 |
| `CLIP_MODEL` | `ViT-L/14` | CLIP 모델 변형 |
| `TEXT_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | 텍스트 임베딩 모델 |
| `SEARCH_TOP_K` | `10` | 검색 결과 최대 수 |
| `IMAGE_WEIGHT` | `0.15` | 하이브리드 검색 이미지 가중치 (CLIP Fine-tuning 후 활성화) |
| `TEXT_WEIGHT` | `0.85` | 하이브리드 검색 텍스트 가중치 |
| `UPLOAD_DIR` | `./data/sample_drawings` | 도면 업로드 디렉토리 |
| `MAX_FILE_SIZE_MB` | `50` | 최대 파일 크기 (MB) |
| `SUPPORTED_FORMATS` | `png,jpg,jpeg,pdf,tiff,tif` | 지원 파일 형식 |
| `DRAWING_PATH_REMAP_FROM` | (빈 문자열) | 도면 경로 치환 원본 접두사 (Docker 경로 매핑용) |
| `DRAWING_PATH_REMAP_TO` | (빈 문자열) | 도면 경로 치환 대상 접두사 (Docker 경로 매핑용) |

#### YOLO 설정

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `YOLO_CLS_MODEL_PATH` | `./models/yolo_cls_v2_best.pt` | YOLO-cls v2 모델 경로 |
| `YOLO_CLS_CONFIDENCE_THRESHOLD` | `0.5` | 분류 신뢰도 임계값 |
| `YOLO_CLS_ENABLED` | `True` | 분류기 활성화 여부 |
| `YOLO_DET_MODEL_PATH` | `./models/yolo_det_best.pt` | YOLO-det 모델 경로 |
| `YOLO_DET_CONFIDENCE_THRESHOLD` | `0.3` | 탐지 신뢰도 임계값 (recall 우선) |
| `YOLO_DET_ENABLED` | `True` | 탐지기 활성화 여부 |
| `YOLO_DET_IOU_THRESHOLD` | `0.5` | NMS IoU 임계값 |

#### Phase 4: LLM 컨텍스트 주입

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `LLM_CONTEXT_INJECTION` | `True` | YOLO/OCR 컨텍스트를 LLM에 주입 |
| `LLM_TEXT_ONLY_MODE` | `True` | 충분한 컨텍스트 시 이미지 없이 분석 |
| `LLM_HALLUCINATION_CHECK` | `True` | 환각 검증 활성화 |
| `LLM_NUM_PREDICT_DESCRIBE` | `4096` | describe 응답 토큰 제한 |
| `LLM_NUM_PREDICT_METADATA` | `1024` | metadata 응답 토큰 제한 |
| `LLM_NUM_PREDICT_QA` | `2048` | Q&A 응답 토큰 제한 |

#### 보안 설정

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `YOLO_CLS_SHA256` | (빈 문자열) | YOLO-cls 모델 SHA256 해시 (빈 문자열이면 스킵) |
| `YOLO_DET_SHA256` | (빈 문자열) | YOLO-det 모델 SHA256 해시 (빈 문자열이면 스킵) |
| `LLM_RATE_LIMIT_RPM` | `30` | 분당 최대 LLM 호출 횟수 (0이면 무제한) |
| `LOG_ROTATION` | `50 MB` | 로그 파일 회전 크기 |
| `LOG_RETENTION` | `7 days` | 로그 보관 기간 |
| `LOG_FILE` | `logs/drawingllm.log` | 로그 파일 경로 |

### 우선순위

```
환경변수 (OS/Docker)  >  .env 파일  >  settings.py 기본값
```

---

## 7. 테스트

### 7-1. 전체 테스트 실행

```bash
# 가상환경 활성화 후
pytest tests/ -v
```

**현재 상태: 412개 테스트 통과**

### 7-2. 개별 모듈 테스트

```bash
pytest tests/test_embeddings.py -v     # 임베딩
pytest tests/test_llm.py -v            # LLM 기본
pytest tests/test_llm_context.py -v    # 컨텍스트 주입 + 환각 검증
pytest tests/test_classifier.py -v     # YOLO-cls 분류기
pytest tests/test_detector.py -v       # YOLO-det 탐지기
pytest tests/test_ocr.py -v            # OCR
pytest tests/test_pipeline.py -v       # 파이프라인 통합
pytest tests/test_security.py -v       # 보안 (SSRF, 인젝션, 레이트리밋)
pytest tests/test_vector_store.py -v   # 벡터 DB
```

### 7-3. 특정 테스트만 실행

```bash
pytest tests/test_security.py::TestSanitizeUserInput -v
pytest tests/test_vector_store.py::TestSearch::test_search_by_text -v
```

### 7-4. 테스트 커버리지

```bash
pip install pytest-cov
pytest tests/ --cov=core --cov=config --cov-report=term-missing
```

---

## 8. REST API 엔드포인트 (v5.0+)

| 그룹 | 메서드 | 경로 | 설명 |
|------|--------|------|------|
| **도면** | POST | `/api/v1/drawings/register` | 도면 등록 (PNG/DXF) |
| | GET | `/api/v1/drawings` | 도면 목록 (페이지네이션) |
| | GET | `/api/v1/drawings/{id}` | 도면 조회 |
| | DELETE | `/api/v1/drawings/{id}` | 도면 삭제 |
| **검색** | POST | `/api/v1/drawings/search/text` | 텍스트 검색 |
| | POST | `/api/v1/drawings/search/image` | 이미지 유사 검색 |
| | POST | `/api/v1/drawings/search/dxf` | DXF 구조 검색 |
| | POST | `/api/v1/drawings/search/part-number` | 부품번호 검색 |
| **분석** | POST | `/api/v1/drawings/{id}/describe` | LLM 설명 생성 |
| | POST | `/api/v1/drawings/{id}/ask` | Q&A |
| | POST | `/api/v1/drawings/classify` | YOLO 분류 |
| | POST | `/api/v1/drawings/analyze/stream` | SSE 스트리밍 분석 |
| **도구** | POST | `/api/v1/drawings/compare/dimensions` | 치수 비교 |
| | POST | `/api/v1/drawings/diff/dxf` | DXF 비교 |
| | GET | `/api/v1/drawings/{id}/bom` | BOM 추출 |
| | GET | `/api/v1/drawings/versions/{pn}` | 부품번호별 버전 |
| **시스템** | GET | `/health` | 헬스체크 |
| | GET | `/api/v1/stats` | 시스템 통계 |
| | GET | `/api/v1/models` | Ollama 모델 목록 |
| | PUT | `/api/v1/settings/model` | 모델 변경 |
| | POST | `/api/v1/feedback` | 피드백 제출 |

---

## 9. 핵심 모듈 상세

### `core/embeddings.py` — 임베딩 엔진

- **OpenCLIP**: 이미지 → 768차원 벡터 (ViT-L/14)
- **E5-small**: 텍스트 → 384차원 벡터 (multilingual-e5-small)
- 두 임베딩을 ChromaDB 별도 컬렉션에 저장

### `core/vector_store.py` — 벡터 DB

- ChromaDB `PersistentClient` 사용 (v1.0+)
- 3채널 컬렉션 (이미지/텍스트/GNN) 분리 관리
- 하이브리드 검색: `image_weight * 이미지유사도 + text_weight * 텍스트유사도`

### `core/llm.py` — VLM 인터페이스 + 컨텍스트 주입

- Ollama REST API (`/api/generate`) 통신
- **AnalysisContext**: YOLO/OCR 추출 데이터를 `=== PRE-EXTRACTED FACTS ===` 블록으로 프롬프트에 주입
- **HallucinationDetector**: LLM 응답을 OCR/YOLO 사실(부품번호, 재질, 카테고리, 치수)과 대조 검증
- **텍스트 전용 모드**: 충분한 컨텍스트 시 이미지 인코딩 스킵 → 60-90초 → <20초
- `describe_drawing()`, `classify_drawing()`, `answer_question()`, `generate_metadata()` 모두 `context` 파라미터 지원
- SSRF 방어: URL 스키마/호스트 검증, 레이트 리미팅(30 RPM), 프롬프트 인젝션 방어(18 패턴)

### `core/classifier.py` — 도면 분류기

- **YOLO-cls v2** 기반 이미지 분류 (81 카테고리)
- 정확도: Top-1 **93.87%**, Top-5 **98.04%**
- SHA256 모델 무결성 검증
- 디바이스 자동 선택 (MPS → CUDA → CPU)
- Top-K 예측 결과 반환 (카테고리, 신뢰도)

### `core/detector.py` — 객체 탐지기

- **YOLO-det** 기반 영역 탐지 (표제란, 부품표, 치수 영역)
- **mAP50=0.552**, NMS IoU 임계값 0.5
- 탐지 결과를 AnalysisContext에 구조화
- 탐지된 영역에서 PaddleOCR로 구조화 텍스트 추출

### `core/pipeline.py` — 등록/분석 파이프라인

```
이미지 ──┬──→ OCR(텍스트 추출) ──→ 임베딩(CLIP+E5) ──→ ChromaDB 저장
         ├──→ YOLO-cls(분류) ──┐
         └──→ YOLO-det(탐지) ──┤
                                  ▼
                        AnalysisContext 구성
                                  │
                     VLM(컨텍스트 주입 분석) → HallucinationDetector
```

- `_build_analysis_context()`: OCR/YOLO 결과 → AnalysisContext 조립
- `_build_analysis_context_from_record()`: 기존 DrawingRecord에서 AnalysisContext 복원

### `core/ocr.py` — OCR

- **PaddleOCR 3.4.0** (Korean) 으로 도면 내 텍스트 추출
- 부품번호, 재질, 치수 **패턴 자동 매칭** (정규식 기반)
- OCR 텍스트 살균 (셸 인젝션, 경로 탐색, null byte 제거)

### `core/benchmark.py` — 벤치마크

- YOLO-cls/det 추론 속도 측정
- OCR 처리 속도 측정
- LLM 레이턴시 비교 (컨텍스트 유무, 이미지/텍스트 전용)
- 메모리 사용량 프로파일링

---

## 9. 데이터 관리

### 9-1. 도면 데이터

```
data/sample_drawings/
├── MISUMI/          # 카테고리별 하위 디렉토리
│   ├── drawing_001.png
│   ├── drawing_002.pdf
│   └── ...
└── ...
```

### 9-2. ChromaDB 백업/복원

```bash
# 백업
tar -czf vector_store_backup.tar.gz data/vector_store/

# 복원
tar -xzf vector_store_backup.tar.gz
```

### 9-3. Docker에서 기존 데이터 사용

`docker-compose.yml` 이 `./data`를 바인드 마운트하므로, 로컬에 이미 데이터가 있으면
Docker 컨테이너가 **즉시 인식**합니다. 별도 마이그레이션이 필요 없습니다.

**주의**: `records.json`에 저장된 도면 파일 경로가 호스트의 절대 경로인 경우,
컨테이너 내부에서 이미지가 표시되지 않을 수 있습니다.
이 경우 [4-6. 외부 도면 이미지 마운트](#4-6-외부-도면-이미지-마운트)를 참조하세요.

---

## 10. 트러블슈팅

### Ollama 연결 실패

```
증상: "Ollama 서버 연결 실패" / "Connection refused" / 대시보드에서 🔴 오프라인

# 로컬
ollama serve                # 서버가 실행 중인지 확인
curl http://localhost:11434  # 응답 확인

# Docker
docker compose logs ollama   # Ollama 컨테이너 로그 확인
docker compose restart ollama

# Docker에서 앱→Ollama 연결 확인
docker compose exec app curl -sf http://ollama:11434
# "Ollama is running" 이 출력되면 네트워크 정상

# 설정값 확인
docker compose exec app python3 -c "from config.settings import settings; print(settings.ollama_base_url)"
# http://ollama:11434 가 출력되어야 함 (localhost가 아님)
```

> **참고**: `streamlit_app.py`의 `get_pipeline()`은 `config.settings`를 통해
> 환경변수 `OLLAMA_BASE_URL`을 주입받습니다. Docker 환경에서는 반드시
> `http://ollama:11434`로 설정되어야 합니다.

### LLM 500 에러 / 도면 분석 실패

```
증상: "[오류] LLM 호출 실패: HTTP 500" / 도면 분석 탭에서 오류 표시

# 1. Ollama 서버 상태 확인
docker compose exec app curl -sf http://ollama:11434
# "Ollama is running" 출력 확인

# 2. 모델 설치 확인
docker compose exec ollama ollama list
# qwen3.5:9b 가 목록에 있어야 함

# 3. 모델 미설치 시 다운로드
docker compose exec ollama ollama pull qwen3.5:9b

# 4. Ollama 로그에서 상세 원인 확인
docker compose logs ollama --tail 50
# "out of memory", "model is loading" 등 확인

# 5. 메모리 부족(OOM) 시 Ollama 재시작
docker compose restart ollama
```

> **참고**: `core/llm.py`의 `_generate()`는 500 에러 시 **최대 2회 자동 재시도**
> (지수 백오프: 3초→6초)를 수행합니다. 모든 재시도 실패 시 Ollama 응답 본문의
> 상세 에러 메시지를 파싱하여 UI에 표시합니다.
>
> 모델이 설치되지 않은 경우(404/not found) `/api/tags`로 설치된 모델 목록을 조회하여
> 구체적인 안내 메시지를 생성합니다.

### ChromaDB 오류

```
증상: "Collection not found" / 데이터 불일치

# 벡터 DB 상태 확인
python3 -c "
from core.vector_store import VectorStore
vs = VectorStore()
print(vs.get_stats())
"
```

### 메모리 부족

```
증상: 컨테이너가 OOM으로 종료됨

# Docker Desktop 설정에서 메모리 증가 (최소 8GB 권장)
# 또는 docker-compose.yml에 메모리 제한 추가:
services:
  app:
    deploy:
      resources:
        limits:
          memory: 4G
```

### 포트 충돌

```
증상: "port is already allocated"

# 사용 중인 프로세스 확인
lsof -i :8501
lsof -i :11434

# 다른 포트로 변경 (docker-compose.yml)
ports:
  - "8502:8501"    # 호스트:컨테이너
```

### 도면 이미지 미표시 (Docker)

```
증상: 검색 결과/대시보드에서 이미지가 "이미지 없음"으로 표시

# 원인: records.json의 파일 경로가 호스트 절대 경로
# 확인 방법:
python3 -c "
import json
with open('data/vector_store/records.json') as f:
    d = json.load(f)
k = list(d.keys())[0]
print(d[k]['file_path'])
"
# 출력이 /Volumes/... 또는 /Users/... 등 호스트 경로이면 경로 매핑 필요

# 해결: docker-compose.yml에 볼륨 마운트 + 경로 매핑 환경변수 설정
# 상세: 4-6. 외부 도면 이미지 마운트 섹션 참조
```

### 외장 드라이브 마운트 오류

```
증상: "No such file or directory" / docker compose 실행 시 "mounts denied"

# 1. 외장 드라이브 마운트 상태 확인
ls "<EXTERNAL_DRIVE>/"

# 2. Docker Desktop 파일 공유 설정 확인 (Settings → Resources → File Sharing)
#    외장 드라이브 경로가 공유 목록에 포함되어야 함
#    macOS의 경우 /Volumes/ 전체를 추가하면 편리

# 3. 드라이브 연결 후 Docker 재시작
docker compose down
docker compose up -d
```

> **주의**: 외장 드라이브의 파일시스템이 **APFS** 또는 **exFAT**인 경우 Docker 볼륨 마운트가 정상 동작합니다.
> NTFS(Windows 전용)인 경우 macOS에서 읽기 전용으로 마운트되어 문제가 발생할 수 있습니다.

### pip 설치 오류 (CLIP)

```
증상: "No matching distribution found for openai-clip"
또는: "ModuleNotFoundError: No module named 'pkg_resources'"

# pip 26+에서 setuptools 82가 pkg_resources를 제거하여 CLIP 빌드 실패
# Dockerfile에서는 아래와 같이 분리 빌드로 해결:
pip install --no-cache-dir "setuptools<81" wheel
pip install --no-cache-dir --no-build-isolation \
    clip@git+https://github.com/openai/CLIP.git@a1d071733d7111c9c014f024669f959182114e33

# 로컬 개발 시: pip install setuptools<81 먼저 실행 후 requirements.txt 설치
```

### ChromaDB 버전 불일치

```
증상: "ChromaDB 초기화 실패: '_type'" / 벡터 DB 로드 불가

# 원인: 호스트에서 ChromaDB 1.x로 생성한 데이터를 0.6.x로 읽으려 할 때 발생
# 해결: requirements.txt의 chromadb 버전이 >=1.0.0,<2.0.0 인지 확인
grep chromadb requirements.txt
# 출력: chromadb>=1.0.0,<2.0.0

# Docker 재빌드
docker compose up -d --build
```

### pydantic-settings 모듈 미설치 (Docker)

```
증상: "ModuleNotFoundError: No module named 'pydantic_settings'"

# requirements.txt에 pydantic-settings가 포함되어 있는지 확인:
grep pydantic-settings requirements.txt
# 출력: pydantic-settings>=2.0.0

# 없으면 추가 후 Docker 이미지 재빌드:
echo "pydantic-settings>=2.0.0" >> requirements.txt
docker compose up -d --build
```

---

## 11. 보안 설계

### 11-1. 보안 계층

| 계층 | 방어 수단 | 설명 |
|---|---|---|
| **모델 무결성** | SHA256 해시 검증 | YOLO-cls/det 모델 파일 로드 시 해시 대조 |
| **네트워크** | SSRF 방어 | Ollama URL 스키마(http/https), 내부 IP 차단, 포트 범위 검증 |
| **API** | 레이트 리미팅 | 분당 30회 LLM 호출 제한 (토큰 버킷) |
| **입력** | 프롬프트 인젝션 방어 | 18개 정규식 패턴으로 시스템 프롬프트 조작 차단 |
| **입력** | OCR 텍스트 살균 | 셸 인젝션, 경로 탐색, null byte 제거 |
| **의존성** | 버전 핀닝 | 모든 패키지에 상한 버전 명시 (supply chain 방어) |
| **런타임** | Docker 비루트 | appuser (UID 1000) 권한으로 실행 |
| **로그** | 로테이션 | 50MB 회전 + 7일 보관 (디스크 고갈 방지) |

### 11-2. 보안 테스트 (60개)

```bash
# 보안 테스트 전체 실행
pytest tests/test_security.py -v

# 주요 테스트 클래스
pytest tests/test_security.py::TestSsrfDefense -v         # SSRF 방어
pytest tests/test_security.py::TestPromptInjection -v     # 프롬프트 인젝션
pytest tests/test_security.py::TestRateLimiting -v        # 레이트 리미팅
pytest tests/test_security.py::TestModelIntegrity -v      # 모델 무결성
pytest tests/test_security.py::TestOcrSanitization -v     # OCR 살균
```

### 11-3. SHA256 모델 해시 설정

```bash
# 모델 해시 생성
shasum -a 256 models/yolo_cls_best.pt
shasum -a 256 models/yolo_det_best.pt

# .env에 설정 (빈 문자열이면 검증 스킵)
YOLO_CLS_SHA256=abc123...
YOLO_DET_SHA256=def456...
```

---

## 12. 유용한 명령어 모음

```bash
# === 프로젝트 경로 (외장 드라이브) ===
PROJECT="<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/drawing-llm"
cd "$PROJECT"

# === 개발 ===
streamlit run app/streamlit_app.py                    # 앱 실행
streamlit run app/streamlit_app.py --server.port 8502 # 다른 포트
pytest tests/ -v                                       # 테스트
pytest tests/ -v -x                                    # 첫 실패에서 중단

# === Docker ===
docker compose up -d --build                           # 빌드 + 시작
docker compose down                                    # 중지
docker compose exec app bash                           # 앱 셸 접속
docker compose exec ollama ollama list                 # 모델 목록
docker compose exec ollama ollama pull qwen3.5:9b    # 모델 다운로드

# === Ollama ===
ollama list                                            # 로컬 모델 목록
ollama pull qwen3.5:9b                               # 모델 다운로드
ollama rm qwen3.5:9b                                 # 모델 삭제
curl http://localhost:11434/api/tags                   # API로 모델 확인

# === 데이터 ===
du -sh data/vector_store/                              # ChromaDB 크기
du -sh data/sample_drawings/                           # 도면 파일 크기
find data/sample_drawings -type f | wc -l             # 도면 파일 수

# === 디버깅 (Docker) ===
docker compose exec app python3 -c "from config.settings import settings; print(vars(settings))"  # 전체 설정 확인
docker compose exec app curl -sf http://ollama:11434   # Ollama 연결 확인
docker compose exec app python3 -c "
import json
with open('/app/data/vector_store/records.json') as f:
    d = json.load(f)
k = list(d.keys())[0]
print('총 레코드:', len(d))
print('샘플 경로:', d[k]['file_path'])
"                                                       # records.json 경로 확인

# === 외장 드라이브 확인 ===
ls "<EXTERNAL_DRIVE>/"                    # 드라이브 마운트 확인
df -h "<EXTERNAL_DRIVE>/"                 # 드라이브 남은 공간
```

---

> **v5.3 업데이트 (2026-03-25)**: FastAPI REST API 분리, Docker Compose 3-컨테이너, 한/영 동의어 사전, 카테고리 특화 프롬프트(15종), DXF 리랭커, 치수비교 이미지 표시, 724 tests
