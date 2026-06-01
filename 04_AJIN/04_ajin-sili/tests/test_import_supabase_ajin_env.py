"""Tests for importing AJIN Supabase handoff values into dotenv format."""

from __future__ import annotations

import stat

from scripts.import_supabase_ajin_env import (
    build_env_values,
    parse_supabase_ajin,
    render_dotenv,
    safe_status,
    write_dotenv,
)


def test_parse_supabase_ajin_extracts_remote_values() -> None:
    """The handoff parser extracts Supabase URL, key, database URL, and password."""
    text = """
https://ycjuzwltwbeudanjykag.supabase.co
sb_publishable_PUBLICVALUE
postgresql://postgres.ycjuzwltwbeudanjykag:pass-123!@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres
"""

    config = parse_supabase_ajin(text)

    assert config.project_ref == "ycjuzwltwbeudanjykag"
    assert config.supabase_url == "https://ycjuzwltwbeudanjykag.supabase.co"
    assert config.publishable_key == "sb_publishable_PUBLICVALUE"
    assert config.db_password == "pass-123!"
    assert config.database_url.startswith(
        "postgresql://postgres.ycjuzwltwbeudanjykag:"
    )


def test_parse_supabase_ajin_builds_database_url_from_labeled_fields() -> None:
    """The parser can derive DATABASE_URL when only field labels are present."""
    text = """
https://ycjuzwltwbeudanjykag.supabase.co
sb_publishable_PUBLICVALUE
host:
aws-1-ap-northeast-1.pooler.supabase.com
port:
5432
database:
postgres
user:
postgres.ycjuzwltwbeudanjykag
AJIN-SILI supabase pw : p@ss word!
"""

    config = parse_supabase_ajin(text)

    assert "p%40ss%20word%21" in config.database_url
    assert config.db_password == "p@ss word!"


def test_build_env_values_preserves_manual_tokens() -> None:
    """Manual access and backend secret keys survive regeneration."""
    config = parse_supabase_ajin(
        """
https://ycjuzwltwbeudanjykag.supabase.co
sb_publishable_PUBLICVALUE
postgresql://postgres.ycjuzwltwbeudanjykag:pass@host:5432/postgres
"""
    )

    values = build_env_values(
        config,
        existing={
            "SUPABASE_ACCESS_TOKEN": "sbp_existing",
            "SUPABASE_SECRET_KEY": "sb_secret_existing",
        },
    )

    assert values["APP_DB_BACKEND"] == "postgres"
    assert values["FIREBASE_WRITE_ENABLED"] == "false"
    assert values["FIREBASE_READ_FALLBACK_ENABLED"] == "false"
    assert values["SUPABASE_ACCESS_TOKEN"] == "sbp_existing"
    assert values["SUPABASE_SECRET_KEY"] == "sb_secret_existing"


def test_render_dotenv_and_safe_status_keep_separate_outputs() -> None:
    """Rendering writes dotenv values while the status view stays secret-safe."""
    config = parse_supabase_ajin(
        """
https://ycjuzwltwbeudanjykag.supabase.co
sb_publishable_PUBLICVALUE
postgresql://postgres.ycjuzwltwbeudanjykag:pass@host:5432/postgres
"""
    )
    values = build_env_values(config)

    dotenv = render_dotenv(values)
    status = safe_status(values)

    assert "DATABASE_URL=postgresql://" in dotenv
    assert status["DATABASE_URL"] == "set"
    assert status["SUPABASE_ACCESS_TOKEN"] == "missing"
    assert status["SUPABASE_SECRET_KEY"] == "missing"


def test_write_dotenv_uses_owner_only_permissions(tmp_path) -> None:
    """Generated local secret files are not group/world readable."""
    output = tmp_path / ".env.supabase.local"

    write_dotenv(output, "SUPABASE_PROJECT_REF=ycjuzwltwbeudanjykag\n")

    mode = stat.S_IMODE(output.stat().st_mode)
    assert mode == 0o600
