"""Tests for the Firebase -> Supabase/PostgreSQL DB settings layer."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.db import get_database_settings, get_database_url, is_postgres_enabled


def test_database_settings_default_to_sqlite() -> None:
    """Default runtime must keep existing SQLite behavior."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("APP_DB_BACKEND", None)
        os.environ.pop("DATABASE_URL", None)
        settings = get_database_settings()
        assert settings.backend == "sqlite"
        assert settings.database_url.startswith("sqlite:///")
        assert is_postgres_enabled() is False


def test_database_settings_normalize_supabase_postgres_url() -> None:
    """Postgres URLs without DBAPI are normalized to psycopg."""
    with patch.dict(
        os.environ,
        {
            "APP_DB_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:pass@example.supabase.co:5432/postgres",
        },
        clear=False,
    ):
        settings = get_database_settings()
        assert settings.backend == "postgres"
        assert settings.database_url.startswith("postgresql+psycopg://")
        assert is_postgres_enabled() is True


def test_database_settings_reject_unknown_backend() -> None:
    """Invalid APP_DB_BACKEND values fail closed."""
    with patch.dict(os.environ, {"APP_DB_BACKEND": "firestore"}, clear=False):
        with pytest.raises(ValueError):
            get_database_settings()


def test_get_database_url_required_raises_for_empty_postgres_url() -> None:
    """Postgres mode requires an explicit DATABASE_URL."""
    with patch.dict(os.environ, {"APP_DB_BACKEND": "postgres", "DATABASE_URL": ""}, clear=False):
        with pytest.raises(RuntimeError):
            get_database_url(required=True)


class _FakeEngine:
    """Stand-in for a SQLAlchemy engine (avoids needing a real DBAPI driver)."""

    def __init__(self, url: str, **kwargs: object) -> None:
        self.url = url
        self.kwargs = kwargs


def _patch_create_engine(monkeypatch) -> None:
    import sqlalchemy

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda url, **kw: _FakeEngine(url, **kw))


def test_create_engine_caches_one_bounded_postgres_engine_per_url(monkeypatch) -> None:
    """Repeated calls reuse a single bounded engine — guards the connection leak
    that exhausted the Supabase session pooler (EMAXCONNSESSION)."""
    import core.db as db

    db._PG_ENGINE_CACHE.clear()
    _patch_create_engine(monkeypatch)
    try:
        with patch.dict(
            os.environ,
            {"APP_DB_BACKEND": "postgres", "DATABASE_URL": "postgresql://u:p@h:5432/postgres"},
            clear=False,
        ):
            first = db.create_sqlalchemy_engine()
            second = db.create_sqlalchemy_engine()

        assert first is second  # cached → no new connection pool per call
        assert first.kwargs.get("pool_pre_ping") is True
        assert first.kwargs.get("pool_size") == 2
        assert first.kwargs.get("max_overflow") == 3
        assert first.kwargs.get("pool_recycle") == 1800
    finally:
        db._PG_ENGINE_CACHE.clear()


def test_create_engine_sqlite_stays_per_call_and_untuned(monkeypatch) -> None:
    """SQLite keeps the previous per-call behaviour with no Postgres pool args."""
    import core.db as db

    db._PG_ENGINE_CACHE.clear()
    _patch_create_engine(monkeypatch)
    with patch.dict(
        os.environ,
        {"APP_DB_BACKEND": "sqlite", "DATABASE_URL": "sqlite:///tmp/test_db_config.db"},
        clear=False,
    ):
        first = db.create_sqlalchemy_engine()
        second = db.create_sqlalchemy_engine()

    assert first is not second  # not cached
    assert "pool_size" not in first.kwargs  # no Postgres pool tuning leaked onto SQLite
