#!/usr/bin/env python3
"""Verify Feature E auth/admin release hardening posture.

The verifier is secret-safe. It checks endpoint surface, cookie auth wiring,
frontend token persistence removal, production session requirements, and active
default/demo account blockers without printing credential values.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC_REFERENCES = (
    "https://fastapi.tiangolo.com/tutorial/security/",
    "https://fastapi.tiangolo.com/tutorial/dependencies/",
    "https://owasp.org/www-project-application-security-verification-standard/",
    "https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html",
    "https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html",
    "https://openid.net/specs/openid-connect-core-1_0.html",
    "https://pages.nist.gov/800-63-4/sp800-63b.html",
    "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie",
    "https://fastapi.tiangolo.com/advanced/response-cookies/",
)
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head"}
EXPECTED_TAG_COUNTS = {
    "auth": 12,
    "idp": 5,
    "admin": 48,
    "admin-scenarios": 9,
}
REQUIRED_ROUTES: Mapping[str, set[str]] = {
    "/api/auth/login": {"post"},
    "/api/auth/refresh": {"post"},
    "/api/auth/me": {"get", "put"},
    "/api/auth/change-password": {"post"},
    "/api/auth/2fa/verify": {"post"},
    "/api/auth/idp/capabilities": {"get"},
    "/api/auth/idp/{provider}/callback": {"get"},
    "/api/auth/idp/ldap/login": {"post"},
    "/api/admin/system/health-extended": {"get"},
    "/api/admin/permissions/queue": {"get"},
    "/api/admin/scenarios": {"get"},
}
FRONTEND_FORBIDDEN_MARKERS = {
    "frontend/src/store/auth.ts": (
        "accessToken:",
        "refreshToken:",
        "setTokens",
        "setAccessToken",
    ),
    "frontend/src/api/client.ts": (
        "Authorization",
        "Bearer",
        "refresh_token",
        "access_token",
    ),
    "frontend/src/components/auth/AuthBootstrap.tsx": (
        "ajin_access",
        "ajin_refresh",
        "setTokens",
    ),
}
DEMO_EMPLOYEE_IDS = {"SYS-0001", "HR-0001", "QA-0001", "PE-0019", "admin"}


@dataclass(frozen=True)
class CheckResult:
    """Single release check result.

    Args:
        name: Stable machine-readable check name.
        status: One of pass, warn, fail, or skip.
        summary: Human-readable secret-safe summary.
        details: Optional secret-safe metadata.
    """

    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable check."""

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class FeatureEConfig:
    """Runtime configuration for the Feature E verifier.

    Args:
        root: Repository root.
        openapi_path: OpenAPI JSON path.
        auth_db_path: SQLite auth DB path to inspect for default accounts.
        strict: Whether fail checks should return a non-zero exit code.
    """

    root: Path = ROOT
    openapi_path: Path = ROOT / "docs" / "openapi.json"
    auth_db_path: Path = ROOT / "data" / "auth.db"
    strict: bool = False


def _is_production_env() -> bool:
    return (
        os.environ.get("APP_ENV", "").strip().lower() == "production"
        or os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
        or bool(os.environ.get("K_SERVICE"))
    )


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _load_openapi(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _count_operations_by_tag(openapi: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in openapi.get("paths", {}).values():
        if not isinstance(item, Mapping):
            continue
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, Mapping):
                continue
            for tag in operation.get("tags", []):
                counts[str(tag)] = counts.get(str(tag), 0) + 1
    return counts


def verify_endpoint_surface(config: FeatureEConfig) -> CheckResult:
    """Verify Feature E OpenAPI tag counts and required routes."""

    openapi = _load_openapi(config.openapi_path)
    counts = _count_operations_by_tag(openapi)
    paths = openapi.get("paths", {})
    missing_counts = {
        tag: {"expected": expected, "actual": counts.get(tag, 0)}
        for tag, expected in EXPECTED_TAG_COUNTS.items()
        if counts.get(tag, 0) != expected
    }
    missing_required: dict[str, list[str]] = {}
    for route, methods in REQUIRED_ROUTES.items():
        operations = paths.get(route, {})
        present = {m for m in operations.keys() if m.lower() in HTTP_METHODS}
        missing = sorted(methods - present)
        if missing:
            missing_required[route] = missing

    if missing_counts or missing_required:
        return CheckResult(
            "feature_e_endpoint_surface",
            "fail",
            "Feature E endpoint surface does not match the release baseline.",
            {
                "counts": {tag: counts.get(tag, 0) for tag in EXPECTED_TAG_COUNTS},
                "missing_counts": missing_counts,
                "missing_required": missing_required,
            },
        )
    return CheckResult(
        "feature_e_endpoint_surface",
        "pass",
        "Feature E endpoint surface matches the 74-operation baseline.",
        {"counts": {tag: counts.get(tag, 0) for tag in EXPECTED_TAG_COUNTS}},
    )


def verify_cookie_csrf_wiring(config: FeatureEConfig) -> CheckResult:
    """Verify backend cookie names, paths, HttpOnly split, and CSRF middleware wiring."""

    from core.auth.cookies import (
        ACCESS_COOKIE_NAME,
        CSRF_COOKIE_NAME,
        REFRESH_COOKIE_NAME,
        resolve_auth_cookie_settings,
    )

    settings = resolve_auth_cookie_settings()
    files = {
        "cookies": config.root / "core/auth/cookies.py",
        "csrf_middleware": config.root / "backend/csrf_middleware.py",
        "auth_router": config.root / "backend/routers/auth.py",
        "idp_router": config.root / "backend/routers/idp.py",
    }
    missing_files = [str(path.relative_to(config.root)) for path in files.values() if not path.exists()]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files.values() if path.exists())
    required_markers = [
        ACCESS_COOKIE_NAME,
        REFRESH_COOKIE_NAME,
        CSRF_COOKIE_NAME,
        "httponly=True",
        "httponly=False",
        "samesite=settings.samesite",
        "path=settings.access_path",
        "path=settings.refresh_path",
        "path=settings.csrf_path",
        "csrf_matches_request",
        "set_auth_cookies",
        "clear_auth_cookies",
    ]
    missing_markers = [marker for marker in required_markers if marker not in text]
    if missing_files or missing_markers:
        return CheckResult(
            "cookie_csrf_wiring",
            "fail",
            "Cookie/CSRF implementation wiring is incomplete.",
            {"missing_files": missing_files, "missing_markers": missing_markers},
        )
    return CheckResult(
        "cookie_csrf_wiring",
        "pass",
        "HttpOnly access/refresh cookies and JS-readable CSRF cookie are wired.",
        {
            "cookies": [ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME],
            "paths": {
                ACCESS_COOKIE_NAME: settings.access_path,
                REFRESH_COOKIE_NAME: settings.refresh_path,
                CSRF_COOKIE_NAME: settings.csrf_path,
            },
            "samesite": settings.samesite,
            "secure_runtime": settings.secure,
        },
    )


def verify_frontend_token_posture(config: FeatureEConfig) -> CheckResult:
    """Fail when frontend auth reintroduces token persistence or query tokens."""

    violations: dict[str, list[str]] = {}
    for rel_path, markers in FRONTEND_FORBIDDEN_MARKERS.items():
        path = config.root / rel_path
        if not path.exists():
            violations[rel_path] = ["missing_file"]
            continue
        text = path.read_text(encoding="utf-8")
        found = [marker for marker in markers if marker in text]
        if found:
            violations[rel_path] = found
    if violations:
        return CheckResult(
            "frontend_browser_token_posture",
            "fail",
            "Frontend still exposes or persists browser auth tokens.",
            {"violations": violations},
        )
    return CheckResult(
        "frontend_browser_token_posture",
        "pass",
        "Frontend stores only user profile metadata and uses cookie auth.",
    )


def verify_production_environment_gate(_: FeatureEConfig) -> CheckResult:
    """Verify production-only auth/session environment requirements."""

    from core.auth.policy import auth_primary_provider

    production = _is_production_env()
    try:
        primary_provider = auth_primary_provider()
    except ValueError as exc:
        primary_provider = "invalid"
        provider_error = str(exc)
    else:
        provider_error = ""
    details: dict[str, Any] = {
        "production_detected": production,
        "AUTH_PRIMARY_PROVIDER": primary_provider,
    }
    blockers: list[str] = []
    warnings: list[str] = []

    if primary_provider == "invalid":
        blockers.append("AUTH_PRIMARY_PROVIDER_invalid")
    if production:
        if primary_provider != "idp":
            blockers.append("AUTH_PRIMARY_PROVIDER_must_be_idp")
        jwt_secret = os.environ.get("AJIN_JWT_SECRET", "")
        if len(jwt_secret) < 32:
            blockers.append("AJIN_JWT_SECRET_missing_or_too_short")
        if os.environ.get("SESSION_STORE", "").strip().lower() != "redis":
            blockers.append("SESSION_STORE_must_be_redis")
        if not os.environ.get("REDIS_URL"):
            blockers.append("REDIS_URL_missing")
        if os.environ.get("AUTH_COOKIE_SECURE", "").strip().lower() == "false":
            blockers.append("AUTH_COOKIE_SECURE_false_in_production")
        if _truthy("AUTH_BOOTSTRAP_ADMIN_ENABLED"):
            blockers.append("AUTH_BOOTSTRAP_ADMIN_ENABLED_true")
        if _truthy("AUTH_ALLOW_LEGACY_ADMIN"):
            blockers.append("AUTH_ALLOW_LEGACY_ADMIN_true")
        if _truthy("AUTH_SEED_TEST_USERS"):
            blockers.append("AUTH_SEED_TEST_USERS_true")
        if _truthy("AUTH_ALLOW_HARD_DELETE"):
            blockers.append("AUTH_ALLOW_HARD_DELETE_true")
        if _truthy("AUTH_ALLOW_PLAINTEXT_INITIAL_PASSWORD"):
            blockers.append("AUTH_ALLOW_PLAINTEXT_INITIAL_PASSWORD_true")
        if _truthy("ALLOW_BEARER_AUTH"):
            warnings.append("ALLOW_BEARER_AUTH_enabled_for_automation_exception")
    else:
        details["release_note"] = "production env not detected; runtime secret/session checks are advisory locally"

    details.update(
        {
            "AJIN_JWT_SECRET_present": bool(os.environ.get("AJIN_JWT_SECRET")),
            "SESSION_STORE": os.environ.get("SESSION_STORE", ""),
            "REDIS_URL_present": bool(os.environ.get("REDIS_URL")),
            "provider_error": provider_error,
            "blockers": blockers,
            "warnings": warnings,
        }
    )
    if blockers:
        return CheckResult(
            "production_auth_environment",
            "fail",
            "Production auth/session environment is not release-safe.",
            details,
        )
    if warnings:
        return CheckResult(
            "production_auth_environment",
            "warn",
            "Production auth/session environment has automation exceptions enabled.",
            details,
        )
    return CheckResult(
        "production_auth_environment",
        "pass",
        "Production auth/session environment gate passed or is advisory locally.",
        details,
    )


def verify_default_account_gate(config: FeatureEConfig) -> CheckResult:
    """Check active default/demo accounts in auth.db."""

    production = _is_production_env()
    if not config.auth_db_path.exists():
        return CheckResult(
            "default_account_gate",
            "warn",
            "auth.db was not found; default account posture could not be inspected locally.",
            {"auth_db_path": str(config.auth_db_path.relative_to(config.root)) if config.auth_db_path.is_relative_to(config.root) else str(config.auth_db_path)},
        )

    conn = sqlite3.connect(str(config.auth_db_path))
    conn.row_factory = sqlite3.Row
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        select_columns = ["employee_id", "username", "is_active"]
        if "data_class" in columns:
            select_columns.append("data_class")
        if "source_system" in columns:
            select_columns.append("source_system")
        predicates = ["employee_id IN ({})".format(",".join("?" for _ in DEMO_EMPLOYEE_IDS))]
        params: list[Any] = list(sorted(DEMO_EMPLOYEE_IDS))
        if "data_class" in columns:
            predicates.append("lower(coalesce(data_class, '')) IN ('synthetic', 'demo')")
        if "source_system" in columns:
            predicates.append(
                "lower(coalesce(source_system, '')) IN ('seed_test_users', 'mock_seed', 'demo')"
            )
        rows = conn.execute(
            f"""SELECT {", ".join(select_columns)}
                  FROM users
                 WHERE {" OR ".join(predicates)}
                 ORDER BY employee_id""",
            tuple(params),
        ).fetchall()
    finally:
        conn.close()

    active = [row["employee_id"] for row in rows if int(row["is_active"] or 0) == 1]
    active_synthetic = [
        row["employee_id"]
        for row in rows
        if int(row["is_active"] or 0) == 1
        and (
            ("data_class" in row.keys() and str(row["data_class"] or "").lower() in {"synthetic", "demo"})
            or (
                "source_system" in row.keys()
                and str(row["source_system"] or "").lower() in {"seed_test_users", "mock_seed", "demo"}
            )
        )
    ]
    details = {
        "active_default_or_demo_accounts": active,
        "active_synthetic_or_demo_accounts": active_synthetic,
        "production_detected": production,
    }
    if active and production:
        return CheckResult(
            "default_account_gate",
            "fail",
            "Active default/demo accounts are production blockers.",
            details,
        )
    if active:
        return CheckResult(
            "default_account_gate",
            "warn",
            "Active default/demo accounts found in local auth.db; production must disable them.",
            details,
        )
    return CheckResult(
        "default_account_gate",
        "pass",
        "No active default/demo account rows found.",
        details,
    )


def verify_feature_e_policy_wiring(config: FeatureEConfig) -> CheckResult:
    """Verify IdP-first and admin hardening policy markers are wired."""

    files = {
        "policy": config.root / "core/auth/policy.py",
        "auth_router": config.root / "backend/routers/auth.py",
        "admin_router": config.root / "backend/routers/admin.py",
        "demo_accounts": config.root / "frontend/src/lib/demoAccounts.ts",
    }
    missing_files = [str(path.relative_to(config.root)) for path in files.values() if not path.exists()]
    text_by_name = {
        name: path.read_text(encoding="utf-8") for name, path in files.items() if path.exists()
    }
    required_markers = {
        "policy": [
            "AUTH_PRIMARY_PROVIDER",
            "local_password_login_block_reason",
            "AUTH_SEED_TEST_USERS",
            "AUTH_ALLOW_HARD_DELETE",
            "AuditRetentionPolicy",
        ],
        "auth_router": ["local_password_login_block_reason", "login_policy_block"],
        "admin_router": [
            "resolve_user_role_level",
            "plaintext_initial_password_allowed",
            "hard_delete_disabled",
        ],
        "demo_accounts": ["import.meta.env.PROD", "VITE_DEMO_CHIPS_ENABLED"],
    }
    missing_markers: dict[str, list[str]] = {}
    for name, markers in required_markers.items():
        text = text_by_name.get(name, "")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            missing_markers[name] = missing

    if missing_files or missing_markers:
        return CheckResult(
            "feature_e_policy_wiring",
            "fail",
            "Feature E IdP-first/admin hardening policy wiring is incomplete.",
            {"missing_files": missing_files, "missing_markers": missing_markers},
        )
    return CheckResult(
        "feature_e_policy_wiring",
        "pass",
        "IdP-first login, admin plaintext suppression, hard-delete guard, and demo-chip gate are wired.",
    )


def verify_audit_retention_policy(_: FeatureEConfig) -> CheckResult:
    """Verify the default audit retention policy is fail-closed."""

    from core.auth.policy import audit_retention_policy

    policy = audit_retention_policy()
    details = {
        "hot_days": policy.hot_days,
        "archive_years": policy.archive_years,
        "hard_delete_default": policy.hard_delete_default,
    }
    if policy.hot_days < 365 or policy.archive_years < 3 or policy.hard_delete_default:
        return CheckResult(
            "audit_retention_policy",
            "fail",
            "Feature E audit retention policy is weaker than the release baseline.",
            details,
        )
    return CheckResult(
        "audit_retention_policy",
        "pass",
        "Feature E audit retention defaults to 1 year hot, 3 years archive, hard delete off.",
        details,
    )


def run_verification(config: FeatureEConfig) -> dict[str, Any]:
    """Run all Feature E release checks."""

    checks = [
        verify_endpoint_surface(config),
        verify_cookie_csrf_wiring(config),
        verify_frontend_token_posture(config),
        verify_feature_e_policy_wiring(config),
        verify_production_environment_gate(config),
        verify_default_account_gate(config),
        verify_audit_retention_policy(config),
    ]
    statuses = [check.status for check in checks]
    overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {
        "feature": "E",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "status": overall,
            "pass": statuses.count("pass"),
            "warn": statuses.count("warn"),
            "fail": statuses.count("fail"),
        },
        "checks": [check.to_dict() for check in checks],
        "references": list(DOC_REFERENCES),
    }


def write_markdown(report: Mapping[str, Any], path: Path) -> None:
    """Write a secret-safe Markdown report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Feature E Release Hardening Check",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Overall: `{report['summary']['status']}`",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        lines.extend(
            [
                f"### {check['name']}",
                "",
                f"- Status: `{check['status']}`",
                f"- Summary: {check['summary']}",
                "",
                "```json",
                json.dumps(check.get("details", {}), ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    lines.extend(["## References", ""])
    lines.extend(f"- {url}" for url in report.get("references", []))
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any check fails.")
    parser.add_argument("--markdown", type=Path, help="Write a Markdown report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--openapi", type=Path, default=ROOT / "docs" / "openapi.json")
    parser.add_argument("--auth-db", type=Path, default=ROOT / "data" / "auth.db")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config = FeatureEConfig(openapi_path=args.openapi, auth_db_path=args.auth_db, strict=args.strict)
    report = run_verification(config)
    if args.markdown:
        write_markdown(report, args.markdown)
        print(f"[feature-e] wrote {args.markdown}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.markdown and not args.json:
        print(f"[feature-e] status={report['summary']['status']}")
    return 1 if args.strict and report["summary"]["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
