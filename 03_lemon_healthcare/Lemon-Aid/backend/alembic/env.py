"""Alembic migration environment."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from src.config import get_settings
from src.models.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Return the application database URL for Alembic.

    Returns:
        Configured SQLAlchemy database URL.
    """
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection.

    Returns:
        None.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with an existing synchronous Alembic connection.

    Args:
        connection: Synchronous connection adapted from SQLAlchemy AsyncConnection.

    Returns:
        None.
    """
    _ensure_revision_id_capacity(connection)
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _ensure_revision_id_capacity(connection: Connection) -> None:
    """Allow descriptive Alembic revision IDs to be persisted.

    Alembic's default version table uses ``VARCHAR(32)``. This project already
    uses descriptive revision IDs such as ``0005_create_learning_vector_tables``,
    so a real PostgreSQL migration smoke must widen the column before Alembic
    writes the next head.

    Args:
        connection: Synchronous Alembic connection.
    """
    connection.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(255) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        )
        """)
    connection.exec_driver_sql("""
        ALTER TABLE alembic_version
        ALTER COLUMN version_num TYPE VARCHAR(255)
        """)


async def run_async_migrations() -> None:
    """Create an async engine and run online Alembic migrations.

    Returns:
        None.

    Raises:
        RuntimeError: If Alembic cannot load its configured ini section.
    """
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        raise RuntimeError("Alembic configuration section is missing.")

    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against the configured database.

    Returns:
        None.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
