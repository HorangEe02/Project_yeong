"""Integration: persist_scope OWN-mode autobegin->commit, proven on a real engine.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md
(§"Step 0 리뷰 후속" LOW(Step 3): the OWN-mode unit test uses a fake that does not
model SQLAlchemy's autobegin state machine, so the claim "the outermost own scope
commits an autobegun transaction" is only asserted against a live engine here.)

ambient-tx Step 3 migrated ``create_food_record_service`` to ``persist_scope``. On
a legacy (un-marked) session — the ``get_async_session`` path — ``persist_scope``
must OWN the transaction: flush + commit the autobegun transaction so the write is
durable and visible to a *different* session, leaving no transaction open. The
unit fake (tests/unit/services/test_food_records.py) records the commit call but
cannot prove real autobegin/commit semantics; this does.

Run gate (skip unless set):
  TEST_DATABASE_URL — a privileged connection (the legacy request role).
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.config import get_settings
from src.db.tx import REQUEST_MANAGED_TX
from src.models.schemas.food_record import FoodRecordCreate
from src.security.auth import AuthenticatedUser
from src.services.food_records import create_food_record_service

ADMIN_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None,
    reason="Set TEST_DATABASE_URL to run the persist_scope OWN-mode live probe.",
)


async def test_own_mode_commits_autobegun_tx_and_is_visible_cross_session() -> None:
    """Legacy session: persist_scope commits the write; another session sees it."""
    assert ADMIN_URL is not None
    settings = get_settings()
    user = AuthenticatedUser(subject=f"own-{uuid.uuid4()}", issuer="test-issuer")
    amount_text = f"own-mode-{uuid.uuid4()}"

    engine = create_async_engine(ADMIN_URL, pool_pre_ping=True)
    created_id: uuid.UUID | None = None
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        # Legacy / un-marked session -> persist_scope OWNS the transaction.
        async with sessionmaker() as session:
            assert REQUEST_MANAGED_TX not in session.info  # OWN mode, not participate
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
            # The outermost own scope committed the autobegun transaction: nothing
            # is left open, and the server-default timestamps were loaded.
            assert session.in_transaction() is False
            assert response.created_at is not None

        # A DIFFERENT session sees the committed row -> a real commit happened,
        # not a mere flush that a rollback could discard.
        async with sessionmaker() as other:
            seen = (
                await other.execute(
                    text("SELECT count(*) FROM food_records WHERE id = :rid"),
                    {"rid": str(created_id)},
                )
            ).scalar_one()
            assert seen == 1
    finally:
        if created_id is not None:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM food_records WHERE id = :rid"),
                    {"rid": str(created_id)},
                )
        await engine.dispose()
