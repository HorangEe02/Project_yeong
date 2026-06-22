"""Integration: Stage-2 owner isolation for the ambient-tx Step 6 meal-image write paths.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md
           outputs/todo-list/2026-06-14/2026-06-14-step6-design.md

ambient-tx Step 6 migrated ``create_meal_image_analysis_preview`` /
``confirm_meal_record_from_preview`` to ``persist_scope`` and the meal write routes
(``POST /meals/analyze-image`` / ``POST /meals/{id}/confirm``) to
``get_rls_context_session`` (dropping the consent-read closer; audit stays route-level via
``record_sensitive_audit_event``). This proves the *actual migrated service code* works
under the FORCE RLS Stage-2 posture, connected as the non-superuser ``lemon_app`` role
inside a request-managed transaction with the owner GUCs set:

  * the participate-mode preview INSERTs into the plaintext-owner ``meal_records`` and
    ``food_image_analysis_runs`` tables (0023b Type A, keyed to ``app.current_subject``)
    succeed and isolate,
  * the participate-mode confirm — ``meal_records`` UPDATE + ``meal_food_items`` child
    INSERT (0023b Type C → ``meal_records`` via ``meal_id``) — passes USING + WITH CHECK in
    one flush-only transaction,
  * a different subject sees none of the rows (USING isolation), and
  * every row persists once the request transaction commits.

Run gate (skip unless both set):
  TEST_DATABASE_URL          — admin/privileged conn (verify + cleanup)
  TEST_RLS_APP_DATABASE_URL  — lemon_app (NOSUPERUSER, NOBYPASSRLS) request conn
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.config import get_settings
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.models.schemas.meal import MealConfirmationRequest, MealFoodItemInput, MealType
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.meal_image_analysis import (
    ValidatedMealImage,
    confirm_meal_record_from_preview,
    create_meal_image_analysis_preview,
)

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Step 6 meal-image owner-isolation proofs."
    ),
)


@asynccontextmanager
async def _stage2_engines() -> AsyncIterator[tuple[AsyncEngine, AsyncEngine]]:
    """Yield (admin, lemon_app) engines and dispose both afterwards."""
    assert ADMIN_URL is not None and APP_URL is not None
    admin = create_async_engine(ADMIN_URL, pool_pre_ping=True)
    app = create_async_engine(APP_URL, pool_pre_ping=True)
    try:
        yield admin, app
    finally:
        await app.dispose()
        await admin.dispose()


async def _assert_request_role_enforces_rls(session: AsyncSession) -> None:
    """Fail fast if the request role bypasses RLS (would make isolation vacuous)."""
    rls_bypassed = (
        await session.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
    ).scalar_one()
    assert rls_bypassed is False, (
        "TEST_RLS_APP_DATABASE_URL must connect as a NOSUPERUSER, NOBYPASSRLS role "
        "(e.g. lemon_app); otherwise RLS is bypassed and this proves nothing."
    )


async def _count_where(session: AsyncSession, table: str, column: str, value: uuid.UUID) -> int:
    """Count rows visible to the current GUC subject where ``column`` matches ``value``."""
    return (
        await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column} = :val"),
            {"val": str(value)},
        )
    ).scalar_one()


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _image_metadata() -> ValidatedMealImage:
    return ValidatedMealImage(
        sha256="a" * 64,
        mime_type="image/png",
        size_bytes=128,
        width=3,
        height=2,
        normalized_bytes=_png_bytes(),
    )


def _confirm_request(run_id: uuid.UUID) -> MealConfirmationRequest:
    return MealConfirmationRequest(
        analysis_id=run_id,
        meal_type=MealType.LUNCH,
        food_items=[
            MealFoodItemInput(
                display_name="비빔밥",
                portion_amount=1,
                portion_unit="bowl",
                kcal=520,
                confidence=0.88,
                source="vision",
            )
        ],
        user_confirmed=True,
    )


async def test_stage2_meal_preview_and_confirm_are_owner_isolated_and_persist() -> None:
    """Type-A meal/run policies + Type-C food-item child policy accept the participate writes."""
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    meal_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                preview = await create_meal_image_analysis_preview(
                    session=session,
                    user=user,
                    image_metadata=_image_metadata(),
                    meal_type=MealType.LUNCH,
                    eaten_at=None,
                    client_request_id=None,
                    settings=settings,
                )
                meal_id = preview.meal_record.id
                run_id = preview.analysis_run.id

                await confirm_meal_record_from_preview(
                    session=session,
                    user=user,
                    meal_id=meal_id,
                    request=_confirm_request(run_id),
                )

                # Owner sees the meal, its analysis run, and the confirmed food item.
                assert await _count_where(session, "meal_records", "id", meal_id) == 1
                assert (
                    await _count_where(session, "food_image_analysis_runs", "meal_id", meal_id) == 1
                )
                assert await _count_where(session, "meal_food_items", "meal_id", meal_id) == 1

                # A different subject sees none of them (parent USING + child join isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_where(session, "meal_records", "id", meal_id) == 0
                assert (
                    await _count_where(session, "food_image_analysis_runs", "meal_id", meal_id) == 0
                )
                assert await _count_where(session, "meal_food_items", "meal_id", meal_id) == 0

                await transaction.commit()

            async with admin.connect() as conn:
                for table, column in (
                    ("meal_records", "id"),
                    ("food_image_analysis_runs", "meal_id"),
                    ("meal_food_items", "meal_id"),
                ):
                    persisted = (
                        await conn.execute(
                            text(f"SELECT count(*) FROM {table} WHERE {column} = :rid"),
                            {"rid": str(meal_id)},
                        )
                    ).scalar_one()
                    assert persisted == 1, f"{table} did not persist"
        finally:
            if meal_id is not None:
                async with admin.begin() as conn:
                    # FK-safe order: children before the parent meal record.
                    await conn.execute(
                        text("DELETE FROM meal_food_items WHERE meal_id = :rid"),
                        {"rid": str(meal_id)},
                    )
                    await conn.execute(
                        text("DELETE FROM food_image_analysis_runs WHERE meal_id = :rid"),
                        {"rid": str(meal_id)},
                    )
                    await conn.execute(
                        text("DELETE FROM meal_records WHERE id = :rid"),
                        {"rid": str(meal_id)},
                    )
