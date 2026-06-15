"""P2 D5 — Feedback Loop 단위 테스트."""
from __future__ import annotations

import json
import sys
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


def _seed_change(cd, **overrides):
    base = {
        "regulation_type": "test",
        "change_type": "modified",
        "item_id": "X-1",
        "item_title": "산안법",
        "old_value": "",
        "new_value": "5년 이하 징역",
        "severity": "info",
        "summary_ko": "변경 요약",
        "grade": "MEDIUM",
        "affected_departments": ["안전보건팀"],
        "affected_plants": [],
        "legal_class": ["administrative"],
        "penalty_extract": "",
        "penalty_severity_krw_mn": 0,
    }
    base.update(overrides)
    return cd.save_changes([base])[0]


# ─────────────────────────────────────────────────────────────
# record_correction
# ─────────────────────────────────────────────────────────────
class TestRecordCorrection:
    def test_legal_class_correction(self, tmp_db):
        from features.compliance.feedback_loop import record_correction
        cid = _seed_change(tmp_db)

        out = record_correction(
            cid, "legal_class", ["criminal", "administrative"],
            user_id="u1", user_role="legal", note="penalty 키워드",
        )
        assert out["ok"]
        assert out["correction_id"] > 0

        # change row 의 legal_class 가 갱신됐는지
        import sqlite3
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        row = conn.execute(
            "SELECT legal_class, audit_trail FROM regulation_changes WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert json.loads(row[0]) == ["criminal", "administrative"]
        # audit_trail 에 correction event 적재
        trail = json.loads(row[1])
        assert any(e.get("action") == "correction" for e in trail)

    def test_grade_correction_string_value(self, tmp_db):
        from features.compliance.feedback_loop import record_correction
        cid = _seed_change(tmp_db)

        out = record_correction(cid, "grade", "HIGH", user_id="u1")
        assert out["ok"]

        import sqlite3
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        row = conn.execute(
            "SELECT grade FROM regulation_changes WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert row[0] == "HIGH"

    def test_invalid_field_rejected(self, tmp_db):
        from features.compliance.feedback_loop import record_correction
        cid = _seed_change(tmp_db)
        out = record_correction(cid, "nonexistent_field", "x")
        assert out["ok"] is False
        assert "invalid field" in out["error"]

    def test_nonexistent_change_id(self, tmp_db):
        from features.compliance.feedback_loop import record_correction
        out = record_correction(99999, "grade", "HIGH")
        assert out["ok"] is False
        assert "미존재" in out["error"]

    def test_correction_log_persisted(self, tmp_db):
        from features.compliance.feedback_loop import record_correction
        cid = _seed_change(tmp_db)
        record_correction(cid, "legal_class", ["criminal"], user_id="u1", note="추가 분류")

        import sqlite3
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        rows = conn.execute(
            "SELECT field, old_value, new_value, user_id, note FROM change_corrections WHERE change_id = ?",
            (cid,),
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "legal_class"
        # old_value 는 ["administrative"] (seed)
        assert "administrative" in rows[0][1]
        # new_value 는 ["criminal"]
        assert "criminal" in rows[0][2]
        assert rows[0][3] == "u1"
        assert rows[0][4] == "추가 분류"


# ─────────────────────────────────────────────────────────────
# aggregate_corrections
# ─────────────────────────────────────────────────────────────
class TestAggregateCorrections:
    def test_empty_returns_zeros(self, tmp_db):
        from features.compliance.feedback_loop import aggregate_corrections
        agg = aggregate_corrections()
        assert agg["total"] == 0
        assert agg["by_field"] == {}

    def test_aggregates_by_field_and_role(self, tmp_db):
        from features.compliance.feedback_loop import record_correction, aggregate_corrections
        cid1 = _seed_change(tmp_db, item_id="X-1")
        cid2 = _seed_change(tmp_db, item_id="X-2")

        record_correction(cid1, "legal_class", ["criminal"], user_id="u1", user_role="legal")
        record_correction(cid1, "grade", "HIGH", user_id="u1", user_role="legal")
        record_correction(cid2, "affected_departments", ["A팀", "B팀", "법무팀"],
                          user_id="u2", user_role="compliance")

        agg = aggregate_corrections()
        assert agg["total"] == 3
        assert agg["by_field"]["legal_class"] == 1
        assert agg["by_field"]["grade"] == 1
        assert agg["by_field"]["affected_departments"] == 1
        assert agg["by_role"]["legal"] == 2
        assert agg["by_role"]["compliance"] == 1

    def test_frequent_dept_changes_extracts_added(self, tmp_db):
        from features.compliance.feedback_loop import record_correction, aggregate_corrections
        cid = _seed_change(tmp_db)
        # seed 의 affected_departments = ['안전보건팀']
        # 사용자가 ['안전보건팀', '법무팀', '품질경영팀'] 로 수정 — 법무팀, 품질경영팀이 새로 추가
        record_correction(cid, "affected_departments",
                          ["안전보건팀", "법무팀", "품질경영팀"],
                          user_id="u1")

        agg = aggregate_corrections()
        added = dict(agg["frequent_dept_changes"])
        assert "법무팀" in added
        assert "품질경영팀" in added

    def test_accuracy_signal_field_specific(self, tmp_db):
        from features.compliance.feedback_loop import record_correction, aggregate_corrections
        cid = _seed_change(tmp_db)  # 1건 seed
        record_correction(cid, "legal_class", ["criminal"], user_id="u1")

        agg = aggregate_corrections()
        # 1건 변경 중 1건 수정 → legal_class accuracy = 0.0
        assert agg["accuracy_signal"]["legal_class"] == 0.0
        # grade 는 수정 없음 → accuracy 1.0
        assert agg["accuracy_signal"]["grade"] == 1.0


# ─────────────────────────────────────────────────────────────
# dump_fewshot_examples
# ─────────────────────────────────────────────────────────────
class TestDumpFewshot:
    def test_empty_returns_empty_list(self, tmp_db):
        from features.compliance.feedback_loop import dump_fewshot_examples
        assert dump_fewshot_examples() == []

    def test_dumps_legal_class_corrections(self, tmp_db):
        from features.compliance.feedback_loop import record_correction, dump_fewshot_examples
        cid = _seed_change(tmp_db, item_title="화관법 7조")

        record_correction(cid, "legal_class", ["criminal", "administrative"],
                          user_id="u1", note="형사 누락")

        examples = dump_fewshot_examples("legal_class", n=10)
        assert len(examples) == 1
        ex = examples[0]
        assert ex["input"]["item_title"] == "화관법 7조"
        assert "administrative" in ex["ai_recommendation"]
        assert "criminal" in ex["human_correction"]
        assert ex["note"] == "형사 누락"

    def test_filter_by_field(self, tmp_db):
        from features.compliance.feedback_loop import record_correction, dump_fewshot_examples
        cid = _seed_change(tmp_db)
        record_correction(cid, "legal_class", ["criminal"], user_id="u1")
        record_correction(cid, "grade", "HIGH", user_id="u1")

        legal = dump_fewshot_examples("legal_class")
        grade = dump_fewshot_examples("grade")
        assert len(legal) == 1
        assert len(grade) == 1
