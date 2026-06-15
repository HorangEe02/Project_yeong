"""P3 D10 — What-if 시뮬레이션 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────
# 5 default scenarios
# ─────────────────────────────────────────────────────────────
class TestScenarios:
    def test_tariff_returns_kpi_dict(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("tariff", {"rate_pct": 25.0})
        assert out["scenario_type"] == "tariff"
        assert "baseline_kpi" in out
        assert "new_kpi" in out
        assert "operating_profit_krw_mn" in out["baseline_kpi"]
        assert "operating_profit_krw_mn" in out["new_kpi"]

    def test_fx_negative_change_reduces_revenue_for_export(self):
        """원화 강세(-10%) → 수출 매출 감소."""
        from features.compliance.whatif_engine import simulate
        out = simulate("fx", {"krw_usd_change_pct": -10.0})
        assert out["new_kpi"]["revenue_krw_mn"] < out["baseline_kpi"]["revenue_krw_mn"]

    def test_chemical_uses_substance(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("chemical", {"substance": "6가 크롬"})
        assert out["scenario_type"] == "chemical"
        assert out["params"]["substance"] == "6가 크롬"
        # 6가 크롬은 30% 단가 상승 → 원가 증가
        assert out["new_kpi"]["cogs_krw_mn"] > out["baseline_kpi"]["cogs_krw_mn"]

    def test_chemical_empty_substance_safe_response(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("chemical", {})
        assert out["new_kpi"]["operating_profit_krw_mn"] == 0
        assert "substance 파라미터 필요" in out["note"]

    def test_labor_increase_reduces_op_profit(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("labor", {"min_wage_increase_pct": 5.0})
        assert out["delta"]["operating_profit_krw_mn"] < 0
        assert out["delta_pct"]["labor_cost"] == 5.0

    def test_carbon_tax_calculates_total(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("carbon", {"krw_per_ton": 30000, "annual_tons": 50000})
        # 50,000 ton * 30,000원 = 1.5B = 1500 백만
        assert out["new_kpi"]["cogs_krw_mn"] > out["baseline_kpi"]["cogs_krw_mn"]
        assert out["delta"]["cogs_krw_mn"] == 1500


# ─────────────────────────────────────────────────────────────
# Natural language routing
# ─────────────────────────────────────────────────────────────
class TestNaturalLanguageRouting:
    def test_regex_extracts_tariff(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("natural_language", {"query": "관세 50% 추가시?"})
        assert out["scenario_type"] == "tariff"
        assert out["params"]["rate_pct"] == 50.0

    def test_regex_extracts_fx(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("natural_language", {"query": "환율 -10% 변동시?"})
        assert out["scenario_type"] == "fx"
        assert out["params"]["krw_usd_change_pct"] == -10.0

    def test_regex_extracts_chemical(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("natural_language", {"query": "6가 크롬 사용 제한시?"})
        assert out["scenario_type"] == "chemical"
        assert out["params"]["substance"] == "6가 크롬"

    def test_regex_extracts_labor(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("natural_language", {"query": "최저시급 8% 인상시?"})
        assert out["scenario_type"] == "labor"
        assert out["params"]["min_wage_increase_pct"] == 8.0

    def test_regex_extracts_carbon(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("natural_language", {"query": "탄소세 톤당 5만원 도입시?"})
        assert out["scenario_type"] == "carbon"
        assert out["params"]["krw_per_ton"] == 50000.0

    def test_unparseable_returns_safe_response(self, monkeypatch):
        """LLM 미가용 + 정규식 매치 없음 → safe response."""
        import config
        monkeypatch.setattr(config, "OLLAMA_BASE_URL", "")  # LLM 미가용

        from features.compliance.whatif_engine import simulate
        out = simulate("natural_language", {"query": "완전히 모르는 질문 ABC"})
        assert out["scenario_type"] == "natural_language"
        # safe response — 모든 KPI 0
        assert out["baseline_kpi"]["operating_profit_krw_mn"] == 0
        assert "5 시나리오" in out["note"]

    def test_empty_query_safe_response(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("natural_language", {"query": ""})
        assert out["new_kpi"]["operating_profit_krw_mn"] == 0
        assert "query 파라미터 필요" in out["note"]


# ─────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────
class TestValidation:
    def test_unknown_scenario_returns_safe(self):
        from features.compliance.whatif_engine import simulate
        out = simulate("unknown_scenario", {})
        # safe response
        assert out["new_kpi"]["operating_profit_krw_mn"] == 0
        assert "지원되지 않는" in out["note"]

    def test_returns_required_keys(self):
        """모든 시나리오는 동일한 KPI 키 셋 반환."""
        from features.compliance.whatif_engine import simulate
        for st, params in [
            ("tariff", {"rate_pct": 25}),
            ("fx", {"krw_usd_change_pct": 5}),
            ("chemical", {"substance": "6가 크롬"}),
            ("labor", {"min_wage_increase_pct": 3}),
            ("carbon", {"krw_per_ton": 10000, "annual_tons": 1000}),
        ]:
            out = simulate(st, params)
            for kpi_key in ("baseline_kpi", "new_kpi", "delta"):
                for f in ("revenue_krw_mn", "cogs_krw_mn", "operating_profit_krw_mn", "risk_score"):
                    assert f in out[kpi_key], f"{st} missing {kpi_key}.{f}"


# ─────────────────────────────────────────────────────────────
# Integration with cost_simulator (P2 D6)
# ─────────────────────────────────────────────────────────────
class TestIntegration:
    def test_tariff_uses_cost_simulator(self):
        """tariff 시나리오는 P2 의 simulate_tariff_impact 결과를 기반."""
        from features.compliance.whatif_engine import simulate
        out = simulate("tariff", {"rate_pct": 25.0, "hs_codes": ["8708"]})
        # cost_simulator 가 baseline/new 산출 — 빈 supplier DB 면 0
        assert "baseline_kpi" in out
        assert "by_dimension" in out

    def test_chemical_uses_p2_substitution(self):
        """chemical 시나리오는 P2 의 simulate_chemical_substitution 활용."""
        from features.compliance.whatif_engine import simulate
        out = simulate("chemical", {"substance": "납"})
        # 납은 15% 단가 영향
        assert out["delta_pct"]["cogs"] == 15.0
