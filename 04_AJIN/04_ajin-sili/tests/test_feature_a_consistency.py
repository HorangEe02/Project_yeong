"""Feature A consistency verifier tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import scripts.verify_feature_a_consistency as verifier


class FakeCollection:
    """Small Chroma collection test double."""

    def __init__(self, employee_ids: list[str] | None = None, count_value: int | None = None):
        """Create a fake collection.

        Args:
            employee_ids: Employee ids to expose as ``emp_<id>`` records.
            count_value: Optional fixed count for document collections.
        """

        self.records = {
            f"emp_{employee_id}": {"employee_id": employee_id}
            for employee_id in (employee_ids or [])
        }
        self.count_value = count_value

    def count(self) -> int:
        """Return collection size.

        Returns:
            int: Fixed count or record count.
        """

        if self.count_value is not None:
            return self.count_value
        return len(self.records)

    def get(self, ids=None, include=None, limit=None):  # noqa: ANN001, ARG002
        """Return Chroma-like records.

        Args:
            ids: Optional ids to fetch.
            include: Ignored compatibility argument.
            limit: Optional max count.

        Returns:
            dict: Chroma-like ids/metadatas payload.
        """

        if ids is None:
            selected = list(self.records)
            if limit is not None:
                selected = selected[:limit]
        else:
            selected = [record_id for record_id in ids if record_id in self.records]
        return {
            "ids": selected,
            "metadatas": [self.records[record_id] for record_id in selected],
        }

    def add_employee(self, employee_id: str) -> None:
        """Add one fake employee profile.

        Args:
            employee_id: Employee id to add.
        """

        self.records[f"emp_{employee_id}"] = {"employee_id": employee_id}


def _seed_employees(path: Path) -> None:
    """Seed a minimal Feature A employees database.

    Args:
        path: SQLite DB path.
    """

    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_en TEXT,
            gender TEXT,
            position TEXT NOT NULL,
            position_level INTEGER NOT NULL DEFAULT 1,
            division TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            department_id TEXT,
            role TEXT DEFAULT '',
            email TEXT,
            phone TEXT,
            extension TEXT,
            plant TEXT DEFAULT '',
            plant_id TEXT DEFAULT '',
            hire_date TEXT,
            is_active INTEGER DEFAULT 1,
            is_team_leader INTEGER DEFAULT 0,
            photo_url TEXT DEFAULT '',
            overseas_assignment TEXT DEFAULT NULL,
            language_skills TEXT DEFAULT NULL,
            is_synthetic INTEGER NOT NULL DEFAULT 1,
            source_system TEXT NOT NULL DEFAULT 'seed',
            canonical_employee_id TEXT DEFAULT NULL,
            data_class TEXT NOT NULL DEFAULT 'unknown',
            source_label TEXT DEFAULT '',
            source_updated_at TEXT DEFAULT ''
        );
        INSERT INTO employees (
            employee_id, name, position, position_level, division, department,
            email, phone, extension, plant, is_active, is_synthetic,
            source_system, canonical_employee_id, data_class
        ) VALUES
            ('ERP-001', '홍길동', '과장', 4, '품질본부', '품질보증팀',
             'hong@example.invalid', '010-0000-0001', '1001', '경산 본사', 1, 0,
             'erp_csv', 'ERP-001', 'real'),
            ('ERP-002', '김영희', '대리', 3, '관리본부', '인사팀',
             'kim@example.invalid', '010-0000-0002', '1002', '경산 본사', 1, 0,
             'erp_csv', 'ERP-002', 'real'),
            ('ERP-003', '장보고', '부장', 6, '영업본부', '영업팀',
             'jang@example.invalid', '010-0000-0003', '1003', '경산 본사', 0, 0,
             'erp_csv', 'ERP-003', 'real'),
            ('EMP-001', '합성직원', '사원', 1, '생산본부', '생산기술팀',
             'demo@example.invalid', '010-0000-0004', '1004', '경산 본사', 1, 1,
             'seed', 'EMP-001', 'synthetic');
        """
    )
    conn.commit()
    conn.close()


def _seed_partial_fts(path: Path) -> None:
    """Create an FTS table that omits the real active rows.

    Args:
        path: SQLite DB path.
    """

    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE VIRTUAL TABLE employees_fts USING fts5(
            name, department, position, phone, email, extension, plant,
            tokenize='unicode61 remove_diacritics 0'
        );
        INSERT INTO employees_fts(rowid, name, department, position, phone, email, extension, plant)
        SELECT rowid, name, department, position, phone, email, extension, plant
          FROM employees
         WHERE employee_id = 'EMP-001';
        """
    )
    conn.commit()
    conn.close()


def _write_matching_bm25(vectorstore: Path, chunks: int = 2) -> None:
    """Write a minimal BM25 corpus.

    Args:
        vectorstore: Vectorstore root.
        chunks: Chunk count.
    """

    vectorstore.mkdir(parents=True, exist_ok=True)
    corpus = [
        {"doc_id": f"DOC-{idx}", "content": "sample", "metadata": {"title": "sample"}}
        for idx in range(chunks)
    ]
    (vectorstore / "bm25_corpus.json").write_text(json.dumps(corpus), encoding="utf-8")


def _config(tmp_path: Path) -> verifier.FeatureAConfig:
    """Create a verifier config for tests.

    Args:
        tmp_path: Pytest temp path.

    Returns:
        FeatureAConfig: Isolated config.
    """

    employees_db = tmp_path / "employees.db"
    vectorstore = tmp_path / "vectorstore"
    _seed_employees(employees_db)
    _write_matching_bm25(vectorstore)
    return verifier.FeatureAConfig(
        root=tmp_path,
        employees_db=employees_db,
        vectorstore_path=vectorstore,
        strict=True,
    )


def test_fts_repair_restores_real_active_coverage(tmp_path: Path) -> None:
    """FTS rebuild should cover real active employees."""

    config = _config(tmp_path)
    _seed_partial_fts(config.employees_db)
    source = verifier.inspect_employee_source(config)

    before = verifier.inspect_fts_coverage(config, source.real_active)
    repair = verifier.repair_fts_index(config)
    after = verifier.inspect_fts_coverage(config, source.real_active)

    assert before.check.status == "fail"
    assert set(before.missing_ids) == {"ERP-001", "ERP-002"}
    assert repair.status == "pass"
    assert after.check.status == "pass"


def test_chroma_repair_upserts_missing_real_ids(tmp_path: Path) -> None:
    """Chroma repair should call the employee indexer for missing real ids."""

    config = _config(tmp_path)
    source = verifier.inspect_employee_source(config)
    collection = FakeCollection(employee_ids=["EMP-001"])

    def loader(path: Path, collection_name: str):  # noqa: ARG001
        return collection

    def indexer(employee: dict) -> bool:
        collection.add_employee(str(employee["employee_id"]))
        return True

    before = verifier.inspect_chroma_employee_coverage(
        config,
        source.real_active,
        collection_loader=loader,
    )
    repair = verifier.repair_chroma_employee_index(
        config,
        source.real_active,
        before.missing_ids,
        employee_indexer=indexer,
    )
    after = verifier.inspect_chroma_employee_coverage(
        config,
        source.real_active,
        collection_loader=loader,
    )

    assert before.check.status == "fail"
    assert set(before.missing_ids) == {"ERP-001", "ERP-002"}
    assert repair.status == "pass"
    assert after.missing_ids == ()
    assert after.check.status == "warn"
    assert after.extra_ids == ("EMP-001",)


def test_postgres_repair_upserts_missing_real_ids(monkeypatch, tmp_path: Path) -> None:
    """Postgres repair should upsert missing real active rows."""

    config = _config(tmp_path)
    source = verifier.inspect_employee_source(config)
    pg_path = tmp_path / "pg.db"
    monkeypatch.setenv("APP_DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{pg_path}")

    before = verifier.inspect_postgres_employee_mirror(source.real_active)
    repair = verifier.repair_postgres_employee_mirror(source.real_active, before.missing_ids)
    after = verifier.inspect_postgres_employee_mirror(source.real_active)

    assert before.check.status == "fail"
    assert set(before.missing_ids) == {"ERP-001", "ERP-002"}
    assert repair.status == "pass"
    assert after.check.status == "pass"


def test_synthetic_only_chroma_extra_is_warn_not_fail(monkeypatch, tmp_path: Path) -> None:
    """Synthetic Chroma extras should warn but not create a blocker."""

    config = _config(tmp_path)
    verifier.repair_fts_index(config)
    employee_collection = FakeCollection(employee_ids=["ERP-001", "ERP-002", "EMP-001"])
    document_collection = FakeCollection(count_value=2)

    def loader(path: Path, collection_name: str):  # noqa: ARG001
        if collection_name == verifier.EMPLOYEE_CHROMA_COLLECTION:
            return employee_collection
        return document_collection

    report = verifier.run_consistency(
        config,
        collection_loader=loader,
        postgres_reader=lambda: {"ERP-001", "ERP-002"},
    )
    statuses = {check["name"]: check["status"] for check in report["checks"]}

    assert statuses["employee_chroma_coverage"] == "warn"
    assert statuses["postgres_employee_mirror"] == "pass"
    assert statuses["document_chroma_bm25_consistency"] == "pass"
    assert report["summary"]["status"] == "warn"
