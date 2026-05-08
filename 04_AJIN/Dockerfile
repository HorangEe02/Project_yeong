# AJIN Backend — 통합 Dockerfile (slim / full)
#
# v3.6.1 — 이전엔 Dockerfile (slim) ↔ Dockerfile.full 두 파일 + deploy-fullmode.sh 가
# 임시로 파일을 복사·교체하는 방식이라 "잘못된 requirements 파일이 빌드에 들어가는" 회귀
# 사고가 반복됐다 (예: 00104 의 python-multipart 누락). 두 모드를 multi-stage 로 통합해
# 단일 진실 출처로 만든다.
#
# 사용법:
#   • 슬림 (기본 — gcloud run deploy --source . 그대로 동작):
#       docker build -t ajin-backend:slim .
#       # 또는 명시:
#       docker build --target slim -t ajin-backend:slim .
#
#   • 풀 모드:
#       docker build --target full -t ajin-backend:full .
#       # gcloud builds submit --config cloudbuild.yaml --substitutions=_MODE=full
#
# `gcloud run deploy --source .` 는 가장 마지막 stage 를 빌드하므로, 마지막 stage 는
# `slim` 의 alias 로 둬서 zero-arg 흐름이 망가지지 않게 한다 (호환성 보존).
# scripts/deploy-backend.sh 는 mode 인자에 따라 explicit `--target` 을 거친다.

# ════════════════════════════════════════════════════════════════
# Stage 0: 공통 베이스
# ════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS base

# 시스템 패키지 — kiwipiepy 빌드용 build-essential + PDF 한글 폰트
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# 애플리케이션 코드 — 두 모드 공통
COPY backend/ ./backend/
COPY core/ ./core/
COPY features/ ./features/
COPY config.py .

EXPOSE 8080
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers


# ════════════════════════════════════════════════════════════════
# Stage 1: SLIM (~500MB) — Module D + Auth 위주, 데이터 자산 최소
# Module A(검색)/E(HR Stats) 는 환경변수로 비활성. 단, BM25/chroma 등 검색 의존성은
# requirements-cloudrun.txt 에 포함되어 있어야 features.search 패키지가 import 시에
# ImportError 를 내지 않는다 (admin 라우트가 사이드 이펙트로 search 패키지를 거침).
# ════════════════════════════════════════════════════════════════
FROM base AS slim

COPY requirements-cloudrun.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-cloudrun.txt

# 데이터 자산 (auth.db + 시나리오 + 시설 DB + 분류기 모델 + 변경이력 DB)
COPY data/auth.db ./data/auth.db
COPY data/employees.db ./data/employees.db
COPY data/scenarios/ ./data/scenarios/
COPY data/facility_db/ ./data/facility_db/
COPY data/regulation_ml/ ./data/regulation_ml/
COPY data/compliance.db ./data/compliance.db
COPY data/compliance_changes.db ./data/compliance_changes.db
COPY data/crawled/ ./data/crawled/
COPY data/metadata/ ./data/metadata/
COPY data/.jwt_secret ./data/.jwt_secret

# Module B (문서 작성) 자산
COPY data/knowledge_base/templates/ ./data/knowledge_base/templates/
COPY data/templates/ ./data/templates/
RUN mkdir -p ./data/knowledge_base/uploads

# Dashboard 메트릭용 — equipment 의 일부 DB 만
COPY data/equipment/error_codes.db ./data/equipment/error_codes.db
COPY data/equipment/error_history.db ./data/equipment/error_history.db
COPY data/equipment/drawings.db ./data/equipment/drawings.db
COPY data/equipment/molds.db ./data/equipment/molds.db
COPY data/equipment/inspection.db ./data/equipment/inspection.db

# 슬림 모드 기본 환경변수
ENV ENABLE_FEATURE_A=false \
    ENABLE_FEATURE_B=true \
    ENABLE_FEATURE_E=false \
    OLLAMA_BASE_URL= \
    FEATURE_B_BLOCK_GEMINI=false \
    UPLOAD_MAX_BYTES=5242880


# ════════════════════════════════════════════════════════════════
# Stage 2: FULL (~3GB) — Module A/B/D/E 전체 + vectorstore 베이킹
# 메모리 ≥ 2Gi 권장. 시연/풀 데모 시 사용.
# ════════════════════════════════════════════════════════════════
FROM base AS full

COPY requirements-cloudrun-full.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-cloudrun-full.txt

# 데이터 자산 — 풀 모드는 검색/문서/ML 자산까지 baking
COPY data/auth.db ./data/auth.db
COPY data/employees.db ./data/employees.db
COPY data/scenarios/ ./data/scenarios/
COPY data/facility_db/ ./data/facility_db/
COPY data/regulation_ml/ ./data/regulation_ml/
COPY data/intent_ml/ ./data/intent_ml/
COPY data/markov_ml/ ./data/markov_ml/
COPY data/mold_ml/ ./data/mold_ml/
COPY data/spc_ml/ ./data/spc_ml/
COPY data/spc_samples/ ./data/spc_samples/
COPY data/equipment/ ./data/equipment/
COPY data/templates/ ./data/templates/
COPY data/knowledge_base/ ./data/knowledge_base/
COPY data/documents/ ./data/documents/
COPY data/metadata/ ./data/metadata/
COPY data/crawled/ ./data/crawled/
COPY data/compliance.db ./data/compliance.db
COPY data/compliance_changes.db ./data/compliance_changes.db
COPY data/draft_versions.db ./data/draft_versions.db
COPY data/.jwt_secret ./data/.jwt_secret

# Vectorstore (chromadb 인덱스). 대용량은 GCS sync 옵션 — scripts/sync_vectorstore_gcs.py
COPY vectorstore/ ./vectorstore/

# 풀 모드 기본 환경변수
ENV ENABLE_FEATURE_A=true \
    ENABLE_FEATURE_B=true \
    ENABLE_FEATURE_E=true \
    OLLAMA_BASE_URL= \
    EMBEDDING_BACKEND=gemini \
    AUTH_BACKEND=firestore


# ════════════════════════════════════════════════════════════════
# Default target — gcloud run deploy --source . 무인자 흐름 호환용.
# 슬림이 "안전 기본값" — explicit `--target full` 로만 풀 모드 진입.
# ════════════════════════════════════════════════════════════════
FROM slim AS default
