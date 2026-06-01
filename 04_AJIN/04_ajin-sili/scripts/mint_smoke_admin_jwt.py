#!/usr/bin/env python3
"""Mint a short-lived SYS_ADMIN JWT for Cloud Run runtime smoke tests."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.auth.rbac import get_role_level  # noqa: E402
from core.db import create_sqlalchemy_engine  # noqa: E402
from scripts.bootstrap_supabase_sys_admin import (  # noqa: E402
    DEFAULT_SYS_ADMIN,
    AdminPosture,
    SysAdminSpec,
    fetch_admin_posture,
    validate_bootstrap_environment,
)
from scripts.supabase_cutover import (  # noqa: E402
    DEFAULT_ENV_FILES,
    EnvIssue,
    load_env_files,
    unique_paths,
)
from scripts.verify_supabase_remote import DEFAULT_PROJECT_REF  # noqa: E402

DEFAULT_TOKEN_FILE = ROOT / "secrets" / "smoke-admin.jwt"
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class SmokeTokenSpec:
    """Smoke-token subject and lifetime.

    Args:
        employee_id: Active SYS_ADMIN employee id used as the JWT subject.
        username: Operator-facing display name to include in the token.
        role_name: AJIN RBAC role name. Must resolve to a positive role level.
        ttl_minutes: Token validity in minutes.
    """

    employee_id: str
    username: str
    role_name: str
    ttl_minutes: int


def _json_safe(value: Any) -> Any:
    """Convert paths, dataclasses, and datetimes into JSON-safe values.

    Args:
        value: Arbitrary value returned by the smoke-token workflow.

    Returns:
        Any: JSON-compatible representation.
    """

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def read_jwt_secret_file(path: Path) -> str:
    """Read a local JWT secret file after checking owner-only permissions.

    Args:
        path: Local file containing only the AJIN JWT secret.

    Returns:
        str: JWT signing secret.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If group or other permissions are present.
        ValueError: If the file is empty.
    """

    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(f"{path} must be readable only by the owner")
    secret = path.read_text(encoding="utf-8").strip()
    if not secret:
        raise ValueError(f"{path} is empty")
    return secret


def resolve_jwt_secret(jwt_secret_file: Path | None = None) -> tuple[str, str]:
    """Resolve the JWT signing secret from a secure file or environment.

    Args:
        jwt_secret_file: Optional local 0600 file. When provided, it is preferred
            over ``AJIN_JWT_SECRET`` to make Secret Manager recovery explicit.

    Returns:
        tuple[str, str]: Secret value and sanitized source label.

    Raises:
        RuntimeError: If neither source is available.
        FileNotFoundError: If the requested file is missing.
        PermissionError: If the requested file permissions are too broad.
        ValueError: If the requested file is empty.
    """

    if jwt_secret_file is not None:
        return read_jwt_secret_file(jwt_secret_file), f"file:{jwt_secret_file}"
    env_secret = os.getenv("AJIN_JWT_SECRET", "").strip()
    if env_secret:
        return env_secret, "env:AJIN_JWT_SECRET"
    raise RuntimeError("AJIN_JWT_SECRET or --jwt-secret-file is required")


def validate_smoke_environment(
    project_ref: str,
    *,
    jwt_secret_file: Path | None = None,
) -> list[EnvIssue]:
    """Validate env required for minting a deploy-smoke JWT.

    Args:
        project_ref: Expected Supabase project reference.
        jwt_secret_file: Optional local 0600 JWT secret file.

    Returns:
        list[EnvIssue]: Secret-safe validation failures.
    """

    issues = validate_bootstrap_environment(project_ref)
    try:
        resolve_jwt_secret(jwt_secret_file)
    except Exception as exc:
        issues.append(
            EnvIssue(
                "AJIN_JWT_SECRET",
                f"AJIN_JWT_SECRET or --jwt-secret-file is required: {exc}",
            )
        )
    return issues


def assert_smoke_admin_posture(posture: AdminPosture) -> None:
    """Fail closed unless the exact target is an active named SYS_ADMIN.

    Args:
        posture: Sanitized admin posture from the target database.

    Raises:
        RuntimeError: If a legacy active admin exists or the target is invalid.
    """

    if posture.active_default_admin_count:
        raise RuntimeError("active default admin account must be disabled first")
    if not posture.target_is_active_sys_admin:
        raise RuntimeError("target employee_id is not an active SYS_ADMIN")


def mint_smoke_admin_token(
    *,
    spec: SmokeTokenSpec,
    jwt_secret: str,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """Create a signed, short-lived AJIN access token.

    Args:
        spec: Token subject and lifetime.
        jwt_secret: HS256 signing secret used by the Cloud Run backend.
        now: Optional fixed clock for tests.

    Returns:
        tuple[str, datetime]: Encoded JWT and its UTC expiration timestamp.

    Raises:
        ValueError: If the requested role or TTL is invalid.
    """

    if spec.ttl_minutes < 1 or spec.ttl_minutes > 60:
        raise ValueError("ttl_minutes must be between 1 and 60")
    role_level = get_role_level(spec.role_name)
    if role_level <= 0:
        raise ValueError(f"unknown or inactive role: {spec.role_name}")

    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=spec.ttl_minutes)
    payload = {
        "sub": spec.employee_id,
        "username": spec.username,
        "role": spec.role_name,
        "role_level": role_level,
        "exp": expires_at,
        "iat": issued_at,
        "type": "access",
        "purpose": "cloud_run_smoke",
    }
    return jwt.encode(payload, jwt_secret, algorithm=JWT_ALGORITHM), expires_at


def write_token_file(path: Path, token: str, *, overwrite: bool) -> None:
    """Write the smoke token with owner-only permissions.

    Args:
        path: Gitignored output path.
        token: Encoded JWT.
        overwrite: Whether an existing token file may be replaced.

    Raises:
        FileExistsError: If the file exists and overwrite is false.
        OSError: If the file cannot be written or chmodded.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if not overwrite:
        flags |= os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token)
            handle.write("\n")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def mint_smoke_admin_jwt(
    engine: Engine,
    *,
    token_spec: SmokeTokenSpec,
    jwt_secret: str | None = None,
    output_file: Path = DEFAULT_TOKEN_FILE,
    overwrite: bool = False,
    print_token: bool = False,
) -> dict[str, Any]:
    """Validate SYS_ADMIN posture and write a smoke JWT.

    Args:
        engine: SQLAlchemy engine connected to the Supabase/Postgres database.
        token_spec: Token subject and lifetime.
        jwt_secret: Optional explicit signing secret. Defaults to env resolution.
        output_file: Gitignored token output path.
        overwrite: Whether an existing token file may be replaced.
        print_token: Include the token in the returned result only when explicit.

    Returns:
        dict[str, Any]: Secret-safe summary by default.

    Raises:
        RuntimeError: If the database posture is unsafe.
        FileExistsError: If the output file exists and overwrite is false.
    """

    admin_spec = SysAdminSpec(
        employee_id=token_spec.employee_id,
        username=token_spec.username,
        role_name=token_spec.role_name,
    )
    with engine.connect() as connection:
        posture = fetch_admin_posture(connection, admin_spec)
    assert_smoke_admin_posture(posture)

    token, expires_at = mint_smoke_admin_token(
        spec=token_spec,
        jwt_secret=jwt_secret or os.environ["AJIN_JWT_SECRET"],
    )
    write_token_file(output_file, token, overwrite=overwrite)
    result: dict[str, Any] = {
        "ok": True,
        "employee_id": token_spec.employee_id,
        "username": token_spec.username,
        "role_name": token_spec.role_name,
        "ttl_minutes": token_spec.ttl_minutes,
        "expires_at": expires_at,
        "token_file": output_file,
        "token_file_written": True,
        "posture": posture,
    }
    if print_token:
        result["token"] = token
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        action="append",
        type=Path,
        default=[],
        help="dotenv file to load before connecting; may be passed multiple times",
    )
    parser.add_argument(
        "--project-ref",
        default=DEFAULT_PROJECT_REF,
        help="expected Supabase project ref",
    )
    parser.add_argument(
        "--employee-id",
        default=DEFAULT_SYS_ADMIN.employee_id,
        help="active SYS_ADMIN employee id to mint for",
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_SYS_ADMIN.username,
        help="username claim for the smoke token",
    )
    parser.add_argument(
        "--role-name",
        default=DEFAULT_SYS_ADMIN.role_name,
        help="RBAC role claim; defaults to SYS_ADMIN",
    )
    parser.add_argument(
        "--ttl-minutes",
        type=int,
        default=15,
        help="token lifetime in minutes, between 1 and 60",
    )
    parser.add_argument(
        "--jwt-secret-file",
        type=Path,
        default=None,
        help=f"local 0600 file containing AJIN_JWT_SECRET; default env only",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        help="gitignored path for the generated JWT",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing smoke token file",
    )
    parser.add_argument(
        "--print",
        dest="print_token",
        action="store_true",
        help="include the JWT in stdout; default stdout redacts it",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the smoke-token minting CLI.

    Args:
        argv: Optional command-line arguments.

    Returns:
        int: Process exit status.
    """

    args = build_arg_parser().parse_args(argv)
    env_paths = unique_paths([*DEFAULT_ENV_FILES, *args.env_file])
    loaded_env_files = load_env_files(env_paths, override=False)
    issues = validate_smoke_environment(
        args.project_ref,
        jwt_secret_file=args.jwt_secret_file,
    )
    if issues:
        print(
            json.dumps(
                {
                    "ok": False,
                    "loaded_env_files": loaded_env_files,
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    try:
        jwt_secret, jwt_secret_source = resolve_jwt_secret(args.jwt_secret_file)
        result = mint_smoke_admin_jwt(
            create_sqlalchemy_engine(),
            token_spec=SmokeTokenSpec(
                employee_id=args.employee_id,
                username=args.username,
                role_name=args.role_name,
                ttl_minutes=args.ttl_minutes,
            ),
            jwt_secret=jwt_secret,
            output_file=args.output_file,
            overwrite=args.overwrite,
            print_token=args.print_token,
        )
        result["jwt_secret_source"] = jwt_secret_source
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "loaded_env_files": loaded_env_files,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(
        json.dumps(
            _json_safe({"loaded_env_files": loaded_env_files, **result}),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
