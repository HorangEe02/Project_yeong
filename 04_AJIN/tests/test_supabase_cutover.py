"""Tests for the guarded Supabase cutover runner."""

from __future__ import annotations

from types import SimpleNamespace

import scripts.supabase_cutover as cutover


def test_validate_environment_blocks_missing_values(monkeypatch) -> None:
    """Missing cutover env vars are reported without secret values."""
    for name in (*cutover.REQUIRED_ENV, *cutover.OPTIONAL_ENV):
        monkeypatch.delenv(name, raising=False)

    issues = cutover.validate_environment("ycjuzwltwbeudanjykag")
    names = {issue.name for issue in issues}

    assert "SUPABASE_URL" in names
    assert "DATABASE_URL" in names
    assert "SUPABASE_SECRET_KEY" in names


def test_validate_environment_accepts_complete_cutover_env(monkeypatch) -> None:
    """A complete Supabase env contract has no preflight issues."""
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "ycjuzwltwbeudanjykag")
    monkeypatch.setenv("SUPABASE_URL", "https://ycjuzwltwbeudanjykag.supabase.co")
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_" + "a" * 40)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://app:pass@example.supabase.co/postgres"
    )
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_PRIVATE")
    monkeypatch.setenv("APP_DB_BACKEND", "postgres")
    monkeypatch.setenv("FIREBASE_WRITE_ENABLED", "false")
    monkeypatch.setenv("FIREBASE_READ_FALLBACK_ENABLED", "false")

    assert cutover.validate_environment("ycjuzwltwbeudanjykag") == []


def test_load_env_files_does_not_override_existing(monkeypatch, tmp_path) -> None:
    """Process env keeps precedence unless override is explicitly requested."""
    env_file = tmp_path / ".env.supabase.local"
    env_file.write_text(
        "SUPABASE_PROJECT_REF=ycjuzwltwbeudanjykag\nAPP_DB_BACKEND=postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_DB_BACKEND", "sqlite")

    loaded = cutover.load_env_files([env_file], override=False)

    assert loaded == [str(env_file)]
    assert cutover.os.environ["SUPABASE_PROJECT_REF"] == "ycjuzwltwbeudanjykag"
    assert cutover.os.environ["APP_DB_BACKEND"] == "sqlite"


def test_unique_paths_deduplicates_resolved_paths(tmp_path) -> None:
    """Default and explicit env files should not appear twice in diagnostics."""
    env_file = tmp_path / ".env.supabase.local"
    env_file.touch()

    assert cutover.unique_paths([env_file, tmp_path / "." / ".env.supabase.local"]) == [
        env_file.resolve()
    ]


def test_redact_text_removes_known_secret_fragments(monkeypatch) -> None:
    """Subprocess diagnostics redact local secret values."""
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_DO_NOT_PRINT")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://app:db-password@example.supabase.co/postgres"
    )

    text = cutover.redact_text("key=sb_secret_DO_NOT_PRINT db-password visible")

    assert "DO_NOT_PRINT" not in text
    assert "db-password" not in text


def test_ensure_private_bucket_creates_missing_bucket() -> None:
    """Missing buckets are created as private."""
    calls: list[tuple[str, str, dict]] = []

    class Storage:
        def list_buckets(self):
            return []

        def create_bucket(self, bucket_id, options):
            calls.append(("create", bucket_id, options))

    assert cutover.ensure_private_bucket(Storage(), "ajin-attachments") == "created"
    assert calls == [("create", "ajin-attachments", {"public": False})]


def test_ensure_private_bucket_updates_public_bucket() -> None:
    """Existing public buckets are updated to private."""
    calls: list[tuple[str, str, dict]] = []

    class Storage:
        def list_buckets(self):
            return [
                SimpleNamespace(
                    id="ajin-attachments", name="ajin-attachments", public=True
                )
            ]

        def update_bucket(self, bucket_id, options):
            calls.append(("update", bucket_id, options))

    assert (
        cutover.ensure_private_bucket(Storage(), "ajin-attachments")
        == "updated_private"
    )
    assert calls == [("update", "ajin-attachments", {"public": False})]


def test_ensure_private_bucket_keeps_private_bucket() -> None:
    """Existing private buckets are left untouched."""

    class Storage:
        def list_buckets(self):
            return [{"id": "ajin-attachments", "public": False}]

    assert (
        cutover.ensure_private_bucket(Storage(), "ajin-attachments")
        == "already_private"
    )
