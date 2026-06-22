"""Medical source registry readiness tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from lemon_ai_agent.knowledge import REVIEWED_MEDICAL_SOURCE_REGISTRY
from src.config import Settings
from src.services.medical_source_readiness import (
    MedicalSourceGovernanceRepository,
    MedicalSourceReadinessRecord,
    build_medical_source_readiness,
    build_medical_source_readiness_from_db,
    build_medical_source_readiness_from_records,
)

NUTRITION_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _kdca_topic_ids() -> dict[str, str]:
    by_id = {source.source_id: source for source in REVIEWED_MEDICAL_SOURCE_REGISTRY}
    return {
        topic_id: f"{index:04d}"
        for index, (topic_id, _label) in enumerate(
            by_id["kdca-healthinfo"].topic_id_requirements,
            start=1,
        )
    }


def test_medical_source_readiness_requires_key_for_reviewed_keyed_sources() -> None:
    """Verify keyed reviewed sources are explicit before live retrieval work."""
    readiness = build_medical_source_readiness(
        Settings(_env_file=None),
        today=date(2026, 5, 24),
    )
    by_id = {source.source_id: source for source in readiness.sources}

    assert by_id["kdca-healthinfo"].ready is False
    assert by_id["kdca-healthinfo"].error_code == "missing_topic_ids"
    assert by_id["kdca-healthinfo"].env_key is None
    assert "hypertension" in by_id["kdca-healthinfo"].missing_topic_ids

    assert by_id["kdris-2025"].ready is True
    assert by_id["kdris-2025"].error_code is None


def test_medical_source_readiness_keeps_draft_sources_out_of_user_facing_use() -> None:
    """Verify research backlog sources do not become user-facing when a key exists."""
    settings = Settings(
        _env_file=None,
        kdca_healthinfo_topic_ids=_kdca_topic_ids(),
        mfds_data_api_key="mfds-key",
        semantic_scholar_api_key="semantic-key",
    )

    readiness = build_medical_source_readiness(settings, today=date(2026, 5, 24))
    by_id = {source.source_id: source for source in readiness.sources}

    assert by_id["kdca-healthinfo"].ready is True
    assert by_id["kdca-healthinfo"].configured is True
    assert by_id["kdca-healthinfo"].topics[:3] == (
        "hypertension",
        "diabetes",
        "kidney_disease",
    )
    assert by_id["mfds-drug-safety"].ready is True
    assert by_id["mfds-drug-safety"].configured is True

    semantic_scholar = by_id["semantic-scholar"]
    assert semantic_scholar.configured is True
    assert semantic_scholar.ready is False
    assert semantic_scholar.user_facing_allowed is False
    assert semantic_scholar.error_code == "not_reviewed"
    assert readiness.ready is True


def test_medical_source_readiness_marks_expired_review_as_stale() -> None:
    """Verify stale-source behavior is deterministic before RAG/live retrieval."""
    readiness = build_medical_source_readiness(
        Settings(_env_file=None, kdca_healthinfo_topic_ids=_kdca_topic_ids()),
        today=date(2027, 1, 1),
    )
    by_id = {source.source_id: source for source in readiness.sources}

    assert by_id["kdca-healthinfo"].ready is False
    assert by_id["kdca-healthinfo"].error_code == "source_stale"
    assert by_id["kdca-healthinfo"].review_expires_at == "2026-11-22"
    assert readiness.ready is False


def test_medical_source_readiness_loads_kdca_topic_ids_file(tmp_path) -> None:
    """Verify KDCA topic identifiers can be kept in an ignored local JSON file."""
    topic_ids = _kdca_topic_ids()
    topic_ids_file = tmp_path / "kdca_healthinfo_topics.local.json"
    topic_ids_file.write_text(
        '{"topics": {'
        + ", ".join(
            f'"{topic_id}": {{"title": "{topic_id}", "topic_id": "{value}"}}'
            for topic_id, value in topic_ids.items()
        )
        + "}}",
        encoding="utf-8",
    )

    readiness = build_medical_source_readiness(
        Settings(
            _env_file=None,
            kdca_healthinfo_topic_ids_file=topic_ids_file,
        ),
        today=date(2026, 5, 24),
    )
    by_id = {source.source_id: source for source in readiness.sources}

    assert by_id["kdca-healthinfo"].ready is True
    assert by_id["kdca-healthinfo"].missing_topic_ids == ()


def test_kdca_topic_ids_example_matches_required_topics() -> None:
    """Verify the tracked KDCA topic-id template stays aligned with readiness."""
    example_path = NUTRITION_BACKEND_ROOT / "config" / "kdca_healthinfo_topics.example.json"
    raw_value = json.loads(example_path.read_text(encoding="utf-8"))
    assert isinstance(raw_value, dict)
    topics = raw_value["topics"]
    assert isinstance(topics, dict)

    assert set(topics) == set(_kdca_topic_ids())


def test_db_backed_readiness_uses_only_reviewed_unexpired_sources() -> None:
    """Verify DB-backed readiness exposes only reviewed current source families."""
    readiness = build_medical_source_readiness_from_records(
        [
            MedicalSourceReadinessRecord(
                source_id="kdca-healthinfo",
                title="KDCA health information",
                source_family="public_health_guidance",
                review_status="reviewed",
                reviewed_at=date(2026, 5, 22),
                expires_at=date(2026, 11, 22),
            ),
            MedicalSourceReadinessRecord(
                source_id="semantic-scholar",
                title="Semantic Scholar candidate papers",
                source_family="paper_research",
                review_status="paper_candidate",
                reviewed_at=date(2026, 5, 22),
                expires_at=date(2026, 11, 22),
            ),
        ],
        today=date(2026, 5, 24),
    )
    by_id = {source.source_id: source for source in readiness.sources}

    assert readiness.ready is True
    assert by_id["kdca-healthinfo"].ready is True
    assert by_id["kdca-healthinfo"].source_families == ("public_health_guidance",)
    assert by_id["kdca-healthinfo"].status == "reviewed"
    assert by_id["semantic-scholar"].ready is False
    assert by_id["semantic-scholar"].user_facing_allowed is False
    assert by_id["semantic-scholar"].error_code == "not_reviewed"


def test_db_backed_readiness_fails_closed_when_no_reviewed_sources() -> None:
    """Verify production-like DB readiness fails closed when governance rows are empty."""
    readiness = build_medical_source_readiness_from_records(
        [],
        today=date(2026, 5, 24),
        allow_registry_fallback=False,
    )

    assert readiness.ready is False
    assert len(readiness.sources) == 1
    assert readiness.sources[0].source_id == "medical-source-governance"
    assert readiness.sources[0].ready is False
    assert readiness.sources[0].error_code == "no_reviewed_sources"
    assert readiness.sources[0].user_facing_allowed is False


def test_db_backed_readiness_marks_reviewed_expired_source_stale() -> None:
    """Verify reviewed DB sources become non-ready after expiry."""
    readiness = build_medical_source_readiness_from_records(
        [
            MedicalSourceReadinessRecord(
                source_id="kdca-healthinfo",
                title="KDCA health information",
                source_family="public_health_guidance",
                review_status="reviewed",
                reviewed_at=date(2026, 5, 22),
                expires_at=date(2026, 5, 23),
            ),
        ],
        today=date(2026, 5, 24),
    )

    assert readiness.ready is False
    assert readiness.sources[0].ready is False
    assert readiness.sources[0].error_code == "source_stale"
    assert readiness.sources[0].user_facing_allowed is False


def test_local_registry_fallback_remains_explicit_dev_only() -> None:
    """Verify registry fallback is an explicit local/dev bootstrap path."""
    readiness = build_medical_source_readiness_from_records(
        [],
        today=date(2026, 5, 24),
        allow_registry_fallback=True,
        settings=Settings(_env_file=None, kdca_healthinfo_topic_ids=_kdca_topic_ids()),
    )
    by_id = {source.source_id: source for source in readiness.sources}

    assert "kdca-healthinfo" in by_id
    assert by_id["kdca-healthinfo"].ready is True
    assert all(source.error_code != "no_reviewed_sources" for source in readiness.sources)


class _FakeResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def execute(self, statement: object) -> _FakeResult:
        self.statement = statement
        return _FakeResult(self.rows)


async def test_medical_source_governance_repository_maps_db_rows() -> None:
    """Verify the DB-backed repository maps source/version rows into readiness records."""
    session = _FakeSession(
        [
            SimpleNamespace(
                source_id="kdca-healthinfo",
                title="KDCA health information",
                source_family="public_health_guidance",
                review_status="reviewed",
                reviewed_at=date(2026, 5, 22),
                expires_at=date(2026, 11, 22),
            )
        ]
    )

    records = await MedicalSourceGovernanceRepository(session).list_readiness_records()

    assert session.statement is not None
    assert records == (
        MedicalSourceReadinessRecord(
            source_id="kdca-healthinfo",
            title="KDCA health information",
            source_family="public_health_guidance",
            review_status="reviewed",
            reviewed_at=date(2026, 5, 22),
            expires_at=date(2026, 11, 22),
        ),
    )


async def test_db_readiness_fails_closed_for_empty_production_db() -> None:
    """Verify production-like DB readiness does not fall back to the static registry."""
    readiness = await build_medical_source_readiness_from_db(
        _FakeSession([]),
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+asyncpg://lemon_prod:secret@db.example.com:5432/lemon",
            allowed_origins=["https://app.example.com"],
            allowed_hosts=["api.example.com"],
            auth_mode="jwt",
            jwt_issuer="https://issuer.example.com",
            jwt_audience="lemon-api",
            jwt_jwks_url="https://issuer.example.com/.well-known/jwks.json",
            jwt_token_use_claim="token_use",
            jwt_token_use_allowed_values=["access"],
            privacy_hash_secret="prod-privacy-secret-0123456789abcdef0123456789abcdef",
            allow_sample_kdris=False,
            kdris_data_version="2025",
            kdris_data_path="data/nutrition_reference/kdris/kdris_2025.csv",
        ),
        today=date(2026, 5, 24),
    )

    assert readiness.ready is False
    assert readiness.sources[0].error_code == "no_reviewed_sources"


async def test_db_readiness_allows_registry_fallback_for_development_empty_db() -> None:
    """Verify development DB readiness can use the registry bootstrap fallback."""
    readiness = await build_medical_source_readiness_from_db(
        _FakeSession([]),
        Settings(_env_file=None, kdca_healthinfo_topic_ids=_kdca_topic_ids()),
        today=date(2026, 5, 24),
    )

    by_id = {source.source_id: source for source in readiness.sources}
    assert "kdca-healthinfo" in by_id
    assert by_id["kdca-healthinfo"].error_code is None
    assert all(source.error_code != "no_reviewed_sources" for source in readiness.sources)
