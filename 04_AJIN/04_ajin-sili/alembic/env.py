"""Alembic environment for the AJIN application database."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from core.db import get_database_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _database_url() -> str:
    """Return the effective SQLAlchemy URL for Alembic.

    Returns:
        str: Database URL from ``core.db`` settings.

    Raises:
        RuntimeError: If no database URL is configured.
    """
    settings = get_database_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for Alembic migrations")
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in offline SQL generation mode."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
    from sqlalchemy import create_engine, pool

    connectable = create_engine(_database_url(), poolclass=pool.NullPool, future=True)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
