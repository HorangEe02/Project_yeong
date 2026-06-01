"""Tests for Cloud Run Supabase runtime configuration planning."""

from __future__ import annotations

import json

import pytest

from scripts.configure_cloudrun_supabase_runtime import (
    CommandResult,
    apply_runtime_configuration,
    build_runtime_plan,
    verify_service_runtime_mapping,
)


def _set_base_env(monkeypatch) -> None:
    """Set the minimum local env needed for a runtime plan.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """

    monkeypatch.setenv("SUPABASE_PROJECT_REF", "ycjuzwltwbeudanjykag")
    monkeypatch.setenv("SUPABASE_URL", "https://ycjuzwltwbeudanjykag.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_PUBLIC_VALUE")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:db-password@example.supabase.co/postgres")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_SUPER_PRIVATE_VALUE")
    monkeypatch.setenv("AJIN_JWT_SECRET", "jwt-secret-32-byte-test-value-0001")
    monkeypatch.setenv("LAW_GO_KR_OC", "law-oc-test-value")
    monkeypatch.setenv("CUSTOMS_API_KEY", "customs-api-key-test-value")
    monkeypatch.setenv("DART_API_KEY", "dart-api-key-test-value")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET_ATTACHMENTS", "ajin-attachments")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS", "ajin-draft-exports")


def test_build_runtime_plan_is_secret_safe_and_excludes_deploy_only_env(monkeypatch) -> None:
    """Runtime planning maps only expected env names to Cloud Run."""

    _set_base_env(monkeypatch)

    plan = build_runtime_plan(
        project="ajin-cb",
        region="asia-northeast3",
        service="ajin-backend",
        project_ref="ycjuzwltwbeudanjykag",
    )

    assert "SUPABASE_ACCESS_TOKEN" not in plan.runtime_env
    assert "SUPABASE_DB_PASSWORD" not in plan.runtime_env
    assert "SMOKE_ADMIN_JWT" not in plan.runtime_env
    assert plan.runtime_env["APP_DB_BACKEND"] == "postgres"
    assert plan.runtime_env["FIREBASE_WRITE_ENABLED"] == "false"
    assert plan.secret_env_map == {
        "DATABASE_URL": "AJIN_DATABASE_URL",
        "SUPABASE_SECRET_KEY": "AJIN_SUPABASE_SECRET_KEY",
        "AJIN_JWT_SECRET": "AJIN_JWT_SECRET",
        "LAW_GO_KR_OC": "law-oc",
        "CUSTOMS_API_KEY": "customs-api-key",
        "DART_API_KEY": "dart-api-key",
    }
    assert sorted(plan.secret_values) == [
        "AJIN_DATABASE_URL",
        "AJIN_JWT_SECRET",
        "AJIN_SUPABASE_SECRET_KEY",
        "customs-api-key",
        "dart-api-key",
        "law-oc",
    ]


def test_build_runtime_plan_rejects_missing_jwt_secret(monkeypatch) -> None:
    """The helper fails closed when no JWT source is available."""

    _set_base_env(monkeypatch)
    monkeypatch.delenv("AJIN_JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="AJIN_JWT_SECRET"):
        build_runtime_plan(
            project="ajin-cb",
            region="asia-northeast3",
            service="ajin-backend",
            project_ref="ycjuzwltwbeudanjykag",
        )


def test_build_runtime_plan_allows_missing_optional_feature_d_secrets(monkeypatch) -> None:
    """Feature D official API secrets are optional for deployment fallback posture."""

    _set_base_env(monkeypatch)
    monkeypatch.delenv("CUSTOMS_API_KEY", raising=False)

    plan = build_runtime_plan(
        project="ajin-cb",
        region="asia-northeast3",
        service="ajin-backend",
        project_ref="ycjuzwltwbeudanjykag",
    )

    assert "CUSTOMS_API_KEY" not in plan.secret_env_map
    assert "customs-api-key" not in plan.secret_values
    assert plan.secret_env_map["LAW_GO_KR_OC"] == "law-oc"
    assert plan.secret_env_map["DART_API_KEY"] == "dart-api-key"


def test_verify_service_mapping_rejects_banned_runtime_env(monkeypatch) -> None:
    """Deploy-local Supabase access tokens must not be present in Cloud Run."""

    _set_base_env(monkeypatch)
    plan = build_runtime_plan(
        project="ajin-cb",
        region="asia-northeast3",
        service="ajin-backend",
        project_ref="ycjuzwltwbeudanjykag",
    )
    service_spec = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "env": [
                                {"name": "SUPABASE_ACCESS_TOKEN", "value": "sbp_DO_NOT_INJECT"},
                            ]
                        }
                    ]
                }
            }
        }
    }

    issues = verify_service_runtime_mapping(service_spec, plan, require_expected=False)

    assert [issue.name for issue in issues] == ["SUPABASE_ACCESS_TOKEN"]


def test_verify_service_mapping_rejects_plain_secret_env(monkeypatch) -> None:
    """Secret-backed runtime fields must use Secret Manager references."""

    _set_base_env(monkeypatch)
    plan = build_runtime_plan(
        project="ajin-cb",
        region="asia-northeast3",
        service="ajin-backend",
        project_ref="ycjuzwltwbeudanjykag",
    )
    service_spec = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "env": [
                                {"name": "DATABASE_URL", "value": "postgresql://leaked"},
                            ]
                        }
                    ]
                }
            }
        }
    }

    issues = verify_service_runtime_mapping(service_spec, plan, require_expected=False)

    assert [issue.name for issue in issues] == ["DATABASE_URL"]
    assert "plain value" in issues[0].message


class FakeRunner:
    """Fake gcloud runner that records commands without touching Google Cloud."""

    def __init__(self) -> None:
        """Initialize command capture."""

        self.calls: list[tuple[list[str], str | None, bool]] = []

    def __call__(self, args: list[str], input_text: str | None, check: bool) -> CommandResult:
        """Return deterministic gcloud-like responses.

        Args:
            args: Command arguments.
            input_text: Optional stdin payload.
            check: Whether the caller expects failure to raise.

        Returns:
            CommandResult: Fake command result.
        """

        self.calls.append((args, input_text, check))
        if args[:5] == ["gcloud", "beta", "billing", "projects", "describe"]:
            return CommandResult(0, json.dumps({"billingEnabled": True}), "")
        if args[:4] == ["gcloud", "run", "services", "describe"]:
            if args[-1] == "--format=value(spec.template.spec.serviceAccountName)":
                return CommandResult(0, "service-account@example.iam.gserviceaccount.com\n", "")
            return CommandResult(
                0,
                json.dumps(
                    {
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "env": [
                                                {"name": "ENABLE_FEATURE_A", "value": "false"},
                                            ]
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ),
                "",
            )
        if args[:3] == ["gcloud", "secrets", "describe"]:
            return CommandResult(1, "", "not found")
        return CommandResult(0, "", "")


def test_apply_creates_secret_versions_and_grants_iam_without_secret_args(monkeypatch) -> None:
    """Apply mode sends secret payloads through stdin, not command arguments."""

    _set_base_env(monkeypatch)
    plan = build_runtime_plan(
        project="ajin-cb",
        region="asia-northeast3",
        service="ajin-backend",
        project_ref="ycjuzwltwbeudanjykag",
    )
    runner = FakeRunner()

    result = apply_runtime_configuration(plan, runner)

    flattened_args = " ".join(" ".join(args) for args, _input_text, _check in runner.calls)
    secret_inputs = [input_text for _args, input_text, _check in runner.calls if input_text]
    assert result["billing_enabled"] is True
    assert sorted(result["secrets_created"]) == [
        "AJIN_DATABASE_URL",
        "AJIN_JWT_SECRET",
        "AJIN_SUPABASE_SECRET_KEY",
        "customs-api-key",
        "dart-api-key",
        "law-oc",
    ]
    assert "db-password" not in flattened_args
    assert "SUPER_PRIVATE" not in flattened_args
    assert "jwt-secret" not in flattened_args
    assert "customs-api-key-test-value" not in flattened_args
    assert "law-oc-test-value" not in flattened_args
    assert "dart-api-key-test-value" not in flattened_args
    assert any("db-password" in value for value in secret_inputs)
    assert any("SUPER_PRIVATE" in value for value in secret_inputs)
    assert any("jwt-secret" in value for value in secret_inputs)
    assert any("customs-api-key-test-value" in value for value in secret_inputs)
