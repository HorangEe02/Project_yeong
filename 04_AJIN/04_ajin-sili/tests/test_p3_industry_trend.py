"""P3 D11 — 산업 트렌드 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_industry_db(monkeypatch, tmp_path):
    import features.compliance.industry_trend as it
    monkeypatch.setattr(it, "DB_PATH", tmp_path / "industry.db")
    it.init_industry_db()
    return it


# ─────────────────────────────────────────────────────────────
# fetch_dart_filings
# ─────────────────────────────────────────────────────────────
class TestFetchDart:
    def test_no_api_key_returns_empty(self, tmp_industry_db, monkeypatch):
        monkeypatch.delenv("DART_API_KEY", raising=False)
        out = tmp_industry_db.fetch_dart_filings()
        assert out == []

    def test_external_failure_returns_empty(self, tmp_industry_db, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test-key")
        monkeypatch.setattr(
            "features.compliance._http.fetch_json",
            lambda url: (_ for _ in ()).throw(RuntimeError("network down")),
        )
        out = tmp_industry_db.fetch_dart_filings()
        assert out == []

    def test_normalizes_dart_response(self, tmp_industry_db, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test-key")

        fake = {
            "status": "000",
            "list": [
                {"rcept_no": "RC001", "report_nm": "관세 영향 분기", "rcept_dt": "20250410"},
            ],
        }
        monkeypatch.setattr(
            "features.compliance._http.fetch_json",
            lambda url: fake,
        )
        out = tmp_industry_db.fetch_dart_filings(corp_codes={"00126308": "현대모비스"})
        assert len(out) == 1
        assert out[0]["corp_name"] == "현대모비스"
        assert out[0]["rcept_no"] == "RC001"


# ─────────────────────────────────────────────────────────────
# index_filings (UNIQUE rcept_no dedupe)
# ─────────────────────────────────────────────────────────────
class TestIndexFilings:
    def test_dedupe_same_rcept_no(self, tmp_industry_db):
        out1 = tmp_industry_db.index_filings([
            {"corp_code": "C1", "corp_name": "X사", "rcept_no": "R001",
             "report_nm": "관세 보고서", "rcept_dt": "20250410"},
        ])
        out2 = tmp_industry_db.index_filings([
            {"corp_code": "C1", "corp_name": "X사", "rcept_no": "R001",
             "report_nm": "관세 보고서", "rcept_dt": "20250410"},
            {"corp_code": "C1", "corp_name": "X사", "rcept_no": "R002",
             "report_nm": "REACH 대응", "rcept_dt": "20250420"},
        ])
        assert out1 == 1
        # R001 은 dedupe → R002 만 새 1건
        assert tmp_industry_db.collection_stats()["total_filings"] == 2

    def test_extracts_keywords(self, tmp_industry_db):
        tmp_industry_db.index_filings([
            {"corp_code": "C1", "corp_name": "X", "rcept_no": "R1",
             "report_nm": "관세 25% 영향 — REACH 대응", "rcept_dt": "20250410"},
        ])
        import sqlite3
        conn = sqlite3.connect(str(tmp_industry_db.DB_PATH))
        row = conn.execute("SELECT keywords FROM industry_filings WHERE rcept_no = ?",
                            ("R1",)).fetchone()
        conn.close()
        kw = (row[0] or "").split(",")
        assert "관세" in kw
        assert "REACH" in kw


# ─────────────────────────────────────────────────────────────
# compare_change_to_industry
# ─────────────────────────────────────────────────────────────
class TestCompare:
    def test_no_data_returns_no_data_verdict(self, tmp_industry_db):
        out = tmp_industry_db.compare_change_to_industry({
            "item_title": "관세 25%", "new_value": "관세 영향"
        })
        assert out["verdict"] == "no_data"
        assert out["available"] is False

    def test_industry_wide_verdict_when_average_high(self, tmp_industry_db):
        # 5개사 모두 같은 키워드 공시 → industry_wide
        for cc in ("C1", "C2", "C3", "C4", "C5"):
            tmp_industry_db.index_filings([
                {"corp_code": cc, "corp_name": f"Co_{cc}", "rcept_no": f"R-{cc}",
                 "report_nm": "관세 25% 분기 영향", "rcept_dt": "20250410"},
            ])

        out = tmp_industry_db.compare_change_to_industry({
            "item_title": "관세 25%", "new_value": "관세 영향"
        })
        assert out["available"] is True
        assert out["matching_filings_count"] >= 5
        # industry_average >= 1.0 → industry_wide
        assert out["verdict"] == "industry_wide"

    def test_company_specific_when_average_low(self, tmp_industry_db):
        # 1개사만 공시 → company_specific (산업 평균 낮음)
        tmp_industry_db.index_filings([
            {"corp_code": "C1", "corp_name": "X", "rcept_no": "R001",
             "report_nm": "관세 영향", "rcept_dt": "20250410"},
        ])

        out = tmp_industry_db.compare_change_to_industry({
            "item_title": "관세 25%", "new_value": "관세 영향"
        })
        # 1건 / 5개사 = 0.2 (1.0 미만)
        assert out["verdict"] == "company_specific"

    def test_no_keywords_returns_no_data(self, tmp_industry_db):
        # 키워드 매칭 안 되는 본문
        tmp_industry_db.index_filings([
            {"corp_code": "C1", "corp_name": "X", "rcept_no": "R001",
             "report_nm": "관세 영향", "rcept_dt": "20250410"},
        ])
        out = tmp_industry_db.compare_change_to_industry({
            "item_title": "관련 없는 본문", "new_value": "그냥 일반 텍스트"
        })
        assert out["verdict"] == "no_data"
        assert out["change_keywords"] == []


# ─────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────
class TestStats:
    def test_collection_stats(self, tmp_industry_db):
        s = tmp_industry_db.collection_stats()
        assert s["total_filings"] == 0
        assert s["corp_count"] == 0

        tmp_industry_db.index_filings([
            {"corp_code": "C1", "corp_name": "X", "rcept_no": "R1", "report_nm": "관세", "rcept_dt": "20250101"},
            {"corp_code": "C2", "corp_name": "Y", "rcept_no": "R2", "report_nm": "안전", "rcept_dt": "20250102"},
        ])
        s2 = tmp_industry_db.collection_stats()
        assert s2["total_filings"] == 2
        assert s2["corp_count"] == 2
