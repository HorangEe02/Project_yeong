# dev-guides/00 — 환경 세팅

> **Phase**: 0 | **선행 작업**: 없음 | **예상 소요**: 1~2시간

---

## 🎯 작업 목표

백엔드 프로젝트의 기본 골격(폴더 구조·도구 설정·CI 연동)을 만들어 이후 알고리즘 구현을 시작할 수 있는 환경을 갖춘다.

---

## 📋 산출물 (Deliverables)

이 작업이 완료되면 다음 파일들이 존재해야 합니다:

```
backend/
├── pyproject.toml             # Black/Ruff/mypy/pytest 설정
├── requirements.txt           # 핵심 의존성
├── requirements-dev.txt       # 개발 도구
├── .env.example
├── alembic.ini                # 빈 골격
├── docker-compose.yml         # ← 루트에 (이미 있을 수 있음)
│
└── src/
    ├── __init__.py
    ├── main.py                # FastAPI app
    ├── config.py              # Pydantic Settings
    │
    ├── algorithms/__init__.py
    ├── nutrition/__init__.py
    ├── ocr/__init__.py
    ├── llm/__init__.py
    ├── api/__init__.py
    ├── api/v1/__init__.py
    ├── models/__init__.py
    ├── models/schemas/__init__.py
    ├── models/db/__init__.py
    ├── db/__init__.py
    ├── cache/__init__.py
    └── utils/
        ├── __init__.py
        └── logger.py

tests/
├── __init__.py
├── conftest.py
├── unit/__init__.py
└── integration/__init__.py
```

---

## 🔧 구현 명세

### 1. `pyproject.toml`

`backend/CLAUDE.md` §"pyproject.toml 표준 설정" 섹션을 그대로 사용. 단, `[project]` 메타정보는 본 프로젝트에 맞게:

```toml
[project]
name = "lemon-healthcare-backend"
version = "0.1.0"
description = "Lemon Healthcare AI - Backend API"
requires-python = ">=3.11"
authors = [{ name = "TBD Team" }]
license = { text = "MIT" }
```

### 2. `requirements.txt`

```
# Core Web
fastapi>=0.110,<0.120
uvicorn[standard]>=0.27,<0.30

# Pydantic v2
pydantic>=2.6,<3.0
pydantic-settings>=2.2,<3.0

# DB
sqlalchemy>=2.0,<3.0
asyncpg>=0.29
alembic>=1.13

# Cache
redis>=5.0

# External APIs
google-cloud-vision>=3.7
anthropic>=0.25
httpx>=0.27

# Image
pillow>=10.2

# Utils
python-multipart>=0.0.9
```

### 3. `requirements-dev.txt`

```
-r requirements.txt

# Code quality
black>=24.4
ruff>=0.4
mypy>=1.10

# Testing
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=4.1
pytest-mock>=3.12
httpx>=0.27   # for FastAPI TestClient

# Dev tools
ipython>=8.0
```

### 4. `src/main.py`

```python
"""FastAPI 애플리케이션 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src.config import get_settings
from src.utils.logger import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """애플리케이션 시작·종료 라이프사이클.

    Yields:
        None: 애플리케이션 실행 중.
    """
    setup_logging()
    # TODO: DB 연결 풀 초기화 (Phase 1 후반)
    # TODO: Redis 연결 (Phase 2)
    yield
    # TODO: 정리 작업


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리.

    Returns:
        설정이 완료된 FastAPI 인스턴스.
    """
    settings = get_settings()
    app = FastAPI(
        title="Lemon Healthcare API",
        description="만성질환자 중심의 AI 헬스케어 플랫폼 API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """헬스 체크 엔드포인트.

        Returns:
            서비스 상태 정보.
        """
        return {"status": "ok", "version": "0.1.0"}

    # TODO: 라우터 등록 (Phase 1)
    # app.include_router(activity.router, prefix="/api/v1")

    return app


app = create_app()
```

### 5. `src/config.py`

`backend/CLAUDE.md` §"Pattern 6. Pydantic Settings" 그대로 구현. 단, 현재 단계에서 미사용 키들은 `Optional`로:

```python
"""애플리케이션 설정."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = Field(default="INFO")

    # DB (Phase 1 후반부터 사용)
    database_url: str = Field(default="postgresql+asyncpg://lemon:lemon@localhost:5432/lemon")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # External APIs (Phase 2부터 사용, 현재는 선택)
    anthropic_api_key: SecretStr | None = Field(default=None)
    google_application_credentials: str | None = Field(default=None)
    mfds_api_key: SecretStr | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴.

    Returns:
        애플리케이션 설정 (lru_cache로 1회만 로드).
    """
    return Settings()
```

### 6. `src/utils/logger.py`

```python
"""로깅 설정."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """루트 로거를 설정한다.

    Args:
        level: 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
```

### 7. `tests/conftest.py`

`backend/CLAUDE.md` §"conftest.py — 공통 픽스처" 그대로 구현. 단, `UserProfile` import는 다음 작업(`01-bmi-and-v1`) 이후에 추가하므로 **이 단계에서는 빈 conftest.py**로 시작:

```python
"""공통 pytest 픽스처.

알고리즘 구현이 추가되면 여기에 가이드 예시 픽스처를 추가한다.
"""

import pytest

# TODO: dev-guides/01 이후 추가
# @pytest.fixture
# def user_50f_obese1() -> UserProfile: ...
```

### 8. `.env.example`

```
# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Database (Phase 1 후반부터)
DATABASE_URL=postgresql+asyncpg://lemon:lemon@localhost:5432/lemon
REDIS_URL=redis://localhost:6379/0

# External APIs (Phase 2부터)
ANTHROPIC_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
MFDS_API_KEY=
```

### 9. 각 폴더의 `__init__.py`

비어있는 `__init__.py` 파일 (단, `src/__init__.py`에는 모듈 docstring 추가):

```python
# src/__init__.py
"""Lemon Healthcare backend.

만성질환자 중심의 AI 헬스케어 플랫폼 백엔드.
"""

__version__ = "0.1.0"
```

---

## 🧪 검증 (Verification)

작업 완료 후 다음 모두 통과해야 합니다:

```bash
cd backend

# 1. 의존성 설치
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. 도구 정상 작동
black --version
ruff --version
mypy --version
pytest --version

# 3. 코드 품질 (빈 프로젝트라도 통과해야 함)
black src tests --check
ruff check src tests
mypy src --strict

# 4. 테스트 (현재 0개지만 정상 실행돼야 함)
pytest

# 5. 서버 시작
uvicorn src.main:app --reload --port 8000
# 브라우저에서 http://localhost:8000/docs 확인 → Swagger UI 표시
# http://localhost:8000/health → {"status": "ok", "version": "0.1.0"}
```

---

## ✅ Definition of Done

- [ ] `pyproject.toml` 작성됨 (Black/Ruff/mypy/pytest 설정)
- [ ] `requirements.txt` + `requirements-dev.txt` 작성됨
- [ ] 모든 폴더 구조 생성 + `__init__.py`
- [ ] `src/main.py` — FastAPI 앱 + `/health` 엔드포인트
- [ ] `src/config.py` — Pydantic Settings
- [ ] `src/utils/logger.py` — 로깅 설정
- [ ] `.env.example` 작성됨
- [ ] `tests/conftest.py` 골격 (TODO 주석)
- [ ] `mypy src --strict` 통과
- [ ] `black src tests --check` 통과
- [ ] `ruff check src tests` 통과
- [ ] `pytest` 정상 실행 (0 tests OK)
- [ ] `uvicorn src.main:app` 시작 성공
- [ ] `/docs` Swagger UI 정상 표시
- [ ] `/health` 응답 `{"status": "ok"}` 확인

---

## 🚫 이 작업에서 하지 말 것

- ❌ 알고리즘 구현 (다음 작업)
- ❌ DB 모델 정의 (Phase 1 후반)
- ❌ 라우터 정의 (Phase 1 후반)
- ❌ Docker 컨테이너 빌드 (인프라 담당자가 별도)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- 다음 작업: [`01-bmi-and-v1-algorithm.md`](./01-bmi-and-v1-algorithm.md)
