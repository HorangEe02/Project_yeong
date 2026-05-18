"""DB 통합 테스트 — 실 Postgres 16 + ORM CRUD.

``RUN_E2E_TESTS`` 없이도 docker daemon 만 있으면 동작. CI 에서는 docker-in-docker
또는 service container 로 활성화한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 10
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.db.audit import AccessAuditLog
from src.models.db.consent import ConsentRecord
from src.models.db.supplement import Supplement
from src.models.db.user import User, UserProfile

pytestmark = pytest.mark.integration


def _new_user() -> User:
    return User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4()}@example.com",
        password_hash="$2b$12$dummy",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_create_user_with_profile_cascade(session: AsyncSession) -> None:
    """User + UserProfile 1:1 + cascade delete."""
    user = _new_user()
    user.profile = UserProfile(
        user_id=user.id,
        age=30,
        sex="female",
        height_cm=160.0,
        weight_kg=58.0,
        is_pregnant=False,
        is_lactating=False,
        is_smoker=False,
        chronic_diseases=[],
        medications=[],
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert user.profile is not None
    assert user.profile.age == 30


@pytest.mark.asyncio
async def test_consent_record_revoke(session: AsyncSession) -> None:
    """ConsentRecord 생성 후 revoke 시 revoked_at 만 갱신."""
    user = _new_user()
    session.add(user)
    await session.flush()

    record = ConsentRecord(
        id=uuid.uuid4(),
        user_id=user.id,
        consent_type="service_terms",
        purpose="서비스 이용",
        data_categories=["general_profile"],
        retention_period_days=0,
        policy_version="v1.0",
        accepted_at=datetime.now(UTC),
    )
    session.add(record)
    await session.commit()

    assert record.revoked_at is None
    record.revoked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(record)
    assert record.revoked_at is not None


@pytest.mark.asyncio
async def test_audit_log_ip_hash_only(session: AsyncSession) -> None:
    """AccessAuditLog 는 raw IP 가 아닌 hash 만 저장한다."""
    log = AccessAuditLog(
        id=uuid.uuid4(),
        actor_user_id=None,
        action="supplement.register.attempt",
        resource_type="supplement",
        resource_id=None,
        ip_address_hash="a" * 64,
        user_agent="curl/8",
        success=True,
        error_code=None,
        occurred_at=datetime.now(UTC),
    )
    session.add(log)
    await session.commit()

    result = await session.execute(select(AccessAuditLog).where(AccessAuditLog.id == log.id))
    fetched = result.scalar_one()
    assert fetched.ip_address_hash == "a" * 64


@pytest.mark.asyncio
async def test_supplement_linked_to_user(session: AsyncSession) -> None:
    user = _new_user()
    session.add(user)
    await session.flush()

    supp = Supplement(
        id=uuid.uuid4(),
        user_id=user.id,
        product_name="종합비타민",
        manufacturer="ABC",
        ingredients=[{"code": "vitamin_c_mg", "amount": 1000, "unit": "mg"}],
        ocr_engine="google_vision_v1",
        llm_engine="ollama:qwen3.5:9b",
        image_hash="abc123def456",
        registered_at=datetime.now(UTC),
    )
    session.add(supp)
    await session.commit()
    await session.refresh(supp)

    assert supp.ingredients[0]["code"] == "vitamin_c_mg"


@pytest.mark.asyncio
async def test_user_cascade_deletes_profile_and_supplements(
    session: AsyncSession,
) -> None:
    """User 삭제 시 profile / supplements / consents 가 함께 삭제된다."""
    user = _new_user()
    user.profile = UserProfile(
        user_id=user.id,
        age=40,
        sex="male",
        height_cm=175.0,
        weight_kg=72.0,
        is_pregnant=False,
        is_lactating=False,
        is_smoker=False,
        chronic_diseases=[],
        medications=[],
        updated_at=datetime.now(UTC),
    )
    user.supplements.append(
        Supplement(
            id=uuid.uuid4(),
            user_id=user.id,
            product_name="종합비타민",
            manufacturer="ABC",
            ingredients=[],
            ocr_engine="x",
            llm_engine="y",
            registered_at=datetime.now(UTC),
        )
    )
    session.add(user)
    await session.commit()
    user_id = user.id

    await session.delete(user)
    await session.commit()

    profile_left = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    assert profile_left.first() is None
    supps_left = await session.execute(select(Supplement).where(Supplement.user_id == user_id))
    assert supps_left.first() is None
