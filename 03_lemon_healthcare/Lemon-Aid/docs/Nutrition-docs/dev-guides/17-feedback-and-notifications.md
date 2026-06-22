# dev-guides/17 — 사용자 피드백 + 푸시 알림 시스템

> **Phase**: 3 | **선행 작업**: [`09-supplement-registration-api.md`](./09-supplement-registration-api.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

사용자 피드백 수집·집계 백엔드와 FCM(Android)+APNs(iOS) 푸시 알림 시스템을 구축한다. 인식 정확도 향상을 위한 피드백 루프 + 일일 활동 리마인더.

---

## 📋 산출물

```
backend/
├── src/
│   ├── feedback/
│   │   ├── __init__.py
│   │   ├── service.py             # 피드백 수집·집계
│   │   └── analytics.py           # 통계·트렌드 분석
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── base.py                # NotificationAdapter ABC
│   │   ├── fcm.py                 # Firebase FCM
│   │   ├── apns.py                # Apple APNs
│   │   ├── dispatcher.py          # 통합 디스패처
│   │   └── templates.py           # 알림 템플릿 (의료법 표현)
│   ├── api/v1/
│   │   ├── feedback.py            # POST /api/v1/feedback
│   │   └── notifications.py       # 디바이스 토큰 등록
│   └── models/db/
│       ├── feedback.py            # SQLAlchemy
│       └── device_token.py
└── tests/
    ├── unit/feedback/
    ├── unit/notifications/
    ├── integration/
    └── e2e/
        └── test_feedback_loop_e2e.py
```

---

## 📐 피드백 시스템 설계

### 피드백 종류

| 종류 | 코드 | 수집 시점 |
|------|------|---------|
| **OCR 정확도** | `ocr_accuracy` | 영양제 등록 직후 (성분이 맞는지) |
| **LLM 파싱 정확도** | `llm_parsing` | 영양제 등록 직후 |
| **식단 인식 정확도** | `meal_recognition` | 식단 등록 직후 |
| **목적별 분석 만족도** | `goal_analysis` | 목적별 분석 화면 |
| **체중 예측 정확도** | `weight_prediction` | 1주 후 실제 체중 비교 |
| **앱 전반 만족도** | `general` | 일주일 1회 |

### 피드백 데이터 구조

```
{
  "feedback_id": "uuid",
  "user_id": "uuid",
  "type": "ocr_accuracy",
  "rating": 4,          // 1~5
  "comment": "비타민D만 인식 못함",  // 선택
  "context_id": "supplement_uuid",  // 관련 객체 ID
  "metadata": {
    "ocr_engine": "google_vision_v1",
    "llm_engine": "ollama:qwen3.5:9b"
  },
  "created_at": "2026-05-03T10:00:00Z"
}
```

### 알림 종류

| 종류 | 코드 | 발송 시점 |
|------|------|---------|
| **활동 리마인더** | `activity_reminder` | 권장 걸음수 70% 미달 시, 18시 |
| **영양제 복용** | `supplement_reminder` | 사용자 설정 시간 |
| **주간 리포트** | `weekly_report` | 매주 일요일 20시 |
| **신규 기능** | `feature_announcement` | 운영자 수동 발송 |

---

## 🔧 구현 명세

### 1. `src/models/db/feedback.py`

```python
"""피드백 DB 모델."""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db.base import Base


class Feedback(Base):
    """사용자 피드백 한 건.

    Attributes:
        id: UUID 기본키.
        user_id: 사용자.
        type: 피드백 종류.
        rating: 1~5 평점.
        comment: 자유 코멘트 (선택).
        context_id: 관련 객체 ID (예: supplement.id).
        metadata: 추가 정보 (사용된 엔진 등).
        created_at: 작성 시각.
    """

    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    context_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
```

### 2. `src/models/db/device_token.py`

```python
"""디바이스 토큰 (FCM/APNs)."""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db.base import Base


class DeviceToken(Base):
    """푸시 알림 토큰.

    Attributes:
        id: UUID 기본키.
        user_id: 사용자.
        platform: "ios" | "android".
        token: FCM/APNs 토큰.
        device_name: 기기 식별 (선택).
        created_at, last_used_at: 추적.
    """

    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", "token", name="uq_user_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    platform: Mapped[str] = mapped_column(String(10), nullable=False)
    token: Mapped[str] = mapped_column(String(500), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
```

### 3. `src/feedback/service.py`

```python
"""피드백 수집·집계 서비스."""

from __future__ import annotations

import logging
import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.feedback import Feedback


logger = logging.getLogger(__name__)


VALID_TYPES: Final[set[str]] = {
    "ocr_accuracy",
    "llm_parsing",
    "meal_recognition",
    "goal_analysis",
    "weight_prediction",
    "general",
}


class FeedbackService:
    """피드백 수집·집계."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def submit(
        self,
        user_id: uuid.UUID,
        type: str,
        rating: int,
        comment: str | None = None,
        context_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> Feedback:
        """피드백 저장.

        Args:
            user_id: 사용자.
            type: 종류.
            rating: 1~5.
            comment: 코멘트.
            context_id: 관련 객체 ID.
            metadata: 추가 정보.

        Returns:
            저장된 Feedback.

        Raises:
            ValueError: 검증 실패.
        """
        if type not in VALID_TYPES:
            raise ValueError(f"Invalid feedback type: {type}")
        if not 1 <= rating <= 5:
            raise ValueError(f"rating must be 1-5, got {rating}")
        if comment and len(comment) > 1000:
            raise ValueError(f"comment too long: {len(comment)}")

        feedback = Feedback(
            id=uuid.uuid4(),
            user_id=user_id,
            type=type,
            rating=rating,
            comment=comment,
            context_id=context_id,
            extra_metadata=metadata or {},
        )
        self._session.add(feedback)
        await self._session.commit()
        await self._session.refresh(feedback)

        logger.info(
            "Feedback submitted: user=%s type=%s rating=%d",
            user_id, type, rating,
        )
        return feedback

    async def get_average_rating(
        self, type: str, days: int = 30,
    ) -> float | None:
        """최근 N일 평균 평점.

        Args:
            type: 피드백 종류.
            days: 집계 기간.

        Returns:
            평균 평점 (없으면 None).
        """
        from datetime import datetime, UTC, timedelta
        from sqlalchemy import func
        cutoff = datetime.now(UTC) - timedelta(days=days)

        result = await self._session.execute(
            select(func.avg(Feedback.rating))
            .where(Feedback.type == type)
            .where(Feedback.created_at >= cutoff)
        )
        avg = result.scalar()
        return float(avg) if avg is not None else None
```

### 4. `src/notifications/base.py`

```python
"""푸시 알림 추상."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class PushNotification(BaseModel):
    """알림 페이로드."""

    model_config = ConfigDict(frozen=True)

    title: str
    body: str
    data: dict[str, str] = {}


class NotificationResult(BaseModel):
    """발송 결과."""

    model_config = ConfigDict(frozen=True)

    success: bool
    message_id: str | None = None
    error_message: str | None = None


class NotificationAdapter(ABC):
    """푸시 알림 추상."""

    @abstractmethod
    async def send(
        self, token: str, notification: PushNotification,
    ) -> NotificationResult:
        ...

    @property
    @abstractmethod
    def platform(self) -> str:
        ...
```

### 5. `src/notifications/fcm.py`

```python
"""Firebase FCM 구현 (Android)."""

from __future__ import annotations

import logging

import firebase_admin
from firebase_admin import credentials, messaging

from src.notifications.base import (
    NotificationAdapter,
    NotificationResult,
    PushNotification,
)


logger = logging.getLogger(__name__)


class FCMAdapter(NotificationAdapter):
    """Firebase FCM 기반 알림."""

    def __init__(self, credentials_path: str) -> None:
        """초기화.

        Args:
            credentials_path: 서비스 계정 키 JSON 경로.
        """
        cred = credentials.Certificate(credentials_path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

    @property
    def platform(self) -> str:
        return "android"

    async def send(
        self, token: str, notification: PushNotification,
    ) -> NotificationResult:
        """FCM 전송.

        Args:
            token: FCM 디바이스 토큰.
            notification: 알림 내용.

        Returns:
            발송 결과.
        """
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(
                title=notification.title,
                body=notification.body,
            ),
            data=notification.data,
        )
        try:
            message_id = messaging.send(message)
            return NotificationResult(success=True, message_id=message_id)
        except messaging.UnregisteredError as e:
            logger.warning("FCM token unregistered: %s", token[:20])
            return NotificationResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error("FCM send failed: %s", e)
            return NotificationResult(success=False, error_message=str(e))
```

### 6. `src/notifications/apns.py`

```python
"""Apple APNs 구현 (iOS)."""

from __future__ import annotations

import logging

from src.notifications.base import (
    NotificationAdapter,
    NotificationResult,
    PushNotification,
)


logger = logging.getLogger(__name__)


class APNsAdapter(NotificationAdapter):
    """Apple APNs 기반 알림.

    Note:
        실제 구현은 aioapns 라이브러리 사용 권장.
    """

    def __init__(
        self,
        cert_path: str,
        key_id: str,
        team_id: str,
        bundle_id: str,
        use_sandbox: bool = False,
    ) -> None:
        from aioapns import APNs, NotificationRequest

        self._apns = APNs(
            key=cert_path,
            key_id=key_id,
            team_id=team_id,
            topic=bundle_id,
            use_sandbox=use_sandbox,
        )
        self._NotificationRequest = NotificationRequest

    @property
    def platform(self) -> str:
        return "ios"

    async def send(
        self, token: str, notification: PushNotification,
    ) -> NotificationResult:
        request = self._NotificationRequest(
            device_token=token,
            message={
                "aps": {
                    "alert": {
                        "title": notification.title,
                        "body": notification.body,
                    },
                    "sound": "default",
                },
                **notification.data,
            },
        )
        try:
            await self._apns.send_notification(request)
            return NotificationResult(success=True)
        except Exception as e:
            logger.error("APNs send failed: %s", e)
            return NotificationResult(success=False, error_message=str(e))
```

### 7. `src/notifications/dispatcher.py`

```python
"""플랫폼 통합 디스패처."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.device_token import DeviceToken
from src.notifications.apns import APNsAdapter
from src.notifications.base import NotificationResult, PushNotification
from src.notifications.fcm import FCMAdapter


logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """플랫폼별 알림 통합 발송."""

    def __init__(
        self,
        fcm: FCMAdapter,
        apns: APNsAdapter,
        session: AsyncSession,
    ) -> None:
        self._fcm = fcm
        self._apns = apns
        self._session = session

    async def send_to_user(
        self,
        user_id: uuid.UUID,
        notification: PushNotification,
    ) -> list[NotificationResult]:
        """사용자의 모든 디바이스에 발송."""
        # 사용자의 모든 토큰 조회
        result = await self._session.execute(
            select(DeviceToken).where(DeviceToken.user_id == user_id)
        )
        tokens = result.scalars().all()

        results: list[NotificationResult] = []
        for device in tokens:
            adapter = self._fcm if device.platform == "android" else self._apns
            try:
                res = await adapter.send(device.token, notification)
                results.append(res)
                if not res.success and "unregistered" in (res.error_message or "").lower():
                    # 만료된 토큰 삭제
                    await self._session.delete(device)
            except Exception as e:
                logger.error("Dispatch failed for device %s: %s", device.id, e)
                results.append(NotificationResult(success=False, error_message=str(e)))

        await self._session.commit()
        return results
```

### 8. `src/notifications/templates.py`

```python
"""알림 템플릿 (의료법 표현 가이드 준수)."""

from __future__ import annotations

from src.notifications.base import PushNotification


def activity_reminder(percentage: int) -> PushNotification:
    """활동 리마인더 알림.

    Args:
        percentage: 권장 걸음수 달성률.

    Returns:
        알림 페이로드.
    """
    return PushNotification(
        title="오늘의 활동",
        body=(
            f"오늘 권장 걸음수의 {percentage}%를 채우셨어요. "
            "잠깐 산책 어떠세요?"
        ),
        data={"type": "activity_reminder"},
    )


def supplement_reminder(time_label: str) -> PushNotification:
    """영양제 복용 리마인더."""
    return PushNotification(
        title="영양제 복용 시간",
        body=f"{time_label} 영양제 챙기는 거 잊지 마세요.",
        data={"type": "supplement_reminder"},
    )


def weekly_report() -> PushNotification:
    """주간 리포트 안내."""
    return PushNotification(
        title="이번 주 건강 리포트",
        body="한 주 동안의 영양·활동 분석을 확인해보세요.",
        data={"type": "weekly_report"},
    )
```

### 9. `src/api/v1/feedback.py`

```python
"""피드백 API 라우터."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_session
from src.feedback.service import FeedbackService
from src.models.db.user import User


router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    type: str
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)
    context_id: UUID | None = None
    metadata: dict | None = None


class FeedbackResponse(BaseModel):
    feedback_id: UUID


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FeedbackResponse:
    service = FeedbackService(session)
    try:
        feedback = await service.submit(
            user_id=current_user.id,
            type=request.type,
            rating=request.rating,
            comment=request.comment,
            context_id=request.context_id,
            metadata=request.metadata,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    return FeedbackResponse(feedback_id=feedback.id)
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트

| 모듈 | 테스트 |
|------|------|
| FeedbackService | 12+ (저장·검증·집계) |
| FCMAdapter | 5+ (모킹) |
| APNsAdapter | 5+ |
| Dispatcher | 5+ (만료 토큰 자동 삭제) |
| Templates | 3+ (의료법 표현 검증) |

### Tier 2: 통합 테스트

```python
@pytest.mark.integration
class TestFeedbackIntegration:
    async def test_submit_and_retrieve(self, db_session):
        service = FeedbackService(db_session)
        f = await service.submit(
            user_id=test_user_id,
            type="ocr_accuracy",
            rating=4,
            comment="비타민D만 누락",
        )
        assert f.id is not None

        avg = await service.get_average_rating("ocr_accuracy")
        assert avg == 4.0
```

### Tier 3: E2E 테스트

```python
@pytest.mark.e2e
class TestFeedbackLoopE2E:
    async def test_feedback_after_supplement_register(self, client):
        # 1. 영양제 등록
        supp_response = await client.post(
            "/api/v1/supplements/register", ...
        )
        supplement_id = supp_response.json()["supplement_id"]

        # 2. 피드백 제출
        fb_response = await client.post(
            "/api/v1/feedback",
            json={
                "type": "ocr_accuracy",
                "rating": 4,
                "context_id": supplement_id,
                "comment": "정확함",
            },
        )
        assert fb_response.status_code == 200
```

### Tier 4: 컴플라이언스 테스트

```python
class TestNotificationCompliance:
    """모든 알림 템플릿 의료법 표현 준수."""

    def test_no_forbidden_terms_in_templates(self):
        forbidden = {"진단", "처방", "치료"}
        templates = [
            activity_reminder(50),
            supplement_reminder("아침"),
            weekly_report(),
        ]
        for tmpl in templates:
            for term in forbidden:
                assert term not in tmpl.title
                assert term not in tmpl.body
```

---

## ✅ Definition of Done

- [ ] `src/models/db/feedback.py`, `device_token.py` + 마이그레이션
- [ ] `src/feedback/service.py` — submit, get_average_rating
- [ ] `src/notifications/base.py`, `fcm.py`, `apns.py`, `dispatcher.py`
- [ ] `src/notifications/templates.py` (3+ 템플릿)
- [ ] `src/api/v1/feedback.py` 라우터
- [ ] 모든 함수 docstring + 타입 힌트
- [ ] 단위 테스트 30+
- [ ] 통합 테스트
- [ ] E2E 테스트 (피드백 루프)
- [ ] 컴플라이언스 테스트 (알림 표현 검증)
- [ ] `mypy --strict` 통과

---

## 💡 구현 팁

### FCM/APNs 인증 파일

- FCM: Firebase Console → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성 → JSON 다운로드
- APNs: Apple Developer → Certificates → APNs → .p8 키 + Key ID + Team ID

→ 모두 `.env` 또는 secrets 매니저에. 절대 git에 X.

### 토큰 만료 처리

```python
# Unregistered 에러 시 자동 삭제 → 다음 발송 비용 절감
if "unregistered" in error_message.lower():
    await session.delete(device_token)
```

### 알림 발송 빈도 제한

너무 잦은 알림은 사용자 차단 위험:
- 활동 리마인더: 하루 1회
- 영양제 리마인더: 사용자 설정대로
- 주간 리포트: 주 1회
- 운영 알림: 월 1~2회 최대

### 향후 확장

- 사용자 선호 시간대 학습
- A/B 테스트 (어떤 문구가 더 효과적인지)
- 푸시 + 인앱 메시지 분기

---

## 🚫 이 작업에서 하지 말 것

- ❌ 의료적 알림 ("당뇨가 의심됩니다" 등)
- ❌ 광고성 알림 (영양제 판매 X)
- ❌ 야간 시간(22~07시) 발송
- ❌ 사용자 동의 없는 마케팅 알림

---

## 🔗 관련 문서

- [`/docs/Nutrition-docs/10-compliance-checklist.md`](../10-compliance-checklist.md) — 알림 동의·표현
- 이전: [`16-meal-recognition.md`](./16-meal-recognition.md)
- 다음: [`18-mobile-deficient-screen.md`](./18-mobile-deficient-screen.md)
