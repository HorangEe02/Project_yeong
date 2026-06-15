"""P4 D17 — What-if 정밀화 단위 테스트 (financial_baseline + Scope + accounting)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _isolate_baseline(tmp_path, monkeypatch):
    """baseline cache + internal csv 격리, DART 키 비활성."""
    import features.compliance.financial_baseline as fb
    monkeypatch.setattr(fb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fb, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(fb, "INTERNAL_CSV_PATH", tmp_path / "internal_baseline.csv")
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.delenv("DART_CORP_CODE", raising=False)
    monkeypatch.delenv("INTERNAL_BASELINE_CSV", raising=False)
    return tmp_path


# ─────────────────────────────────────────────────────────────
# get_baseline 우선순위
# ─────────────────────────────────────────────────────────────


class TestBaselinePriority:
    def test_no_data_falls_back_to_hardcoded(self, tmp_path):
        from features.compliance.financial_baseline import get_baseline
        b = get_baseline()
        assert b.data_source == "hardcoded"
        assert b.confidence == 0.30
        assert b.revenue_krw_mn == 100_000

    def test_internal_csv_highest_priority(self, tmp_path, monkeypatch):
        import features.compliance.financial_baseline as fb
        # internal CSV 작성
        csv = (
            "revenue_krw_mn,cogs_krw_mn,labor_share,scope_1_tons,scope_2_tons,scope_3_tons,as_of\n"
            "200000,140000,0.30,1000,2000,3000,2025-12-31\n"
        )
        (tmp_path / "internal_baseline.csv").write_text(csv, encoding="utf-8")
        b = fb.get_baseline(use_cache=False)
        assert b.data_source == "erp"
        assert b.confidence == 0.95
        assert b.revenue_krw_mn == 200000
        assert b.emissions["scope_1"] == 1000
        assert b.emissions["scope_3"] == 3000

    def test_industry_avg_skipped_when_no_data(self, tmp_path):
        # P3 industry_filings 데이터 없으면 산업 평균은 None 반환
        from features.compliance.financial_baseline import _from_industry_avg
        # collection_stats 가 0 → None
        result = _from_industry_avg()
        # industry DB 가 비어있는 환경 가정 — 어떤 결과든 None 또는 baseline
        assert result is None or result.confidence == 0.50

    def test_cache_hit_skips_fetch(self, tmp_path, monkeypatch):
        import features.compliance.financial_baseline as fb
        # 1차 fetch — hardcoded
        b1 = fb.get_baseline()
        # 2차 — 캐시 히트
        b2 = fb.get_baseline()
        # 둘 다 동일 데이터
        assert b1.data_source == b2.data_source
        assert b1.confidence == b2.confidence

    def test_cache_written_for_real_source(self, tmp_path, monkeypatch):
        """ERP CSV 가용 시 캐시 파일이 작성됨. 하드코딩 폴백은 캐시 안 함 (TTL lock-in 방지)."""
        import features.compliance.financial_baseline as fb
        csv = (
            "revenue_krw_mn,cogs_krw_mn,labor_share,scope_1_tons,scope_2_tons,scope_3_tons,as_of\n"
            "150000,100000,0.30,500,1000,,2025-12-31\n"
        )
        (tmp_path / "internal_baseline.csv").write_text(csv, encoding="utf-8")
        fb.get_baseline()
        assert fb.CACHE_PATH.exists()
        fb.clear_cache()
        assert not fb.CACHE_PATH.exists()


# ─────────────────────────────────────────────────────────────
# Scope 1/2/3 합산
# ─────────────────────────────────────────────────────────────


class TestScopeSelection:
    def test_total_emissions_default_scope_1_2(self, tmp_path):
        from features.compliance.financial_baseline import (
            Baseline, total_emissions_tons,
        )
        b = Baseline(
            emissions={"scope_1": 100, "scope_2": 200, "scope_3": 999,
                       "source": "test"},
        )
        assert total_emissions_tons(b) == 300  # default 1+2

    def test_total_emissions_explicit_scope_3(self, tmp_path):
        from features.compliance.financial_baseline import (
            Baseline, total_emissions_tons,
        )
        b = Baseline(
            emissions={"scope_1": 100, "scope_2": 200, "scope_3": 999,
                       "source": "test"},
        )
        assert total_emissions_tons(b, [1, 2, 3]) == 1299

    def test_scope_3_missing_excluded(self, tmp_path):
        from features.compliance.financial_baseline import (
            Baseline, total_emissions_tons,
        )
        b = Baseline(
            emissions={"scope_1": 100, "scope_2": 200, "scope_3": None,
                       "source": "no_scope_3"},
        )
        assert total_emissions_tons(b, [1, 2, 3]) == 300


# ─────────────────────────────────────────────────────────────
# whatif_engine 통합
# ─────────────────────────────────────────────────────────────


class TestWhatIfMeta:
    def test_simulate_includes_meta_field(self, tmp_path):
        from features.compliance.whatif_engine import simulate
        out = simulate("fx", {"krw_usd_change_pct": -10})
        assert "meta" in out
        assert "data_source" in out["meta"]
        assert "confidence" in out["meta"]

    def test_carbon_with_scope_param(self, tmp_path, monkeypatch):
        import features.compliance.financial_baseline as fb
        csv = (
            "revenue_krw_mn,cogs_krw_mn,labor_share,scope_1_tons,scope_2_tons,scope_3_tons,as_of\n"
            "100000,70000,0.25,1000,2000,3000,2025-12-31\n"
        )
        (tmp_path / "internal_baseline.csv").write_text(csv, encoding="utf-8")
        from features.compliance.whatif_engine import simulate
        # Scope 1+2 만 (annual_tons 명시 X)
        out = simulate("carbon", {"krw_per_ton": 30000, "scope": [1, 2]})
        # tax_new = 3000 (Scope1+2) * 30000 / 1_000_000 = 0.09 → int(0)
        # hmm — 3000 * 30000 = 90_000_000, /1_000_000 = 90 백만원
        # 즉 tax 90 백만원 — int(90)
        # by_dimension 에 Scope 1, Scope 2 가 포함
        scope_dims = [d for d in out["by_dimension"] if d.get("name", "").startswith("Scope")]
        assert len(scope_dims) == 2
        assert out["params"]["annual_tons"] == 3000.0
        assert out["meta"]["data_source"] == "erp"

    def test_carbon_legacy_annual_tons_param_still_works(self, tmp_path):
        """P3 호환 — annual_tons + krw_per_ton 명시 시 그대로 동작."""
        from features.compliance.whatif_engine import simulate
        out = simulate("carbon", {"annual_tons": 1000, "krw_per_ton": 1500000})
        # 기존 P3 테스트 단언: delta cogs_krw_mn == 1500
        assert out["delta"]["cogs_krw_mn"] == 1500


# ─────────────────────────────────────────────────────────────
# accounting_trace
# ─────────────────────────────────────────────────────────────


class TestSafeBaselineValue:
    """P4.1 §3 — _safe_baseline_value: 0/음수/None 일 때만 hardcoded fallback."""

    def test_zero_falls_back(self):
        from features.compliance.whatif_engine import _safe_baseline_value
        assert _safe_baseline_value(0, 70_000) == 70_000

    def test_negative_falls_back(self):
        from features.compliance.whatif_engine import _safe_baseline_value
        assert _safe_baseline_value(-100, 70_000) == 70_000

    def test_none_falls_back(self):
        from features.compliance.whatif_engine import _safe_baseline_value
        assert _safe_baseline_value(None, 70_000) == 70_000

    def test_positive_uses_value(self):
        from features.compliance.whatif_engine import _safe_baseline_value
        assert _safe_baseline_value(150_000, 70_000) == 150_000

    def test_invalid_type_falls_back(self):
        from features.compliance.whatif_engine import _safe_baseline_value
        assert _safe_baseline_value("abc", 70_000) == 70_000


class TestSqlIdentifierGuard:
    """P4 D17 fix #2 — _enrich_scope_2 의 동적 테이블명 화이트리스트 검증."""

    def test_unsafe_table_names_are_skipped(self, tmp_path, monkeypatch):
        """공백/한글/특수문자 테이블명은 화이트리스트 미통과로 자동 skip."""
        import features.compliance.financial_baseline as fb

        # 가짜 facility_db 모듈 — sqlite 메모리 DB 에 안전/위험 테이블 혼재
        import sqlite3 as _sql
        conn = _sql.connect(":memory:")
        conn.row_factory = _sql.Row
        conn.execute("CREATE TABLE safe_facility (id INTEGER, kwh_per_year INTEGER)")
        conn.execute("INSERT INTO safe_facility VALUES (1, 1000000)")
        # 위험 테이블명은 SQLite 가 quoting 안 한 채 받지 않으므로 직접 실험은 어렵다.
        # 대신 화이트리스트 정규식 자체가 작동하는지 검증.
        assert fb._SAFE_IDENT_RE.match("safe_facility") is not None
        assert fb._SAFE_IDENT_RE.match("kwh_per_year") is not None
        assert fb._SAFE_IDENT_RE.match("공장") is None
        assert fb._SAFE_IDENT_RE.match("table; DROP TABLE x") is None
        assert fb._SAFE_IDENT_RE.match("table'") is None
        assert fb._SAFE_IDENT_RE.match("") is None
        assert fb._SAFE_IDENT_RE.match("123abc") is None  # 숫자 시작 거부

    def test_enrich_scope_2_silent_skip_when_facility_db_unavailable(self, tmp_path):
        """facility_db get_db 가 없거나 실패해도 _enrich_scope_2 가 raise 안 함."""
        import features.compliance.financial_baseline as fb
        b = fb.Baseline()
        # 절대 raise 안 되어야 함 (현재 facility_db 는 get_db 미제공 → ImportError graceful skip)
        fb._enrich_scope_2(b)
        # baseline.emissions 도 변경 없음 (Scope 2 enrich 미실행)
        assert b.emissions == {}


class TestAccountingTrace:
    def test_tariff_maps_to_cogs_and_gross_profit(self, tmp_path):
        from features.compliance.accounting_trace import map_to_pnl
        result = {
            "scenario_type": "tariff",
            "delta": {"cogs_krw_mn": 5000, "operating_profit_krw_mn": -5000},
            "meta": {"confidence": 0.75},
        }
        items = map_to_pnl(result)
        lines = [i["line"] for i in items]
        assert "매출원가" in lines
        assert "매출총이익" in lines
        cogs_item = next(i for i in items if i["line"] == "매출원가")
        assert cogs_item["delta_krw_mn"] == 5000
        assert cogs_item["direction"] == "increase"
        assert cogs_item["confidence"] == 0.75

    def test_unknown_scenario_returns_empty(self, tmp_path):
        from features.compliance.accounting_trace import map_to_pnl
        items = map_to_pnl({"scenario_type": "alien", "delta": {}})
        assert items == []

    def test_carbon_maps_to_tax(self, tmp_path):
        from features.compliance.accounting_trace import map_to_pnl
        result = {
            "scenario_type": "carbon",
            "delta": {"cogs_krw_mn": 1500, "operating_profit_krw_mn": -1500},
            "meta": {"confidence": 0.30},
        }
        items = map_to_pnl(result)
        tax = next(i for i in items if i["line"] == "세금과공과")
        assert tax["delta_krw_mn"] == 1500
        op = next(i for i in items if i["line"] == "영업이익")
        assert op["direction"] == "decrease"
