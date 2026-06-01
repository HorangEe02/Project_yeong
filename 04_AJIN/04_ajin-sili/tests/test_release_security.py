"""Tests for release security guardrails."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_release_security import (
    check_admin_health_json,
    check_api_access_policy,
    check_cloud_run_service_json,
    check_leak_prevention_policy,
    check_rbac_policy,
    check_source_markers,
    scan_frontend_for_secret_exposure,
    summarize_supabase_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_frontend(root, relative: str, content: str) -> None:
    """Write a frontend fixture file.

    Args:
        root: Temporary repository root.
        relative: Path relative to the temporary root.
        content: File content.
    """

    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _supabase_report(statuses: dict[str, str]) -> dict:
    """Build a minimal Supabase verifier report.

    Args:
        statuses: Check name to status mapping.

    Returns:
        dict: Verifier-like report.
    """

    return {"checks": [{"name": name, "status": status} for name, status in statuses.items()]}


def test_frontend_scan_passes_without_backend_secret_markers(tmp_path) -> None:
    """Frontend scan allows public Vite/Firebase env values only."""

    _write_frontend(
        tmp_path,
        "frontend/src/main.ts",
        "const apiBase = import.meta.env.VITE_API_BASE_URL;\n",
    )
    _write_frontend(
        tmp_path,
        "frontend/.env.development",
        "VITE_API_BASE_URL=http://localhost:8000/api\nVITE_FIREBASE_DATABASE_URL=https://example.invalid\n",
    )

    result = scan_frontend_for_secret_exposure(tmp_path)

    assert result.status == "pass"


def test_frontend_scan_rejects_supabase_secret_and_vite_database_url(tmp_path) -> None:
    """Frontend scan fails on backend-only Supabase secret markers."""

    _write_frontend(
        tmp_path,
        "frontend/src/leak.ts",
        "const leaked = 'sb_secret_TEST_VALUE';\n",
    )
    _write_frontend(
        tmp_path,
        "frontend/.env.production",
        "VITE_DATABASE_URL=postgresql://app:secret@example.invalid/postgres\n",
    )

    result = scan_frontend_for_secret_exposure(tmp_path)
    encoded = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.status == "fail"
    assert "sb_secret_TEST_VALUE" not in encoded
    assert "app:secret" not in encoded
    assert "frontend/src/leak.ts" in encoded
    assert "frontend/.env.production" in encoded


def test_supabase_summary_requires_rls_and_data_api_checks() -> None:
    """Supabase guard passes only when all required verifier checks are pass."""

    passing = _supabase_report(
        {
            "required_tables_rls_enabled": "pass",
            "sensitive_role_grants": "pass",
            "data_api_deny_policies": "pass",
            "default_admin_risk": "pass",
        }
    )
    failing = _supabase_report(
        {
            "required_tables_rls_enabled": "pass",
            "sensitive_role_grants": "fail",
            "data_api_deny_policies": "pass",
            "default_admin_risk": "pass",
        }
    )

    assert summarize_supabase_report(passing).status == "pass"
    assert summarize_supabase_report(failing).status == "fail"


def test_cloud_run_json_rejects_deploy_local_and_plain_secret_env() -> None:
    """Cloud Run service JSON must not contain deploy-local values or plain secrets."""

    service_spec = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "env": [
                                {"name": "SUPABASE_ACCESS_TOKEN", "value": "sbp_DO_NOT_PRINT"},
                                {"name": "DATABASE_URL", "value": "postgresql://leaked"},
                            ]
                        }
                    ]
                }
            }
        }
    }

    result = check_cloud_run_service_json(service_spec)
    encoded = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.status == "fail"
    assert "sbp_DO_NOT_PRINT" not in encoded
    assert "postgresql://leaked" not in encoded


def test_admin_health_json_rejects_secret_fields_and_fallback_enabled() -> None:
    """Admin health JSON must expose status posture, not raw secret fields."""

    result = check_admin_health_json(
        {
            "firebase_write_enabled": False,
            "firebase_read_fallback_enabled": True,
            "external": {"supabase": {"status": "ok", "secret_key": "sb_secret_DO_NOT_PRINT"}},
        }
    )
    encoded = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.status == "fail"
    assert "sb_secret_DO_NOT_PRINT" not in encoded


def test_admin_health_json_accepts_secret_safe_fallback_off_payload() -> None:
    """Admin health JSON accepts status-only Supabase posture."""

    result = check_admin_health_json(
        {
            "sections": {
                "external": {
                    "firebase_write_enabled": False,
                    "firebase_read_fallback_enabled": False,
                    "supabase": {"status": "ok", "database_connected": True},
                }
            },
        }
    )

    assert result.status == "pass"


def test_api_rbac_and_leak_prevention_source_guards_pass_current_repo() -> None:
    """Release verifier pins auth, RBAC, and leak-prevention source markers."""

    assert check_api_access_policy(PROJECT_ROOT).status == "pass"
    assert check_rbac_policy(PROJECT_ROOT).status == "pass"
    assert check_leak_prevention_policy(PROJECT_ROOT).status == "pass"


def test_source_marker_guard_reports_missing_requirements_secret_safely(tmp_path) -> None:
    """Source marker guard fails closed without echoing source contents."""

    source = tmp_path / "backend/routers/search.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("router = APIRouter(prefix='/search')\nSECRET_VALUE\n", encoding="utf-8")

    result = check_source_markers(
        tmp_path,
        name="example_source_guard",
        markers={
            "search_router_login_required": (
                "backend/routers/search.py",
                ("dependencies=[Depends(get_current_user)]",),
            )
        },
        pass_summary="ok",
        fail_summary="missing marker",
    )
    rendered = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.status == "fail"
    assert "dependencies=[Depends(get_current_user)]" in rendered
    assert "SECRET_VALUE" not in rendered
