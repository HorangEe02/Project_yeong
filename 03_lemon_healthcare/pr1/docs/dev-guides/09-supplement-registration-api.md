# dev-guides/09 — 영양제 등록 API (FastAPI 통합)

> **Phase**: 2 | **선행 작업**: [`07-ocr-pipeline.md`](./07-ocr-pipeline.md), [`08-llm-supplement-parsing.md`](./08-llm-supplement-parsing.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

OCR → LLM 파싱 → 식약처 매칭 → 부족 영양소 진단을 **하나의 FastAPI 엔드포인트**로 통합한다. multipart 이미지 업로드, 인증, 캐싱, 응답 시간 < 6초 목표.

---

## 📋 산출물

```
backend/
├── src/
│   ├── api/
│   │   ├── deps.py                # 의존성 주입 (DI)
│   │   └── v1/
│   │       └── supplements.py     # 영양제 라우터
│   ├── models/
│   │   ├── schemas/
│   │   │   └── supplement.py      # API 요청·응답 스키마
│   │   └── db/
│   │       └── supplement.py      # SQLAlchemy 모델
│   ├── db/
│   │   ├── session.py             # AsyncSession 의존성
│   │   └── migrations/
│   │       └── versions/
│   │           └── xxx_add_supplements.py  # Alembic
│   └── services/
│       └── supplement_service.py  # 비즈니스 로직 (라우터에서 분리)
└── tests/
    ├── unit/api/
    │   └── test_supplements_router.py
    ├── integration/api/
    │   └── test_supplements_integration.py
    └── e2e/api/
        └── test_supplement_registration_e2e.py
```

---

## 📐 API 명세

### 엔드포인트

```
POST /api/v1/supplements/register
Content-Type: multipart/form-data

Body:
  image: <binary>  (필수, ≤ 5MB, JPEG/PNG)
  
Headers:
  Authorization: Bearer <token>  (필수)

Response 200:
{
  "supplement_id": "uuid",
  "product_name": "종합비타민",
  "manufacturer": "ABC제약",
  "ingredients": [
    {
      "code": "vitamin_c_mg",
      "name_ko": "비타민 C",
      "amount": 1000,
      "unit": "mg"
    }
  ],
  "diagnosis": {
    "diagnoses": [...],
    "summary_message_ko": "..."
  },
  "ocr_engine": "google_vision_v1",
  "llm_engine": "claude:claude-sonnet-4-6",
  "elapsed_ms": 2340
}

Response 400: 이미지 검증 실패
Response 401: 인증 실패
Response 422: OCR/LLM 처리 실패
Response 500: 시스템 오류
```

---

## 🔧 구현 명세

### 1. `src/models/schemas/supplement.py`

```python
"""영양제 API 입출력 스키마."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.nutrition import DiagnosisResult, NutrientIntake


class IngredientResponse(BaseModel):
    """응답에 포함되는 단일 성분."""

    model_config = ConfigDict(frozen=True)

    code: str
    name_ko: str
    amount: float
    unit: str


class SupplementRegisterResponse(BaseModel):
    """영양제 등록 API 응답.

    Attributes:
        supplement_id: 저장된 영양제 ID.
        product_name: 제품명.
        manufacturer: 제조사.
        ingredients: 매칭된 성분 리스트.
        diagnosis: 부족 영양소 진단.
        ocr_engine: 사용된 OCR 엔진.
        llm_engine: 사용된 LLM 엔진.
        elapsed_ms: 전체 처리 시간 (ms).
    """

    model_config = ConfigDict(frozen=True)

    supplement_id: UUID
    product_name: str | None
    manufacturer: str | None
    ingredients: list[IngredientResponse]
    diagnosis: DiagnosisResult
    ocr_engine: str
    llm_engine: str
    elapsed_ms: float = Field(..., ge=0)
```

### 2. `src/models/db/supplement.py`

```python
"""영양제 DB 모델 (SQLAlchemy)."""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base

if TYPE_CHECKING:
    from src.models.db.user import User


class Supplement(Base):
    """등록된 영양제 한 건.

    Attributes:
        id: UUID 기본키.
        user_id: 등록한 사용자.
        product_name: 제품명.
        manufacturer: 제조사.
        ingredients: 성분 정보 (JSON).
        ocr_engine: 사용된 OCR 엔진.
        llm_engine: 사용된 LLM 엔진.
        registered_at: 등록 시각 (UTC).
    """

    __tablename__ = "supplements"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    product_name: Mapped[str | None] = mapped_column(String(200))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    ingredients: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    ocr_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship(back_populates="supplements")
```

### 3. `src/api/deps.py`

```python
"""FastAPI 의존성 주입."""

from __future__ import annotations

from typing import Annotated, AsyncIterator

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.ocr_cache import OCRCache
from src.config import Settings, get_settings
from src.db.session import get_session
from src.llm.base import LLMAdapter
from src.llm.claude import ClaudeAdapter
from src.llm.openai import OpenAIAdapter
from src.models.db.user import User
from src.ocr.base import OCRAdapter
from src.ocr.clova import ClovaOCR
from src.ocr.google_vision import GoogleVisionOCR
from src.ocr.pipeline import OCRPipeline


def get_ocr_pipeline(
    settings: Annotated[Settings, Depends(get_settings)],
) -> OCRPipeline:
    """OCR 파이프라인 의존성 (캐싱 + 폴백 포함)."""
    primary = GoogleVisionOCR()
    fallback = (
        ClovaOCR(
            api_url=settings.clova_ocr_url,
            secret_key=settings.clova_ocr_secret.get_secret_value(),
        )
        if settings.clova_ocr_url and settings.clova_ocr_secret
        else None
    )
    redis_client = redis.from_url(settings.redis_url)
    cache = OCRCache(redis_client)
    return OCRPipeline(primary=primary, fallback=fallback, cache=cache)


def get_primary_llm(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMAdapter:
    """주력 LLM (Claude)."""
    return ClaudeAdapter(api_key=settings.anthropic_api_key.get_secret_value())


def get_fallback_llm(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMAdapter | None:
    """백업 LLM (GPT). 키 없으면 None."""
    if not settings.openai_api_key:
        return None
    return OpenAIAdapter(api_key=settings.openai_api_key.get_secret_value())


async def get_current_user(
    authorization: Annotated[str, Header()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """JWT 토큰으로 현재 사용자 조회.

    Raises:
        HTTPException 401: 토큰 누락 또는 만료.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization[7:]
    # JWT 검증 (별도 모듈 필요, 여기선 간단히)
    # ... (jwt.decode + DB 조회)
    raise NotImplementedError("Implement JWT verification")
```

### 4. `src/services/supplement_service.py`

```python
"""영양제 등록 서비스 — 비즈니스 로직.

라우터에서 분리하여 테스트 용이성 + 재사용성 확보.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.base import LLMAdapter
from src.llm.exceptions import LLMError
from src.models.db.supplement import Supplement
from src.models.db.user import User
from src.models.schemas.nutrition import UserKDRIsContext
from src.models.schemas.supplement import (
    IngredientResponse,
    SupplementRegisterResponse,
)
from src.nutrition.diagnosis import diagnose
from src.nutrition.mfds_matcher import to_nutrient_intakes
from src.ocr.exceptions import OCRError
from src.ocr.pipeline import OCRPipeline


logger = logging.getLogger(__name__)


MAX_IMAGE_SIZE_BYTES: Final[int] = 5 * 1024 * 1024  # 5MB
ALLOWED_CONTENT_TYPES: Final[set[str]] = {"image/jpeg", "image/png", "image/jpg"}


class SupplementService:
    """영양제 등록·관리 서비스."""

    def __init__(
        self,
        ocr_pipeline: OCRPipeline,
        primary_llm: LLMAdapter,
        fallback_llm: LLMAdapter | None,
        session: AsyncSession,
    ) -> None:
        self._ocr = ocr_pipeline
        self._primary_llm = primary_llm
        self._fallback_llm = fallback_llm
        self._session = session

    async def register(
        self,
        image_bytes: bytes,
        content_type: str,
        user: User,
    ) -> SupplementRegisterResponse:
        """영양제 사진 → 분석 → 저장 전체 흐름.

        Args:
            image_bytes: 이미지 바이트.
            content_type: MIME 타입.
            user: 인증된 사용자.

        Returns:
            등록 결과.

        Raises:
            HTTPException: 검증 실패, 처리 실패 시.
        """
        start = time.perf_counter()

        # 1. 이미지 검증
        self._validate_image(image_bytes, content_type)

        # 2. OCR
        try:
            ocr_result = await self._ocr.extract(image_bytes)
        except OCRError as e:
            logger.error("OCR failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="이미지에서 텍스트를 인식하지 못했습니다.",
            ) from e

        if not ocr_result.text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="이미지에서 텍스트를 추출할 수 없습니다.",
            )

        # 3. LLM 파싱 (폴백 포함)
        parsed = await self._parse_with_fallback(ocr_result.text)

        # 4. 식약처 매칭
        intakes = to_nutrient_intakes(parsed.ingredients)
        if not intakes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="라벨에서 인식 가능한 성분을 찾지 못했습니다.",
            )

        # 5. 진단
        user_ctx = UserKDRIsContext(
            age=user.age,
            sex=user.sex,
            is_pregnant=user.is_pregnant,
            is_lactating=user.is_lactating,
        )
        diagnosis = diagnose(intakes, user_ctx)

        # 6. DB 저장
        supplement = Supplement(
            id=uuid.uuid4(),
            user_id=user.id,
            product_name=parsed.product_name,
            manufacturer=parsed.manufacturer,
            ingredients=[
                {
                    "code": i.code,
                    "amount": i.amount,
                    "unit": i.unit,
                }
                for i in intakes
            ],
            ocr_engine=ocr_result.engine,
            llm_engine=parsed.engine,
        )
        self._session.add(supplement)
        await self._session.commit()
        await self._session.refresh(supplement)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return SupplementRegisterResponse(
            supplement_id=supplement.id,
            product_name=parsed.product_name,
            manufacturer=parsed.manufacturer,
            ingredients=[
                IngredientResponse(
                    code=i.code,
                    name_ko=next(
                        (d.name_ko for d in diagnosis.diagnoses if d.code == i.code),
                        i.code,
                    ),
                    amount=i.amount,
                    unit=i.unit,
                )
                for i in intakes
            ],
            diagnosis=diagnosis,
            ocr_engine=ocr_result.engine,
            llm_engine=parsed.engine,
            elapsed_ms=elapsed_ms,
        )

    def _validate_image(self, image_bytes: bytes, content_type: str) -> None:
        """이미지 검증."""
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 형식: {content_type}",
            )
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"이미지 크기 초과: {len(image_bytes) / 1024 / 1024:.1f}MB > 5MB",
            )
        if len(image_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="빈 이미지",
            )

    async def _parse_with_fallback(self, ocr_text: str):
        """주력 LLM 시도 → 실패 시 백업."""
        try:
            return await self._primary_llm.parse_supplement(ocr_text)
        except LLMError as e:
            logger.warning("Primary LLM failed: %s", e)
            if self._fallback_llm is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="영양제 정보 파싱에 실패했습니다.",
                ) from e
            try:
                return await self._fallback_llm.parse_supplement(ocr_text)
            except LLMError as e2:
                logger.error("Fallback LLM also failed: %s", e2)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="영양제 정보 파싱에 실패했습니다.",
                ) from e2
```

### 5. `src/api/v1/supplements.py`

```python
"""영양제 API 라우터."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    get_current_user,
    get_fallback_llm,
    get_ocr_pipeline,
    get_primary_llm,
)
from src.db.session import get_session
from src.llm.base import LLMAdapter
from src.models.db.user import User
from src.models.schemas.supplement import SupplementRegisterResponse
from src.ocr.pipeline import OCRPipeline
from src.services.supplement_service import SupplementService


router = APIRouter(prefix="/supplements", tags=["supplements"])


@router.post(
    "/register",
    response_model=SupplementRegisterResponse,
    status_code=status.HTTP_200_OK,
    summary="영양제 사진 등록·분석",
    description=(
        "영양제 라벨 사진을 업로드하면 OCR + LLM으로 성분을 추출하고, "
        "사용자의 KDRIs와 비교하여 부족 영양소를 분석합니다."
    ),
)
async def register_supplement(
    image: Annotated[UploadFile, File(..., description="영양제 라벨 사진")],
    current_user: Annotated[User, Depends(get_current_user)],
    ocr_pipeline: Annotated[OCRPipeline, Depends(get_ocr_pipeline)],
    primary_llm: Annotated[LLMAdapter, Depends(get_primary_llm)],
    fallback_llm: Annotated[LLMAdapter | None, Depends(get_fallback_llm)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SupplementRegisterResponse:
    """영양제 사진을 등록하고 성분을 분석한다."""
    image_bytes = await image.read()

    service = SupplementService(
        ocr_pipeline=ocr_pipeline,
        primary_llm=primary_llm,
        fallback_llm=fallback_llm,
        session=session,
    )
    return await service.register(
        image_bytes=image_bytes,
        content_type=image.content_type or "application/octet-stream",
        user=current_user,
    )
```

### 6. Alembic 마이그레이션

```bash
cd backend
alembic revision -m "add supplements table" --autogenerate
alembic upgrade head
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트 (서비스)

```python
"""SupplementService 단위 테스트 (모든 외부 의존성 모킹)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from src.services.supplement_service import SupplementService


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.age = 30
    user.sex = "male"
    user.is_pregnant = False
    user.is_lactating = False
    return user


class TestSupplementService:
    @pytest.mark.asyncio
    async def test_invalid_content_type_raises_400(self, mock_user):
        service = SupplementService(
            ocr_pipeline=AsyncMock(),
            primary_llm=AsyncMock(),
            fallback_llm=None,
            session=AsyncMock(),
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.register(b"data", "text/plain", mock_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_oversized_image_raises_400(self, mock_user):
        service = SupplementService(
            ocr_pipeline=AsyncMock(),
            primary_llm=AsyncMock(),
            fallback_llm=None,
            session=AsyncMock(),
        )
        large = b"x" * (6 * 1024 * 1024)
        with pytest.raises(HTTPException) as exc_info:
            await service.register(large, "image/jpeg", mock_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_empty_ocr_text_raises_422(self, mock_user):
        ocr_mock = AsyncMock()
        ocr_mock.extract.return_value.text = "  "  # 공백만
        ocr_mock.extract.return_value.engine = "mock"

        service = SupplementService(
            ocr_pipeline=ocr_mock,
            primary_llm=AsyncMock(),
            fallback_llm=None,
            session=AsyncMock(),
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.register(b"data", "image/jpeg", mock_user)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_primary_llm_fails_uses_fallback(self, mock_user):
        # 주력 LLM 실패 시 백업 호출 검증
        ...

    @pytest.mark.asyncio
    async def test_no_matched_ingredients_raises_422(self, mock_user):
        # 식약처 매칭 0개 → 422
        ...
```

### Tier 2: 라우터 통합 테스트 (TestClient)

```python
"""FastAPI 라우터 + 서비스 통합 (외부 API 모킹)."""

from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client_with_mocks(monkeypatch):
    # OCR, LLM 의존성 오버라이드
    app.dependency_overrides[get_ocr_pipeline] = lambda: MockOCRPipeline()
    app.dependency_overrides[get_primary_llm] = lambda: MockLLM()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_register_returns_200(client_with_mocks):
    with open("tests/fixtures/sample.jpg", "rb") as f:
        response = client_with_mocks.post(
            "/api/v1/supplements/register",
            files={"image": ("sample.jpg", f, "image/jpeg")},
            headers={"Authorization": "Bearer test"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "supplement_id" in data
    assert "diagnosis" in data
    assert data["elapsed_ms"] > 0


def test_register_no_auth_returns_401(client_with_mocks):
    # ...

def test_register_no_image_returns_422(client_with_mocks):
    # ...

def test_register_oversized_image_returns_400(client_with_mocks):
    # ...
```

### Tier 3: E2E 테스트 (실제 인프라)

```python
"""실제 PostgreSQL + Redis + 외부 API 사용 (Docker Compose 환경)."""

@pytest.mark.e2e
class TestSupplementRegistrationE2E:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_real_image(
        self, real_app_client, test_user_token,
    ):
        with open("tests/fixtures/real_supplement.jpg", "rb") as f:
            response = await real_app_client.post(
                "/api/v1/supplements/register",
                files={"image": ("supp.jpg", f, "image/jpeg")},
                headers={"Authorization": f"Bearer {test_user_token}"},
            )
        assert response.status_code == 200
        data = response.json()
        # 최소 1개 이상의 성분이 등록되어야 함
        assert len(data["ingredients"]) > 0
        # 진단 결과가 포함되어야 함
        assert "diagnosis" in data
        # 응답 시간 < 6초
        assert data["elapsed_ms"] < 6000
```

### Tier 4: 성능 테스트

```python
"""응답 시간 + 동시성 테스트."""

@pytest.mark.performance
class TestSupplementPerformance:
    @pytest.mark.asyncio
    async def test_response_under_6s(self, client):
        """첫 호출 (캐시 미스) < 6초."""
        ...

    @pytest.mark.asyncio
    async def test_cached_response_under_500ms(self, client):
        """동일 이미지 재호출 (캐시 hit) < 500ms."""
        ...

    @pytest.mark.asyncio
    async def test_concurrent_10_requests(self, client):
        """10개 동시 요청 처리."""
        import asyncio
        # ...
```

---

## ✅ Definition of Done

- [ ] `src/models/schemas/supplement.py` — API 스키마
- [ ] `src/models/db/supplement.py` — SQLAlchemy 모델
- [ ] Alembic 마이그레이션 생성·적용
- [ ] `src/api/deps.py` — 의존성 주입 (OCR, LLM, User, Session)
- [ ] `src/services/supplement_service.py` — 비즈니스 로직
- [ ] `src/api/v1/supplements.py` — 라우터
- [ ] `src/main.py` 에 라우터 등록
- [ ] 단위 테스트 (서비스) 10+
- [ ] 라우터 통합 테스트 (TestClient + 모킹) 10+
- [ ] E2E 테스트 (실 인프라) 3+
- [ ] 성능 테스트 (캐시 미스 < 6초, hit < 500ms, 동시 10건)
- [ ] Swagger UI에서 정상 표시 + 시연 가능
- [ ] `mypy src --strict` 통과
- [ ] 코드 커버리지 ≥ 85%

---

## 💡 구현 팁

### 의존성 오버라이드 (테스트)

```python
app.dependency_overrides[get_ocr_pipeline] = lambda: MockOCRPipeline()
```

→ 실제 외부 API 없이 라우터 테스트 가능.

### 응답 시간 최적화

| 단계 | 시간 | 최적화 |
|------|------|--------|
| 이미지 전처리 | ~100ms | PIL이 빠름 |
| OCR | 800~1500ms | 캐싱으로 0ms 가능 |
| LLM | 1500~3000ms | Sonnet 4.6 권장 (Opus는 느림) |
| 매칭·진단 | < 50ms | 메모리 룩업 |
| DB 저장 | ~50ms | 비동기 |
| **합계** | **~2.5~5초** | 캐시 hit 시 < 500ms |

### 에러 매핑 표준

| 발생 위치 | HTTP | 메시지 |
|----------|------|--------|
| 이미지 형식·크기 | 400 | "이미지 형식·크기 검증 실패" |
| 인증 실패 | 401 | "인증이 필요합니다" |
| OCR 실패 | 422 | "텍스트 인식에 실패했습니다" |
| LLM 실패 | 422 | "성분 정보 파싱에 실패했습니다" |
| 매칭 0개 | 422 | "인식 가능한 성분을 찾지 못했습니다" |
| 시스템 오류 | 500 | "내부 오류" (구체 정보 X) |

---

## 🚫 이 작업에서 하지 말 것

- ❌ 인증 로직 직접 작성 (별도 모듈)
- ❌ 라우터에 비즈니스 로직 직접 작성 (서비스로 분리)
- ❌ DB 세션 직접 관리 (Depends 사용)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- 이전: [`08-llm-supplement-parsing.md`](./08-llm-supplement-parsing.md)
- 다음: [`10-mobile-flutter-setup.md`](./10-mobile-flutter-setup.md)
