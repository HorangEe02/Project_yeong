"""P5 §10 — 2차 협력사 자동 발굴 단위 테스트."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_dbs(tmp_path, monkeypatch):
    """suppliers.db + industry_trend DB 둘 다 격리."""
    import features.compliance.supplier_compliance as sc
    import features.compliance.industry_trend as it
    monkeypatch.setattr(sc, "DB_PATH", tmp_path / "suppliers.db")
    monkeypatch.setattr(it, "DB_PATH", tmp_path / "industry.db")
    sc.init_suppliers_db()
    it.init_industry_db()
    return (sc, it)


def _seed_filing(it_mod, *, corp_code, corp_name, count=1, rcept_dt="20240601"):
    conn = sqlite3.connect(str(it_mod.DB_PATH))
    for i in range(count):
        conn.execute(
            """INSERT OR IGNORE INTO industry_filings
               (corp_code, corp_name, rcept_no, report_nm, rcept_dt)
               VALUES (?,?,?,?,?)""",
            (corp_code, corp_name, f"{corp_code}-{i:04d}", "분기보고서", rcept_dt),
        )
    conn.commit()
    conn.close()


def _seed_supplier(sc_mod, *, supplier_id, name="", tier=1):
    conn = sqlite3.connect(str(sc_mod.DB_PATH))
    conn.execute(
        """INSERT INTO suppliers (supplier_id, name, tier, country)
           VALUES (?,?,?,?)""",
        (supplier_id, name or supplier_id, tier, "KR"),
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# discover_candidates
# ─────────────────────────────────────────────────────────────


class TestDiscoverCandidates:
    def test_empty_when_no_filings(self, tmp_dbs):
        from features.compliance.supplier_discovery import discover_candidates
        assert discover_candidates() == []

    def test_returns_unregistered_only(self, tmp_dbs):
        sc, it = tmp_dbs
        # industry_filings 에 3개사
        _seed_filing(it, corp_code="00001", corp_name="A사", count=3)
        _seed_filing(it, corp_code="00002", corp_name="B사", count=2)
        _seed_filing(it, corp_code="00003", corp_name="C사", count=1)
        # B사는 우리 suppliers 에 등록됨
        _seed_supplier(sc, supplier_id="00002", name="B사")
        from features.compliance.supplier_discovery import discover_candidates
        cands = discover_candidates()
        ids = {c["corp_code"] for c in cands}
        assert ids == {"00001", "00003"}

    def test_excluded_by_name_match(self, tmp_dbs):
        """corp_code 다르지만 name 동일 → 중복 등록 방지 (이미 같은 회사)."""
        sc, it = tmp_dbs
        _seed_filing(it, corp_code="11111", corp_name="동성화학")
        _seed_supplier(sc, supplier_id="OUR-DS", name="동성화학")
        from features.compliance.supplier_discovery import discover_candidates
        assert discover_candidates() == []

    def test_min_filings_filter(self, tmp_dbs):
        sc, it = tmp_dbs
        _seed_filing(it, corp_code="x1", corp_name="활성", count=5)
        _seed_filing(it, corp_code="x2", corp_name="저활동", count=1)
        from features.compliance.supplier_discovery import discover_candidates
        cands = discover_candidates(min_filings=3)
        assert len(cands) == 1
        assert cands[0]["corp_code"] == "x1"

    def test_sorted_by_filing_count_desc(self, tmp_dbs):
        sc, it = tmp_dbs
        _seed_filing(it, corp_code="LOW", corp_name="L", count=1)
        _seed_filing(it, corp_code="HI", corp_name="H", count=10)
        _seed_filing(it, corp_code="MID", corp_name="M", count=5)
        from features.compliance.supplier_discovery import discover_candidates
        cands = discover_candidates()
        assert [c["corp_code"] for c in cands] == ["HI", "MID", "LOW"]


# ─────────────────────────────────────────────────────────────
# promote_to_supplier
# ─────────────────────────────────────────────────────────────


class TestPromote:
    def test_promote_creates_supplier(self, tmp_dbs):
        sc, it = tmp_dbs
        _seed_filing(it, corp_code="22222", corp_name="신규공급")
        from features.compliance.supplier_discovery import promote_to_supplier
        out = promote_to_supplier("22222")
        assert out["ok"] is True
        assert out["supplier_id"] == "22222"
        assert out["name"] == "신규공급"
        assert out["tier_depth"] == 2
        # suppliers DB 에 저장 확인
        conn = sqlite3.connect(str(sc.DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ?", ("22222",),
        ).fetchone()
        conn.close()
        assert row["name"] == "신규공급"
        assert row["tier_depth"] == 2
        assert row["relation_type"] == "sub_assembly"

    def test_promote_already_exists(self, tmp_dbs):
        sc, it = tmp_dbs
        _seed_supplier(sc, supplier_id="00001", name="기존")
        from features.compliance.supplier_discovery import promote_to_supplier
        out = promote_to_supplier("00001")
        assert out["ok"] is False
        assert out["error"] == "already_exists"

    def test_promote_with_overrides(self, tmp_dbs):
        sc, it = tmp_dbs
        _seed_filing(it, corp_code="33333", corp_name="원본명")
        from features.compliance.supplier_discovery import promote_to_supplier
        out = promote_to_supplier(
            "33333", name_override="커스텀명",
            tier=3, relation_type="raw_material",
            parent_supplier_id="PARENT-A",
        )
        assert out["ok"] is True
        assert out["name"] == "커스텀명"
        conn = sqlite3.connect(str(sc.DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ?", ("33333",),
        ).fetchone()
        conn.close()
        assert row["tier_depth"] == 3
        assert row["relation_type"] == "raw_material"
        assert row["parent_supplier_id"] == "PARENT-A"

    def test_missing_corp_code(self, tmp_dbs):
        from features.compliance.supplier_discovery import promote_to_supplier
        assert promote_to_supplier("")["error"] == "missing_corp_code"
