"""SQLAlchemy AsyncEngine + AsyncSession factory.

FastAPI ``Depends(get_session)`` 으로 라우터에 주입된다. 엔진과 세션 팩토리는
process-wide singleton — 첫 호출 시 생성, ``dispose_engine`` 으로 명시 종료.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 7
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """프로세스-wide ``AsyncEngine`` 싱글턴을 반환한다.

    Returns:
        활성 ``AsyncEngine``.
    """
    global _engine  # noqa: PLW0603 — process-wide singleton pattern
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=5,
            future=True,
        )
        logger.info("AsyncEngine created", extra={"url_scheme": "postgres"})
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """``AsyncSession`` 팩토리 싱글턴."""
    global _session_factory  # noqa: PLW0603 — process-wide singleton pattern
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성 — 요청당 ``AsyncSession`` 컨텍스트.

    Yields:
        활성 ``AsyncSession``. 호출처에서 ``commit`` 명시.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    """앱 종료 시 엔진을 닫는다 (``lifespan`` 에서 호출)."""
    global _engine, _session_factory  # noqa: PLW0603 — singleton lifecycle
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("AsyncEngine disposed")
