"""Async SQLAlchemy engine and session factory helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import Settings, get_settings

# Non-superuser request role created in migration 0023a. When DATABASE_URL
# connects as this role (FORCE RLS Stage-2), privileged out-of-band writes
# (audit, post-commit learning) must NOT fall back to the request engine.
REQUEST_ROLE_LEMON_APP = "lemon_app"


@dataclass
class _DatabaseState:
    """Hold lazy database infrastructure instances.

    Attributes:
        engine: Cached async SQLAlchemy engine.
        sessionmaker: Cached async session factory.
    """

    engine: AsyncEngine | None = None
    sessionmaker: async_sessionmaker[AsyncSession] | None = None
    audit_engine: AsyncEngine | None = None
    audit_sessionmaker: async_sessionmaker[AsyncSession] | None = None
    learning_engine: AsyncEngine | None = None
    learning_sessionmaker: async_sessionmaker[AsyncSession] | None = None


_state = _DatabaseState()


def _engine_kwargs(settings: Settings) -> dict[str, object]:
    """Build the shared ``create_async_engine`` keyword arguments.

    Applies the configured connection-pool sizing uniformly to every engine
    (main, audit, learning) so the per-engine, per-worker connection budget is
    explicit and tunable against the server's ``max_connections``.

    Args:
        settings: Loaded application settings.

    Returns:
        Keyword arguments for ``create_async_engine``.
    """
    return {
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
    }


def get_engine() -> AsyncEngine:
    """Return the shared async SQLAlchemy engine.

    Returns:
        Lazily initialized async engine using the configured database URL.
    """
    if _state.engine is None:
        settings = get_settings()
        _state.engine = create_async_engine(settings.database_url, **_engine_kwargs(settings))

    return _state.engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the shared async session factory.

    Returns:
        Async sessionmaker configured for request-scoped database sessions.
    """
    if _state.sessionmaker is None:
        _state.sessionmaker = async_sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )

    return _state.sessionmaker


def get_audit_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the session factory for privileged audit writes.

    Audit rows are written out-of-band of the request transaction (preserving
    the legacy "commit the audit immediately" semantics). Under the FORCE RLS
    Stage-2 posture the request role (``lemon_app``) holds only SELECT on
    ``audit_logs``, so audits must use a privileged connection: set
    ``AUDIT_DATABASE_URL`` to a role that can INSERT audit rows. When it is unset
    (or equal to ``DATABASE_URL``, e.g. today's superuser request role) the main
    factory is reused — but each audit still opens its own short-lived session,
    so the write is always independent of the request transaction.

    Returns:
        Async sessionmaker bound to the audit (privileged) engine.
    """
    settings = get_settings()
    audit_url = settings.audit_database_url
    if audit_url is None or audit_url == settings.database_url:
        return get_sessionmaker()

    if _state.audit_sessionmaker is None:
        _state.audit_engine = create_async_engine(audit_url, **_engine_kwargs(settings))
        _state.audit_sessionmaker = async_sessionmaker(
            bind=_state.audit_engine,
            autoflush=False,
            expire_on_commit=False,
        )

    return _state.audit_sessionmaker


def get_learning_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the session factory for privileged post-commit learning writes.

    Learning artifacts (``learning_image_objects``, ``annotation_tasks``) are
    persisted *after* the request transaction commits, on a fresh short-lived
    session (see ``store_supplement_learning_artifacts``). Those tables are under
    FORCE ROW LEVEL SECURITY (migration 0023c): the request role ``lemon_app``
    (NOSUPERUSER, NOBYPASSRLS) is granted CRUD but its writes are still checked
    against the owner policies, which read transaction-local GUCs the fresh
    session never sets — so a ``lemon_app`` write would fail closed. Setting the
    GUCs once does not help either, because ``maybe_store_learning_image_object``
    commits mid-task (DO-NOT-TOUCH learning pipeline), which drops the
    transaction-local GUCs before the annotation write. The fix mirrors
    ``get_audit_sessionmaker``: bind this work to a privileged engine (superuser
    or BYPASSRLS role via ``LEARNING_DATABASE_URL``) that bypasses RLS.

    When ``LEARNING_DATABASE_URL`` is unset (or equal to ``DATABASE_URL``, e.g.
    today's superuser request role) the main factory is reused — behavior is
    byte-identical to the pre-Stage-2 path. Each post-commit task still opens its
    own short-lived session, independent of the request transaction.

    Returns:
        Async sessionmaker bound to the learning (privileged) engine.
    """
    settings = get_settings()
    learning_url = settings.learning_database_url
    if learning_url is None or learning_url == settings.database_url:
        return get_sessionmaker()

    if _state.learning_sessionmaker is None:
        _state.learning_engine = create_async_engine(learning_url, **_engine_kwargs(settings))
        _state.learning_sessionmaker = async_sessionmaker(
            bind=_state.learning_engine,
            autoflush=False,
            expire_on_commit=False,
        )

    return _state.learning_sessionmaker


def verify_stage2_privileged_database_urls(settings: Settings) -> None:
    """Fail fast at startup when the request role lacks its privileged engines.

    Under the FORCE RLS Stage-2 posture ``DATABASE_URL`` connects as the
    non-superuser request role ``lemon_app`` (migration 0023a). Two write paths
    must then run on a privileged (superuser/BYPASSRLS) connection rather than
    the request engine:

    * out-of-band audit writes (``audit_logs`` grants ``lemon_app`` SELECT only),
    * post-commit learning writes (``learning_image_objects`` / ``annotation_tasks``
      are FORCE RLS and the GUC-less post-commit session would fail closed).

    ``get_audit_sessionmaker`` / ``get_learning_sessionmaker`` reuse the main
    factory whenever their URL is unset *or equal to* ``DATABASE_URL``. If the
    operator flips ``DATABASE_URL`` to ``lemon_app`` without configuring those
    URLs, both paths would silently fall back to the request engine and break.
    This guard makes that misconfiguration a hard startup error instead. A
    privileged URL that is a distinct DSN but still connects as ``lemon_app`` is
    rejected too, since it would build a separate yet equally unprivileged engine.

    No-op while the request role is still privileged (e.g. today's superuser),
    so it is safe to wire before the flip.

    Args:
        settings: Loaded application settings.

    Raises:
        RuntimeError: When the request role is ``lemon_app`` but
            ``AUDIT_DATABASE_URL`` or ``LEARNING_DATABASE_URL`` is unset, equal to
            ``DATABASE_URL``, or itself connects as ``lemon_app``.
    """
    request_role = make_url(settings.database_url).username
    if request_role != REQUEST_ROLE_LEMON_APP:
        return

    missing = [
        name
        for name, url in (
            ("AUDIT_DATABASE_URL", settings.audit_database_url),
            ("LEARNING_DATABASE_URL", settings.learning_database_url),
        )
        if url is None
        or url == settings.database_url
        or make_url(url).username == REQUEST_ROLE_LEMON_APP
    ]
    if missing:
        raise RuntimeError(
            "DATABASE_URL connects as the non-superuser request role "
            f"'{REQUEST_ROLE_LEMON_APP}', but {', '.join(missing)} must be set to a "
            "privileged (superuser/BYPASSRLS) role distinct from DATABASE_URL. "
            "Without it, out-of-band audit and post-commit learning writes would "
            "run on the request engine and fail closed under FORCE RLS."
        )


async def dispose_engine() -> None:
    """Dispose the shared async engines and reset cached factories.

    Returns:
        None.
    """
    if _state.engine is not None:
        await _state.engine.dispose()
    if _state.audit_engine is not None:
        await _state.audit_engine.dispose()
    if _state.learning_engine is not None:
        await _state.learning_engine.dispose()

    _state.engine = None
    _state.sessionmaker = None
    _state.audit_engine = None
    _state.audit_sessionmaker = None
    _state.learning_engine = None
    _state.learning_sessionmaker = None
