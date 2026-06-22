"""Readiness checks for reviewed medical source metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from lemon_ai_agent.knowledge import REVIEWED_MEDICAL_SOURCE_REGISTRY, ReviewedMedicalSource
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import BACKEND_ROOT, PROJECT_ROOT, Settings
from src.models.db.medical_source import MedicalSource, MedicalSourceVersion


@dataclass(frozen=True)
class MedicalSourceStatus:
    source_id: str
    title: str
    status: str
    configured: bool
    ready: bool
    error_code: str | None
    env_key: str | None
    missing_topic_ids: tuple[str, ...]
    source_families: tuple[str, ...]
    topics: tuple[str, ...]
    user_facing_allowed: bool
    last_reviewed_at: str
    review_expires_at: str


@dataclass(frozen=True)
class MedicalSourceReadiness:
    ready: bool
    sources: tuple[MedicalSourceStatus, ...]


@dataclass(frozen=True)
class MedicalSourceReadinessRecord:
    source_id: str
    title: str
    source_family: str
    review_status: str
    reviewed_at: date
    expires_at: date


class MedicalSourceGovernanceRepository:
    """Read reviewed source-governance readiness metadata from the application DB."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_readiness_records(self) -> tuple[MedicalSourceReadinessRecord, ...]:
        """Return the latest source-version rows needed for readiness checks."""
        statement = (
            select(
                MedicalSource.id.label("source_id"),
                MedicalSource.title.label("title"),
                MedicalSource.source_family.label("source_family"),
                MedicalSourceVersion.review_status.label("review_status"),
                MedicalSourceVersion.reviewed_at.label("reviewed_at"),
                MedicalSourceVersion.expires_at.label("expires_at"),
            )
            .join(MedicalSourceVersion, MedicalSourceVersion.source_id == MedicalSource.id)
            .order_by(
                MedicalSource.id.asc(),
                MedicalSourceVersion.reviewed_at.desc(),
                MedicalSourceVersion.created_at.desc(),
            )
        )
        result = await self._session.execute(statement)
        records: list[MedicalSourceReadinessRecord] = []
        seen_source_ids: set[str] = set()
        for row in result.all():
            source_id = str(row.source_id)
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            records.append(
                MedicalSourceReadinessRecord(
                    source_id=source_id,
                    title=str(row.title),
                    source_family=str(row.source_family),
                    review_status=str(row.review_status),
                    reviewed_at=row.reviewed_at,
                    expires_at=row.expires_at,
                )
            )
        return tuple(records)


def build_medical_source_readiness(
    settings: Settings,
    *,
    today: date | None = None,
) -> MedicalSourceReadiness:
    """Return sanitized readiness for source-governance checks.

    The check does not call external APIs and never exposes secret values. It only
    verifies that reviewed source metadata is current and that keyed sources have
    a configured key before future live retrieval or RAG work can rely on them.
    """
    current_date = today or datetime.now(UTC).date()
    statuses = tuple(
        _source_status(settings, source, current_date)
        for source in REVIEWED_MEDICAL_SOURCE_REGISTRY
    )
    return MedicalSourceReadiness(
        ready=all(source.ready for source in statuses if source.user_facing_allowed),
        sources=statuses,
    )


async def build_medical_source_readiness_from_db(
    session: AsyncSession,
    settings: Settings,
    *,
    today: date | None = None,
    allow_registry_fallback: bool | None = None,
) -> MedicalSourceReadiness:
    """Return readiness from DB rows, with registry fallback only outside production."""
    records = await MedicalSourceGovernanceRepository(session).list_readiness_records()
    fallback_allowed = (
        settings.environment != "production"
        if allow_registry_fallback is None
        else allow_registry_fallback
    )
    return build_medical_source_readiness_from_records(
        records,
        today=today,
        allow_registry_fallback=fallback_allowed,
        settings=settings,
    )


def build_medical_source_readiness_from_records(
    records: list[MedicalSourceReadinessRecord] | tuple[MedicalSourceReadinessRecord, ...],
    *,
    today: date | None = None,
    allow_registry_fallback: bool = False,
    settings: Settings | None = None,
) -> MedicalSourceReadiness:
    """Return readiness from DB-backed source governance records.

    Empty DB-backed records fail closed unless the caller explicitly opts into
    the local/dev registry fallback for bootstrap checks.
    """
    current_date = today or datetime.now(UTC).date()
    if not records:
        if allow_registry_fallback:
            return build_medical_source_readiness(settings or Settings(), today=current_date)
        return MedicalSourceReadiness(
            ready=False,
            sources=(
                MedicalSourceStatus(
                    source_id="medical-source-governance",
                    title="Medical source governance DB",
                    status="missing",
                    configured=False,
                    ready=False,
                    error_code="no_reviewed_sources",
                    env_key=None,
                    missing_topic_ids=(),
                    source_families=(),
                    topics=(),
                    user_facing_allowed=False,
                    last_reviewed_at="",
                    review_expires_at="",
                ),
            ),
        )

    statuses = tuple(_db_record_status(record, current_date) for record in records)
    return MedicalSourceReadiness(
        ready=any(source.ready and source.user_facing_allowed for source in statuses),
        sources=statuses,
    )


def _db_record_status(
    record: MedicalSourceReadinessRecord,
    today: date,
) -> MedicalSourceStatus:
    status = record.review_status
    user_facing_allowed = status == "reviewed" and today <= record.expires_at
    error_code: str | None = None
    if status != "reviewed":
        error_code = "not_reviewed"
    elif today > record.expires_at:
        error_code = "source_stale"

    return MedicalSourceStatus(
        source_id=record.source_id,
        title=record.title,
        status=status,
        configured=error_code is None,
        ready=error_code is None,
        error_code=error_code,
        env_key=None,
        missing_topic_ids=(),
        source_families=(record.source_family,),
        topics=(),
        user_facing_allowed=user_facing_allowed,
        last_reviewed_at=record.reviewed_at.isoformat(),
        review_expires_at=record.expires_at.isoformat(),
    )


def _source_status(
    settings: Settings,
    source: ReviewedMedicalSource,
    today: date,
) -> MedicalSourceStatus:
    env_key = source.env_key
    configured = True if env_key is None else _has_secret_setting(settings, env_key)
    missing_topic_ids = _missing_required_topic_ids(settings, source)
    configured = configured and not missing_topic_ids
    expires_at = date.fromisoformat(source.review_expires_at)
    status = source.status
    user_facing_allowed = source.user_facing_allowed

    error_code: str | None = None
    if status != "reviewed":
        error_code = "not_reviewed"
    elif today > expires_at:
        error_code = "source_stale"
    elif not configured:
        error_code = "missing_topic_ids" if missing_topic_ids else "missing_api_key"

    return MedicalSourceStatus(
        source_id=source.source_id,
        title=source.title,
        status=status,
        configured=configured,
        ready=error_code is None and user_facing_allowed,
        error_code=error_code,
        env_key=env_key,
        missing_topic_ids=missing_topic_ids,
        source_families=source.source_families,
        topics=source.topics,
        user_facing_allowed=user_facing_allowed,
        last_reviewed_at=source.last_reviewed_at,
        review_expires_at=source.review_expires_at,
    )


def _has_secret_setting(settings: Settings, env_key: str) -> bool:
    attr_name = env_key.lower()
    value = getattr(settings, attr_name, None)
    if value is None:
        return False
    if hasattr(value, "get_secret_value"):
        return bool(value.get_secret_value())
    return bool(value)


def _missing_required_topic_ids(
    settings: Settings,
    source: ReviewedMedicalSource,
) -> tuple[str, ...]:
    if not source.topic_id_requirements:
        return ()

    configured_topic_ids = _configured_kdca_healthinfo_topic_ids(settings)
    return tuple(
        topic_id
        for topic_id, _label in source.topic_id_requirements
        if not configured_topic_ids.get(topic_id)
    )


def _configured_kdca_healthinfo_topic_ids(settings: Settings) -> dict[str, str]:
    topic_ids = _load_topic_ids_from_file(settings.kdca_healthinfo_topic_ids_file)
    topic_ids.update(
        {
            key: value
            for key, value in settings.kdca_healthinfo_topic_ids.items()
            if isinstance(value, str) and value.strip()
        }
    )
    return topic_ids


def _load_topic_ids_from_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    resolved_path = _resolve_topic_ids_path(path)
    if resolved_path is None:
        return {}
    try:
        raw_value = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _parse_topic_ids(raw_value)


def _resolve_topic_ids_path(path: Path) -> Path | None:
    candidates = [path]
    if not path.is_absolute():
        candidates.extend((PROJECT_ROOT / path, BACKEND_ROOT / path))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _parse_topic_ids(raw_value: Any) -> dict[str, str]:
    if not isinstance(raw_value, dict):
        return {}

    raw_topics = raw_value.get("topics", raw_value)
    if not isinstance(raw_topics, dict):
        return {}

    topic_ids: dict[str, str] = {}
    for key, value in raw_topics.items():
        if not isinstance(key, str):
            continue
        parsed_value = _parse_topic_id_value(value)
        if parsed_value:
            topic_ids[key] = parsed_value
    return topic_ids


def _parse_topic_id_value(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        raw_topic_id = value.get("topic_id")
        if isinstance(raw_topic_id, str):
            return raw_topic_id.strip() or None
    return None
