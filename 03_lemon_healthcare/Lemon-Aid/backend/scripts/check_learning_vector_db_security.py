"""Check sensitive learning/vector/media DB posture without printing secrets."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import get_settings  # noqa: E402

SCHEMA_VERSION = "learning-vector-db-security-v9"
LEARNING_VECTOR_TABLES = (
    "learning_image_objects",
    "image_embedding_jobs",
    "image_embedding_records",
)
INTERNAL_MEDIA_TABLES = (
    "media_objects",
    "media_processing_runs",
    "supplement_image_evidence",
)
FOOD_MEAL_TABLES = (
    "meal_records",
    "meal_food_items",
    "food_image_analysis_runs",
)
HEALTH_PROFILE_TABLES = (
    "users",
    "health_sync_batches",
    "health_daily_summaries",
    "body_profile_snapshots",
    "health_metric_samples",
)
MEDICAL_RECORD_TABLES = (
    "regulated_documents",
    "prescription_items",
    "lab_result_items",
    "medical_record_collections",
    "patient_conditions",
    "patient_medications",
    "patient_status_snapshots",
)
LEARNING_RETRAINING_TABLES = (
    "learning_dataset_versions",
    "learning_dataset_items",
    "annotation_tasks",
    "model_training_runs",
    "model_registry",
    "model_eval_results",
)
SENSITIVE_INTERNAL_TABLES = (
    LEARNING_VECTOR_TABLES
    + INTERNAL_MEDIA_TABLES
    + FOOD_MEAL_TABLES
    + HEALTH_PROFILE_TABLES
    + MEDICAL_RECORD_TABLES
    + LEARNING_RETRAINING_TABLES
)
LEARNING_STORAGE_BUCKET = "learning-images"
LEARNING_STORAGE_FILE_SIZE_LIMIT_BYTES = 20 * 1024 * 1024
LEARNING_STORAGE_ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
SUPABASE_API_ROLES = ("PUBLIC", "anon", "authenticated", "service_role")
SUPABASE_CLIENT_STORAGE_ROLES = ("public", "anon", "authenticated")
SUPABASE_CLIENT_EXECUTE_ROLES = ("PUBLIC", "anon", "authenticated", "service_role")
FORBIDDEN_COLUMNS = (
    "image_bytes",
    "raw_image",
    "raw_image_bytes",
    "image_base64",
    "access_token",
    "device_payload",
    "diagnosis",
    "diagnosis_text",
    "ocr_text",
    "public_url",
    "provider_raw_payload",
    "prescription_instruction",
    "raw_payload",
    "raw_document",
    "raw_document_text",
    "raw_ocr_text",
    "provider_payload",
    "raw_provider_payload",
    "request_headers",
    "secret",
    "signed_url",
    "treatment_instruction",
    "treatment_instructions",
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any security check fails.",
    )
    return parser.parse_args()


async def collect_security_report() -> dict[str, Any]:
    """Collect a sanitized learning/vector/media DB security report.

    Returns:
        JSON-serializable report without database URLs, secrets, or raw data.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            vector_extension_installed = bool(
                await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                )
            )
            vector_extension_schema = await connection.scalar(text("""
                    SELECT n.nspname
                    FROM pg_extension e
                    JOIN pg_namespace n ON n.oid = e.extnamespace
                    WHERE e.extname = 'vector'
                    """))
            table_reports = []
            unsafe_privileges = []
            forbidden_columns = []
            unsafe_security_definer_functions = []
            storage_bucket_report = await _learning_storage_bucket_report(connection)
            unsafe_storage_policies = await _unsafe_learning_storage_policies(connection)
            unsafe_public_views = await _unsafe_public_views(connection)
            for table_name in SENSITIVE_INTERNAL_TABLES:
                table_reports.append(
                    await _table_security_report(connection, table_name=table_name)
                )
                unsafe_privileges.extend(
                    await _unsafe_privileges(connection, table_name=table_name)
                )
                forbidden_columns.extend(
                    await _forbidden_columns(connection, table_name=table_name)
                )
            unsafe_security_definer_functions.extend(
                await _unsafe_security_definer_functions(connection)
            )
    finally:
        await engine.dispose()

    passed = (
        vector_extension_installed
        and vector_extension_schema == "extensions"
        and all(table["exists"] and table["rls_enabled"] for table in table_reports)
        and not unsafe_privileges
        and not forbidden_columns
        and not unsafe_security_definer_functions
        and not unsafe_public_views
        and storage_bucket_report["exists"]
        and storage_bucket_report["private"]
        and storage_bucket_report["file_size_limit_ok"]
        and storage_bucket_report["allowed_mime_types_ok"]
        and not unsafe_storage_policies
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "vector_extension_installed": vector_extension_installed,
        "vector_extension_schema": vector_extension_schema,
        "tables": table_reports,
        "unsafe_privilege_count": len(unsafe_privileges),
        "unsafe_privileges": unsafe_privileges,
        "forbidden_column_count": len(forbidden_columns),
        "forbidden_columns": forbidden_columns,
        "unsafe_security_definer_function_count": len(unsafe_security_definer_functions),
        "unsafe_security_definer_functions": unsafe_security_definer_functions,
        "unsafe_public_view_count": len(unsafe_public_views),
        "unsafe_public_views": unsafe_public_views,
        "learning_storage_bucket": storage_bucket_report,
        "unsafe_learning_storage_policy_count": len(unsafe_storage_policies),
        "unsafe_learning_storage_policies": unsafe_storage_policies,
        "raw_image_bytes_stored_in_db": False,
        "raw_ocr_text_stored_in_db": False,
    }


async def _table_security_report(connection: Any, *, table_name: str) -> dict[str, Any]:
    """Return table existence and RLS status.

    Args:
        connection: Async SQLAlchemy connection.
        table_name: Public schema table name.

    Returns:
        Sanitized table security report.
    """
    row = (
        (
            await connection.execute(
                text("""
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = :table_name
                """),
                {"table_name": table_name},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return {
            "table": table_name,
            "exists": False,
            "rls_enabled": False,
            "rls_forced": False,
        }
    return {
        "table": table_name,
        "exists": True,
        "rls_enabled": bool(row["relrowsecurity"]),
        "rls_forced": bool(row["relforcerowsecurity"]),
    }


async def _unsafe_privileges(connection: Any, *, table_name: str) -> list[dict[str, str]]:
    """Return Supabase API-role privileges that should be absent.

    Args:
        connection: Async SQLAlchemy connection.
        table_name: Public schema table name.

    Returns:
        Unsafe privilege rows.
    """
    rows = (
        (
            await connection.execute(
                text("""
                SELECT grantee, privilege_type
                FROM information_schema.table_privileges
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND grantee IN :roles
                ORDER BY grantee, privilege_type
                """).bindparams(bindparam("roles", expanding=True)),
                {"table_name": table_name, "roles": list(SUPABASE_API_ROLES)},
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "table": table_name,
            "grantee": str(row["grantee"]),
            "privilege_type": str(row["privilege_type"]),
        }
        for row in rows
    ]


async def _forbidden_columns(connection: Any, *, table_name: str) -> list[dict[str, str]]:
    """Return forbidden raw payload columns if they exist.

    Args:
        connection: Async SQLAlchemy connection.
        table_name: Public schema table name.

    Returns:
        Forbidden column rows.
    """
    rows = (
        (
            await connection.execute(
                text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND lower(column_name) IN :forbidden_columns
                ORDER BY column_name
                """).bindparams(bindparam("forbidden_columns", expanding=True)),
                {"table_name": table_name, "forbidden_columns": list(FORBIDDEN_COLUMNS)},
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "table": table_name,
            "column": str(row["column_name"]),
        }
        for row in rows
    ]


async def _unsafe_security_definer_functions(connection: Any) -> list[dict[str, str]]:
    """Return public SECURITY DEFINER functions executable by Supabase API roles.

    Args:
        connection: Async SQLAlchemy connection.

    Returns:
        Unsafe function grants.
    """
    rows = (
        (
            await connection.execute(
                text("""
                SELECT
                    n.nspname AS schema_name,
                    p.proname AS function_name,
                    pg_get_function_identity_arguments(p.oid) AS arguments,
                    COALESCE(grantee.rolname, 'PUBLIC') AS role_name
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                CROSS JOIN LATERAL aclexplode(
                    COALESCE(p.proacl, acldefault('f', p.proowner))
                ) AS acl
                LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
                WHERE n.nspname = 'public'
                  AND p.prosecdef
                  AND acl.privilege_type = 'EXECUTE'
                  AND (
                    acl.grantee = 0
                    OR grantee.rolname IN ('anon', 'authenticated', 'service_role')
                  )
                ORDER BY n.nspname, p.proname, role_name
                """),
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "schema": str(row["schema_name"]),
            "function": str(row["function_name"]),
            "arguments": str(row["arguments"]),
            "grantee": str(row["role_name"]),
        }
        for row in rows
    ]


def _view_has_security_invoker(reloptions: str) -> bool:
    """Return whether a Postgres view reloptions string enables security invoker.

    Args:
        reloptions: Comma-separated reloptions from ``pg_class.reloptions``.

    Returns:
        True when ``security_invoker=true`` is present.
    """
    normalized = "".join(char for char in reloptions.casefold() if not char.isspace())
    return "security_invoker=true" in normalized


def _public_view_exposure_reason(*, relkind: str, reloptions: str) -> str | None:
    """Return the fail-closed reason for a public view exposed to API roles.

    Args:
        relkind: Postgres relation kind from ``pg_class.relkind``.
        reloptions: Comma-separated reloptions from ``pg_class.reloptions``.

    Returns:
        Sanitized reason code when the view exposure is unsafe, otherwise None.
    """
    if relkind == "m":
        return "materialized_view_exposed"
    if relkind == "v" and not _view_has_security_invoker(reloptions):
        return "security_invoker_missing"
    return None


async def _unsafe_public_views(connection: Any) -> list[dict[str, str]]:
    """Return public views that could expose data through Supabase API roles.

    Args:
        connection: Async SQLAlchemy connection.

    Returns:
        Sanitized view summaries without view definitions or query text.
    """
    rows = (
        (
            await connection.execute(
                text("""
                SELECT
                    n.nspname AS schema_name,
                    c.relname AS view_name,
                    c.relkind AS relkind,
                    COALESCE(array_to_string(c.reloptions, ','), '') AS reloptions,
                    COALESCE(grantee.rolname, 'PUBLIC') AS role_name,
                    acl.privilege_type
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                CROSS JOIN LATERAL aclexplode(
                    COALESCE(c.relacl, acldefault('r', c.relowner))
                ) AS acl
                LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('v', 'm')
                  AND acl.privilege_type = 'SELECT'
                  AND (
                    acl.grantee = 0
                    OR grantee.rolname IN ('anon', 'authenticated', 'service_role')
                  )
                ORDER BY n.nspname, c.relname, role_name
                """),
            )
        )
        .mappings()
        .all()
    )
    unsafe = []
    for row in rows:
        reason = _public_view_exposure_reason(
            relkind=str(row["relkind"]),
            reloptions=str(row["reloptions"]),
        )
        if reason is None:
            continue
        unsafe.append(
            {
                "schema": str(row["schema_name"]),
                "view": str(row["view_name"]),
                "object_type": ("materialized_view" if row["relkind"] == "m" else "view"),
                "grantee": str(row["role_name"]),
                "privilege_type": str(row["privilege_type"]),
                "reason": reason,
            }
        )
    return unsafe


async def _learning_storage_bucket_report(connection: Any) -> dict[str, Any]:
    """Return private Storage bucket posture for retained learning images.

    Args:
        connection: Async SQLAlchemy connection.

    Returns:
        Sanitized Storage bucket report.
    """
    storage_schema_available = bool(
        await connection.scalar(text("SELECT to_regclass('storage.buckets') IS NOT NULL"))
    )
    if not storage_schema_available:
        return {
            "bucket": LEARNING_STORAGE_BUCKET,
            "storage_schema_available": False,
            "exists": False,
            "private": False,
            "file_size_limit_bytes": None,
            "file_size_limit_ok": False,
            "allowed_mime_types": [],
            "allowed_mime_types_ok": False,
        }
    row = (
        (
            await connection.execute(
                text("""
                SELECT id, public, file_size_limit, allowed_mime_types
                FROM storage.buckets
                WHERE id = :bucket
                """),
                {"bucket": LEARNING_STORAGE_BUCKET},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return {
            "bucket": LEARNING_STORAGE_BUCKET,
            "storage_schema_available": True,
            "exists": False,
            "private": False,
            "file_size_limit_bytes": None,
            "file_size_limit_ok": False,
            "allowed_mime_types": [],
            "allowed_mime_types_ok": False,
        }
    file_size_limit = row["file_size_limit"]
    file_size_limit_bytes = int(file_size_limit) if file_size_limit is not None else None
    allowed_mime_types = sorted(str(item) for item in (row["allowed_mime_types"] or []))
    return {
        "bucket": LEARNING_STORAGE_BUCKET,
        "storage_schema_available": True,
        "exists": True,
        "private": not bool(row["public"]),
        "file_size_limit_bytes": file_size_limit_bytes,
        "file_size_limit_ok": file_size_limit_bytes == LEARNING_STORAGE_FILE_SIZE_LIMIT_BYTES,
        "allowed_mime_types": allowed_mime_types,
        "allowed_mime_types_ok": set(allowed_mime_types)
        == set(LEARNING_STORAGE_ALLOWED_MIME_TYPES),
    }


async def _unsafe_learning_storage_policies(connection: Any) -> list[dict[str, str]]:
    """Return Storage policies that could expose the private learning bucket.

    Args:
        connection: Async SQLAlchemy connection.

    Returns:
        Sanitized policy summaries without raw SQL expressions.
    """
    storage_schema_available = bool(
        await connection.scalar(text("SELECT to_regclass('pg_catalog.pg_policies') IS NOT NULL"))
    )
    if not storage_schema_available:
        return []
    rows = (
        (
            await connection.execute(
                text("""
                SELECT tablename, policyname, roles::text AS roles, cmd,
                       COALESCE(qual, '') AS qual,
                       COALESCE(with_check, '') AS with_check
                FROM pg_policies
                WHERE schemaname = 'storage'
                  AND tablename IN ('objects', 'buckets')
                ORDER BY tablename, policyname
                """),
            )
        )
        .mappings()
        .all()
    )
    unsafe = []
    for row in rows:
        roles_text = str(row["roles"]).casefold()
        if not any(role in roles_text for role in SUPABASE_CLIENT_STORAGE_ROLES):
            continue
        expression = f"{row['qual']} {row['with_check']}".casefold()
        targets_learning_bucket = LEARNING_STORAGE_BUCKET.casefold() in expression
        has_bucket_guard = (
            "bucket_id" in expression if row["tablename"] == "objects" else "id" in expression
        )
        if targets_learning_bucket or not has_bucket_guard:
            unsafe.append(
                {
                    "table": str(row["tablename"]),
                    "policy": str(row["policyname"]),
                    "roles": str(row["roles"]),
                    "command": str(row["cmd"]),
                    "reason": (
                        "targets_learning_bucket"
                        if targets_learning_bucket
                        else "missing_bucket_guard"
                    ),
                }
            )
    return unsafe


async def run_preflight(
    *,
    strict: bool = False,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run the security preflight and write sanitized JSON.

    Args:
        strict: Return a failing exit code when checks do not pass.
        stdout: Destination for successful report JSON.
        stderr: Destination for connection or execution failure JSON.

    Returns:
        Process-style exit code.
    """
    try:
        report = await collect_security_report()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "failed",
                    "error_type": exc.__class__.__name__,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), file=stdout)
    if strict and not report["passed"]:
        return 1
    return 0


def main() -> None:
    """Run the DB security check."""
    args = parse_args()
    raise SystemExit(asyncio.run(run_preflight(strict=args.strict)))


if __name__ == "__main__":
    main()
