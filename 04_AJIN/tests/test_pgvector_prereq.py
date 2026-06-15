"""Supabase pgvector prerequisite verifier tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import scripts.verify_pgvector_prereq as verifier


def _fixture_root(tmp_path: Path, sql: str | None = None) -> Path:
    """Create an isolated Supabase migration fixture root.

    Args:
        tmp_path: Pytest temporary directory.
        sql: Optional migration SQL. When omitted, the repository migration is copied.

    Returns:
        Path: Fixture repository root.
    """

    root = tmp_path / "repo"
    migrations = root / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    if sql is None:
        source = verifier.find_pgvector_migration(verifier.ROOT)
        assert source is not None
        shutil.copyfile(source, migrations / source.name)
    else:
        (migrations / "20260521000000_add_pgvector_search_store.sql").write_text(
            sql,
            encoding="utf-8",
        )
    return root


def test_local_pgvector_migration_passes_for_repo() -> None:
    """The checked-in pgvector migration should contain the required release posture."""

    result = verifier.verify_local_migration(
        verifier.PgvectorPrereqConfig(root=verifier.ROOT, skip_remote=True)
    )

    assert result.status == "pass"
    assert "document_chunks" in result.details["tables"]
    assert result.details["embedding_dim"] == 1024


def test_missing_pgvector_migration_fails(tmp_path: Path) -> None:
    """A missing migration should fail the local schema gate."""

    root = tmp_path / "repo"
    (root / "supabase").mkdir(parents=True)

    result = verifier.verify_local_migration(
        verifier.PgvectorPrereqConfig(root=root, skip_remote=True)
    )

    assert result.status == "fail"
    assert result.details["expected_dir"] == "supabase/migrations"


def test_incomplete_pgvector_migration_fails(tmp_path: Path) -> None:
    """The verifier should reject a migration without tables, RLS, and private RPCs."""

    root = _fixture_root(tmp_path, "create extension if not exists vector with schema extensions;")

    result = verifier.verify_local_migration(
        verifier.PgvectorPrereqConfig(root=root, skip_remote=True)
    )

    assert result.status == "fail"
    assert "vector_dimension" in result.details["missing"]
    assert "table:document_chunks" in result.details["missing"]
    assert "function:match_document_chunks" in result.details["missing"]


def test_remote_required_without_database_url_fails(monkeypatch) -> None:
    """Strict release mode can require a remote database URL without printing it."""

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AJIN_DATABASE_URL", raising=False)

    result = verifier.verify_remote_pgvector(
        verifier.PgvectorPrereqConfig(require_remote=True)
    )

    assert result.status == "fail"
    assert result.details["credential_presence"] is False


def test_markdown_report_is_secret_safe(tmp_path: Path, monkeypatch) -> None:
    """Reports must not include raw database URLs or secret-like values."""

    root = _fixture_root(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:super-secret@example.invalid/db")
    report = verifier.run_verification(
        verifier.PgvectorPrereqConfig(root=root, skip_remote=True)
    )
    output = tmp_path / "report.md"
    verifier.write_markdown(report, output)

    content = output.read_text(encoding="utf-8")
    assert "super-secret" not in content
    assert "postgresql://user" not in content
    assert "DATABASE_URL" not in content
    assert "Supabase pgvector" in content


def test_embedding_smoke_skips_by_default() -> None:
    """Ollama embedding calls should be opt-in for deterministic local tests."""

    result = verifier.verify_embedding_smoke(verifier.PgvectorPrereqConfig())

    assert result.status == "skip"
    assert result.details["expected_dim"] == 1024
