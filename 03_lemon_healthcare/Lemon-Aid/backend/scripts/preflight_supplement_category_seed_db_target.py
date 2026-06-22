"""Preflight the DB target before category seed taxonomy apply.

This script validates the configured SQLAlchemy database target without opening
a DB connection. It exists to prevent category seed ``--apply`` from being run
against a remote or production database by accident.

References:
    https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.engine.make_url
    https://www.postgresql.org/docs/current/ddl-constraints.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import POSTGRESQL_ASYNCPG_DRIVER, get_settings  # noqa: E402

from scripts import gate_supplement_category_seed_db_apply as category_gate  # noqa: E402

SCHEMA_VERSION = "supplement-category-seed-db-target-preflight-v1"
READY_STATUS = "ready_for_local_category_seed_apply"
BLOCKED_STATUS = "blocked_by_db_target_safety"
ERROR_STATUS = "error"
SOURCE_DOC_URLS = (
    "https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls",
    "https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.engine.make_url",
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
)
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
READY_NEXT_STEPS = (
    "run_category_seed_apply_against_local_database",
    "run_category_seed_db_verifier",
    "record_category_seed_apply_result",
)
BLOCKED_NEXT_STEPS = (
    "switch_to_local_development_database",
    "rerun_category_seed_db_target_preflight",
)


class CategorySeedDbTargetPreflightError(ValueError):
    """Raised when the DB target preflight cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category-seed-apply-gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a DB target preflight report.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    gate_path = args.category_seed_apply_gate.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        settings = get_settings()
        summary = build_db_target_preflight(
            category_seed_apply_gate=gate_path,
            database_url=settings.database_url,
            environment=settings.environment,
        )
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, CategorySeedDbTargetPreflightError, ValueError) as exc:
        failure = _failure_summary(output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_db_target_preflight(
    *,
    category_seed_apply_gate: Path,
    database_url: str,
    environment: str,
) -> dict[str, Any]:
    """Build a DB target safety preflight.

    Args:
        category_seed_apply_gate: Category seed apply gate JSON.
        database_url: Configured SQLAlchemy database URL.
        environment: Runtime environment.

    Returns:
        Redacted DB target preflight summary.
    """
    gate_payload = _load_json_object(category_seed_apply_gate)
    _require_schema(gate_payload, category_gate.SCHEMA_VERSION)
    _reject_unsafe_payload(gate_payload)
    parsed_url = _parse_database_url(database_url)
    host_class = _database_host_class(parsed_url.host)
    driver = str(parsed_url.drivername)
    conditions = {
        "category_seed_apply_gate_status_ready": gate_payload.get("status")
        == category_gate.READY_STATUS,
        "category_seed_apply_gate_ready": gate_payload.get("category_seed_db_apply_allowed")
        is True,
        "product_apply_blocked": gate_payload.get("product_db_apply_allowed") is False,
        "product_category_apply_blocked": gate_payload.get("product_category_db_apply_allowed")
        is False,
        "apply_gate_performed_no_db_write": gate_payload.get("db_write_performed") is False,
        "environment_is_development": environment == "development",
        "driver_is_postgresql_asyncpg": driver == POSTGRESQL_ASYNCPG_DRIVER,
        "database_host_is_local": host_class == "local",
    }
    failed_conditions = sorted(key for key, value in conditions.items() if not value)
    allowed = not failed_conditions
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": READY_STATUS if allowed else BLOCKED_STATUS,
        "generated_at": datetime.now(UTC).isoformat(),
        "category_seed_apply_gate_name": category_seed_apply_gate.name,
        "category_seed_apply_gate_sha256": _sha256_file(category_seed_apply_gate),
        "runtime_environment": _safe_token(environment),
        "database_driver": _safe_token(driver),
        "database_host_class": _safe_token(host_class),
        "database_target_kind": "local_postgres" if host_class == "local" else "remote_or_unknown",
        "database_port_present": parsed_url.port is not None,
        "database_name_present": parsed_url.database is not None,
        "database_auth_present": parsed_url.username is not None or parsed_url.password is not None,
        "conditions": conditions,
        "failed_conditions": failed_conditions,
        "category_seed_db_apply_target_allowed": allowed,
        "product_db_apply_allowed": False,
        "product_category_db_apply_allowed": False,
        "db_connection_opened": False,
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "database_url_printed": False,
        "database_credentials_printed": False,
        "next_steps": list(READY_NEXT_STEPS if allowed else BLOCKED_NEXT_STEPS),
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown DB target preflight report.

    Args:
        summary: Preflight summary.

    Returns:
        Markdown report.
    """
    _reject_unsafe_payload(summary)
    conditions = _mapping(summary["conditions"])
    condition_lines = "\n".join(
        f"- `{_safe_token(str(key))}`: `{_bool_text(value)}`"
        for key, value in sorted(conditions.items())
    )
    failed_conditions = _markdown_token_list(summary.get("failed_conditions"))
    next_steps = "\n".join(f"- `{_safe_token(str(step))}`" for step in summary["next_steps"])
    markdown = "\n".join(
        [
            "# Supplement Category Seed DB Target Preflight",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 category seed DB apply 전 연결 대상이 로컬 개발 DB인지 확인합니다. DB URL 원문, 사용자명, 비밀번호, DB 이름은 출력하지 않습니다.",
            "",
            f"- Status: `{_safe_token(str(summary.get('status') or 'unknown'))}`",
            f"- Target apply allowed: `{_bool_text(summary.get('category_seed_db_apply_target_allowed'))}`",
            f"- Runtime environment: `{_safe_token(str(summary.get('runtime_environment') or 'unknown'))}`",
            f"- Database driver: `{_safe_token(str(summary.get('database_driver') or 'unknown'))}`",
            f"- Database host class: `{_safe_token(str(summary.get('database_host_class') or 'unknown'))}`",
            f"- Database target kind: `{_safe_token(str(summary.get('database_target_kind') or 'unknown'))}`",
            "",
            "## Conditions",
            "",
            condition_lines,
            "",
            "## Failed Conditions",
            "",
            failed_conditions,
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Rule",
            "",
            "이 preflight가 통과해도 제품/브랜드 DB write는 허용하지 않습니다. category seed apply는 로컬 개발 DB에서만 진행합니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _parse_database_url(database_url: str) -> Any:
    """Parse a SQLAlchemy database URL.

    Args:
        database_url: SQLAlchemy URL.

    Returns:
        Parsed SQLAlchemy URL object.
    """
    try:
        return make_url(database_url)
    except ArgumentError as exc:
        raise CategorySeedDbTargetPreflightError("DATABASE_URL is invalid.") from exc


def _database_host_class(host: str | None) -> str:
    """Classify a database host without exposing it.

    Args:
        host: Parsed hostname.

    Returns:
        ``local`` or ``remote_or_unknown``.
    """
    if host in LOCAL_HOSTS:
        return "local"
    return "remote_or_unknown"


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object.

    Args:
        path: JSON path.

    Returns:
        Parsed JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CategorySeedDbTargetPreflightError("Preflight input must be a JSON object.")
    return payload


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate schema version.

    Args:
        payload: Parsed JSON payload.
        expected_schema: Expected schema version.
    """
    if payload.get("schema_version") != expected_schema:
        raise CategorySeedDbTargetPreflightError("Preflight input schema does not match.")


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return a mapping or fail closed.

    Args:
        value: Candidate value.

    Returns:
        Mapping value.
    """
    if not isinstance(value, Mapping):
        raise CategorySeedDbTargetPreflightError("Expected a mapping.")
    return value


def _safe_token(value: str) -> str:
    """Return a conservative token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789가-힣_:-.+")
    if not value or any(char not in allowed for char in value):
        raise CategorySeedDbTargetPreflightError("Unsafe token.")
    return value


def _markdown_token_list(value: Any) -> str:
    """Return Markdown bullets for safe tokens.

    Args:
        value: Candidate token list.

    Returns:
        Markdown bullet list.
    """
    if value is None:
        return "- none"
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise CategorySeedDbTargetPreflightError("Expected a token sequence.")
    if not value:
        return "- none"
    return "\n".join(f"- `{_safe_token(str(item))}`" for item in value)


def _bool_text(value: object) -> str:
    """Return lowercase boolean text.

    Args:
        value: Candidate boolean.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR/provider payloads and DB URL literals.

    Args:
        value: Candidate JSON-like value.
    """
    _reject_unsafe_keys(value)
    _reject_unsafe_strings(value)


def _reject_unsafe_keys(value: Any) -> None:
    """Reject exact raw/sensitive JSON keys without blocking safe boolean flags.

    Args:
        value: Candidate JSON-like value.
    """
    forbidden_keys = {
        "database_url",
        "db_url",
        "image_bytes",
        "object_uri",
        "owner_hash",
        "owner_subject",
        "password",
        "provider_payload",
        "provider_response",
        "raw_ocr_text",
        "secret",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in forbidden_keys:
                raise CategorySeedDbTargetPreflightError(
                    "Preflight payload contains an unsafe key."
                )
            _reject_unsafe_keys(child)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for child in value:
            _reject_unsafe_keys(child)


def _reject_unsafe_strings(value: Any) -> None:
    """Reject raw DB URLs and local path literals from string values.

    Args:
        value: Candidate JSON-like value.
    """
    forbidden_fragments = (
        "/Volumes/",
        "/Users/",
        "/private/",
        "DATABASE_URL=",
        "postgres://",
        "postgresql://",
        "postgresql+asyncpg://",
    )
    if isinstance(value, str):
        if any(fragment in value for fragment in forbidden_fragments):
            raise CategorySeedDbTargetPreflightError("Preflight payload contains an unsafe string.")
    elif isinstance(value, Mapping):
        for child in value.values():
            _reject_unsafe_strings(child)
    elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        for child in value:
            _reject_unsafe_strings(child)


def _sha256_file(path: Path) -> str:
    """Return SHA-256 digest for a local artifact.

    Args:
        path: Artifact path.

    Returns:
        Hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for a text value.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    _reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        summary: Full preflight summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary["status"],
        "category_seed_db_apply_target_allowed": summary["category_seed_db_apply_target_allowed"],
        "database_host_class": summary["database_host_class"],
        "runtime_environment": summary["runtime_environment"],
        "db_connection_opened": False,
        "db_write_performed": False,
    }


def _failure_summary(*, output_path: Path, error: Exception) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Redacted failure payload.
    """
    _ = error
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": ERROR_STATUS,
        "generated_at": datetime.now(UTC).isoformat(),
        "output_name": output_path.name,
        "category_seed_db_apply_target_allowed": False,
        "db_connection_opened": False,
        "db_write_performed": False,
        "database_url_printed": False,
        "database_credentials_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


if __name__ == "__main__":
    main()
