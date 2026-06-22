"""Database session helper tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import session as session_module
from src.db.dependencies import get_async_session
from src.db.session import (
    dispose_engine,
    get_engine,
    get_learning_sessionmaker,
    get_sessionmaker,
    verify_stage2_privileged_database_urls,
)


class DummySettings:
    """Minimal settings object for database session tests.

    Attributes:
        database_url: SQLAlchemy async database URL.
        audit_database_url: Optional privileged URL for out-of-band audit writes.
        learning_database_url: Optional privileged URL for post-commit learning writes.
    """

    database_url = "postgresql+asyncpg://user:pass@localhost:5432/lemon_test"
    audit_database_url: str | None = None
    learning_database_url: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 10


def get_dummy_settings() -> DummySettings:
    """Return deterministic settings for session tests.

    Returns:
        Dummy settings object with a PostgreSQL async URL.
    """
    return DummySettings()


def _settings_with_learning(learning_url: str | None) -> DummySettings:
    """Return dummy settings overriding only ``learning_database_url``.

    Args:
        learning_url: Value to assign to ``learning_database_url``.

    Returns:
        Dummy settings instance with the requested learning URL.
    """
    settings = DummySettings()
    settings.learning_database_url = learning_url
    return settings


def _settings(
    *,
    database_url: str,
    audit_database_url: str | None = None,
    learning_database_url: str | None = None,
) -> DummySettings:
    """Return dummy settings with the given DB URLs for the startup guard.

    Args:
        database_url: Request-role async database URL.
        audit_database_url: Optional privileged audit URL.
        learning_database_url: Optional privileged learning URL.

    Returns:
        Dummy settings instance with the requested URLs.
    """
    settings = DummySettings()
    settings.database_url = database_url
    settings.audit_database_url = audit_database_url
    settings.learning_database_url = learning_database_url
    return settings


_LEMON_APP_URL = "postgresql+asyncpg://lemon_app:pw@localhost:5432/lemon"
_SUPERUSER_URL = "postgresql+asyncpg://lemon:pw@localhost:5432/lemon"
_AUDIT_URL = "postgresql+asyncpg://lemon_audit:pw@localhost:5432/lemon"
_LEARNING_URL = "postgresql+asyncpg://lemon_learn:pw@localhost:5432/lemon"


def test_guard_noop_when_request_role_is_not_lemon_app() -> None:
    """No requirement when the request role is still the superuser (today)."""
    # Missing privileged URLs is fine because the superuser bypasses RLS.
    verify_stage2_privileged_database_urls(_settings(database_url=_SUPERUSER_URL))


def test_guard_passes_when_lemon_app_with_both_privileged_urls() -> None:
    """lemon_app request role with both distinct privileged URLs is valid."""
    verify_stage2_privileged_database_urls(
        _settings(
            database_url=_LEMON_APP_URL,
            audit_database_url=_AUDIT_URL,
            learning_database_url=_LEARNING_URL,
        )
    )


def test_guard_raises_when_lemon_app_missing_audit_url() -> None:
    """lemon_app without AUDIT_DATABASE_URL fails closed at startup."""
    with pytest.raises(RuntimeError, match="AUDIT_DATABASE_URL"):
        verify_stage2_privileged_database_urls(
            _settings(
                database_url=_LEMON_APP_URL,
                audit_database_url=None,
                learning_database_url=_LEARNING_URL,
            )
        )


def test_guard_raises_when_lemon_app_missing_learning_url() -> None:
    """lemon_app without LEARNING_DATABASE_URL fails closed at startup."""
    with pytest.raises(RuntimeError, match="LEARNING_DATABASE_URL"):
        verify_stage2_privileged_database_urls(
            _settings(
                database_url=_LEMON_APP_URL,
                audit_database_url=_AUDIT_URL,
                learning_database_url=None,
            )
        )


def test_guard_raises_when_privileged_url_equals_database_url() -> None:
    """A privileged URL equal to DATABASE_URL would reuse the request engine."""
    with pytest.raises(RuntimeError, match="AUDIT_DATABASE_URL"):
        verify_stage2_privileged_database_urls(
            _settings(
                database_url=_LEMON_APP_URL,
                audit_database_url=_LEMON_APP_URL,
                learning_database_url=_LEARNING_URL,
            )
        )


def test_guard_raises_when_privileged_url_is_a_distinct_lemon_app_dsn() -> None:
    """A distinct DSN that still connects as lemon_app is not privileged."""
    distinct_lemon_app = "postgresql+asyncpg://lemon_app:pw@otherhost:5432/lemon"
    with pytest.raises(RuntimeError, match="AUDIT_DATABASE_URL"):
        verify_stage2_privileged_database_urls(
            _settings(
                database_url=_LEMON_APP_URL,
                audit_database_url=distinct_lemon_app,
                learning_database_url=_LEARNING_URL,
            )
        )


def _settings_with_pool(pool_size: int, max_overflow: int) -> DummySettings:
    """Return dummy settings overriding the connection-pool sizing.

    Args:
        pool_size: Value for ``db_pool_size``.
        max_overflow: Value for ``db_max_overflow``.

    Returns:
        Dummy settings instance with the requested pool sizing.
    """
    settings = DummySettings()
    settings.db_pool_size = pool_size
    settings.db_max_overflow = max_overflow
    return settings


async def test_get_engine_applies_configured_pool_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The main engine is built with the configured pool sizing."""
    await dispose_engine()
    captured: dict[str, object] = {}
    real_create = session_module.create_async_engine

    def _spy(url: str, **kwargs: object) -> object:
        captured.update(kwargs)
        return real_create(url, **kwargs)

    monkeypatch.setattr("src.db.session.create_async_engine", _spy)
    monkeypatch.setattr("src.db.session.get_settings", lambda: _settings_with_pool(7, 3))

    get_engine()

    assert captured["pool_size"] == 7
    assert captured["max_overflow"] == 3
    assert captured["pool_pre_ping"] is True

    await dispose_engine()


async def test_get_learning_sessionmaker_applies_configured_pool_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The privileged learning engine is built with the configured pool sizing."""
    await dispose_engine()
    captured: dict[str, object] = {}
    real_create = session_module.create_async_engine

    def _spy(url: str, **kwargs: object) -> object:
        captured.update(kwargs)
        return real_create(url, **kwargs)

    settings = DummySettings()
    settings.learning_database_url = "postgresql+asyncpg://learn:pass@localhost:5432/lemon_learn"
    settings.db_pool_size = 9
    settings.db_max_overflow = 2
    monkeypatch.setattr("src.db.session.create_async_engine", _spy)
    monkeypatch.setattr("src.db.session.get_settings", lambda: settings)

    get_learning_sessionmaker()

    assert captured["pool_size"] == 9
    assert captured["max_overflow"] == 2
    assert captured["pool_pre_ping"] is True

    await dispose_engine()


async def test_get_engine_uses_configured_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the engine is created from the application settings."""
    await dispose_engine()
    monkeypatch.setattr("src.db.session.get_settings", get_dummy_settings)

    engine = get_engine()

    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.database == "lemon_test"

    await dispose_engine()


async def test_get_sessionmaker_returns_async_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the session factory creates AsyncSession instances."""
    await dispose_engine()
    monkeypatch.setattr("src.db.session.get_settings", get_dummy_settings)

    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session:
        assert isinstance(session, AsyncSession)

    await dispose_engine()


async def test_get_async_session_dependency_yields_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the FastAPI dependency yields an AsyncSession."""
    await dispose_engine()
    monkeypatch.setattr("src.db.session.get_settings", get_dummy_settings)

    async for session in get_async_session():
        assert isinstance(session, AsyncSession)
        break

    await dispose_engine()


async def test_get_learning_sessionmaker_reuses_main_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset LEARNING_DATABASE_URL reuses the main factory (today's superuser path)."""
    await dispose_engine()
    monkeypatch.setattr("src.db.session.get_settings", get_dummy_settings)

    assert get_learning_sessionmaker() is get_sessionmaker()

    await dispose_engine()


async def test_get_learning_sessionmaker_reuses_main_when_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LEARNING_DATABASE_URL equal to DATABASE_URL reuses the main factory."""
    await dispose_engine()
    monkeypatch.setattr(
        "src.db.session.get_settings",
        lambda: _settings_with_learning(DummySettings.database_url),
    )

    assert get_learning_sessionmaker() is get_sessionmaker()

    await dispose_engine()


async def test_get_learning_sessionmaker_uses_privileged_engine_when_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A distinct LEARNING_DATABASE_URL builds a separate privileged engine."""
    await dispose_engine()
    learning_url = "postgresql+asyncpg://learn:pass@localhost:5432/lemon_learn"
    monkeypatch.setattr(
        "src.db.session.get_settings",
        lambda: _settings_with_learning(learning_url),
    )

    learning_sessionmaker = get_learning_sessionmaker()

    assert learning_sessionmaker is not get_sessionmaker()
    assert session_module._state.learning_engine is not None
    assert session_module._state.learning_engine.url.database == "lemon_learn"

    await dispose_engine()


async def test_get_learning_sessionmaker_caches_privileged_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated calls reuse the cached privileged engine/factory (no per-call churn)."""
    await dispose_engine()
    learning_url = "postgresql+asyncpg://learn:pass@localhost:5432/lemon_learn"
    monkeypatch.setattr(
        "src.db.session.get_settings",
        lambda: _settings_with_learning(learning_url),
    )

    first = get_learning_sessionmaker()
    cached_engine = session_module._state.learning_engine
    second = get_learning_sessionmaker()

    assert first is second
    assert session_module._state.learning_engine is cached_engine

    await dispose_engine()


async def test_dispose_engine_resets_learning_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dispose_engine clears the cached learning engine and factory."""
    await dispose_engine()
    learning_url = "postgresql+asyncpg://learn:pass@localhost:5432/lemon_learn"
    monkeypatch.setattr(
        "src.db.session.get_settings",
        lambda: _settings_with_learning(learning_url),
    )

    get_learning_sessionmaker()
    assert session_module._state.learning_engine is not None

    await dispose_engine()

    assert session_module._state.learning_engine is None
    assert session_module._state.learning_sessionmaker is None
