"""Integration: Stage-2 owner isolation for the ambient-tx Step 4 write paths.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md

ambient-tx Step 4 migrated the user_medications, reminder_preferences (notifications),
body_profile_snapshots / health_metric_samples (health_profile) and
health_sync_batches / health_daily_summaries (health_sync) write services to
``persist_scope`` and their routes to ``get_rls_context_session``. This proves the
*actual migrated service code* works under the FORCE RLS Stage-2 posture: connected
as the non-superuser ``lemon_app`` role, inside a request-managed transaction with
the owner GUCs set (as ``get_rls_context_session`` does),

  * the participate-mode write (flush, no commit) succeeds against the owner
    WITH CHECK policy (hashed ``owner_subject_hash`` = ``app.current_subject_hash``
    for user_medications [0041]; plaintext ``owner_subject`` =
    ``app.current_subject`` for reminder_preferences [0041] and the health tables
    [0023b]),
  * a different subject sees none of the owner's rows (USING isolation), and
  * the row persists once the request transaction commits.

The generic seam (audit out-of-band + analysis_results owner write) is proven by
test_ambient_audit_stage2.py; food_records by test_food_records_stage2.py. This is
the Step 4-specific load-bearing check called for by the plan's VERIFICATION PLAN.

Run gate (skip unless both set):
  TEST_DATABASE_URL          — admin/privileged conn (verify + cleanup)
  TEST_RLS_APP_DATABASE_URL  — lemon_app (NOSUPERUSER, NOBYPASSRLS) request conn
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.api.v1.notifications import create_reminder_preference_service
from src.config import get_settings
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.models.schemas.health import (
    BodyProfileSnapshotCreate,
    HealthMetricSampleCreate,
    HealthSyncRequest,
)
from src.models.schemas.notification import ReminderCategory, ReminderPreferenceCreate
from src.models.schemas.user_medication import UserMedicationCreate, UserMedicationUpdate
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.health_profile import create_body_profile_snapshot, create_health_metric_sample
from src.services.health_sync import sync_health_daily_aggregates
from src.services.user_medications import (
    create_user_medication_service,
    update_user_medication_service,
)

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Step 4 owner-isolation proofs."
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


async def _count_by_id(session: AsyncSession, table: str, row_id: uuid.UUID) -> int:
    """Return the count of rows visible to the current GUC subject for ``id``.

    ``table`` is a hardcoded constant from this module, never user input.

    Note: the ``WHERE id = :rid`` filter matches the row unconditionally without
    RLS, so a count of 0 under a *different* GUC subject proves the USING policy
    (not the filter) hid it — it would be 1 if RLS were bypassed.
    """
    return (
        await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE id = :rid"),
            {"rid": str(row_id)},
        )
    ).scalar_one()


async def _count_by_owner(session: AsyncSession, table: str, owner: str) -> int:
    """Return ``owner``'s rows visible to the current GUC subject.

    For child tables without a single ``id`` column (e.g. the composite-PK
    ``health_daily_summaries``). Like ``_count_by_id``, the explicit owner filter
    matches without RLS, so 0 under a different subject proves USING isolation.
    ``table`` is a hardcoded constant from this module, never user input.
    """
    return (
        await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE owner_subject = :owner"),
            {"owner": owner},
        )
    ).scalar_one()


async def _prove_owner_isolated_and_persists(
    *,
    owner: str,
    owner_hash: str,
    table: str,
    write: Callable[[AsyncSession], Awaitable[uuid.UUID]],
    child_table: str | None = None,
) -> None:
    """Drive one migrated write service under lemon_app and assert RLS behavior.

    Args:
        owner: Issuer-qualified plaintext owner subject (``app.current_subject``).
        owner_hash: HMAC owner-subject hash (``app.current_subject_hash``).
        table: Owner table whose ``id`` column gates the isolation/persistence check.
        write: Coroutine that performs the owner write and returns the new row id.
        child_table: Optional same-transaction child table (keyed on ``owner_subject``,
            e.g. ``health_daily_summaries``) to also prove isolated + persisted + cleaned.
    """
    created_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                # Reproduce get_rls_context_session's setup on the lemon_app session.
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                # Owner-scoped WRITE through the real migrated service (participate
                # mode: flush only; the WITH CHECK policy must accept the owner GUC).
                created_id = await write(session)

                # Isolation: the owner sees its just-written row(s)...
                assert await _count_by_id(session, table, created_id) == 1
                if child_table is not None:
                    assert await _count_by_owner(session, child_table, owner) >= 1
                # ...and a different subject sees none of it (USING row isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_by_id(session, table, created_id) == 0
                if child_table is not None:
                    assert await _count_by_owner(session, child_table, owner) == 0

                # Commit the request transaction: the owner write persists.
                await transaction.commit()

            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text(f"SELECT count(*) FROM {table} WHERE id = :rid"),
                        {"rid": str(created_id)},
                    )
                ).scalar_one()
                assert persisted == 1
                if child_table is not None:
                    persisted_child = (
                        await conn.execute(
                            text(
                                f"SELECT count(*) FROM {child_table} WHERE owner_subject = :owner"
                            ),
                            {"owner": owner},
                        )
                    ).scalar_one()
                    assert persisted_child >= 1
        finally:
            if created_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text(f"DELETE FROM {table} WHERE id = :rid"),
                        {"rid": str(created_id)},
                    )
                    if child_table is not None:
                        await conn.execute(
                            text(f"DELETE FROM {child_table} WHERE owner_subject = :owner"),
                            {"owner": owner},
                        )


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


async def test_stage2_user_medication_write_is_owner_isolated_and_persists() -> None:
    """Hashed owner_subject_hash policy (0041) accepts the participate-mode write."""
    settings = get_settings()
    user = _user()

    async def _write(session: AsyncSession) -> uuid.UUID:
        response = await create_user_medication_service(
            session,
            user,
            settings,
            UserMedicationCreate(
                display_name="amlodipine",
                medication_class="calcium_channel_blocker",
                condition_tags=["hypertension"],
            ),
        )
        return response.id

    await _prove_owner_isolated_and_persists(
        owner=build_owner_subject(user),
        owner_hash=hash_actor_subject(user, settings),
        table="user_medications",
        write=_write,
    )


async def test_stage2_reminder_preference_write_is_owner_isolated_and_persists() -> None:
    """Plaintext owner_subject policy (0041) accepts the participate-mode write."""
    settings = get_settings()
    user = _user()

    async def _write(session: AsyncSession) -> uuid.UUID:
        response = await create_reminder_preference_service(
            session,
            user,
            ReminderPreferenceCreate(
                category=ReminderCategory.SUPPLEMENT_REMINDER,
                time_of_day="09:00",
                timezone="Asia/Seoul",
                message="기록 시간을 확인해 주세요.",
            ),
        )
        return response.id

    await _prove_owner_isolated_and_persists(
        owner=build_owner_subject(user),
        owner_hash=hash_actor_subject(user, settings),
        table="reminder_preferences",
        write=_write,
    )


async def test_stage2_body_profile_snapshot_write_is_owner_isolated_and_persists() -> None:
    """Plaintext owner_subject policy (0023b) accepts the participate-mode write."""
    settings = get_settings()
    user = _user()

    async def _write(session: AsyncSession) -> uuid.UUID:
        snapshot = await create_body_profile_snapshot(
            session,
            user,
            BodyProfileSnapshotCreate(
                source="manual",
                height_cm=Decimal("172.5"),
                weight_kg=Decimal("68.4"),
            ),
        )
        return snapshot.id

    await _prove_owner_isolated_and_persists(
        owner=build_owner_subject(user),
        owner_hash=hash_actor_subject(user, settings),
        table="body_profile_snapshots",
        write=_write,
    )


async def test_stage2_health_metric_sample_write_is_owner_isolated_and_persists() -> None:
    """Plaintext owner_subject policy (0023b) accepts the participate-mode write."""
    settings = get_settings()
    user = _user()

    async def _write(session: AsyncSession) -> uuid.UUID:
        sample = await create_health_metric_sample(
            session,
            user,
            HealthMetricSampleCreate(
                metric_type="weight_kg",
                measured_at=datetime(2026, 5, 27, 9, 30, tzinfo=UTC),
                value_numeric=Decimal("68.4000"),
                unit="kg",
                source_platform="manual",
            ),
        )
        return sample.id

    await _prove_owner_isolated_and_persists(
        owner=build_owner_subject(user),
        owner_hash=hash_actor_subject(user, settings),
        table="health_metric_samples",
        write=_write,
    )


async def test_stage2_health_sync_batch_write_is_owner_isolated_and_persists() -> None:
    """Plaintext owner_subject policy (0023b) accepts the multi-row sync write."""
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)

    async def _write(session: AsyncSession) -> uuid.UUID:
        result = await sync_health_daily_aggregates(
            session,
            user,
            HealthSyncRequest.model_validate(
                {
                    "client_batch_id": f"stage2-{uuid.uuid4()}",
                    "records": [
                        {
                            "measured_date": "2026-05-12",
                            "source_platform": "ios_healthkit",
                            "steps": 7200,
                        }
                    ],
                }
            ),
        )
        return result.batch.id

    await _prove_owner_isolated_and_persists(
        owner=owner,
        owner_hash=hash_actor_subject(user, settings),
        table="health_sync_batches",
        write=_write,
        child_table="health_daily_summaries",
    )


async def test_stage2_user_medication_update_under_rls_is_owner_isolated_and_persists() -> None:
    """UPDATE under FORCE RLS: owner update passes USING+WITH CHECK; others can't touch it.

    The create-path proofs cover INSERT WITH CHECK; an UPDATE is additionally gated by
    the policy USING clause (the row must be visible to update it). This drives the real
    migrated ``update_user_medication_service`` in participate mode for the owner, then
    proves a different subject's raw UPDATE matches 0 rows (USING hides it) — which would
    silently corrupt the owner row if RLS were bypassed.
    """
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    created_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                created = await create_user_medication_service(
                    session,
                    user,
                    settings,
                    UserMedicationCreate(
                        display_name="amlodipine",
                        medication_class="calcium_channel_blocker",
                        condition_tags=["hypertension"],
                    ),
                )
                created_id = created.id

                # Owner UPDATE-under-USING through the real migrated service (participate
                # mode): the policy USING must see the row and WITH CHECK accept the result.
                updated = await update_user_medication_service(
                    session,
                    user,
                    settings,
                    created_id,
                    UserMedicationUpdate(display_name="losartan", medication_class="arb"),
                )
                assert updated.display_name == "losartan"

                # A different subject cannot UPDATE the owner's row: USING hides it, so the
                # statement matches 0 rows (it would match 1 if RLS were bypassed).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                blocked = await session.execute(
                    text("UPDATE user_medications SET display_name = 'hacked' WHERE id = :rid"),
                    {"rid": str(created_id)},
                )
                assert blocked.rowcount == 0

                await transaction.commit()

            async with admin.connect() as conn:
                persisted_name = (
                    await conn.execute(
                        text("SELECT display_name FROM user_medications WHERE id = :rid"),
                        {"rid": str(created_id)},
                    )
                ).scalar_one()
                # Owner's update persisted; the other subject's write never landed.
                assert persisted_name == "losartan"
        finally:
            if created_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM user_medications WHERE id = :rid"),
                        {"rid": str(created_id)},
                    )
