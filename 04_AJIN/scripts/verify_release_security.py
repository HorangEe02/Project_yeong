#!/usr/bin/env python3
"""Verify release security guardrails before Firebase removal.

The checks are intentionally secret-safe: findings include file paths, line
numbers, and rule names, but never echo the matched secret-like value.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_supabase_remote import (  # noqa: E402
    DEFAULT_PROJECT_REF,
    VerificationConfig,
    redact_value,
    run_verification,
)

FRONTEND_DIR = "frontend"
TEXT_SUFFIXES = {
    "",
    ".css",
    ".env",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".local",
    ".mjs",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
}
SKIP_DIRS = {
    ".git",
    ".cache",
    ".vite",
    "node_modules",
}
SKIP_SUFFIXES = {
    ".DS_Store",
    ".eot",
    ".map",
    ".otf",
    ".png",
    ".ttf",
    ".wasm",
    ".woff",
    ".woff2",
}
FORBIDDEN_ENV_NAMES = {
    "DATABASE_URL",
    "SMOKE_ADMIN_JWT",
    "SUPABASE_ACCESS_TOKEN",
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_SERVICE_ROLE",
    "VITE_DATABASE_URL",
    "VITE_SUPABASE_ACCESS_TOKEN",
    "VITE_SUPABASE_DB_PASSWORD",
    "VITE_SUPABASE_SECRET_KEY",
    "VITE_SUPABASE_SERVICE_ROLE",
}
FORBIDDEN_ENV_PREFIXES = (
    "VITE_SUPABASE_SECRET",
    "VITE_SUPABASE_SERVICE_ROLE",
)
REQUIRED_SUPABASE_CHECKS = {
    "required_tables_rls_enabled",
    "sensitive_role_grants",
    "data_api_deny_policies",
    "default_admin_risk",
}
BANNED_CLOUD_RUN_ENV = {
    "SMOKE_ADMIN_JWT",
    "SUPABASE_ACCESS_TOKEN",
    "SUPABASE_DB_PASSWORD",
}
REQUIRED_SECRET_BACKED_ENV = {
    "AJIN_JWT_SECRET",
    "DATABASE_URL",
    "SUPABASE_SECRET_KEY",
}


@dataclass(frozen=True)
class PatternRule:
    """A secret-exposure pattern that must not appear in frontend artifacts.

    Args:
        name: Stable rule name used in reports.
        pattern: Compiled regular expression to search per line.
        summary: Human-readable rule summary.
    """

    name: str
    pattern: re.Pattern[str]
    summary: str


@dataclass(frozen=True)
class Finding:
    """A secret-safe finding location.

    Args:
        path: Repository-relative file path.
        line: One-based line number.
        rule: Rule name that matched.
    """

    path: str
    line: int
    rule: str


@dataclass(frozen=True)
class CheckResult:
    """Single release security check result.

    Args:
        name: Stable machine-readable check name.
        status: One of pass, fail, or skip.
        summary: Secret-safe summary.
        details: Optional secret-safe metadata.
    """

    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable result.

        Returns:
            dict[str, Any]: Check fields for console, JSON, or Markdown output.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": redact_value(dict(self.details)),
        }


FRONTEND_PATTERN_RULES = (
    PatternRule(
        "supabase_secret_key_name",
        re.compile(r"\b(?:VITE_)?SUPABASE_SECRET_KEY\b"),
        "Supabase secret keys must stay backend-only.",
    ),
    PatternRule(
        "supabase_access_token_name",
        re.compile(r"\b(?:VITE_)?SUPABASE_ACCESS_TOKEN\b"),
        "Supabase access tokens are deploy-local only.",
    ),
    PatternRule(
        "supabase_db_password_name",
        re.compile(r"\b(?:VITE_)?SUPABASE_DB_PASSWORD\b"),
        "Supabase DB passwords are deploy-local only.",
    ),
    PatternRule(
        "smoke_admin_jwt_name",
        re.compile(r"\bSMOKE_ADMIN_JWT\b"),
        "Smoke JWTs must not be bundled into frontend artifacts.",
    ),
    PatternRule(
        "vite_database_url_name",
        re.compile(r"\bVITE_DATABASE_URL\b"),
        "Database URLs must not be exposed through Vite env.",
    ),
    PatternRule(
        "supabase_service_role_name",
        re.compile(r"\b(?:VITE_)?SUPABASE_SERVICE_ROLE\b|\bservice_role\b"),
        "Supabase service-role access must stay backend-only.",
    ),
    PatternRule(
        "supabase_secret_key_value",
        re.compile(r"\bsb_secret_[A-Za-z0-9_.=-]+"),
        "Supabase sb_secret values must not appear in frontend artifacts.",
    ),
    PatternRule(
        "postgres_url_value",
        re.compile(r"\bpostgres(?:ql)?://[^\s'\"`<>]+", re.IGNORECASE),
        "Raw Postgres URLs must not appear in frontend artifacts.",
    ),
)


def _is_text_candidate(path: Path) -> bool:
    """Return whether a path should be scanned as text.

    Args:
        path: Candidate file path.

    Returns:
        bool: True when the suffix/name is expected to be textual.
    """

    if path.name in SKIP_SUFFIXES or path.suffix in SKIP_SUFFIXES:
        return False
    if path.name.startswith(".env"):
        return True
    return path.suffix in TEXT_SUFFIXES


def _iter_files(base: Path) -> Iterable[Path]:
    """Yield text-like files below a base directory.

    Args:
        base: Directory or file path to scan.

    Yields:
        Path: Text-like file path.
    """

    if not base.exists():
        return
    if base.is_file():
        if _is_text_candidate(base):
            yield base
        return

    for path in base.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(base).parts)
        if parts.intersection(SKIP_DIRS):
            continue
        if _is_text_candidate(path):
            yield path


def frontend_scan_roots(root: Path) -> list[Path]:
    """Return frontend paths that can carry browser-visible data.

    Args:
        root: Repository root.

    Returns:
        list[Path]: Existing directories/files to scan.
    """

    frontend = root / FRONTEND_DIR
    candidates = [
        frontend / "src",
        frontend / "api",
        frontend / "dist",
        frontend / ".vercel",
        frontend / ".env.development",
        frontend / ".env.development.local",
        frontend / ".env.development.local.example",
        frontend / ".env.production",
    ]
    return [path for path in candidates if path.exists()]


def _parse_env_key(line: str) -> str | None:
    """Extract an env key from one dotenv-style line.

    Args:
        line: Raw line text.

    Returns:
        str | None: Parsed key, or None when the line is not an assignment.
    """

    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    if key.startswith("export "):
        key = key[len("export ") :].strip()
    return key or None


def scan_frontend_for_secret_exposure(root: Path) -> CheckResult:
    """Scan frontend source, env files, and built artifacts for backend secrets.

    Args:
        root: Repository root.

    Returns:
        CheckResult: Pass/fail status with secret-safe findings.
    """

    findings: list[Finding] = []
    files_scanned = 0
    for scan_root in frontend_scan_roots(root):
        for path in _iter_files(scan_root):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            files_scanned += 1
            relative = str(path.relative_to(root))
            for line_number, line in enumerate(lines, start=1):
                key = _parse_env_key(line) if path.name.startswith(".env") else None
                if key in FORBIDDEN_ENV_NAMES or (
                    key is not None and any(key.startswith(prefix) for prefix in FORBIDDEN_ENV_PREFIXES)
                ):
                    findings.append(Finding(relative, line_number, "forbidden_frontend_env_name"))
                    continue
                for rule in FRONTEND_PATTERN_RULES:
                    if rule.pattern.search(line):
                        findings.append(Finding(relative, line_number, rule.name))
                        break

    if findings:
        return CheckResult(
            "frontend_secret_exposure",
            "fail",
            "Frontend artifacts contain backend-only Supabase or database secret markers.",
            {
                "files_scanned": files_scanned,
                "finding_count": len(findings),
                "findings": [asdict(item) for item in findings[:50]],
            },
        )
    return CheckResult(
        "frontend_secret_exposure",
        "pass",
        "No backend-only Supabase secret markers found in frontend artifacts.",
        {"files_scanned": files_scanned},
    )


def summarize_supabase_report(report: Mapping[str, Any]) -> CheckResult:
    """Validate RLS/Data API checks from a Supabase verifier report.

    Args:
        report: Report returned by ``scripts.verify_supabase_remote.run_verification``.

    Returns:
        CheckResult: Pass/fail status for required security checks.
    """

    checks = {str(check.get("name")): str(check.get("status")) for check in report.get("checks", [])}
    missing_or_failed = {
        name: checks.get(name, "missing")
        for name in sorted(REQUIRED_SUPABASE_CHECKS)
        if checks.get(name) != "pass"
    }
    if missing_or_failed:
        return CheckResult(
            "supabase_rls_data_api_guard",
            "fail",
            "Supabase RLS/Data API release checks are not all pass.",
            {"failed": missing_or_failed},
        )
    return CheckResult(
        "supabase_rls_data_api_guard",
        "pass",
        "Supabase RLS/Data API release checks are pass.",
        {"required_checks": sorted(REQUIRED_SUPABASE_CHECKS)},
    )


def run_supabase_guard(project_ref: str, *, strict: bool) -> CheckResult:
    """Run the existing Supabase verifier and summarize its security posture.

    Args:
        project_ref: Expected Supabase project reference.
        strict: Whether verifier warnings should fail.

    Returns:
        CheckResult: RLS/Data API security check summary.
    """

    report = run_verification(
        VerificationConfig(project_ref=project_ref, strict=strict),
        include_cli=strict,
        include_db=True,
        include_storage=False,
    )
    summary = report.get("summary", {})
    if summary.get("status") == "fail":
        return CheckResult(
            "supabase_rls_data_api_guard",
            "fail",
            "Supabase verifier failed before RLS/Data API guard could pass.",
            {"summary": summary},
        )
    return summarize_supabase_report(report)


def _cloud_run_env_entries(service_spec: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return first-container env entries from a Cloud Run service JSON.

    Args:
        service_spec: Cloud Run service description.

    Returns:
        list[Mapping[str, Any]]: Environment entries.
    """

    containers = (
        service_spec.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    if not containers:
        return []
    return [entry for entry in containers[0].get("env", []) or [] if isinstance(entry, Mapping)]


def check_cloud_run_service_json(service_spec: Mapping[str, Any]) -> CheckResult:
    """Validate backend-only secret placement in Cloud Run service JSON.

    Args:
        service_spec: Cloud Run service description.

    Returns:
        CheckResult: Pass/fail status.
    """

    entries = _cloud_run_env_entries(service_spec)
    by_name = {str(entry.get("name")): entry for entry in entries if entry.get("name")}
    issues: list[dict[str, str]] = []

    for name in sorted(BANNED_CLOUD_RUN_ENV.intersection(by_name)):
        issues.append({"name": name, "reason": "deploy-local value present in runtime"})

    for name in sorted(REQUIRED_SECRET_BACKED_ENV.intersection(by_name)):
        entry = by_name[name]
        if "value" in entry:
            issues.append({"name": name, "reason": "secret-backed env configured as plain value"})
            continue
        secret_ref = entry.get("valueFrom", {}).get("secretKeyRef", {})
        if not secret_ref.get("name"):
            issues.append({"name": name, "reason": "secret-backed env missing Secret Manager ref"})

    if issues:
        return CheckResult(
            "cloud_run_secret_mapping",
            "fail",
            "Cloud Run runtime contains disallowed or plain secret env mappings.",
            {"issues": issues},
        )
    return CheckResult(
        "cloud_run_secret_mapping",
        "pass",
        "Cloud Run runtime keeps deploy-local values out and secret envs Secret Manager-backed.",
        {"env_count": len(by_name)},
    )


def _flatten_json(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    """Flatten a JSON-like object into key paths and values.

    Args:
        value: JSON-like value.
        prefix: Current key path.

    Yields:
        tuple[str, Any]: Key path and leaf value.
    """

    if isinstance(value, Mapping):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten_json(item, next_prefix)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            yield from _flatten_json(item, next_prefix)
    else:
        yield prefix, value


def _first_json_value_by_leaf_key(payload: Mapping[str, Any], leaf_key: str) -> Any:
    """Return the first JSON value whose key path ends with a target leaf key.

    Args:
        payload: JSON object to search.
        leaf_key: Final key name to find.

    Returns:
        Any: Matching value, or None when absent.
    """

    suffix = f".{leaf_key}"
    for key_path, value in _flatten_json(payload):
        if key_path == leaf_key or key_path.endswith(suffix):
            return value
    return None


def check_admin_health_json(payload: Mapping[str, Any]) -> CheckResult:
    """Validate that admin health output is secret-safe and fallback-off.

    Args:
        payload: Parsed ``/api/admin/system/health-extended`` response.

    Returns:
        CheckResult: Pass/fail status.
    """

    secret_key_pattern = re.compile(
        r"(secret|token|password|database_url|service_role|access_key)", re.IGNORECASE
    )
    secret_value_pattern = re.compile(
        r"\bsb_secret_[A-Za-z0-9_.=-]+|\bpostgres(?:ql)?://[^\s'\"`<>]+",
        re.IGNORECASE,
    )
    issues: list[dict[str, str]] = []
    for key_path, value in _flatten_json(payload):
        if secret_key_pattern.search(key_path):
            issues.append({"path": key_path, "reason": "secret-like field name"})
        if isinstance(value, str) and secret_value_pattern.search(value):
            issues.append({"path": key_path, "reason": "secret-like string value"})

    firebase_write = _first_json_value_by_leaf_key(payload, "firebase_write_enabled")
    firebase_fallback = _first_json_value_by_leaf_key(payload, "firebase_read_fallback_enabled")
    if firebase_write is not False:
        issues.append({"path": "firebase_write_enabled", "reason": "expected false"})
    if firebase_fallback is not False:
        issues.append({"path": "firebase_read_fallback_enabled", "reason": "expected false"})

    if issues:
        return CheckResult(
            "admin_health_secret_safe",
            "fail",
            "Admin health output exposes secret-like fields or fallback is not disabled.",
            {"issues": issues[:50]},
        )
    return CheckResult(
        "admin_health_secret_safe",
        "pass",
        "Admin health output is secret-safe and Firebase fallback is disabled.",
    )


API_ACCESS_POLICY_MARKERS: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "search_router_login_required": (
        "backend/routers/search.py",
        ("dependencies=[Depends(get_current_user)]",),
    ),
    "onboarding_router_login_required": (
        "backend/routers/onboarding.py",
        ("dependencies=[Depends(get_current_user)]",),
    ),
    "models_router_login_required": (
        "backend/routers/models.py",
        ("dependencies=[Depends(get_current_user)]",),
    ),
    "models_invalidate_cache_l5": (
        "backend/routers/models.py",
        ('@router.post("/invalidate-cache", dependencies=[Depends(require_role_level(5))])',),
    ),
    "health_llm_status_l5": (
        "backend/routers/health.py",
        ('"/health/llm-status"', "dependencies=[Depends(require_role_level(5))]"),
    ),
    "draft_diagnose_l5": (
        "backend/routers/draft.py",
        ('"/diagnose"', "dependencies=[Depends(require_role_level(5))]"),
    ),
}

RBAC_POLICY_MARKERS: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "user_context_role_level": (
        "core/auth/user_context.py",
        ("role_level: int = 1",),
    ),
    "role_level_dependency_fallback": (
        "backend/dependencies.py",
        ('getattr(user, "role_level"', "get_role_level", "return 0"),
    ),
    "jwt_restore_role_level": (
        "backend/auth_middleware.py",
        ('raw_role_level = payload.get("role_level")', "role_level=role_level"),
    ),
    "feature_d_uses_common_role_resolver": (
        "backend/routers/compliance.py",
        ("resolve_user_role_level", "return resolve_user_role_level(user)"),
    ),
    "feature_f_uses_common_role_resolver": (
        "backend/routers/equipment.py",
        ("resolve_user_role_level", "return resolve_user_role_level(user)"),
    ),
    "admin_uses_common_role_resolver": (
        "backend/routers/admin.py",
        ("resolve_user_role_level",),
    ),
}

LEAK_PREVENTION_MARKERS: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "diagnostic_url_redaction": (
        "backend/routers/health.py",
        (
            "def redact_diagnostic_url",
            'base_url=safe_base_url',
            'error=f"{type(e).__name__}: connection_failed"',
        ),
    ),
    "draft_diagnose_url_redaction": (
        "backend/routers/draft.py",
        ("safe_ollama_url = redact_diagnostic_url(OLLAMA_BASE_URL)",),
    ),
    "drawing_ocr_path_allowlist": (
        "backend/routers/equipment.py",
        (
            "EQUIPMENT_DRAWING_OCR_ALLOWED_DIRS",
            "drawing_file_forbidden",
            "resolve(strict=False)",
        ),
    ),
    "storage_complete_metadata_verification": (
        "backend/routers/storage.py",
        (
            "get_storage_object_metadata",
            "upload_size_mismatch",
            "upload_content_type_mismatch",
            "record_attachment_storage_verification",
        ),
    ),
    "supabase_storage_metadata_helper": (
        "backend/services/supabase_storage.py",
        ("class StorageObjectMetadata", "def get_storage_object_metadata"),
    ),
}


def check_source_markers(
    root: Path,
    *,
    name: str,
    markers: Mapping[str, tuple[str, tuple[str, ...]]],
    pass_summary: str,
    fail_summary: str,
) -> CheckResult:
    """Validate that release-critical source markers remain present.

    Args:
        root: Repository root.
        name: Stable check name.
        markers: Requirement name to file path and required text snippets.
        pass_summary: Summary used when all markers pass.
        fail_summary: Summary used when any marker is missing.

    Returns:
        CheckResult: Pass/fail result with secret-safe missing marker names.
    """

    missing: list[dict[str, str]] = []
    for requirement, (relative_path, required_markers) in markers.items():
        path = root / relative_path
        if not path.exists():
            missing.append(
                {"requirement": requirement, "path": relative_path, "marker": "<file missing>"}
            )
            continue
        text = path.read_text(encoding="utf-8")
        for marker in required_markers:
            if marker not in text:
                missing.append(
                    {"requirement": requirement, "path": relative_path, "marker": marker}
                )

    if missing:
        return CheckResult(
            name,
            "fail",
            fail_summary,
            {"missing": missing[:100]},
        )
    return CheckResult(
        name,
        "pass",
        pass_summary,
        {"requirements": sorted(markers.keys())},
    )


def check_api_access_policy(root: Path) -> CheckResult:
    """Check source markers for the public/login/admin API classification.

    Args:
        root: Repository root.

    Returns:
        CheckResult: Pass when the required route dependencies are present.
    """

    return check_source_markers(
        root,
        name="api_access_policy_source_guard",
        markers=API_ACCESS_POLICY_MARKERS,
        pass_summary="Search/onboarding/model routes and diagnostics keep the required auth dependencies.",
        fail_summary="Release-critical API auth dependency markers are missing.",
    )


def check_rbac_policy(root: Path) -> CheckResult:
    """Check source markers for common RBAC role-level resolution.

    Args:
        root: Repository root.

    Returns:
        CheckResult: Pass when JWT, dependencies, and feature routers share RBAC fallback markers.
    """

    return check_source_markers(
        root,
        name="rbac_role_level_source_guard",
        markers=RBAC_POLICY_MARKERS,
        pass_summary="JWT role_level preservation and shared RBAC fallback markers are present.",
        fail_summary="RBAC role_level/fallback markers are missing or diverged.",
    )


def check_leak_prevention_policy(root: Path) -> CheckResult:
    """Check source markers for diagnostic, file, and Storage leak prevention.

    Args:
        root: Repository root.

    Returns:
        CheckResult: Pass when leak-prevention guardrails remain in source.
    """

    return check_source_markers(
        root,
        name="leak_prevention_source_guard",
        markers=LEAK_PREVENTION_MARKERS,
        pass_summary="Diagnostic redaction, drawing OCR allowlist, and Storage metadata guards are present.",
        fail_summary="Leak-prevention source markers are missing.",
    )


def load_json_file(path: Path) -> Mapping[str, Any]:
    """Load a JSON object from disk.

    Args:
        path: JSON file path.

    Returns:
        Mapping[str, Any]: Parsed JSON object.

    Raises:
        ValueError: If the file does not contain a JSON object.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def build_report(checks: Sequence[CheckResult], *, root: Path) -> dict[str, Any]:
    """Build a secret-safe release security report.

    Args:
        checks: Check results.
        root: Repository root.

    Returns:
        dict[str, Any]: JSON-serializable report.
    """

    counts = {status: sum(1 for check in checks if check.status == status) for status in ("pass", "fail", "skip")}
    status = "fail" if counts["fail"] else "pass"
    return redact_value(
        {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "root": str(root),
            "summary": {**counts, "status": status},
            "checks": [check.to_dict() for check in checks],
        }
    )


def write_markdown_report(report: Mapping[str, Any], output_path: Path) -> None:
    """Write a Markdown release security report.

    Args:
        report: Report returned by ``build_report``.
        output_path: Destination Markdown path.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        "# Release Security Verification",
        "",
        f"- Checked at: `{report['checked_at']}`",
        f"- Overall status: `{summary['status']}`",
        f"- Counts: pass={summary['pass']}, fail={summary['fail']}, skip={summary['skip']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Summary |",
        "|---|---:|---|",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` | {check['summary']} |")
    lines.extend(
        [
            "",
            "## Redacted JSON",
            "",
            "```json",
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--project-ref", default=os.getenv("SUPABASE_PROJECT_REF", DEFAULT_PROJECT_REF))
    parser.add_argument("--include-supabase-remote", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--supabase-report-json", type=Path)
    parser.add_argument("--cloud-run-service-json", type=Path)
    parser.add_argument("--admin-health-json", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run release security verification.

    Args:
        argv: Optional CLI arguments.

    Returns:
        int: Process exit code.
    """

    args = build_arg_parser().parse_args(argv)
    root = args.root.resolve()
    checks: list[CheckResult] = [
        scan_frontend_for_secret_exposure(root),
        check_api_access_policy(root),
        check_rbac_policy(root),
        check_leak_prevention_policy(root),
    ]

    if args.include_supabase_remote:
        checks.append(run_supabase_guard(args.project_ref, strict=args.strict))
    elif args.supabase_report_json:
        checks.append(summarize_supabase_report(load_json_file(args.supabase_report_json)))
    else:
        checks.append(
            CheckResult(
                "supabase_rls_data_api_guard",
                "skip",
                "Skipped because no Supabase remote verifier input was requested.",
            )
        )

    if args.cloud_run_service_json:
        checks.append(check_cloud_run_service_json(load_json_file(args.cloud_run_service_json)))
    else:
        checks.append(
            CheckResult(
                "cloud_run_secret_mapping",
                "skip",
                "Skipped because no Cloud Run service JSON was supplied.",
            )
        )

    if args.admin_health_json:
        checks.append(check_admin_health_json(load_json_file(args.admin_health_json)))
    else:
        checks.append(
            CheckResult(
                "admin_health_secret_safe",
                "skip",
                "Skipped because no admin health JSON was supplied.",
            )
        )

    report = build_report(checks, root=root)
    if args.markdown:
        write_markdown_report(report, args.markdown)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            "Release security verification: "
            f"{summary['status']} pass={summary['pass']} fail={summary['fail']} skip={summary['skip']}"
        )
        for check in report["checks"]:
            print(f"- [{check['status']}] {check['name']}: {check['summary']}")
    return 1 if report["summary"]["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
