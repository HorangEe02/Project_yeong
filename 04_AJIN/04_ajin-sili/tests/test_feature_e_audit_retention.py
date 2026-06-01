"""Feature E audit retention and redaction tests."""

from __future__ import annotations

import sqlite3

import scripts.verify_feature_e_release as verifier
from backend.auth_middleware import get_audit_logs, log_api_access
from core.auth.audit_redaction import contains_sensitive_audit_marker, redact_audit_detail


def test_audit_detail_redacts_password_token_and_csrf_values() -> None:
    """Audit details must not preserve credential-like raw values."""

    detail = "password=Secret!234 token=abc.def csrf=csrf-value normal=ok"
    redacted = redact_audit_detail(detail)

    assert "Secret!234" not in redacted
    assert "abc.def" not in redacted
    assert "csrf-value" not in redacted
    assert "normal=ok" in redacted
    assert contains_sensitive_audit_marker(redacted) is False


def test_log_api_access_writes_redacted_detail(tmp_path) -> None:
    """SQLite audit rows store redacted detail values."""

    audit_db = tmp_path / "audit.db"
    log_api_access(
        endpoint="/api/admin/users/E001/reset-password",
        method="POST",
        status_code=200,
        detail='{"password":"Secret!234","token":"abc.def","result":"ok"}',
        db_path=audit_db,
    )

    rows = get_audit_logs(limit=1, db_path=audit_db)
    detail = rows[0]["detail"]
    assert "Secret!234" not in detail
    assert "abc.def" not in detail
    assert "[REDACTED]" in detail


def test_feature_e_retention_policy_verifier_passes() -> None:
    """Release verifier requires 1-year hot and 3-year archive defaults."""

    result = verifier.verify_audit_retention_policy(verifier.FeatureEConfig())

    assert result.status == "pass"
    assert result.details["hot_days"] == 365
    assert result.details["archive_years"] == 3
    assert result.details["hard_delete_default"] is False


def test_default_account_gate_blocks_active_synthetic_user_in_production(tmp_path, monkeypatch) -> None:
    """Active synthetic auth users are production blockers even outside demo ids."""

    db_path = tmp_path / "auth.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE users (
            employee_id TEXT,
            username TEXT,
            is_active INTEGER,
            data_class TEXT,
            source_system TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO users VALUES ('QA-7777', 'synthetic', 1, 'synthetic', 'seed_test_users')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_ENV", "production")

    result = verifier.verify_default_account_gate(verifier.FeatureEConfig(auth_db_path=db_path))

    assert result.status == "fail"
    assert result.details["active_synthetic_or_demo_accounts"] == ["QA-7777"]


def test_production_environment_gate_requires_idp_provider(monkeypatch) -> None:
    """Production release gate fails if local auth is primary."""

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_PRIMARY_PROVIDER", "local")
    monkeypatch.setenv("AJIN_JWT_SECRET", "x" * 40)
    monkeypatch.setenv("SESSION_STORE", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    result = verifier.verify_production_environment_gate(verifier.FeatureEConfig())

    assert result.status == "fail"
    assert "AUTH_PRIMARY_PROVIDER_must_be_idp" in result.details["blockers"]
