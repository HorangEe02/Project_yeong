"""Tests for the Supabase remote verification preflight."""

from __future__ import annotations

import json
from types import SimpleNamespace

import scripts.verify_supabase_remote as verifier
from scripts.verify_supabase_remote import (
    CheckResult,
    DENY_POLICY_TABLES,
    REQUIRED_TABLES,
    VerificationConfig,
    check_database,
    check_environment,
    check_supabase_cli,
    check_storage,
    collect_sanitized_supabase_health,
    run_verification,
    write_markdown_report,
)

VALID_TEST_TOKEN = "sbp_" + ("a" * 40)


def _set_base_env(monkeypatch) -> None:
    """Set a complete secret-bearing Supabase environment for verifier tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """

    monkeypatch.setenv("SUPABASE_PROJECT_REF", "ycjuzwltwbeudanjykag")
    monkeypatch.setenv("APP_DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:db-password@example.supabase.co:5432/postgres")
    monkeypatch.setenv("SUPABASE_URL", "https://ycjuzwltwbeudanjykag.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_SUPER_PRIVATE_VALUE")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_PUBLIC_VALUE")
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.setenv("FIREBASE_WRITE_ENABLED", "false")
    monkeypatch.setenv("FIREBASE_READ_FALLBACK_ENABLED", "false")


def _deny_policies() -> list[dict]:
    """Return explicit deny-all policy rows for the verifier contract.

    Returns:
        list[dict]: pg_policies-like rows.
    """

    return [
        {
            "table_name": table,
            "policy_name": f"deny_all_data_api_{table}",
            "roles": ["anon", "authenticated"],
            "cmd": "ALL",
            "qual": "false",
            "with_check": "false",
        }
        for table in DENY_POLICY_TABLES
    ]


def _snapshot(*, privileges=None, policies=None, admin_users=None) -> dict:
    """Create a passing database metadata snapshot.

    Args:
        privileges: Optional role grant rows.
        policies: Optional pg_policies-like rows.
        admin_users: Optional sanitized admin user rows.

    Returns:
        dict: Snapshot accepted by check_database.
    """

    tables = {table: True for table in (*REQUIRED_TABLES, *DENY_POLICY_TABLES)}
    return {
        "connected": True,
        "alembic_versions": ["20260518_0002"],
        "tables": tables,
        "rls_enabled": {table: True for table in tables},
        "privileges": privileges or [],
        "policies": _deny_policies() if policies is None else policies,
        "admin_users": admin_users
        or [
            {
                "employee_id": "SYS-0001",
                "password_hash": "",
                "is_active": True,
                "role_name": "SYS_ADMIN",
            }
        ],
    }


def _status_by_name(checks) -> dict[str, str]:
    """Index check statuses by name.

    Args:
        checks: Iterable of CheckResult values.

    Returns:
        dict[str, str]: Mapping of check name to status.
    """

    return {check.name: check.status for check in checks}


def test_missing_env_returns_failures_without_secret_leak(monkeypatch) -> None:
    """Missing required env values fail without exposing unrelated local secrets."""
    monkeypatch.delenv("SUPABASE_PROJECT_REF", raising=False)
    monkeypatch.delenv("APP_DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_DO_NOT_PRINT")

    report = run_verification(VerificationConfig(strict=True), include_db=False, include_storage=False)
    encoded = json.dumps(report, ensure_ascii=False)

    assert report["summary"]["status"] == "fail"
    assert "DO_NOT_PRINT" not in encoded


def test_project_url_mismatch_is_detected(monkeypatch) -> None:
    """A SUPABASE_URL for another project fails the project-ref check."""
    _set_base_env(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://wrong-project.supabase.co")

    statuses = _status_by_name(check_environment(VerificationConfig()))

    assert statuses["url_matches_project_ref"] == "fail"


def test_database_checks_accept_mocked_success(monkeypatch) -> None:
    """DB checks pass when the mocked remote metadata matches the contract."""
    _set_base_env(monkeypatch)

    checks = check_database(VerificationConfig(), query_runner=lambda _url, _config: _snapshot())
    statuses = _status_by_name(checks)
    encoded = json.dumps([check.to_dict() for check in checks], ensure_ascii=False)

    assert statuses["database_connected"] == "pass"
    assert statuses["alembic_current"] == "pass"
    assert statuses["required_tables_present"] == "pass"
    assert statuses["required_tables_rls_enabled"] == "pass"
    assert statuses["sensitive_role_grants"] == "pass"
    assert statuses["data_api_deny_policies"] == "pass"
    assert statuses["default_admin_risk"] == "pass"
    assert "db-password" not in encoded


def test_database_anon_grant_on_sensitive_table_fails(monkeypatch) -> None:
    """Sensitive public table privileges granted to anon are release blockers."""
    _set_base_env(monkeypatch)
    checks = check_database(
        VerificationConfig(),
        query_runner=lambda _url, _config: _snapshot(
            privileges=[
                {
                    "grantee": "anon",
                    "table_name": "users",
                    "privilege_type": "SELECT",
                }
            ]
        ),
    )

    assert _status_by_name(checks)["sensitive_role_grants"] == "fail"


def test_database_authenticated_grant_on_sensitive_table_fails_in_strict(monkeypatch) -> None:
    """Strict verifier treats authenticated grants as release blockers."""
    _set_base_env(monkeypatch)
    checks = check_database(
        VerificationConfig(strict=True),
        query_runner=lambda _url, _config: _snapshot(
            privileges=[
                {
                    "grantee": "authenticated",
                    "table_name": "attachments",
                    "privilege_type": "SELECT",
                }
            ]
        ),
    )

    assert _status_by_name(checks)["sensitive_role_grants"] == "fail"


def test_database_service_role_grant_on_sensitive_table_fails(monkeypatch) -> None:
    """service_role table grants are blocked because AJIN backend owns auth."""
    _set_base_env(monkeypatch)
    checks = check_database(
        VerificationConfig(strict=True),
        query_runner=lambda _url, _config: _snapshot(
            privileges=[
                {
                    "grantee": "service_role",
                    "table_name": "users",
                    "privilege_type": "SELECT",
                }
            ]
        ),
    )

    assert _status_by_name(checks)["sensitive_role_grants"] == "fail"


def test_database_missing_deny_policy_fails(monkeypatch) -> None:
    """RLS enable without explicit deny-all policies is not accepted."""
    _set_base_env(monkeypatch)
    policies = [row for row in _deny_policies() if row["table_name"] != "users"]

    checks = check_database(
        VerificationConfig(strict=True),
        query_runner=lambda _url, _config: _snapshot(policies=policies),
    )

    assert _status_by_name(checks)["data_api_deny_policies"] == "fail"


def test_database_default_admin_risk_fails(monkeypatch) -> None:
    """A deployment with only the legacy admin account is a release blocker."""
    _set_base_env(monkeypatch)
    checks = check_database(
        VerificationConfig(strict=True),
        query_runner=lambda _url, _config: _snapshot(
            admin_users=[
                {
                    "employee_id": "admin",
                    "password_hash": "",
                    "is_active": True,
                    "role_name": "SYS_ADMIN",
                }
            ],
        ),
    )

    assert _status_by_name(checks)["default_admin_risk"] == "fail"


def test_cli_invalid_token_shape_skips_project_list(monkeypatch) -> None:
    """Invalid Supabase PAT shape is caught before listing projects."""
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "not-a-valid-token")
    monkeypatch.setattr(verifier.shutil, "which", lambda _name: "/usr/local/bin/supabase")
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="2.98.2\n", stderr=""),
    )
    monkeypatch.setattr(
        verifier,
        "read_linked_project_ref",
        lambda: ("ycjuzwltwbeudanjykag", "test"),
    )

    statuses = _status_by_name(check_supabase_cli(VerificationConfig(strict=True)))

    assert statuses["supabase_cli_available"] == "pass"
    assert statuses["supabase_access_token_shape"] == "fail"
    assert statuses["supabase_project_list"] == "skip"


def test_cli_project_list_success_and_link_match(monkeypatch) -> None:
    """CLI check passes when token, project list, and local link match."""
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.setattr(verifier.shutil, "which", lambda _name: "/usr/local/bin/supabase")
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="2.98.2\n", stderr=""),
    )
    monkeypatch.setattr(
        verifier,
        "read_linked_project_ref",
        lambda: ("ycjuzwltwbeudanjykag", "test"),
    )

    checks = check_supabase_cli(
        VerificationConfig(strict=True),
        project_list_runner=lambda _config: (
            0,
            json.dumps([{"ref": "ycjuzwltwbeudanjykag"}]),
            "",
        ),
    )

    assert _status_by_name(checks) == {
        "supabase_cli_available": "pass",
        "supabase_access_token_shape": "pass",
        "supabase_project_list": "pass",
        "supabase_linked_project_ref": "pass",
    }


def test_cli_linked_project_mismatch_fails(monkeypatch) -> None:
    """A local Supabase link to another project is a release blocker."""
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.setattr(verifier.shutil, "which", lambda _name: "/usr/local/bin/supabase")
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="2.98.2\n", stderr=""),
    )
    monkeypatch.setattr(verifier, "read_linked_project_ref", lambda: ("other-ref", "test"))

    checks = check_supabase_cli(
        VerificationConfig(strict=True),
        project_list_runner=lambda _config: (
            0,
            json.dumps([{"ref": "ycjuzwltwbeudanjykag"}]),
            "",
        ),
    )

    assert _status_by_name(checks)["supabase_linked_project_ref"] == "fail"


def test_storage_bucket_checks_accept_required_private_buckets(monkeypatch) -> None:
    """Storage checks pass when both required buckets are present and private."""
    _set_base_env(monkeypatch)
    checks = check_storage(
        VerificationConfig(),
        bucket_lister=lambda _config: [
            {"name": "ajin-attachments", "public": False},
            {"name": "ajin-draft-exports", "public": False},
        ],
    )

    assert _status_by_name(checks) == {
        "storage_api_access": "pass",
        "storage_buckets_present": "pass",
        "storage_buckets_private": "pass",
    }


def test_storage_missing_bucket_fails(monkeypatch) -> None:
    """A missing required Storage bucket is a verifier failure."""
    _set_base_env(monkeypatch)
    checks = check_storage(
        VerificationConfig(),
        bucket_lister=lambda _config: [{"name": "ajin-attachments", "public": False}],
    )

    assert _status_by_name(checks)["storage_buckets_present"] == "fail"


def test_markdown_report_redacts_secrets(monkeypatch, tmp_path) -> None:
    """Markdown output must not include keys or database passwords."""
    _set_base_env(monkeypatch)
    report = run_verification(VerificationConfig(), include_db=False, include_storage=False)
    output_path = tmp_path / "remote-check.md"

    write_markdown_report(report, output_path)
    text = output_path.read_text(encoding="utf-8")

    assert "SUPER_PRIVATE_VALUE" not in text
    assert "db-password" not in text
    assert "ycjuzwltwbeudanjykag" in text


def test_admin_supabase_health_is_sanitized_and_cache_safe(monkeypatch) -> None:
    """Admin health reports only booleans/status and does not leak secrets."""
    _set_base_env(monkeypatch)
    monkeypatch.setattr(
        verifier,
        "check_database",
        lambda _config: [
            CheckResult("database_connected", "pass", "ok"),
            CheckResult("alembic_current", "pass", "ok"),
            CheckResult("sensitive_role_grants", "pass", "ok"),
            CheckResult("data_api_deny_policies", "pass", "ok"),
            CheckResult("default_admin_risk", "pass", "ok"),
        ],
    )
    monkeypatch.setattr(
        verifier,
        "check_storage",
        lambda _config: [CheckResult("storage_buckets_present", "pass", "ok")],
    )

    health = collect_sanitized_supabase_health(use_cache=False)
    encoded = json.dumps(health, ensure_ascii=False)

    assert health["status"] == "ok"
    assert health["database_connected"] is True
    assert health["data_api_locked_down"] is True
    assert health["default_admin_risk"] is False
    assert health["storage_buckets_present"] is True
    assert "SUPER_PRIVATE_VALUE" not in encoded
    assert "db-password" not in encoded
