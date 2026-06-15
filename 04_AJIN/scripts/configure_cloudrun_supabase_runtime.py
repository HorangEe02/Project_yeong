#!/usr/bin/env python3
"""Prepare Cloud Run Supabase runtime secrets and deploy mappings."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mint_smoke_admin_jwt import resolve_jwt_secret  # noqa: E402
from scripts.supabase_cutover import (  # noqa: E402
    DEFAULT_ENV_FILES,
    EnvIssue,
    key_state,
    load_env_files,
    unique_paths,
)
from scripts.verify_supabase_remote import DEFAULT_PROJECT_REF  # noqa: E402

DEFAULT_PROJECT = "ajin-cb"
DEFAULT_REGION = "asia-northeast3"
DEFAULT_SERVICE = "ajin-backend"
DEFAULT_ATTACHMENT_BUCKET = "ajin-attachments"
DEFAULT_DRAFT_EXPORT_BUCKET = "ajin-draft-exports"

BANNED_CLOUD_RUN_ENV = frozenset(
    {
        "SUPABASE_ACCESS_TOKEN",
        "SUPABASE_DB_PASSWORD",
        "SMOKE_ADMIN_JWT",
    }
)
SECRET_ENV_TO_MANAGER_SECRET = {
    "DATABASE_URL": "AJIN_DATABASE_URL",
    "SUPABASE_SECRET_KEY": "AJIN_SUPABASE_SECRET_KEY",
    "AJIN_JWT_SECRET": "AJIN_JWT_SECRET",
}
OPTIONAL_SECRET_ENV_TO_MANAGER_SECRET = {
    "LAW_GO_KR_OC": "law-oc",
    "CUSTOMS_API_KEY": "customs-api-key",
    "DART_API_KEY": "dart-api-key",
}


@dataclass(frozen=True)
class CommandResult:
    """Subprocess result used by the gcloud wrapper.

    Args:
        returncode: Process exit status.
        stdout: Captured standard output.
        stderr: Captured standard error.
    """

    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RuntimePlan:
    """Cloud Run Supabase runtime configuration plan.

    Args:
        project: Google Cloud project id.
        region: Cloud Run region.
        service: Cloud Run service name.
        project_ref: Supabase project reference.
        runtime_env: Non-secret Cloud Run environment variables.
        secret_values: Secret Manager secret values keyed by Secret Manager name.
        secret_env_map: Cloud Run env names mapped to Secret Manager secret names.
        service_account: Optional Cloud Run service account email.
    """

    project: str
    region: str
    service: str
    project_ref: str
    runtime_env: dict[str, str]
    secret_values: dict[str, str]
    secret_env_map: dict[str, str]
    service_account: str | None = None


Runner = Callable[[list[str], str | None, bool], CommandResult]


def _json_safe(value: Any) -> Any:
    """Convert dataclasses and paths into JSON-safe values.

    Args:
        value: Arbitrary result value.

    Returns:
        Any: JSON-compatible representation.
    """

    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def run_command(args: list[str], input_text: str | None = None, check: bool = True) -> CommandResult:
    """Run a command without placing secret values in argv.

    Args:
        args: Command arguments.
        input_text: Optional stdin, used for secret version payloads.
        check: Whether to raise on non-zero exit.

    Returns:
        CommandResult: Captured process result.

    Raises:
        RuntimeError: If ``check`` is true and the command fails.
    """

    completed = subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    result = CommandResult(completed.returncode, completed.stdout or "", completed.stderr or "")
    if check and result.returncode != 0:
        raise RuntimeError(f"{args[:4]} failed with exit code {result.returncode}")
    return result


def require_env(name: str) -> str:
    """Return a required environment value.

    Args:
        name: Environment variable name.

    Returns:
        str: Non-empty environment value.

    Raises:
        RuntimeError: If the value is missing.
    """

    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def build_runtime_env(project_ref: str) -> dict[str, str]:
    """Build the non-secret Cloud Run runtime env map.

    Args:
        project_ref: Expected Supabase project reference.

    Returns:
        dict[str, str]: Non-secret runtime env values.
    """

    return {
        "SUPABASE_PROJECT_REF": os.getenv("SUPABASE_PROJECT_REF", project_ref).strip()
        or project_ref,
        "SUPABASE_URL": require_env("SUPABASE_URL"),
        "SUPABASE_PUBLISHABLE_KEY": require_env("SUPABASE_PUBLISHABLE_KEY"),
        "APP_DB_BACKEND": "postgres",
        "FIREBASE_WRITE_ENABLED": "false",
        "FIREBASE_READ_FALLBACK_ENABLED": "false",
        "SUPABASE_STORAGE_BUCKET_ATTACHMENTS": os.getenv(
            "SUPABASE_STORAGE_BUCKET_ATTACHMENTS",
            DEFAULT_ATTACHMENT_BUCKET,
        ).strip()
        or DEFAULT_ATTACHMENT_BUCKET,
        "SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS": os.getenv(
            "SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS",
            DEFAULT_DRAFT_EXPORT_BUCKET,
        ).strip()
        or DEFAULT_DRAFT_EXPORT_BUCKET,
        "ENABLE_SUPABASE_REALTIME": "false",
    }


def collect_secret_values(jwt_secret_file: Path | None = None) -> dict[str, str]:
    """Collect runtime secret payloads from env and the optional local file.

    Args:
        jwt_secret_file: Optional 0600 file containing ``AJIN_JWT_SECRET``.

    Returns:
        dict[str, str]: Secret Manager names to secret payloads.
    """

    database_url = require_env("DATABASE_URL")
    supabase_secret_key = require_env("SUPABASE_SECRET_KEY")
    supabase_secret_state = key_state(supabase_secret_key)
    if supabase_secret_state not in {"secret", "legacy_jwt"}:
        raise RuntimeError("SUPABASE_SECRET_KEY must be sb_secret_ or legacy service_role")

    jwt_secret, _source = resolve_jwt_secret(jwt_secret_file)
    if len(jwt_secret) < 32:
        raise RuntimeError("AJIN_JWT_SECRET must be at least 32 characters")

    return {
        "AJIN_DATABASE_URL": database_url,
        "AJIN_SUPABASE_SECRET_KEY": supabase_secret_key,
        "AJIN_JWT_SECRET": jwt_secret,
    }


def collect_optional_secret_values() -> dict[str, str]:
    """Collect optional backend-only integration secrets when present.

    Returns:
        dict[str, str]: Secret Manager names to non-empty optional payloads.
    """

    values: dict[str, str] = {}
    for env_name, secret_name in OPTIONAL_SECRET_ENV_TO_MANAGER_SECRET.items():
        value = os.getenv(env_name, "").strip()
        if value:
            values[secret_name] = value
    return values


def build_runtime_plan(
    *,
    project: str,
    region: str,
    service: str,
    project_ref: str,
    jwt_secret_file: Path | None = None,
    service_account: str | None = None,
) -> RuntimePlan:
    """Build and validate the complete Cloud Run runtime plan.

    Args:
        project: Google Cloud project id.
        region: Cloud Run region.
        service: Cloud Run service name.
        project_ref: Supabase project reference.
        jwt_secret_file: Optional 0600 local JWT secret file.
        service_account: Optional Cloud Run service account email.

    Returns:
        RuntimePlan: Validated runtime plan.
    """

    runtime_env = build_runtime_env(project_ref)
    configured_ref = runtime_env["SUPABASE_PROJECT_REF"]
    expected_url = f"https://{project_ref}.supabase.co"
    if configured_ref != project_ref:
        raise RuntimeError("SUPABASE_PROJECT_REF does not match project-ref")
    if runtime_env["SUPABASE_URL"].rstrip("/") != expected_url:
        raise RuntimeError("SUPABASE_URL does not match project-ref")
    if key_state(runtime_env["SUPABASE_PUBLISHABLE_KEY"]) != "publishable":
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY must use sb_publishable_ prefix")

    secret_values = collect_secret_values(jwt_secret_file)
    optional_secret_values = collect_optional_secret_values()
    secret_values.update(optional_secret_values)
    secret_env_map = dict(SECRET_ENV_TO_MANAGER_SECRET)
    available_optional_secrets = {
        env_name: secret_name
        for env_name, secret_name in OPTIONAL_SECRET_ENV_TO_MANAGER_SECRET.items()
        if secret_name in optional_secret_values
    }
    secret_env_map.update(available_optional_secrets)
    verify_generated_mapping(runtime_env, secret_env_map)
    return RuntimePlan(
        project=project,
        region=region,
        service=service,
        project_ref=project_ref,
        runtime_env=runtime_env,
        secret_values=secret_values,
        secret_env_map=secret_env_map,
        service_account=service_account,
    )


def verify_generated_mapping(runtime_env: dict[str, str], secret_env_map: dict[str, str]) -> None:
    """Fail closed if deploy mappings contain banned runtime values.

    Args:
        runtime_env: Non-secret env variables to pass to Cloud Run.
        secret_env_map: Secret-backed env variables to pass to Cloud Run.

    Raises:
        RuntimeError: If banned deploy-local names would be injected.
    """

    banned = BANNED_CLOUD_RUN_ENV.intersection(runtime_env).union(
        BANNED_CLOUD_RUN_ENV.intersection(secret_env_map)
    )
    if banned:
        raise RuntimeError(f"banned Cloud Run env mapping detected: {', '.join(sorted(banned))}")


def format_update_env_vars(runtime_env: dict[str, str]) -> str:
    """Format Cloud Run ``--update-env-vars`` value.

    Args:
        runtime_env: Non-secret env variables.

    Returns:
        str: Comma-separated gcloud flag payload.
    """

    return ",".join(f"{key}={value}" for key, value in runtime_env.items())


def format_update_secrets(secret_env_map: dict[str, str]) -> str:
    """Format Cloud Run ``--update-secrets`` value.

    Args:
        secret_env_map: Runtime env names to Secret Manager secret names.

    Returns:
        str: Comma-separated gcloud flag payload.
    """

    return ",".join(f"{env_name}={secret_name}:latest" for env_name, secret_name in secret_env_map.items())


def redacted_plan(plan: RuntimePlan) -> dict[str, Any]:
    """Return a secret-safe representation of the runtime plan.

    Args:
        plan: Runtime plan.

    Returns:
        dict[str, Any]: Secret-safe summary.
    """

    return {
        "project": plan.project,
        "region": plan.region,
        "service": plan.service,
        "project_ref": plan.project_ref,
        "service_account": plan.service_account or "<auto>",
        "runtime_env_names": sorted(plan.runtime_env),
        "runtime_secret_env": {
            env_name: f"{secret_name}:latest"
            for env_name, secret_name in sorted(plan.secret_env_map.items())
        },
        "secret_manager_names": sorted(plan.secret_values),
        "deploy_args": {
            "update_env_vars_names": sorted(plan.runtime_env),
            "update_secrets": format_update_secrets(plan.secret_env_map),
        },
    }


def fetch_billing_info(project: str, runner: Runner = run_command) -> dict[str, Any]:
    """Fetch billing info for a project.

    Args:
        project: Google Cloud project id.
        runner: Command runner.

    Returns:
        dict[str, Any]: Parsed billing info.
    """

    result = runner(
        [
            "gcloud",
            "beta",
            "billing",
            "projects",
            "describe",
            project,
            "--format=json",
        ],
        None,
        True,
    )
    return json.loads(result.stdout or "{}")


def ensure_billing_enabled(project: str, runner: Runner = run_command) -> dict[str, Any]:
    """Fail closed unless project billing is enabled.

    Args:
        project: Google Cloud project id.
        runner: Command runner.

    Returns:
        dict[str, Any]: Billing info.

    Raises:
        RuntimeError: If billing is disabled.
    """

    info = fetch_billing_info(project, runner)
    if info.get("billingEnabled") is not True:
        raise RuntimeError("billing must be enabled before configuring Cloud Run runtime")
    return info


def fetch_service_account(plan: RuntimePlan, runner: Runner = run_command) -> str:
    """Return the Cloud Run service account email.

    Args:
        plan: Runtime plan.
        runner: Command runner.

    Returns:
        str: Service account email.

    Raises:
        RuntimeError: If the service account cannot be resolved.
    """

    if plan.service_account:
        return plan.service_account
    result = runner(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            plan.service,
            "--region",
            plan.region,
            "--project",
            plan.project,
            "--format=value(spec.template.spec.serviceAccountName)",
        ],
        None,
        True,
    )
    service_account = result.stdout.strip()
    if not service_account:
        raise RuntimeError("Cloud Run service account could not be resolved")
    return service_account


def secret_exists(project: str, secret_name: str, runner: Runner = run_command) -> bool:
    """Return whether a Secret Manager secret exists.

    Args:
        project: Google Cloud project id.
        secret_name: Secret Manager secret name.
        runner: Command runner.

    Returns:
        bool: True when describe succeeds.
    """

    result = runner(
        ["gcloud", "secrets", "describe", secret_name, "--project", project, "--format=json"],
        None,
        False,
    )
    return result.returncode == 0


def create_secret(project: str, secret_name: str, runner: Runner = run_command) -> None:
    """Create an automatic-replication Secret Manager secret.

    Args:
        project: Google Cloud project id.
        secret_name: Secret Manager secret name.
        runner: Command runner.
    """

    runner(
        [
            "gcloud",
            "secrets",
            "create",
            secret_name,
            "--replication-policy=automatic",
            "--project",
            project,
            "--quiet",
        ],
        None,
        True,
    )


def add_secret_version(
    project: str,
    secret_name: str,
    secret_value: str,
    runner: Runner = run_command,
) -> None:
    """Add a new Secret Manager version via stdin.

    Args:
        project: Google Cloud project id.
        secret_name: Secret Manager secret name.
        secret_value: Secret payload.
        runner: Command runner.
    """

    runner(
        [
            "gcloud",
            "secrets",
            "versions",
            "add",
            secret_name,
            "--data-file=-",
            "--project",
            project,
            "--quiet",
        ],
        secret_value,
        True,
    )


def grant_secret_access(
    project: str,
    secret_name: str,
    service_account: str,
    runner: Runner = run_command,
) -> None:
    """Grant one service account access to one Secret Manager secret.

    Args:
        project: Google Cloud project id.
        secret_name: Secret Manager secret name.
        service_account: Cloud Run service account email.
        runner: Command runner.
    """

    runner(
        [
            "gcloud",
            "secrets",
            "add-iam-policy-binding",
            secret_name,
            "--member",
            f"serviceAccount:{service_account}",
            "--role",
            "roles/secretmanager.secretAccessor",
            "--project",
            project,
            "--quiet",
        ],
        None,
        True,
    )


def fetch_service_spec(plan: RuntimePlan, runner: Runner = run_command) -> dict[str, Any]:
    """Fetch the current Cloud Run service JSON.

    Args:
        plan: Runtime plan.
        runner: Command runner.

    Returns:
        dict[str, Any]: Cloud Run service JSON.
    """

    result = runner(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            plan.service,
            "--region",
            plan.region,
            "--project",
            plan.project,
            "--format=json",
        ],
        None,
        True,
    )
    return json.loads(result.stdout or "{}")


def _service_env_entries(service_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return first-container env entries from a Cloud Run service spec.

    Args:
        service_spec: Cloud Run service JSON.

    Returns:
        list[dict[str, Any]]: Environment entry objects.
    """

    containers = (
        service_spec.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    if not containers:
        return []
    return list(containers[0].get("env", []) or [])


def verify_service_runtime_mapping(
    service_spec: dict[str, Any],
    plan: RuntimePlan,
    *,
    require_expected: bool,
) -> list[EnvIssue]:
    """Validate the current Cloud Run runtime env/secret mapping.

    Args:
        service_spec: Cloud Run service JSON.
        plan: Expected runtime plan.
        require_expected: Whether all expected env/secret entries must exist.

    Returns:
        list[EnvIssue]: Secret-safe validation issues.
    """

    issues: list[EnvIssue] = []
    entries = _service_env_entries(service_spec)
    by_name = {str(entry.get("name")): entry for entry in entries if entry.get("name")}

    for name in sorted(BANNED_CLOUD_RUN_ENV.intersection(by_name)):
        issues.append(EnvIssue(name, "deploy-only/local-only value must not be injected"))

    for env_name, secret_name in sorted(plan.secret_env_map.items()):
        entry = by_name.get(env_name)
        if not entry:
            if require_expected:
                issues.append(EnvIssue(env_name, "expected secret-backed env is missing"))
            continue
        if "value" in entry:
            issues.append(EnvIssue(env_name, "secret-backed env is configured as a plain value"))
            continue
        ref = entry.get("valueFrom", {}).get("secretKeyRef", {})
        if ref.get("name") != secret_name or str(ref.get("key")) != "latest":
            issues.append(EnvIssue(env_name, "secret-backed env points to unexpected secret"))

    if require_expected:
        for env_name, expected_value in sorted(plan.runtime_env.items()):
            entry = by_name.get(env_name)
            if not entry:
                issues.append(EnvIssue(env_name, "expected plain env is missing"))
            elif entry.get("value") != expected_value:
                issues.append(EnvIssue(env_name, "plain env does not match expected value"))
    return issues


def apply_runtime_configuration(plan: RuntimePlan, runner: Runner = run_command) -> dict[str, Any]:
    """Create/update secrets and grant Cloud Run secret access.

    Args:
        plan: Runtime plan.
        runner: Command runner.

    Returns:
        dict[str, Any]: Secret-safe apply summary.
    """

    billing = ensure_billing_enabled(plan.project, runner)
    service_account = fetch_service_account(plan, runner)
    created: list[str] = []
    versioned: list[str] = []
    iam_granted: list[str] = []

    for secret_name, secret_value in sorted(plan.secret_values.items()):
        if not secret_exists(plan.project, secret_name, runner):
            create_secret(plan.project, secret_name, runner)
            created.append(secret_name)
        add_secret_version(plan.project, secret_name, secret_value, runner)
        versioned.append(secret_name)
        grant_secret_access(plan.project, secret_name, service_account, runner)
        iam_granted.append(secret_name)

    service_spec = fetch_service_spec(
        RuntimePlan(
            **{**asdict(plan), "service_account": service_account}
        ),
        runner,
    )
    mapping_issues = verify_service_runtime_mapping(
        service_spec,
        RuntimePlan(**{**asdict(plan), "service_account": service_account}),
        require_expected=False,
    )
    if mapping_issues:
        raise RuntimeError(
            "Cloud Run runtime mapping validation failed: "
            + ", ".join(f"{issue.name}: {issue.message}" for issue in mapping_issues)
        )

    return {
        "billing_enabled": bool(billing.get("billingEnabled")),
        "service_account": service_account,
        "secrets_created": created,
        "secret_versions_added": versioned,
        "secret_iam_granted": iam_granted,
        "current_service_mapping_checked": True,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--project-ref", default=DEFAULT_PROJECT_REF)
    parser.add_argument("--service-account", default=None)
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--jwt-secret-file", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--verify-existing-mapping",
        action="store_true",
        help="require current Cloud Run revision to already have expected runtime mappings",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Cloud Run Supabase runtime configuration helper.

    Args:
        argv: Optional command-line arguments.

    Returns:
        int: Process exit status.
    """

    args = build_arg_parser().parse_args(argv)
    env_paths = unique_paths([*DEFAULT_ENV_FILES, *args.env_file])
    loaded_env_files = load_env_files(env_paths, override=False)

    try:
        plan = build_runtime_plan(
            project=args.project,
            region=args.region,
            service=args.service,
            project_ref=args.project_ref,
            jwt_secret_file=args.jwt_secret_file,
            service_account=args.service_account,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "apply" if args.apply else "dry_run",
                    "loaded_env_files": loaded_env_files,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    output: dict[str, Any] = {
        "ok": True,
        "mode": "apply" if args.apply else "dry_run",
        "loaded_env_files": loaded_env_files,
        "plan": redacted_plan(plan),
    }

    try:
        if args.apply:
            output["apply"] = apply_runtime_configuration(plan)
        if args.verify_existing_mapping:
            service_spec = fetch_service_spec(plan)
            issues = verify_service_runtime_mapping(
                service_spec,
                plan,
                require_expected=True,
            )
            output["existing_mapping_issues"] = [asdict(issue) for issue in issues]
            if issues:
                output["ok"] = False
                print(json.dumps(_json_safe(output), ensure_ascii=False, indent=2))
                return 1
    except Exception as exc:
        output["ok"] = False
        output["error"] = str(exc)
        print(json.dumps(_json_safe(output), ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(_json_safe(output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
