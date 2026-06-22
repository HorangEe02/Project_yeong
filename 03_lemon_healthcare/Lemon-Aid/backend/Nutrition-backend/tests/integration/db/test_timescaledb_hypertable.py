"""Verify the TimescaleDB hypertable conversion for health_daily_summaries.

This test exercises PR-P (alembic 0008): the migration calls
``create_hypertable`` only when the connected PostgreSQL instance has
the ``timescaledb`` extension available. The check therefore requires a
real TimescaleDB-aware database — the default ``pytest`` invocation
excludes the ``timescaledb`` marker so CI / dev runs are unaffected.

Run this suite explicitly against a TimescaleDB instance::

    TEST_DATABASE_URL=postgresql+asyncpg://lemon:secret@db:5432/lemon \
        pytest -m timescaledb \
        Nutrition-backend/tests/integration/db/test_timescaledb_hypertable.py
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.timescaledb,
    pytest.mark.skipif(
        TEST_DATABASE_URL is None,
        reason="Set TEST_DATABASE_URL to a TimescaleDB-aware Postgres URL.",
    ),
]


async def test_health_daily_summaries_is_registered_as_hypertable() -> None:
    """Verify migration 0008 registered the table as a TimescaleDB hypertable."""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session:
            result = await session.execute(
                text(
                    "SELECT count(*) FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name = 'health_daily_summaries'"
                )
            )
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()


async def test_timescaledb_extension_is_installed() -> None:
    """Verify CREATE EXTENSION ran during migration 0008."""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session:
            result = await session.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'timescaledb'")
            )
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()
