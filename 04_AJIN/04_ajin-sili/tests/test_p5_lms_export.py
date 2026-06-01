"""P5 §5 — SCORM 1.2 / xAPI export 단위 테스트."""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()
    return cd


@pytest.fixture(autouse=True)
def _no_external(monkeypatch):
    import config
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "", raising=False)
    monkeypatch.setenv("LEARNING_QUIZ_LLM_PROVIDER", "rule_only")


def _seed_change(cd_mod, change_id: int = 1):
    conn = sqlite3.connect(cd_mod.CHANGE_DB_PATH)
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO regulation_changes
           (id, detected_at, regulation_type, change_type, item_id, item_title,
            old_value, new_value, severity, status, grade, summary_ko,
            affected_departments, affected_plants, legal_class, penalty_severity_krw_mn)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (change_id, now, "test", "added", f"X{change_id}",
         f"테스트 변경 {change_id}", "", "<body>", "info", "pending",
         "MEDIUM", "요약-ko", "[]", "[]", "[]", 0),
    )
    conn.commit()
    conn.close()
    return change_id


# ─────────────────────────────────────────────────────────────
# SCORM 1.2 export
# ─────────────────────────────────────────────────────────────


class TestScormExport:
    def test_path_not_found_returns_none(self, tmp_db):
        from features.compliance.lms_export import export_scorm_package
        assert export_scorm_package(99999) is None

    def test_zip_contains_manifest_and_scos(self, tmp_db):
        from features.compliance.learning_path import curate_path
        from features.compliance.lms_export import export_scorm_package
        c1 = _seed_change(tmp_db, 1)
        c2 = _seed_change(tmp_db, 2)
        pid = curate_path(
            name="p1", owner_employee_id="O", assignee_employee_id="R",
            week_split=[[c1, c2]],
        )
        data = export_scorm_package(pid)
        assert data is not None
        assert data[:2] == b"PK"  # ZIP magic
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            assert "imsmanifest.xml" in names
            assert "sco_1.html" in names
            assert "sco_2.html" in names
            manifest = zf.read("imsmanifest.xml").decode("utf-8")
            assert "schemaversion>1.2<" in manifest
            assert "테스트 변경 1" in manifest or "change_1" in manifest
            sco1 = zf.read("sco_1.html").decode("utf-8")
            assert "LMSInitialize" in sco1   # SCORM API stub
            assert "AI 자문" in sco1          # disclaimer

    def test_empty_curriculum_minimal_zip(self, tmp_db):
        """curriculum 비어있어도 manifest + 빈 resources 가 포함된 ZIP 반환."""
        from features.compliance.lms_export import export_scorm_package
        # 직접 빈 path 1개 적재
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        conn.execute(
            """INSERT INTO learning_paths
               (name, owner_employee_id, assignee_employee_id, week_count,
                curriculum_json, status, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            ("empty", "O", "R", 0, "[]", "active",
             datetime.now().isoformat()),
        )
        conn.commit()
        pid = conn.execute(
            "SELECT id FROM learning_paths WHERE name = 'empty'"
        ).fetchone()[0]
        conn.close()
        data = export_scorm_package(pid)
        assert data is not None
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert "imsmanifest.xml" in zf.namelist()


# ─────────────────────────────────────────────────────────────
# xAPI export
# ─────────────────────────────────────────────────────────────


class TestXapiExport:
    def test_path_not_found_returns_none(self, tmp_db):
        from features.compliance.lms_export import export_xapi_statements
        assert export_xapi_statements(99999) is None

    def test_statements_have_actor_verb_object(self, tmp_db):
        from features.compliance.learning_path import (
            curate_path, get_or_generate_quiz, my_progress, take_quiz,
        )
        from features.compliance.lms_export import export_xapi_statements
        c1 = _seed_change(tmp_db, 5)
        pid = curate_path(name="p", owner_employee_id="MENT",
                          assignee_employee_id="ROOK", week_split=[[c1]])
        # 응시 1회
        prog = my_progress("ROOK")["paths"][0]["progress"][0]
        quiz = get_or_generate_quiz(c1)
        take_quiz(prog["id"], quiz["answer_index"])

        out = export_xapi_statements(pid)
        assert out is not None
        assert len(out) == 1
        st = out[0]
        # 필수 필드
        assert st["actor"]["mbox"].startswith("mailto:")
        assert "verb" in st and "id" in st["verb"]
        assert st["object"]["definition"]["type"].endswith("/lesson")
        # quiz_score=100 → result.score 포함
        assert st["result"]["score"]["raw"] == 100
        assert st["result"]["score"]["scaled"] == 1.0

    def test_unattempted_statement_no_result(self, tmp_db):
        """quiz 미응시 → score 필드 없음 (attempted verb 만)."""
        from features.compliance.learning_path import curate_path
        from features.compliance.lms_export import export_xapi_statements
        c1 = _seed_change(tmp_db, 10)
        pid = curate_path(name="p", owner_employee_id="O",
                          assignee_employee_id="R", week_split=[[c1]])
        out = export_xapi_statements(pid)
        assert out is not None and len(out) == 1
        assert "result" not in out[0]
        assert out[0]["verb"]["display"]["en-US"] == "attempted"
