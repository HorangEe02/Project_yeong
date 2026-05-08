# backend/CLAUDE.md — 백엔드 작업 컨텍스트 (Tier 2)

> 이 문서는 **백엔드(`backend/`) 디렉토리에서 작업할 때 추가로 읽어야 하는 컨텍스트**입니다.  
> 루트 `CLAUDE.md`와 함께 사용하세요.

---

## 🎯 백엔드의 역할

- 모든 비즈니스 로직 (알고리즘 v1~v4, BMR, TDEE, 7-step, 부족 영양소 진단)
- 외부 API Adapter (OCR, LLM)
- FastAPI REST API
- DB 모델 (PostgreSQL + TimescaleDB)
- 인증·권한
- 단위 테스트

> 모바일은 **UI만 담당**하고, **연산은 모두 백엔드**에서 합니다.

---

## 📂 백엔드 폴더 구조 (절대 준수)

```
backend/
├── CLAUDE.md                 ← 이 파일
├── pyproject.toml            # Black/Ruff/mypy/pytest 설정
├── requirements.txt
├── .env.example
├── alembic.ini               # DB 마이그레이션 설정
│
├── src/
│   ├── __init__.py
│   ├── main.py               # FastAPI app 초기화
│   ├── config.py             # 환경 변수 로드 (Pydantic Settings)
│   │
│   ├── algorithms/           # 회사 가이드 정의 알고리즘
│   │   ├── __init__.py
│   │   ├── bmi.py            # BMI 분류
│   │   ├── activity.py       # v1, v2, v3, v4
│   │   ├── metabolism.py     # BMR, TDEE
│   │   └── prediction.py     # 7-step 체중 예측
│   │
│   ├── nutrition/            # 영양 분석
│   │   ├── __init__.py
│   │   ├── kdris.py          # KDRIs 룩업
│   │   ├── diagnosis.py      # 부족 영양소 진단
│   │   └── goal_analysis.py  # 목적별 분석 (눈/간/피로)
│   │
│   ├── ocr/                  # OCR Adapter
│   │   ├── __init__.py
│   │   ├── base.py           # OCRAdapter ABC
│   │   ├── google_vision.py  # Google Cloud Vision 구현
│   │   └── clova.py          # CLOVA OCR 구현 (백업)
│   │
│   ├── llm/                  # LLM Adapter
│   │   ├── __init__.py
│   │   ├── base.py           # LLMAdapter ABC
│   │   ├── claude.py         # Anthropic Claude 구현
│   │   └── openai.py         # OpenAI GPT 구현 (백업)
│   │
│   ├── api/                  # FastAPI 라우터
│   │   ├── __init__.py
│   │   ├── deps.py           # 의존성 주입
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── activity.py
│   │   │   ├── nutrition.py
│   │   │   ├── prediction.py
│   │   │   └── ...
│   │   └── health.py
│   │
│   ├── models/               # Pydantic + SQLAlchemy
│   │   ├── __init__.py
│   │   ├── schemas/          # Pydantic v2 (API 입출력)
│   │   │   ├── user.py
│   │   │   ├── algorithm.py
│   │   │   └── nutrition.py
│   │   └── db/               # SQLAlchemy ORM (DB 모델)
│   │       ├── base.py
│   │       ├── user.py
│   │       └── ...
│   │
│   ├── db/                   # DB 연결·세션
│   │   ├── __init__.py
│   │   ├── session.py
│   │   └── migrations/       # Alembic
│   │
│   ├── cache/                # Redis
│   │   ├── __init__.py
│   │   └── redis.py
│   │
│   └── utils/                # 유틸리티
│       ├── __init__.py
│       ├── logger.py
│       └── validators.py
│
└── tests/
    ├── __init__.py
    ├── conftest.py           # pytest 픽스처
    ├── unit/                 # 단위 테스트
    │   ├── algorithms/
    │   ├── nutrition/
    │   └── ...
    ├── integration/          # 통합 테스트
    └── fixtures/             # 테스트 데이터
```

---

## 🔧 pyproject.toml 표준 설정

```toml
[project]
name = "lemon-healthcare-backend"
version = "0.1.0"
requires-python = ">=3.11"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "W",    # pycodestyle warnings
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "RET",  # flake8-return
    "ARG",  # flake8-unused-arguments
    "PTH",  # flake8-use-pathlib
    "ERA",  # eradicate (commented-out code)
    "PL",   # pylint
    "RUF",  # ruff-specific
]
ignore = [
    "E501",   # line-length (black이 처리)
    "PLR0913", # too-many-arguments
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
plugins = ["pydantic.mypy"]

[tool.mypy-tests.*]
disallow_untyped_defs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
addopts = """
    -v
    --cov=src
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
    --strict-markers
"""
asyncio_mode = "auto"

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

---

## 🧱 표준 코드 패턴 (반드시 따를 것)

### Pattern 1. 알고리즘 모듈 (Pure Function)

```python
"""v1 활동점수 산출 알고리즘.

회사 가이드의 v1 정의를 구현한 순수 함수 모듈.

Reference:
    docs/07-core-algorithm.md §3.2
"""

from __future__ import annotations

from src.models.schemas.algorithm import BMICategory


SEX_FACTORS: dict[str, float] = {"male": 1.0, "female": 0.95}
"""성별 계수 (가이드 기준)."""

BMI_FACTORS: dict[BMICategory, float] = {
    BMICategory.UNDERWEIGHT: 0.9,
    BMICategory.NORMAL: 1.0,
    BMICategory.OVERWEIGHT: 1.05,
    BMICategory.OBESE_1: 1.1,
    BMICategory.OBESE_2: 1.15,
}
"""BMI 카테고리별 계수 (가이드 기준)."""


def get_age_factor(age: int) -> float:
    """연령에 따른 권장 걸음수 보정 계수를 반환한다.

    Args:
        age: 만 나이 (1~120 범위).

    Returns:
        연령 계수 (40세 미만 1.0 / 40~59세 0.9 / 60세 이상 0.8).

    Raises:
        ValueError: age가 1~120 범위를 벗어난 경우.

    Examples:
        >>> get_age_factor(30)
        1.0
        >>> get_age_factor(50)
        0.9
        >>> get_age_factor(65)
        0.8
    """
    if not 1 <= age <= 120:
        raise ValueError(f"age must be 1-120, got {age}")

    if age < 40:
        return 1.0
    if age < 60:
        return 0.9
    return 0.8
```

#### 핵심 규칙
- **순수 함수** 우선 (입력 → 출력만, 사이드 이펙트 X)
- **모듈 상수**는 대문자 + 타입 힌트
- **모듈 docstring** 첫 줄에 한 줄 요약 + Reference
- **Google-style docstring** 모든 함수에
- **`from __future__ import annotations`** 첫 줄에 (forward reference)

### Pattern 2. Pydantic v2 모델

```python
"""사용자 프로필 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """건강 분석을 위한 사용자 프로필 입력.

    Attributes:
        age: 만 나이 (1~120).
        sex: 성별 ("male" | "female").
        height_cm: 키 (cm, 50~250).
        weight_kg: 체중 (kg, 10~300).
        diseases: 만성질환 코드 리스트 (없으면 빈 리스트).
        is_smoker: 흡연자 여부 (목적별 분석에 사용).
    """

    model_config = ConfigDict(
        frozen=True,           # 불변 객체 (안전성 ↑)
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    age: int = Field(..., ge=1, le=120, description="만 나이")
    sex: Literal["male", "female"] = Field(..., description="성별")
    height_cm: float = Field(..., ge=50, le=250, description="키 (cm)")
    weight_kg: float = Field(..., ge=10, le=300, description="체중 (kg)")
    diseases: list[str] = Field(
        default_factory=list,
        description="만성질환 코드. 예: ['diabetes', 'hypertension']",
    )
    is_smoker: bool = Field(default=False, description="흡연자 여부")
```

#### 핵심 규칙
- **`BaseModel` 상속** (dataclass·NamedTuple 사용 X)
- **`ConfigDict(frozen=True)`** 권장 (불변)
- **`Field(...)`** 로 검증 + description (API 자동 문서화에 사용)
- **`Literal[...]`** 로 enum 효과 (간단한 경우)
- **연관된 enum은 별도** (`from enum import StrEnum`)

### Pattern 3. Adapter 패턴 (외부 API)

```python
"""OCR Adapter 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OCRResult:
    """OCR 결과 컨테이너.

    Attributes:
        text: 추출된 전체 텍스트.
        confidence: 평균 신뢰도 (0.0~1.0).
        engine: 사용된 OCR 엔진 식별자 (예: "google_vision_v1").
    """
    text: str
    confidence: float
    engine: str


class OCRAdapter(ABC):
    """OCR 엔진의 추상 인터페이스.

    모든 OCR 구현체는 이 클래스를 상속해야 한다. 실제 호출처는
    이 추상 클래스만 의존하므로, 향후 엔진 교체 시 한 줄만 변경하면 된다.

    Examples:
        >>> from src.ocr.google_vision import GoogleVisionOCR
        >>> ocr: OCRAdapter = GoogleVisionOCR()
        >>> result = await ocr.extract_text(image_bytes)
        >>> print(result.text)
    """

    @abstractmethod
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """이미지에서 텍스트를 추출한다.

        Args:
            image_bytes: 이미지 원본 바이트 (JPEG/PNG, 5MB 이하 권장).

        Returns:
            OCRResult — 추출된 텍스트와 신뢰도.

        Raises:
            OCRError: API 호출 실패 또는 이미지 처리 오류 시.
        """
        ...
```

#### 핵심 규칙
- **ABC + `@abstractmethod`** 사용
- **DTO는 `@dataclass(frozen=True)`** 또는 Pydantic
- **인터페이스는 async** 우선 (외부 호출은 모두 비동기)
- **에러 클래스 명시** (Raises 섹션)

### Pattern 4. FastAPI 라우터

```python
"""활동점수 API 라우터."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.algorithms import activity, bmi
from src.api.deps import get_current_user
from src.models.schemas.activity import ActivityRequest, ActivityResponse
from src.models.schemas.user import UserProfile

router = APIRouter(prefix="/activity", tags=["activity"])


@router.post(
    "/score",
    response_model=ActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="활동점수 v1~v4 계산",
    description="사용자 프로필과 활동 데이터로 v1~v4 활동점수를 산출한다.",
)
async def calculate_activity_score(
    request: ActivityRequest,
    current_user: UserProfile = Depends(get_current_user),
) -> ActivityResponse:
    """활동점수 계산 엔드포인트.

    Args:
        request: 활동 데이터 (걸음수, 심박 시간 등).
        current_user: 인증된 사용자 프로필.

    Returns:
        ActivityResponse — v1~v4 점수와 권장 걸음수.

    Raises:
        HTTPException: 입력값이 비정상이거나 계산 실패 시.
    """
    try:
        bmi_value = bmi.calculate_bmi(current_user.weight_kg, current_user.height_cm)
        bmi_category = bmi.classify_bmi(bmi_value)

        recommended_steps = activity.calculate_recommended_steps(
            sex=current_user.sex,
            age=current_user.age,
            bmi_category=bmi_category,
        )
        # ... v1~v4 계산
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return ActivityResponse(
        recommended_steps=recommended_steps,
        # ...
    )
```

#### 핵심 규칙
- **`prefix=` + `tags=`** 명시 (Swagger UI 그룹화)
- **`response_model=`** 으로 응답 스키마 강제
- **`summary=`, `description=`** Swagger 문서화
- **`Depends()`** 로 의존성 주입
- **`HTTPException(...) from e`** 로 원인 보존
- **try-except**로 ValueError → 400 변환

### Pattern 5. 단위 테스트 (pytest)

```python
"""v1 활동점수 단위 테스트."""

from __future__ import annotations

import pytest

from src.algorithms.activity import (
    calculate_recommended_steps,
    calculate_v1_score,
)
from src.models.schemas.algorithm import BMICategory


class TestRecommendedSteps:
    """권장 걸음수 산출 테스트."""

    def test_50f_obese1_guide_example(self) -> None:
        """[가이드 예시] 50대 여성 비만1단계: 8000 × 0.95 × 0.9 × 1.1 = 7,524."""
        steps = calculate_recommended_steps(
            sex="female",
            age=50,
            bmi_category=BMICategory.OBESE_1,
        )
        assert steps == 7524

    @pytest.mark.parametrize(
        ("sex", "age", "bmi_cat", "expected"),
        [
            ("male", 30, BMICategory.NORMAL, 8000),       # 기준치
            ("female", 30, BMICategory.NORMAL, 7600),     # 여성 0.95
            ("male", 50, BMICategory.NORMAL, 7200),       # 40~59세 0.9
            ("male", 65, BMICategory.NORMAL, 6400),       # 60+ 0.8
        ],
    )
    def test_recommended_steps_factors(
        self,
        sex: str,
        age: int,
        bmi_cat: BMICategory,
        expected: int,
    ) -> None:
        """성별·연령·BMI 계수가 곱으로 적용되는지 검증."""
        assert calculate_recommended_steps(sex, age, bmi_cat) == expected


class TestV1Score:
    """v1 기본점수 산출 테스트."""

    def test_50f_obese1_7000steps_guide_example(self) -> None:
        """[가이드 예시] 7000보 / 7524 = 0.93 × 83.33 ≈ 77.5."""
        score = calculate_v1_score(actual_steps=7000, recommended_steps=7524)
        assert score == pytest.approx(77.5, abs=0.1)
```

#### 핵심 규칙
- **클래스로 그룹화** (`TestXxx`)
- **`[가이드 예시]` 접두어** — 회사 PPTX의 계산 예시 명시
- **`@pytest.mark.parametrize`** 적극 사용
- **`pytest.approx(..., abs=...)`** 부동소수점 비교
- **테스트 함수 docstring 한국어 OK** (가독성)
- **타입 힌트 필수** (테스트도 mypy 검증)

### Pattern 6. Pydantic Settings (환경 변수)

```python
"""애플리케이션 설정."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정.

    Attributes:
        environment: 실행 환경.
        database_url: PostgreSQL 연결 URL.
        anthropic_api_key: Claude API 키 (SecretStr로 보호).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    database_url: str = Field(..., description="PostgreSQL 연결 URL")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # API 키는 SecretStr로 (로그 출력 시 자동 마스킹)
    anthropic_api_key: SecretStr = Field(...)
    google_application_credentials: str = Field(...)
    mfds_api_key: SecretStr = Field(...)

    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴.

    Returns:
        애플리케이션 설정. lru_cache로 1회만 로드.
    """
    return Settings()  # type: ignore[call-arg]
```

#### 핵심 규칙
- **API 키는 `SecretStr`** (로그 누출 방지)
- **`@lru_cache`로 싱글턴** 보장
- **`extra="ignore"`** 로 알 수 없는 환경변수 무시

---

## 🧪 단위 테스트 작성 규칙

### 필수 검증 패턴

| 카테고리 | 필수 케이스 |
|---------|-----------|
| **회사 가이드 예시** | PPTX의 모든 계산 예시 (50대 여성, 45세 남성 등) — 정확히 일치 |
| **경계값** | 카테고리 경계 (BMI 18.5, 23.0, 25.0, 30.0 등) |
| **상한·하한** | 점수 100 상한, 0 하한 |
| **에러 케이스** | ValueError가 적절히 발생하는지 |
| **None / 기본값** | Optional 인자가 None일 때 동작 |
| **Empty Collection** | 빈 리스트·딕셔너리 입력 |

### 테스트 파일 구조

```
tests/unit/algorithms/
├── test_bmi.py
├── test_activity.py        # v1, v2, v3, v4
├── test_metabolism.py      # BMR, TDEE
└── test_prediction.py      # 7-step
```

각 파일 안에서는 **클래스로 그룹화**:

```python
class TestBMICalculation: ...
class TestBMIClassification: ...
class TestBMIBoundaries: ...
```

### conftest.py — 공통 픽스처

```python
"""공통 pytest 픽스처."""

import pytest

from src.models.schemas.user import UserProfile


@pytest.fixture
def user_50f_obese1() -> UserProfile:
    """가이드 예시: 50대 여성, 비만 1단계."""
    return UserProfile(
        age=50,
        sex="female",
        height_cm=160,
        weight_kg=68.0,
        diseases=["diabetes", "hypertension"],
    )


@pytest.fixture
def user_45m_overweight() -> UserProfile:
    """가이드 예시: 45세 남성, 과체중."""
    return UserProfile(
        age=45,
        sex="male",
        height_cm=175,
        weight_kg=82.0,
        diseases=[],
    )
```

---

## 📦 의존성 추가 절차

### 1. 새 패키지 추가 시

```bash
# 추가 후 requirements.txt 갱신
pip install <package>
pip freeze | grep <package>  # 버전 확인
# requirements.txt에 직접 명시 (버전 포함)
```

### 2. requirements.txt 권장 형식

```
# Core
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

# Dev tools (개발 의존성은 별도 파일 권장)
# requirements-dev.txt에 분리
```

### 3. 라이선스 확인

새 의존성 추가 시 **MIT / Apache 2.0 / BSD** 등 본 프로젝트와 호환되는 라이선스인지 확인.

---

## 🚀 일반적인 작업 순서

새 알고리즘을 구현할 때 표준 순서:

```
1. docs/07-core-algorithm.md 에서 명세 확인
2. (있다면) docs/dev-guides/0X-*.md 에서 상세 가이드 확인
3. tests/unit/{module}/test_{name}.py 먼저 작성 (TDD)
   - 회사 가이드 예시를 케이스로
4. src/{module}/{name}.py 구현
5. pytest tests/unit/{module}/test_{name}.py -v 통과
6. mypy src/{module}/{name}.py --strict 통과
7. black + ruff 적용
8. 커밋 (Conventional Commits)
```

---

## 📊 로깅 표준

```python
"""로깅 설정 및 사용 예시."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def some_function() -> None:
    """예시 함수."""
    # ✅ 권장
    logger.info("Processing supplement label", extra={"image_size": 1024})
    logger.warning("OCR confidence below threshold: %.2f", 0.65)
    logger.error("API call failed", exc_info=True)

    # ❌ 금지
    print("처리 중...")  # print() 사용 금지
```

#### 로그 레벨 가이드

| 레벨 | 사용 시점 |
|------|----------|
| DEBUG | 개발 시 추적용. 운영 환경에선 비활성 |
| INFO | 정상적인 흐름 (요청 처리 시작·완료) |
| WARNING | 정상은 아니지만 처리는 가능 (OCR 신뢰도 낮음) |
| ERROR | 예외 발생, 처리 실패 |
| CRITICAL | 시스템 다운 위험 |

#### 민감 정보 로깅 금지

```python
# ❌ 절대 금지
logger.info(f"User logged in: {user.password}")
logger.debug(f"API key: {settings.anthropic_api_key}")

# ✅ 안전
logger.info("User logged in: %s", user.id)  # ID만
# SecretStr은 자동으로 ********로 표시
```

---

## ⚡ 비동기 코드 규칙

```python
# ✅ 권장
async def process_image(image_bytes: bytes) -> OCRResult:
    """이미지를 비동기로 처리."""
    async with httpx.AsyncClient() as client:
        response = await client.post(...)
    return OCRResult(...)


# 동시 호출
import asyncio

async def process_multiple(images: list[bytes]) -> list[OCRResult]:
    """여러 이미지 동시 처리."""
    return await asyncio.gather(*[process_image(img) for img in images])


# ❌ 금지
async def bad_pattern():
    time.sleep(1)         # blocking — asyncio.sleep() 사용
    requests.get(url)     # blocking — httpx.AsyncClient 사용
```

---

## 🔒 보안 체크리스트

| 항목 | 규칙 |
|------|------|
| API 키 | `SecretStr` 사용, 절대 `print()` X |
| SQL | SQLAlchemy ORM 또는 prepared statement만 (raw SQL 금지) |
| 입력 검증 | Pydantic으로 모든 외부 입력 검증 |
| CORS | 명시적 origin만 허용 |
| HTTPS | 운영 환경에서 강제 |
| 의존성 | `pip-audit` 정기 실행 |
| 민감 컬럼 | AES-256 암호화 (의료 정보) |

---

## 📖 자주 참조하는 외부 문서

- FastAPI: https://fastapi.tiangolo.com/
- Pydantic v2: https://docs.pydantic.dev/latest/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
- pytest: https://docs.pytest.org/

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../CLAUDE.md) — 프로젝트 루트 컨텍스트
- [`/docs/06-tech-stack.md`](../docs/06-tech-stack.md) — 기술 스택 의사결정
- [`/docs/07-core-algorithm.md`](../docs/07-core-algorithm.md) — 알고리즘 명세
- [`/docs/dev-guides/`](../docs/dev-guides/) — 작업 단위 가이드

---

**마지막 갱신**: 2026-05-03 | **버전**: v1.0
