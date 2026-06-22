"""Integration: Stage-2 owner isolation for the migrated food_records write path.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md

ambient-tx Step 3 migrated ``create_food_record_service`` to ``persist_scope``
and the ``/me/food-records`` routes to ``get_rls_context_session``. This proves
the *actual migrated service code* works under the FORCE RLS Stage-2 posture:
connected as the non-superuser ``lemon_app`` role, inside a request-managed
transaction with the owner GUCs set (as ``get_rls_context_session`` does),

  * the participate-mode write (flush, no commit) succeeds against the
    ``lemon_app_owner_rw`` WITH CHECK policy (migration 0041, Type B hashed
    ``owner_subject_hash`` keyed to ``app.current_subject_hash``),
  * a different subject sees none of the owner's rows (USING isolation), and
  * the row persists once the request transaction commits.

The generic seam (audit out-of-band + analysis_results owner write) is proven by
test_ambient_audit_stage2.py; this is the food_records-specific load-bearing
check called for by the plan's VERIFICATION PLAN.

Run gate (skip unless both set):
  TEST_DATABASE_URL          — admin/privileged conn (verify + cleanup)
  TEST_RLS_APP_DATABASE_URL  — lemon_app (NOSUPERUSER, NOBYPASSRLS) request conn
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.config import get_settings
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.models.schemas.food_record import FoodRecordCreate
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.food_records import create_food_record_service

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 food_records owner-isolation proof."
    ),
)


async def test_stage2_food_record_write_is_owner_isolated_and_persists() -> None:
    """The migrated create service writes + isolates + persists under lemon_app."""
    assert ADMIN_URL is not None and APP_URL is not None
    settings = get_settings()
    user = AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    # A unique marker on the row so cleanup/verification never collide with peers.
    amount_text = f"stage2-{uuid.uuid4()}"

    admin = create_async_engine(ADMIN_URL, pool_pre_ping=True)
    app = create_async_engine(APP_URL, pool_pre_ping=True)
    created_id: uuid.UUID | None = None
    try:
        app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
        async with app_sessionmaker() as session:
            transaction = await session.begin()
            # Reproduce get_rls_context_session's setup on the lemon_app session.
            await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
            session.info[REQUEST_MANAGED_TX] = True

            # Guard: the isolation assertions below only mean something if the
            # request role actually enforces RLS. Fail fast (not silently green) if
            # TEST_RLS_APP_DATABASE_URL was pointed at a superuser / BYPASSRLS role.
            rls_bypassed = (
                await session.execute(
                    text(
                        "SELECT rolsuper OR rolbypassrls FROM pg_roles "
                        "WHERE rolname = current_user"
                    )
                )
            ).scalar_one()
            assert rls_bypassed is False, (
                "TEST_RLS_APP_DATABASE_URL must connect as a NOSUPERUSER, NOBYPASSRLS "
                "role (e.g. lemon_app); otherwise RLS is bypassed and this proves nothing."
            )

            # Owner-scoped WRITE through the real migrated service (participate mode:
            # flush only, the WITH CHECK policy must accept owner_subject_hash == GUC).
            response = await create_food_record_service(
                session,
                user,
                settings,
                FoodRecordCreate(
                    recorded_date=date(2026, 5, 31),
                    meal_type="lunch",
                    display_items=["라면"],
                    amount_text=amount_text,
                    source="manual",
                ),
            )
            created_id = response.id
            assert response.created_at is not None  # server defaults loaded via refresh

            # Isolation: the owner sees its just-written row...
            seen_own = (
                await session.execute(
                    text("SELECT count(*) FROM food_records WHERE id = :rid"),
                    {"rid": str(created_id)},
                )
            ).scalar_one()
            assert seen_own == 1
            # ...and a different subject sees none of it (USING row isolation).
            await set_request_rls_context(
                session, subject="iss::someone-else", subject_hash="0" * 64
            )
            seen_other = (
                await session.execute(
                    text("SELECT count(*) FROM food_records WHERE id = :rid"),
                    {"rid": str(created_id)},
                )
            ).scalar_one()
            assert seen_other == 0

            # Commit the request transaction: the owner write persists.
            await transaction.commit()

        async with admin.connect() as conn:
            persisted = (
                await conn.execute(
                    text("SELECT count(*) FROM food_records WHERE id = :rid"),
                    {"rid": str(created_id)},
                )
            ).scalar_one()
            assert persisted == 1
    finally:
        if created_id is not None:
            async with admin.begin() as conn:
                await conn.execute(
                    text("DELETE FROM food_records WHERE id = :rid"),
                    {"rid": str(created_id)},
                )
        await app.dispose()
        await admin.dispose()
