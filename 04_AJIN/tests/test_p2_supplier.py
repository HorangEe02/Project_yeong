"""P2 D6 — 공급망 단위 테스트 (compliance + simulator + recommender)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_supp_db(monkeypatch, tmp_path):
    import features.compliance.supplier_compliance as sc
    monkeypatch.setattr(sc, "DB_PATH", tmp_path / "sup.db")
    sc.init_suppliers_db()
    return sc


@pytest.fixture
def seeded_db(tmp_supp_db):
    """4 협력사 + 4 부품 시드."""
    tmp_supp_db.import_suppliers_csv(
        "supplier_id,name,tier,country,contact_email,annual_volume_krw_mn,compliance_score\n"
        "SUP-001,Aplus,1,US,a@a.com,30000,80\n"
        "SUP-002,Beta,1,US,b@b.com,25000,75\n"
        "SUP-003,Gamma,1,KR,g@g.kr,40000,90\n"
        "SUP-004,Delta,2,VN,d@d.vn,5000,60"
    )
    tmp_supp_db.import_components_csv(
        "supplier_id,component_code,hs_code,unit_price_krw,qty_per_year\n"
        "SUP-001,PARTA,8708.10,5000,10000\n"
        "SUP-002,PARTA,8708.10,4500,8000\n"
        "SUP-003,PARTA,8708.10,4800,12000\n"
        "SUP-004,PARTB,9999.00,2000,5000"
    )
    return tmp_supp_db


# ─────────────────────────────────────────────────────────────
# Import + list + detail
# ─────────────────────────────────────────────────────────────
class TestImportList:
    def test_import_suppliers_csv(self, tmp_supp_db):
        out = tmp_supp_db.import_suppliers_csv(
            "supplier_id,name,tier,country,contact_email,annual_volume_krw_mn,compliance_score\n"
            "S1,Test,1,US,t@t.com,1000,70"
        )
        assert out["imported"] == 1
        assert out["skipped"] == 0

    def test_import_skips_missing_id(self, tmp_supp_db):
        out = tmp_supp_db.import_suppliers_csv(
            "supplier_id,name\n,No ID Row\nS1,OK Row"
        )
        assert out["imported"] == 1
        assert out["skipped"] == 1

    def test_list_suppliers_filter(self, seeded_db):
        all_lst = seeded_db.list_suppliers()
        assert len(all_lst) == 4

        tier1 = seeded_db.list_suppliers(tier=1)
        assert len(tier1) == 3

        us_only = seeded_db.list_suppliers(country="US")
        assert len(us_only) == 2

        high_score = seeded_db.list_suppliers(min_score=80)
        assert len(high_score) == 2  # Aplus 80, Gamma 90

    def test_get_supplier_with_components(self, seeded_db):
        s = seeded_db.get_supplier("SUP-001")
        assert s is not None
        assert s["name"] == "Aplus"
        assert len(s["components"]) == 1
        assert s["components"][0]["hs_code"] == "8708.10"

    def test_get_supplier_nonexistent(self, seeded_db):
        assert seeded_db.get_supplier("NOT-EXIST") is None


# ─────────────────────────────────────────────────────────────
# match_suppliers
# ─────────────────────────────────────────────────────────────
class TestMatchSuppliers:
    def test_hs_match(self, seeded_db):
        hits = seeded_db.match_suppliers(
            {"item_title": "8708 관세 25%", "new_value": "8708 계열 부품"}
        )
        # SUP-001/002/003 (HS 8708.10 매칭) + SUP-001/002/004 (US 국가)
        ids = [h["supplier_id"] for h in hits]
        assert "SUP-001" in ids
        assert "SUP-003" in ids

    def test_country_match_us(self, seeded_db):
        hits = seeded_db.match_suppliers(
            {"item_title": "USMCA 원산지", "new_value": "USMCA 적용"}
        )
        # USMCA 키워드 → US 국가 매칭
        ids = [h["supplier_id"] for h in hits]
        assert "SUP-001" in ids or "SUP-002" in ids or "SUP-004" in ids

    def test_no_keywords_returns_empty(self, seeded_db):
        hits = seeded_db.match_suppliers(
            {"item_title": "기타 변경", "new_value": "관련 없음"}
        )
        assert hits == []

    def test_hs_prefix_matches_full_codes(self, seeded_db):
        # 변경에 '8708' 4자리만 → '8708.10' 부품도 매칭
        hits = seeded_db.match_suppliers(
            {"item_title": "8708 관세", "new_value": "HS 8708 영향"}
        )
        ids = [h["supplier_id"] for h in hits]
        assert "SUP-001" in ids


# ─────────────────────────────────────────────────────────────
# Self-assessment form + parse_response
# ─────────────────────────────────────────────────────────────
class TestSelfAssessment:
    def test_generate_form_includes_supplier_and_change(self, tmp_supp_db):
        body = tmp_supp_db.generate_self_assessment_form(
            change={"item_title": "관세 25%", "summary_ko": "긴급", "legal_class": ["administrative"]},
            supplier={"supplier_id": "S-1", "name": "Test Supplier"},
        )
        assert "Test Supplier" in body
        assert "관세 25%" in body
        assert "자가진단" in body

    def test_parse_response_score_calculation(self, tmp_supp_db):
        # 3 YES + 1 NO + 1 부분 → 50 + 60 - 10 + 10 = 110, capped 100
        result = tmp_supp_db.parse_response("S-1", "1번 YES\n2번 YES\n3번 부분\n4번 NO\n5번 YES")
        assert result["yes"] == 3
        assert result["no"] == 1
        assert result["partial"] == 1
        assert result["score"] == 100

    def test_send_assessment_no_smtp_queues(self, seeded_db, monkeypatch):
        import config
        # SMTP 키 비움 — graceful skip
        for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
            monkeypatch.setattr(config, k, "")

        out = seeded_db.send_self_assessment_email(
            change_id=999, supplier_id="SUP-001", body_markdown="test body"
        )
        assert out["ok"] is True
        assert out["status"] == "queued"
        assert out["sent_via_smtp"] is False


# ─────────────────────────────────────────────────────────────
# cost_simulator
# ─────────────────────────────────────────────────────────────
class TestCostSimulator:
    def test_tariff_25pct_calculates_delta(self, seeded_db):
        from features.compliance.cost_simulator import simulate_tariff_impact

        result = simulate_tariff_impact(
            {"item_title": "8708 관세", "new_value": "8708 25% 부과"},
            scenario_rate_pct=25.0,
        )
        # SUP-001/002/003 → HS 8708.10 매칭
        # baseline = (5000*10000 + 4500*8000 + 4800*12000) / 1M = 50+36+57.6 = 143.6 백만
        assert result["baseline_cost_krw_mn"] > 100
        assert result["delta_pct"] == pytest.approx(25.0, abs=2.0)
        assert "8708" in result["applicable_hs"]
        assert len(result["by_supplier"]) >= 3

    def test_no_hs_returns_zero(self, seeded_db):
        from features.compliance.cost_simulator import simulate_tariff_impact

        result = simulate_tariff_impact(
            {"item_title": "기타", "new_value": "관련 없음"},
            scenario_rate_pct=25.0,
        )
        assert result["baseline_cost_krw_mn"] == 0

    def test_chemical_substitution(self, seeded_db):
        from features.compliance.cost_simulator import simulate_chemical_substitution

        result = simulate_chemical_substitution(
            {"item_title": "EU REACH 6가 크롬 인가", "new_value": "6가 크롬 사용 제한"}
        )
        assert "6가 크롬" in result["substances_detected"]
        assert result["estimated_delta_pct"] == 30.0

    def test_chemical_substitution_no_match(self, seeded_db):
        from features.compliance.cost_simulator import simulate_chemical_substitution
        result = simulate_chemical_substitution(
            {"item_title": "관련 없음", "new_value": ""}
        )
        assert result["substances_detected"] == []
        assert result["estimated_delta_pct"] == 0.0


# ─────────────────────────────────────────────────────────────
# supplier_recommender
# ─────────────────────────────────────────────────────────────
class TestRecommender:
    def test_recommends_alternatives_with_scores(self, seeded_db):
        from features.compliance.supplier_recommender import recommend_alternatives

        alts = recommend_alternatives("SUP-001", top_k=3)
        # SUP-002 (PARTA) + SUP-003 (PARTA) 가 후보
        assert len(alts) >= 2
        # 점수 정렬됨
        for a, b in zip(alts, alts[1:]):
            assert a["score_total"] >= b["score_total"]

    def test_diversification_score_for_different_country(self, seeded_db):
        from features.compliance.supplier_recommender import recommend_alternatives

        # SUP-001 (US) → KR/VN 후보는 +10 다양화 점수
        alts = recommend_alternatives("SUP-001", top_k=3)
        gamma = next((a for a in alts if a["supplier_id"] == "SUP-003"), None)
        assert gamma is not None
        assert gamma["score_breakdown"]["diversification"] == 10.0

    def test_nonexistent_supplier_returns_empty(self, seeded_db):
        from features.compliance.supplier_recommender import recommend_alternatives
        assert recommend_alternatives("NOT-EXIST") == []
