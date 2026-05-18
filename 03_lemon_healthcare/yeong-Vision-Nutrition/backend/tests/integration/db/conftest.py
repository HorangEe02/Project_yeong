"""DB 통합 테스트 픽스처 — testcontainers Postgres 16.

Docker daemon 필요. 기본 ``pytest`` 실행에서는 ``-m "not integration"`` 으로
제외된다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 9
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 모델 import — Base.metadata 에 등록되도록
from src.models.db import audit, consent, supplement, user  # noqa: F401
from src.models.db.base import Base
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """testcontainers Postgres 16 인스턴스를 띄우고 asyncpg URL 반환."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
        yield url


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    """세션 스코프 ``AsyncEngine`` + ``Base.metadata.create_all``."""
    eng = create_async_engine(postgres_url, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """함수 스코프 ``AsyncSession`` — 종료 시 rollback."""
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        try:
            yield s
        finally:
            await s.rollback()
