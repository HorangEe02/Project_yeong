#!/usr/bin/env python3
"""Verify Supabase pgvector migration prerequisites.

This verifier is intentionally secret-safe. It reports schema posture, local
index inventory, and optional remote database status without printing database
URLs, JWTs, Supabase keys, or Ollama proxy secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC_REFERENCES = (
    "https://supabase.com/docs/guides/ai",
    "https://supabase.com/docs/guides/ai/semantic-search",
    "https://supabase.com/docs/guides/ai/vector-columns",
    "https://supabase.com/docs/guides/ai/vector-indexes",
    "https://supabase.com/docs/guides/api/securing-your-api",
    "https://supabase.com/changelog?tags=database",
)

PGVECTOR_MIGRATION_GLOBS = (
    "*pgvector*.sql",
    "*vector*.sql",
)
REQUIRED_TABLES = (
    "document_chunks",
    "document_embeddings",
    "employee_embeddings",
    "rag_collections",
    "rag_chunks",
    "rag_chunk_embeddings",
)
REQUIRED_PRIVATE_FUNCTIONS = (
    "match_document_chunks",
    "hybrid_search_document_chunks",
    "match_employee_profiles",
    "match_rag_chunks",
)
REQUIRED_SQL_FRAGMENTS = {
    "pgvector_extension": "create extension if not exists vector with schema extensions",
    "vector_dimension": "extensions.vector(1024)",
    "hnsw_index": "using hnsw",
    "embedding_version": "embedding_version",
    "rls": "enable row level security",
    "client_revoke": "from anon, authenticated",
    "private_schema": "create schema if not exists private",
    "service_role_execute": "grant execute on all functions in schema private to service_role",
}
CHROMA_COLLECTIONS = (
    ("ajin_documents", "document_chroma"),
    ("employee_profiles", "employee_chroma"),
)
DEFAULT_EMBEDDING_MODEL = "bge-m3"
DEFAULT_EMBEDDING_DIM = 1024


@dataclass(frozen=True)
class CheckResult:
    """Single pgvector prerequisite check result.

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
        """Return a JSON-serializable check result.

        Returns:
            dict[str, Any]: Result fields for JSON and Markdown reports.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class PgvectorPrereqConfig:
    """Runtime configuration for the pgvector prerequisite verifier.

    Args:
        root: Repository root.
        strict: Whether fail checks should produce non-zero exit status.
        skip_remote: Whether remote Postgres checks should be skipped.
        require_remote: Whether missing remote DB credentials should fail.
        embedding_smoke: Whether to call Ollama embeddings and validate dim.
        embedding_model: Ollama embedding model name.
        expected_dim: Expected embedding vector dimension.
    """

    root: Path = ROOT
    strict: bool = False
    skip_remote: bool = False
    require_remote: bool = False
    embedding_smoke: bool = False
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    expected_dim: int = DEFAULT_EMBEDDING_DIM


def _display_path(root: Path, path: Path) -> str:
    """Return a repository-relative path when possible.

    Args:
        root: Repository root.
        path: Path to display.

    Returns:
        str: Secret-safe display path.
    """

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _status_summary(checks: Sequence[CheckResult]) -> dict[str, Any]:
    """Summarize check statuses.

    Args:
        checks: Check results.

    Returns:
        dict[str, Any]: Aggregate counts and overall status.
    """

    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    if counts["fail"]:
        status = "fail"
    elif counts["warn"]:
        status = "warn"
    else:
        status = "pass"
    return {"status": status, "counts": counts}


def find_pgvector_migration(root: Path) -> Path | None:
    """Find the latest local pgvector migration.

    Args:
        root: Repository root.

    Returns:
        Path | None: Latest migration path, if present.
    """

    migration_dir = root / "supabase" / "migrations"
    candidates: set[Path] = set()
    if not migration_dir.exists():
        return None
    for pattern in PGVECTOR_MIGRATION_GLOBS:
        candidates.update(migration_dir.glob(pattern))
    if not candidates:
        return None

    base_schema_candidates: list[Path] = []
    for candidate in sorted(candidates):
        try:
            sql = candidate.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        if "create table if not exists public.document_chunks" in sql:
            base_schema_candidates.append(candidate)
    return sorted(base_schema_candidates or candidates)[-1]


def verify_local_migration(config: PgvectorPrereqConfig) -> CheckResult:
    """Verify the local Supabase pgvector migration file.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Migration posture.
    """

    migration = find_pgvector_migration(config.root)
    if migration is None:
        return CheckResult(
            "local_pgvector_migration",
            "fail",
            "Supabase pgvector migration is missing",
            {"expected_dir": "supabase/migrations"},
        )

    sql = migration.read_text(encoding="utf-8")
    normalized = " ".join(sql.lower().split())
    missing_fragments = [
        name
        for name, fragment in REQUIRED_SQL_FRAGMENTS.items()
        if fragment not in normalized
    ]
    missing_tables = [
        table
        for table in REQUIRED_TABLES
        if f"public.{table}" not in normalized
    ]
    missing_functions = [
        function_name
        for function_name in REQUIRED_PRIVATE_FUNCTIONS
        if f"private.{function_name}" not in normalized
    ]
    missing = missing_fragments + [f"table:{name}" for name in missing_tables]
    missing += [f"function:{name}" for name in missing_functions]

    if missing:
        return CheckResult(
            "local_pgvector_migration",
            "fail",
            "Supabase pgvector migration is incomplete",
            {
                "path": _display_path(config.root, migration),
                "missing": missing,
            },
        )

    return CheckResult(
        "local_pgvector_migration",
        "pass",
        "Supabase pgvector migration defines backend-only vector store schema",
        {
            "path": _display_path(config.root, migration),
            "tables": list(REQUIRED_TABLES),
            "private_functions": list(REQUIRED_PRIVATE_FUNCTIONS),
            "embedding_dim": config.expected_dim,
        },
    )


def _load_bm25_count(path: Path) -> tuple[str, int | None, str | None]:
    """Load the local BM25 corpus count.

    Args:
        path: BM25 corpus JSON path.

    Returns:
        tuple[str, int | None, str | None]: Status, count, and optional error.
    """

    if not path.exists():
        return ("warn", None, "bm25_corpus.json missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ("fail", None, type(exc).__name__)
    if not isinstance(data, list):
        return ("fail", None, "BM25 corpus is not a list")
    return ("pass", len(data), None)


def verify_local_chroma_inventory(config: PgvectorPrereqConfig) -> CheckResult:
    """Inspect local Chroma/BM25 inventory before migration.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Inventory check.
    """

    vectorstore = config.root / "vectorstore"
    bm25_status, bm25_count, bm25_error = _load_bm25_count(vectorstore / "bm25_corpus.json")
    details: dict[str, Any] = {
        "vectorstore_exists": vectorstore.exists(),
        "bm25_status": bm25_status,
        "bm25_chunk_count": bm25_count,
    }
    if bm25_error:
        details["bm25_error"] = bm25_error

    chroma_counts: dict[str, int | None] = {}
    chroma_errors: dict[str, str] = {}
    try:
        import chromadb  # type: ignore[import-not-found]
    except Exception as exc:
        details["chroma_import_error"] = type(exc).__name__
        return CheckResult(
            "local_chroma_inventory",
            "warn",
            "Chroma package is unavailable; only BM25 inventory was inspected",
            details,
        )

    try:
        client = chromadb.PersistentClient(path=str(vectorstore))
        for collection_name, detail_key in CHROMA_COLLECTIONS:
            try:
                collection = client.get_collection(collection_name)
                chroma_counts[detail_key] = int(collection.count())
            except Exception as exc:
                chroma_counts[detail_key] = None
                chroma_errors[detail_key] = type(exc).__name__
    except Exception as exc:
        details["chroma_client_error"] = type(exc).__name__
        return CheckResult(
            "local_chroma_inventory",
            "warn",
            "Chroma client could not inspect local vectorstore",
            details,
        )

    details["chroma_counts"] = chroma_counts
    if chroma_errors:
        details["chroma_errors"] = chroma_errors
    status = "pass" if bm25_status == "pass" else bm25_status
    summary = "Local Chroma/BM25 inventory captured for pgvector migration"
    return CheckResult("local_chroma_inventory", status, summary, details)


def _database_url_present() -> bool:
    """Return whether a remote database URL is configured.

    Returns:
        bool: True when ``DATABASE_URL`` or ``AJIN_DATABASE_URL`` exists.
    """

    return bool(os.getenv("DATABASE_URL") or os.getenv("AJIN_DATABASE_URL"))


def _connect_remote(db_url: str):
    """Open a remote Postgres connection using available psycopg package.

    Args:
        db_url: Database URL. The caller must not print it.

    Returns:
        Any: psycopg connection.

    Raises:
        ImportError: When no supported driver is installed.
    """

    try:
        import psycopg  # type: ignore[import-not-found]

        return psycopg.connect(db_url, connect_timeout=10)
    except ImportError:
        import psycopg2  # type: ignore[import-not-found]

        return psycopg2.connect(db_url, connect_timeout=10)


def verify_remote_pgvector(config: PgvectorPrereqConfig) -> CheckResult:
    """Optionally verify remote Supabase/Postgres pgvector posture.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Remote DB posture.
    """

    if config.skip_remote:
        return CheckResult(
            "remote_pgvector_posture",
            "skip",
            "Remote pgvector check skipped by option",
        )

    db_url = os.getenv("DATABASE_URL") or os.getenv("AJIN_DATABASE_URL")
    if not db_url:
        status = "fail" if config.require_remote else "skip"
        return CheckResult(
            "remote_pgvector_posture",
            status,
            "Remote DATABASE_URL is not configured",
            {"credential_presence": False, "required": config.require_remote},
        )

    try:
        conn = _connect_remote(db_url)
    except Exception as exc:
        return CheckResult(
            "remote_pgvector_posture",
            "fail",
            "Remote Postgres connection failed",
            {"credential_presence": True, "error": type(exc).__name__},
        )

    try:
        with conn:
            cur = conn.cursor()
            cur.execute("select exists(select 1 from pg_extension where extname = 'vector')")
            vector_enabled = bool(cur.fetchone()[0])
            table_status: dict[str, dict[str, Any]] = {}
            for table in REQUIRED_TABLES:
                cur.execute(
                    """
                    select
                      to_regclass(%s) is not null as exists,
                      coalesce(c.relrowsecurity, false) as rls_enabled,
                      has_table_privilege('anon', %s, 'select') as anon_select,
                      has_table_privilege('authenticated', %s, 'select') as authenticated_select
                    from (select %s::text as table_name) t
                    left join pg_class c on c.oid = to_regclass(t.table_name)
                    """,
                    (
                        f"public.{table}",
                        f"public.{table}",
                        f"public.{table}",
                        f"public.{table}",
                    ),
                )
                row = cur.fetchone()
                table_status[table] = {
                    "exists": bool(row[0]),
                    "rls_enabled": bool(row[1]),
                    "anon_select": bool(row[2]),
                    "authenticated_select": bool(row[3]),
                }
            cur.execute(
                """
                select proname
                  from pg_proc p
                  join pg_namespace n on n.oid = p.pronamespace
                 where n.nspname = 'private'
                   and proname = any(%s)
                """,
                (list(REQUIRED_PRIVATE_FUNCTIONS),),
            )
            present_functions = sorted(row[0] for row in cur.fetchall())
    finally:
        conn.close()

    missing_tables = [
        name
        for name, status in table_status.items()
        if not status["exists"] or not status["rls_enabled"]
    ]
    exposed_tables = [
        name
        for name, status in table_status.items()
        if status["anon_select"] or status["authenticated_select"]
    ]
    missing_functions = sorted(set(REQUIRED_PRIVATE_FUNCTIONS) - set(present_functions))
    failures: list[str] = []
    if not vector_enabled:
        failures.append("vector_extension")
    failures.extend(f"table:{name}" for name in missing_tables)
    failures.extend(f"client_grant:{name}" for name in exposed_tables)
    failures.extend(f"function:{name}" for name in missing_functions)

    if failures:
        return CheckResult(
            "remote_pgvector_posture",
            "fail",
            "Remote pgvector schema is not release-ready",
            {
                "credential_presence": True,
                "vector_enabled": vector_enabled,
                "failures": failures,
                "table_status": table_status,
                "private_functions": present_functions,
            },
        )

    return CheckResult(
        "remote_pgvector_posture",
        "pass",
        "Remote pgvector schema has vector extension, RLS, no client grants, and private RPC functions",
        {
            "credential_presence": True,
            "vector_enabled": vector_enabled,
            "table_status": table_status,
            "private_functions": present_functions,
        },
    )


async def _run_embedding_smoke(config: PgvectorPrereqConfig) -> CheckResult:
    """Run the optional Ollama embedding dimension smoke.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Embedding smoke status.
    """

    try:
        from core.providers.ollama_provider import OllamaProvider
    except Exception as exc:
        return CheckResult(
            "embedding_dimension_smoke",
            "fail",
            "Ollama provider could not be imported",
            {"error": type(exc).__name__},
        )

    provider = OllamaProvider(timeout=15)
    try:
        embedding = await provider.embed("AJIN pgvector embedding dimension check", config.embedding_model)
    except Exception as exc:
        return CheckResult(
            "embedding_dimension_smoke",
            "fail",
            "Ollama embedding request failed",
            {"model": config.embedding_model, "error": type(exc).__name__},
        )

    dim = len(embedding)
    if dim != config.expected_dim:
        return CheckResult(
            "embedding_dimension_smoke",
            "fail",
            "Embedding dimension does not match pgvector schema",
            {
                "model": config.embedding_model,
                "expected_dim": config.expected_dim,
                "actual_dim": dim,
            },
        )

    return CheckResult(
        "embedding_dimension_smoke",
        "pass",
        "Ollama embedding dimension matches pgvector schema",
        {"model": config.embedding_model, "actual_dim": dim},
    )


def verify_embedding_smoke(config: PgvectorPrereqConfig) -> CheckResult:
    """Run or skip the embedding dimension smoke.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Embedding smoke status.
    """

    if not config.embedding_smoke:
        return CheckResult(
            "embedding_dimension_smoke",
            "skip",
            "Embedding smoke skipped; pass --embedding-smoke to call Ollama",
            {"expected_dim": config.expected_dim, "model": config.embedding_model},
        )
    return asyncio.run(_run_embedding_smoke(config))


def run_verification(config: PgvectorPrereqConfig) -> dict[str, Any]:
    """Run all pgvector prerequisite checks.

    Args:
        config: Verifier config.

    Returns:
        dict[str, Any]: Secret-safe verification report.
    """

    checks = [
        verify_local_migration(config),
        verify_local_chroma_inventory(config),
        verify_remote_pgvector(config),
        verify_embedding_smoke(config),
    ]
    summary = _status_summary(checks)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "checks": [check.to_dict() for check in checks],
        "references": list(DOC_REFERENCES),
    }


def write_markdown(report: Mapping[str, Any], path: Path) -> None:
    """Write a secret-safe Markdown report.

    Args:
        report: Verification report.
        path: Output path.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AJIN Supabase pgvector Prerequisite Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Overall status: `{report['summary']['status']}`",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        lines.append(f"### {check['name']} — {check['status']}")
        lines.append("")
        lines.append(check["summary"])
        if check.get("details"):
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(check["details"], ensure_ascii=False, indent=2, sort_keys=True))
            lines.append("```")
        lines.append("")
    lines.extend(["## References", ""])
    for ref in report["references"]:
        lines.append(f"- {ref}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument vector.

    Returns:
        argparse.Namespace: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit 1 when fail checks exist.")
    parser.add_argument("--skip-remote", action="store_true", help="Skip remote Postgres checks.")
    parser.add_argument("--require-remote", action="store_true", help="Fail when DATABASE_URL is missing.")
    parser.add_argument("--embedding-smoke", action="store_true", help="Call Ollama embeddings and check dim.")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--expected-dim", type=int, default=DEFAULT_EMBEDDING_DIM)
    parser.add_argument("--markdown", type=Path, help="Write Markdown report to path.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entrypoint.

    Args:
        argv: Optional argument vector.

    Returns:
        int: Process exit status.
    """

    args = parse_args(argv)
    config = PgvectorPrereqConfig(
        strict=args.strict,
        skip_remote=args.skip_remote,
        require_remote=args.require_remote,
        embedding_smoke=args.embedding_smoke,
        embedding_model=args.embedding_model,
        expected_dim=args.expected_dim,
    )
    report = run_verification(config)
    if args.markdown:
        write_markdown(report, args.markdown)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "pgvector-prereq:",
            report["summary"]["status"],
            json.dumps(report["summary"]["counts"], sort_keys=True),
        )
    if args.strict and report["summary"]["counts"]["fail"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
