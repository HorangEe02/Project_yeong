#!/usr/bin/env python3
"""Verify and repair Feature A search index consistency.

The verifier is secret-safe: it reports counts, ids, and status only. It never
prints database URLs, Supabase keys, or credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC_REFERENCES = (
    "https://docs.trychroma.com/reference/python/collection",
    "https://www.sqlite.org/fts5.html",
    "https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert",
    "https://supabase.com/docs/guides/api/securing-your-api",
)
REQUIRED_EMPLOYEE_COLUMNS = {
    "employee_id",
    "name",
    "department",
    "position",
    "is_active",
    "is_synthetic",
    "data_class",
    "source_system",
    "canonical_employee_id",
}
REAL_ACTIVE_SQL = "COALESCE(is_active, 1) = 1 AND data_class = 'real'"
EMPLOYEE_CHROMA_COLLECTION = "employee_profiles"
DOCUMENT_CHROMA_COLLECTION = "ajin_documents"
MAX_ID_DETAILS = 25
MAX_CHROMA_SCAN = 10_000


@dataclass(frozen=True)
class CheckResult:
    """Single Feature A consistency check result.

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
        """Return a JSON-serializable result.

        Returns:
            dict[str, Any]: Check fields for console, JSON, or Markdown output.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class FeatureAConfig:
    """Runtime configuration for the Feature A consistency verifier.

    Args:
        root: Repository root.
        employees_db: SQLite employees database path.
        vectorstore_path: Chroma/BM25 vectorstore root path.
        strict: Whether fail checks should return a non-zero process status.
        repair: Whether safe employee index repair should be performed.
        repair_documents: Whether full document index rebuild is allowed.
    """

    root: Path = ROOT
    employees_db: Path = ROOT / "data" / "employees.db"
    vectorstore_path: Path = ROOT / "vectorstore"
    strict: bool = False
    repair: bool = False
    repair_documents: bool = False


@dataclass(frozen=True)
class EmployeeSource:
    """SQLite employee source snapshot.

    Args:
        checks: Source validation checks.
        real_active: Real active employee rows.
        total_count: Total SQLite employee count.
    """

    checks: tuple[CheckResult, ...]
    real_active: tuple[dict[str, Any], ...]
    total_count: int = 0

    @property
    def ok(self) -> bool:
        """Return whether the source can drive downstream checks.

        Returns:
            bool: True when no source check failed.
        """

        return all(check.status != "fail" for check in self.checks)


@dataclass(frozen=True)
class CoverageResult:
    """Coverage check result with id deltas.

    Args:
        check: Public check result.
        missing_ids: Expected ids missing from the target index.
        extra_ids: Target ids outside the real active source set.
    """

    check: CheckResult
    missing_ids: tuple[str, ...] = ()
    extra_ids: tuple[str, ...] = ()


ChromaCollectionLoader = Callable[[Path, str], Any]
EmployeeIndexer = Callable[[dict[str, Any]], bool]


def _resolve_path(root: Path, value: str | Path) -> Path:
    """Resolve a path relative to the repository root when needed.

    Args:
        root: Repository root.
        value: Input path.

    Returns:
        Path: Absolute path.
    """

    path = Path(value)
    return path if path.is_absolute() else root / path


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


def _clip_ids(ids: Sequence[str]) -> list[str]:
    """Return a bounded, sorted id sample for reports.

    Args:
        ids: Id values.

    Returns:
        list[str]: Sorted id sample.
    """

    return sorted(str(value) for value in ids)[:MAX_ID_DETAILS]


def _sqlite_connect(path: Path):
    """Open a SQLite connection with row dictionaries.

    Args:
        path: SQLite database path.

    Returns:
        sqlite3.Connection: Open connection.
    """

    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _sqlite_table_exists(conn, name: str) -> bool:
    """Return whether a SQLite table exists.

    Args:
        conn: SQLite connection.
        name: Table name.

    Returns:
        bool: True when present.
    """

    row = conn.execute(
        "select 1 from sqlite_master where type in ('table', 'view') and name = ?",
        (name,),
    ).fetchone()
    return row is not None


def inspect_employee_source(config: FeatureAConfig) -> EmployeeSource:
    """Inspect the authoritative SQLite employee source.

    Args:
        config: Verifier config.

    Returns:
        EmployeeSource: Source checks and real active rows.
    """

    if not config.employees_db.exists():
        return EmployeeSource(
            checks=(
                CheckResult(
                    "sqlite_employee_source",
                    "fail",
                    "employees.db is missing",
                    {"path": _display_path(config.root, config.employees_db)},
                ),
            ),
            real_active=(),
        )

    try:
        conn = _sqlite_connect(config.employees_db)
    except Exception as exc:
        return EmployeeSource(
            checks=(
                CheckResult(
                    "sqlite_employee_source",
                    "fail",
                    "employees.db could not be opened",
                    {"error": type(exc).__name__},
                ),
            ),
            real_active=(),
        )

    try:
        if not _sqlite_table_exists(conn, "employees"):
            return EmployeeSource(
                checks=(
                    CheckResult(
                        "sqlite_employee_source",
                        "fail",
                        "employees table is missing",
                    ),
                ),
                real_active=(),
            )
        columns = {row["name"] for row in conn.execute("pragma table_info(employees)").fetchall()}
        missing_columns = sorted(REQUIRED_EMPLOYEE_COLUMNS - columns)
        total = int(conn.execute("select count(*) from employees").fetchone()[0] or 0)
        source_status = "pass" if not missing_columns else "fail"
        source_check = CheckResult(
            "sqlite_employee_source",
            source_status,
            "employees.db has required Feature A lineage columns"
            if source_status == "pass"
            else "employees.db is missing required Feature A columns",
            {"total": total, "missing_columns": missing_columns},
        )
        if missing_columns:
            return EmployeeSource(checks=(source_check,), real_active=(), total_count=total)

        rows = [
            dict(row)
            for row in conn.execute(
                f"select * from employees where {REAL_ACTIVE_SQL} order by employee_id"
            ).fetchall()
        ]
        count_check = CheckResult(
            "real_active_employee_set",
            "pass" if rows else "fail",
            f"{len(rows)} real active employees found"
            if rows
            else "no real active employees found for Feature A release gate",
            {"real_active_count": len(rows), "sample_ids": _clip_ids([r["employee_id"] for r in rows])},
        )
        return EmployeeSource(checks=(source_check, count_check), real_active=tuple(rows), total_count=total)
    finally:
        conn.close()


def inspect_fts_coverage(config: FeatureAConfig, real_employees: Sequence[Mapping[str, Any]]) -> CoverageResult:
    """Check SQLite FTS5 rowid coverage for real active employees.

    Args:
        config: Verifier config.
        real_employees: Authoritative real active employee rows.

    Returns:
        CoverageResult: FTS coverage result.
    """

    expected_ids = {str(row["employee_id"]) for row in real_employees}
    try:
        conn = _sqlite_connect(config.employees_db)
        if not _sqlite_table_exists(conn, "employees_fts"):
            return CoverageResult(
                CheckResult(
                    "fts5_employee_coverage",
                    "fail",
                    "employees_fts table is missing",
                    {"expected_real_active": len(expected_ids)},
                ),
                missing_ids=tuple(sorted(expected_ids)),
            )
        fts_total = int(conn.execute("select count(*) from employees_fts").fetchone()[0] or 0)
        rows = conn.execute(
            f"""select e.employee_id
                  from employees e
                  left join employees_fts fts on e.rowid = fts.rowid
                 where {REAL_ACTIVE_SQL}
                   and fts.rowid is null
                 order by e.employee_id"""
        ).fetchall()
        missing_ids = tuple(str(row["employee_id"]) for row in rows)
    except Exception as exc:
        return CoverageResult(
            CheckResult(
                "fts5_employee_coverage",
                "fail",
                "FTS5 coverage could not be inspected",
                {"error": type(exc).__name__},
            ),
            missing_ids=tuple(sorted(expected_ids)),
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if missing_ids:
        return CoverageResult(
            CheckResult(
                "fts5_employee_coverage",
                "fail",
                f"{len(missing_ids)} real active employees are missing from employees_fts",
                {
                    "fts_total": fts_total,
                    "missing_count": len(missing_ids),
                    "missing_sample": _clip_ids(missing_ids),
                },
            ),
            missing_ids=missing_ids,
        )
    return CoverageResult(
        CheckResult(
            "fts5_employee_coverage",
            "pass",
            "employees_fts covers all real active employees",
            {"fts_total": fts_total, "real_active_count": len(expected_ids)},
        ),
    )


def repair_fts_index(config: FeatureAConfig) -> CheckResult:
    """Rebuild the SQLite FTS5 employee index.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Repair result.
    """

    try:
        from features.search.employee.fts_index import rebuild_fts_index

        indexed = rebuild_fts_index(config.employees_db)
        return CheckResult(
            "repair_fts5_rebuild",
            "pass",
            f"employees_fts rebuilt with {indexed} rows",
            {"indexed": indexed},
        )
    except Exception as exc:
        return CheckResult(
            "repair_fts5_rebuild",
            "fail",
            "employees_fts rebuild failed",
            {"error": type(exc).__name__},
        )


def load_chroma_collection(path: Path, collection_name: str):
    """Load a Chroma collection.

    Args:
        path: Chroma persistent path.
        collection_name: Collection name.

    Returns:
        chromadb.Collection: Loaded collection.
    """

    import chromadb

    client = chromadb.PersistentClient(path=str(path))
    return client.get_collection(collection_name)


def _metadata_employee_id(record_id: str, metadata: Mapping[str, Any] | None) -> str:
    """Extract an employee id from Chroma metadata or id.

    Args:
        record_id: Chroma record id.
        metadata: Chroma metadata.

    Returns:
        str: Employee id if present.
    """

    if metadata and metadata.get("employee_id"):
        return str(metadata["employee_id"])
    if record_id.startswith("emp_"):
        return record_id.removeprefix("emp_")
    return record_id


def _safe_collection_get(collection: Any, **kwargs):
    """Call Chroma collection.get with compatibility fallback.

    Args:
        collection: Chroma-like collection.
        kwargs: Keyword arguments.

    Returns:
        Mapping[str, Any]: Collection get result.
    """

    try:
        return collection.get(**kwargs)
    except TypeError:
        kwargs.pop("include", None)
        return collection.get(**kwargs)


def inspect_chroma_employee_coverage(
    config: FeatureAConfig,
    real_employees: Sequence[Mapping[str, Any]],
    *,
    collection_loader: ChromaCollectionLoader = load_chroma_collection,
) -> CoverageResult:
    """Check Chroma employee profile coverage for real active employees.

    Args:
        config: Verifier config.
        real_employees: Authoritative real active employee rows.
        collection_loader: Chroma collection loader for tests.

    Returns:
        CoverageResult: Chroma employee coverage result.
    """

    real_ids = {str(row["employee_id"]) for row in real_employees}
    expected_record_ids = [f"emp_{employee_id}" for employee_id in sorted(real_ids)]
    try:
        collection = collection_loader(config.vectorstore_path, EMPLOYEE_CHROMA_COLLECTION)
        collection_count = int(collection.count())
    except Exception as exc:
        return CoverageResult(
            CheckResult(
                "employee_chroma_coverage",
                "fail",
                "employee_profiles Chroma collection could not be loaded",
                {"error": type(exc).__name__, "expected_real_active": len(real_ids)},
            ),
            missing_ids=tuple(sorted(real_ids)),
        )

    found_ids: set[str] = set()
    if expected_record_ids:
        try:
            result = _safe_collection_get(
                collection,
                ids=expected_record_ids,
                include=["metadatas"],
            )
            ids = [str(value) for value in result.get("ids", [])]
            metadatas = result.get("metadatas", []) or []
            for index, record_id in enumerate(ids):
                metadata = metadatas[index] if index < len(metadatas) else None
                employee_id = _metadata_employee_id(record_id, metadata)
                if employee_id in real_ids:
                    found_ids.add(employee_id)
        except Exception as exc:
            return CoverageResult(
                CheckResult(
                    "employee_chroma_coverage",
                    "fail",
                    "employee_profiles Chroma lookup failed",
                    {"error": type(exc).__name__, "collection_count": collection_count},
                ),
                missing_ids=tuple(sorted(real_ids)),
            )

    all_employee_ids: set[str] = set()
    scanned_all = False
    if 0 < collection_count <= MAX_CHROMA_SCAN:
        try:
            result = _safe_collection_get(
                collection,
                include=["metadatas"],
                limit=collection_count,
            )
            ids = [str(value) for value in result.get("ids", [])]
            metadatas = result.get("metadatas", []) or []
            for index, record_id in enumerate(ids):
                metadata = metadatas[index] if index < len(metadatas) else None
                employee_id = _metadata_employee_id(record_id, metadata)
                if employee_id:
                    all_employee_ids.add(employee_id)
            scanned_all = True
        except Exception:
            scanned_all = False

    missing_ids = tuple(sorted(real_ids - found_ids))
    extra_ids = tuple(sorted(all_employee_ids - real_ids)) if scanned_all else ()
    if missing_ids:
        return CoverageResult(
            CheckResult(
                "employee_chroma_coverage",
                "fail",
                f"{len(missing_ids)} real active employees are missing from Chroma",
                {
                    "collection_count": collection_count,
                    "missing_count": len(missing_ids),
                    "missing_sample": _clip_ids(missing_ids),
                    "extra_count": len(extra_ids),
                },
            ),
            missing_ids=missing_ids,
            extra_ids=extra_ids,
        )
    if extra_ids:
        return CoverageResult(
            CheckResult(
                "employee_chroma_coverage",
                "warn",
                "Chroma includes non-real-active employee profiles",
                {
                    "collection_count": collection_count,
                    "real_active_count": len(real_ids),
                    "extra_count": len(extra_ids),
                    "extra_sample": _clip_ids(extra_ids),
                },
            ),
            extra_ids=extra_ids,
        )
    return CoverageResult(
        CheckResult(
            "employee_chroma_coverage",
            "pass",
            "Chroma employee_profiles covers all real active employees",
            {"collection_count": collection_count, "real_active_count": len(real_ids)},
        ),
    )


def repair_chroma_employee_index(
    config: FeatureAConfig,
    real_employees: Sequence[Mapping[str, Any]],
    missing_ids: Sequence[str],
    *,
    employee_indexer: EmployeeIndexer | None = None,
) -> CheckResult:
    """Upsert missing real active employees into the Chroma employee index.

    Args:
        config: Verifier config.
        real_employees: Authoritative real active employee rows.
        missing_ids: Employee ids missing from Chroma.
        employee_indexer: Optional test double for ``index_employee_one``.

    Returns:
        CheckResult: Repair result.
    """

    missing_set = set(missing_ids)
    if not missing_set:
        return CheckResult("repair_employee_chroma_upsert", "skip", "no Chroma employee repair needed")
    rows = [dict(row) for row in real_employees if str(row["employee_id"]) in missing_set]
    if employee_indexer is None:
        from features.search.employee import semantic_search

        semantic_search.VECTORSTORE_PATH = str(config.vectorstore_path)
        employee_indexer = semantic_search.index_employee_one
    repaired: list[str] = []
    failed: list[str] = []
    for row in rows:
        try:
            ok = bool(employee_indexer(row))
        except Exception:
            ok = False
        if ok:
            repaired.append(str(row["employee_id"]))
        else:
            failed.append(str(row["employee_id"]))
    if failed:
        return CheckResult(
            "repair_employee_chroma_upsert",
            "fail",
            f"Chroma employee upsert failed for {len(failed)} rows",
            {"repaired": len(repaired), "failed_sample": _clip_ids(failed)},
        )
    return CheckResult(
        "repair_employee_chroma_upsert",
        "pass",
        f"Chroma employee upsert completed for {len(repaired)} rows",
        {"repaired": len(repaired), "repaired_sample": _clip_ids(repaired)},
    )


def _postgres_employee_ids() -> set[str]:
    """Read active employee ids from the configured Postgres mirror.

    Returns:
        set[str]: Active employee ids.

    Raises:
        RuntimeError: If Postgres mode is disabled or query fails.
    """

    import sqlalchemy as sa

    from core.db import create_sqlalchemy_engine, get_database_settings

    settings = get_database_settings()
    if settings.backend != "postgres":
        raise RuntimeError("APP_DB_BACKEND is not postgres")
    engine = create_sqlalchemy_engine()
    if engine.dialect.name == "postgresql":
        statement = sa.text("select employee_id from public.employees where is_active = true")
    else:
        statement = sa.text("select employee_id from employees where is_active = 1")
    with engine.connect() as conn:
        rows = conn.execute(statement).mappings().all()
    return {str(row["employee_id"]) for row in rows}


def inspect_postgres_employee_mirror(
    real_employees: Sequence[Mapping[str, Any]],
    *,
    reader: Callable[[], set[str]] = _postgres_employee_ids,
) -> CoverageResult:
    """Check Postgres employee mirror coverage for real active employees.

    Args:
        real_employees: Authoritative real active employee rows.
        reader: Optional test double that returns Postgres active ids.

    Returns:
        CoverageResult: Postgres mirror coverage result.
    """

    real_ids = {str(row["employee_id"]) for row in real_employees}
    try:
        pg_ids = set(reader())
    except Exception as exc:
        return CoverageResult(
            CheckResult(
                "postgres_employee_mirror",
                "fail",
                "Postgres employee mirror could not be inspected",
                {"error": type(exc).__name__, "expected_real_active": len(real_ids)},
            ),
            missing_ids=tuple(sorted(real_ids)),
        )
    missing_ids = tuple(sorted(real_ids - pg_ids))
    extra_ids = tuple(sorted(pg_ids - real_ids))
    if missing_ids:
        return CoverageResult(
            CheckResult(
                "postgres_employee_mirror",
                "fail",
                f"{len(missing_ids)} real active employees are missing from Postgres",
                {
                    "postgres_active_count": len(pg_ids),
                    "missing_count": len(missing_ids),
                    "missing_sample": _clip_ids(missing_ids),
                    "extra_count": len(extra_ids),
                },
            ),
            missing_ids=missing_ids,
            extra_ids=extra_ids,
        )
    if extra_ids:
        return CoverageResult(
            CheckResult(
                "postgres_employee_mirror",
                "warn",
                "Postgres contains active employees outside the real-active SQLite source",
                {
                    "postgres_active_count": len(pg_ids),
                    "extra_count": len(extra_ids),
                    "extra_sample": _clip_ids(extra_ids),
                },
            ),
            extra_ids=extra_ids,
        )
    return CoverageResult(
        CheckResult(
            "postgres_employee_mirror",
            "pass",
            "Postgres employee mirror covers all real active employees",
            {"postgres_active_count": len(pg_ids), "real_active_count": len(real_ids)},
        ),
    )


def repair_postgres_employee_mirror(
    real_employees: Sequence[Mapping[str, Any]],
    missing_ids: Sequence[str],
) -> CheckResult:
    """Upsert missing real active employees into Postgres.

    Args:
        real_employees: Authoritative real active employee rows.
        missing_ids: Employee ids missing from Postgres.

    Returns:
        CheckResult: Repair result.
    """

    missing_set = set(missing_ids)
    if not missing_set:
        return CheckResult("repair_postgres_employee_upsert", "skip", "no Postgres employee repair needed")
    try:
        from features.search.employee.postgres_repository import upsert_employee

        repaired = []
        for row in real_employees:
            employee_id = str(row["employee_id"])
            if employee_id not in missing_set:
                continue
            upsert_employee(dict(row))
            repaired.append(employee_id)
        return CheckResult(
            "repair_postgres_employee_upsert",
            "pass",
            f"Postgres employee upsert completed for {len(repaired)} rows",
            {"repaired": len(repaired), "repaired_sample": _clip_ids(repaired)},
        )
    except Exception as exc:
        return CheckResult(
            "repair_postgres_employee_upsert",
            "fail",
            "Postgres employee upsert failed",
            {"error": type(exc).__name__, "missing_count": len(missing_set)},
        )


def inspect_document_index_consistency(
    config: FeatureAConfig,
    *,
    collection_loader: ChromaCollectionLoader = load_chroma_collection,
) -> CheckResult:
    """Check document Chroma/BM25 chunk count consistency.

    Args:
        config: Verifier config.
        collection_loader: Chroma collection loader for tests.

    Returns:
        CheckResult: Document index consistency result.
    """

    corpus_path = config.vectorstore_path / "bm25_corpus.json"
    try:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        bm25_count = len(corpus)
    except FileNotFoundError:
        return CheckResult(
            "document_chroma_bm25_consistency",
            "fail",
            "bm25_corpus.json is missing",
            {"path": _display_path(config.root, corpus_path)},
        )
    except Exception as exc:
        return CheckResult(
            "document_chroma_bm25_consistency",
            "fail",
            "bm25_corpus.json could not be read",
            {"error": type(exc).__name__},
        )

    try:
        collection = collection_loader(config.vectorstore_path / "documents", DOCUMENT_CHROMA_COLLECTION)
        chroma_count = int(collection.count())
    except Exception as exc:
        return CheckResult(
            "document_chroma_bm25_consistency",
            "fail",
            "ajin_documents Chroma collection could not be loaded",
            {"error": type(exc).__name__, "bm25_chunks": bm25_count},
        )

    if bm25_count <= 0 or chroma_count <= 0:
        return CheckResult(
            "document_chroma_bm25_consistency",
            "fail",
            "document search indexes are empty",
            {"bm25_chunks": bm25_count, "chroma_count": chroma_count},
        )
    if bm25_count != chroma_count:
        return CheckResult(
            "document_chroma_bm25_consistency",
            "fail",
            "document Chroma and BM25 chunk counts differ",
            {"bm25_chunks": bm25_count, "chroma_count": chroma_count},
        )
    return CheckResult(
        "document_chroma_bm25_consistency",
        "pass",
        "document Chroma and BM25 chunk counts match",
        {"bm25_chunks": bm25_count, "chroma_count": chroma_count},
    )


def repair_document_indexes() -> CheckResult:
    """Run the full Feature A document indexing pipeline.

    Returns:
        CheckResult: Repair result.
    """

    try:
        from features.search.indexer import run_indexing

        vectorstore = run_indexing()
        return CheckResult(
            "repair_document_index_rebuild",
            "pass",
            "document Chroma/BM25 full rebuild completed",
            {"vectorstore_returned": vectorstore is not None},
        )
    except Exception as exc:
        return CheckResult(
            "repair_document_index_rebuild",
            "fail",
            "document Chroma/BM25 full rebuild failed",
            {"error": type(exc).__name__},
        )


def summarize(checks: Sequence[CheckResult]) -> dict[str, Any]:
    """Summarize check statuses.

    Args:
        checks: Check results.

    Returns:
        dict[str, Any]: Summary with status counts.
    """

    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    return {"status": status, "counts": counts, "checked_at": datetime.now(timezone.utc).isoformat()}


def run_consistency(
    config: FeatureAConfig,
    *,
    collection_loader: ChromaCollectionLoader = load_chroma_collection,
    employee_indexer: EmployeeIndexer | None = None,
    postgres_reader: Callable[[], set[str]] = _postgres_employee_ids,
) -> dict[str, Any]:
    """Run Feature A consistency checks and optional repair.

    Args:
        config: Verifier config.
        collection_loader: Chroma collection loader for tests.
        employee_indexer: Optional Chroma employee upsert test double.
        postgres_reader: Optional Postgres active-id reader test double.

    Returns:
        dict[str, Any]: Report payload.
    """

    checks: list[CheckResult] = []
    source = inspect_employee_source(config)
    checks.extend(source.checks)
    real_employees = source.real_active
    if source.ok:
        fts = inspect_fts_coverage(config, real_employees)
        if config.repair and fts.missing_ids:
            checks.append(repair_fts_index(config))
            fts = inspect_fts_coverage(config, real_employees)
        checks.append(fts.check)

        chroma = inspect_chroma_employee_coverage(
            config,
            real_employees,
            collection_loader=collection_loader,
        )
        if config.repair and chroma.missing_ids:
            checks.append(
                repair_chroma_employee_index(
                    config,
                    real_employees,
                    chroma.missing_ids,
                    employee_indexer=employee_indexer,
                )
            )
            chroma = inspect_chroma_employee_coverage(
                config,
                real_employees,
                collection_loader=collection_loader,
            )
        checks.append(chroma.check)

        postgres = inspect_postgres_employee_mirror(real_employees, reader=postgres_reader)
        if config.repair and postgres.missing_ids:
            checks.append(repair_postgres_employee_mirror(real_employees, postgres.missing_ids))
            postgres = inspect_postgres_employee_mirror(real_employees, reader=postgres_reader)
        checks.append(postgres.check)

    document_check = inspect_document_index_consistency(config, collection_loader=collection_loader)
    if config.repair_documents and document_check.status == "fail":
        checks.append(repair_document_indexes())
        document_check = inspect_document_index_consistency(config, collection_loader=collection_loader)
    checks.append(document_check)

    summary = summarize(checks)
    return {
        "summary": summary,
        "config": {
            "employees_db": str(config.employees_db.relative_to(config.root))
            if config.employees_db.is_relative_to(config.root)
            else str(config.employees_db),
            "vectorstore_path": str(config.vectorstore_path.relative_to(config.root))
            if config.vectorstore_path.is_relative_to(config.root)
            else str(config.vectorstore_path),
            "strict": config.strict,
            "repair": config.repair,
            "repair_documents": config.repair_documents,
            "app_db_backend": os.getenv("APP_DB_BACKEND", "sqlite"),
        },
        "references": list(DOC_REFERENCES),
        "checks": [check.to_dict() for check in checks],
    }


def write_markdown_report(report: Mapping[str, Any], path: Path) -> None:
    """Write a Markdown report.

    Args:
        report: Report payload.
        path: Output path.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        "# Feature A Consistency Check",
        "",
        f"- Status: `{summary['status']}`",
        f"- Checked at: `{summary['checked_at']}`",
        f"- Counts: `{json.dumps(summary['counts'], ensure_ascii=False)}`",
        f"- Employees DB: `{report['config']['employees_db']}`",
        f"- Vectorstore: `{report['config']['vectorstore_path']}`",
        f"- APP_DB_BACKEND: `{report['config']['app_db_backend']}`",
        "",
        "## Checks",
        "",
        "| Status | Check | Summary | Details |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        details = json.dumps(check.get("details", {}), ensure_ascii=False)
        lines.append(
            f"| `{check['status']}` | `{check['name']}` | {check['summary']} | `{details}` |"
        )
    lines.extend(["", "## References", ""])
    for ref in report["references"]:
        lines.append(f"- {ref}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_text_report(report: Mapping[str, Any]) -> None:
    """Print a compact text report.

    Args:
        report: Report payload.
    """

    summary = report["summary"]
    print(
        "Feature A consistency: "
        f"{summary['status']} "
        f"(pass={summary['counts']['pass']}, warn={summary['counts']['warn']}, "
        f"fail={summary['counts']['fail']}, skip={summary['counts']['skip']})"
    )
    for check in report["checks"]:
        print(f"[{check['status'].upper()}] {check['name']}: {check['summary']}")
        if check.get("details"):
            print(f"  details={json.dumps(check['details'], ensure_ascii=False)}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list.

    Returns:
        argparse.Namespace: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when fail checks remain.")
    parser.add_argument("--repair", action="store_true", help="Repair safe employee index inconsistencies.")
    parser.add_argument(
        "--repair-documents",
        action="store_true",
        help="Allow full document Chroma/BM25 rebuild when document indexes mismatch.",
    )
    parser.add_argument("--employees-db", default="data/employees.db", help="SQLite employees DB path.")
    parser.add_argument("--vectorstore", default="vectorstore", help="Chroma/BM25 vectorstore root.")
    parser.add_argument("--markdown", default="", help="Write a Markdown report to this path.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument list.

    Returns:
        int: Process exit code.
    """

    args = parse_args(argv)
    root = ROOT
    config = FeatureAConfig(
        root=root,
        employees_db=_resolve_path(root, args.employees_db),
        vectorstore_path=_resolve_path(root, args.vectorstore),
        strict=bool(args.strict),
        repair=bool(args.repair),
        repair_documents=bool(args.repair_documents),
    )
    report = run_consistency(config)
    if args.markdown:
        write_markdown_report(report, _resolve_path(root, args.markdown))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)
    if config.strict and report["summary"]["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
