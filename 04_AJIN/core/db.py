"""Application database connection helpers.

Firebase -> Supabase/PostgreSQL 전환의 공통 DB 진입점이다. 기존 기능별
SQLite 경로를 한 번에 제거하지 않고, 새 Postgres 저장소를 추가할 때 같은
설정과 SQLAlchemy engine 생성 규칙을 재사용하도록 분리한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseSettings:
    """Application database settings.

    Attributes:
        backend: Active database backend, either ``sqlite`` or ``postgres``.
        database_url: SQLAlchemy-compatible database URL.
    """

    backend: str
    database_url: str


def _normalize_postgres_url(url: str) -> str:
    """Normalize a Postgres URL for the installed psycopg driver.

    Args:
        url: Raw database URL from ``DATABASE_URL``.

    Returns:
        SQLAlchemy URL using the ``postgresql+psycopg`` dialect when the input
        does not specify a concrete DBAPI driver.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def get_database_settings() -> DatabaseSettings:
    """Load database settings from environment variables.

    Returns:
        DatabaseSettings: Runtime DB backend and SQLAlchemy URL.

    Raises:
        ValueError: If ``APP_DB_BACKEND`` is not ``sqlite`` or ``postgres``.
    """
    backend = os.getenv("APP_DB_BACKEND", "sqlite").strip().lower() or "sqlite"
    if backend not in {"sqlite", "postgres"}:
        raise ValueError("APP_DB_BACKEND must be 'sqlite' or 'postgres'")

    raw_url = os.getenv("DATABASE_URL", "").strip()
    if backend == "postgres":
        database_url = _normalize_postgres_url(raw_url)
    else:
        database_url = raw_url or "sqlite:///data/ajin_app.db"

    return DatabaseSettings(backend=backend, database_url=database_url)


def is_postgres_enabled() -> bool:
    """Return whether the runtime DB backend is Postgres.

    Returns:
        bool: True when ``APP_DB_BACKEND=postgres``.
    """
    return get_database_settings().backend == "postgres"


def get_database_url(required: bool = False) -> str:
    """Return the configured database URL.

    Args:
        required: Raise when the URL is empty.

    Returns:
        str: SQLAlchemy-compatible database URL.

    Raises:
        RuntimeError: If ``required`` is true and no URL is configured.
    """
    settings = get_database_settings()
    if required and not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    return settings.database_url


# Postgres engine 캐시 — URL(+echo) 기준 프로세스당 1개 engine 재사용.
# 매 호출마다 새 engine 을 만들면 engine 마다 별도 connection pool 이 열리고
# 회수되지 않아, Supabase Supavisor session-mode pooler(pool_size 30)가
# 즉시 고갈된다 (FATAL EMAXCONNSESSION). 같은 URL 은 bounded engine 하나를
# 공유해 connection 누수를 막는다. SQLite 경로는 동작 변화 없이 그대로 둔다.
_PG_ENGINE_CACHE: dict[str, object] = {}


def create_sqlalchemy_engine(echo: bool = False):
    """Create (or reuse) a SQLAlchemy engine from runtime settings.

    For Postgres a single bounded, pre-pinged engine is cached per database
    URL so repeated calls do not leak connection pools into the Supabase
    pooler. SQLite keeps the previous per-call behaviour unchanged.

    Args:
        echo: Enable SQLAlchemy SQL echo logging for local debugging.

    Returns:
        sqlalchemy.engine.Engine: Configured SQLAlchemy engine.

    Raises:
        RuntimeError: If SQLAlchemy is not installed or ``DATABASE_URL`` is
            missing while ``APP_DB_BACKEND=postgres``.
    """
    settings = get_database_settings()
    if settings.backend == "postgres" and not settings.database_url:
        raise RuntimeError("DATABASE_URL is required when APP_DB_BACKEND=postgres")
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError("SQLAlchemy is required for the application DB engine") from exc

    url = settings.database_url

    # SQLite(및 비 Postgres) — 기존 동작 유지: 호출마다 새 engine.
    # (APP_DB_BACKEND=postgres + sqlite:// URL 인 테스트 경로도 여기로 떨어진다.)
    if not url.startswith("postgresql"):
        return create_engine(url, echo=echo, future=True)

    cache_key = f"{url}|echo={int(echo)}"
    cached = _PG_ENGINE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # Bounded pool + pre-ping — Supabase session pooler(최대 30)와 공존하도록
    # 프로세스당 connection 을 작게 유지하고, 죽은 connection 은 재사용 전 검증한다.
    engine = create_engine(
        url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
        pool_recycle=1800,
        pool_timeout=10,
    )
    _PG_ENGINE_CACHE[cache_key] = engine
    return engine
