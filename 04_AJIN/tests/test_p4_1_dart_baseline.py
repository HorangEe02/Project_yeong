"""P4.1 §2 + §9 — DART 재무제표 fetch + account_nm 매칭 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """baseline cache + internal csv 격리, DART 키 deactivate (개별 테스트에서 set)."""
    import features.compliance.financial_baseline as fb
    monkeypatch.setattr(fb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fb, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(fb, "INTERNAL_CSV_PATH", tmp_path / "internal.csv")
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.delenv("DART_CORP_CODE", raising=False)


# ─────────────────────────────────────────────────────────────
# account 매칭 헬퍼
# ─────────────────────────────────────────────────────────────


class TestAccountMatch:
    def test_ifrs_revenue_id_matches(self):
        from features.compliance.financial_baseline import _match_dart_revenue
        assert _match_dart_revenue({"account_id": "ifrs-full_Revenue", "account_nm": "X"}) is True
        assert _match_dart_revenue({
            "account_id": "ifrs-full_RevenueFromContractsWithCustomers",
            "account_nm": "Y",
        }) is True

    def test_ifrs_cogs_id_matches(self):
        from features.compliance.financial_baseline import _match_dart_cogs
        assert _match_dart_cogs({"account_id": "ifrs-full_CostOfSales", "account_nm": "X"}) is True

    def test_korean_revenue_partial(self):
        from features.compliance.financial_baseline import _match_dart_revenue
        # 다양한 표기 — 모두 매출
        for nm in ["매출액", "수익(매출액)", "매출액(영업수익)", "영업수익", "매출"]:
            assert _match_dart_revenue({"account_id": "", "account_nm": nm}) is True, nm

    def test_korean_cogs_partial(self):
        from features.compliance.financial_baseline import _match_dart_cogs
        for nm in ["매출원가", "매출원가(매출원가)", "용역원가"]:
            assert _match_dart_cogs({"account_id": "", "account_nm": nm}) is True, nm

    def test_revenue_excludes_cogs_keyword(self):
        """`매출원가` 가 매출 매칭에 잡히면 안 됨."""
        from features.compliance.financial_baseline import (
            _match_dart_revenue, _match_dart_cogs,
        )
        row = {"account_id": "", "account_nm": "매출원가(매출원가)"}
        assert _match_dart_revenue(row) is False  # `원가` 가드
        assert _match_dart_cogs(row) is True

    def test_unrelated_account(self):
        from features.compliance.financial_baseline import (
            _match_dart_revenue, _match_dart_cogs,
        )
        row = {"account_id": "", "account_nm": "유형자산"}
        assert _match_dart_revenue(row) is False
        assert _match_dart_cogs(row) is False


# ─────────────────────────────────────────────────────────────
# _from_dart httpx mock
# ─────────────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, json_body: dict, status_code: int = 200):
        self._body = json_body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"status={self.status_code}", request=None, response=None,
            )

    def json(self):
        return self._body


class TestFromDart:
    def test_no_api_key_returns_none(self, monkeypatch):
        from features.compliance.financial_baseline import _from_dart
        # API_KEY 미설정 — fixture 에서 이미 delete
        assert _from_dart("00126380") is None

    def test_no_corp_code_returns_none(self, monkeypatch):
        from features.compliance.financial_baseline import _from_dart
        monkeypatch.setenv("DART_API_KEY", "fake-key")
        assert _from_dart("") is None

    def test_ifrs_match_returns_baseline(self, monkeypatch):
        from features.compliance.financial_baseline import _from_dart

        def _fake_get(url, params=None, timeout=None):
            return _FakeResp({
                "status": "000",
                "list": [
                    {"account_id": "ifrs-full_Revenue", "account_nm": "수익(매출액)",
                     "thstrm_amount": "200000000000"},   # 2000억 (= 200,000 백만원)
                    {"account_id": "ifrs-full_CostOfSales", "account_nm": "매출원가",
                     "thstrm_amount": "140000000000"},   # 1400억
                    {"account_id": "ifrs-full_OtherStuff", "account_nm": "유형자산",
                     "thstrm_amount": "999999999999"},
                ],
            })

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setenv("DART_API_KEY", "fake-key")

        b = _from_dart("00126380")
        assert b is not None
        assert b.data_source == "dart"
        assert b.confidence == 0.75
        assert b.revenue_krw_mn == 200_000
        assert b.cogs_krw_mn == 140_000
        assert b.corp_code == "00126380"

    def test_korean_partial_match_when_no_ifrs_id(self, monkeypatch):
        from features.compliance.financial_baseline import _from_dart

        def _fake_get(url, params=None, timeout=None):
            return _FakeResp({
                "status": "000",
                "list": [
                    {"account_id": "", "account_nm": "수익(매출액)",
                     "thstrm_amount": "100000000000"},
                    {"account_id": "", "account_nm": "매출원가(매출원가)",
                     "thstrm_amount": "70000000000"},
                ],
            })

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setenv("DART_API_KEY", "fake-key")

        b = _from_dart("00126380")
        assert b is not None
        assert b.revenue_krw_mn == 100_000
        assert b.cogs_krw_mn == 70_000

    def test_dart_error_status_returns_none(self, monkeypatch):
        from features.compliance.financial_baseline import _from_dart

        def _fake_get(url, params=None, timeout=None):
            # DART rate limit / 키 오류 등
            return _FakeResp({"status": "020", "message": "한도초과"})

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setenv("DART_API_KEY", "fake-key")

        assert _from_dart("00126380") is None

    def test_empty_list_returns_none(self, monkeypatch):
        from features.compliance.financial_baseline import _from_dart

        def _fake_get(url, params=None, timeout=None):
            return _FakeResp({"status": "000", "list": []})

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setenv("DART_API_KEY", "fake-key")

        assert _from_dart("00126380") is None

    def test_cfs_consolidated_returns_higher_confidence(self, monkeypatch):
        """P5 §8 — fs_div='CFS' 연결재무제표 호출 시 data_source='dart_cfs', confidence 0.80."""
        from features.compliance.financial_baseline import _from_dart

        captured = {}

        def _fake_get(url, params=None, timeout=None):
            captured["fs_div"] = (params or {}).get("fs_div")
            return _FakeResp({
                "status": "000",
                "list": [
                    {"account_id": "ifrs-full_Revenue", "account_nm": "매출액(연결)",
                     "thstrm_amount": "300000000000"},
                    {"account_id": "ifrs-full_CostOfSales", "account_nm": "매출원가",
                     "thstrm_amount": "210000000000"},
                ],
            })

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setenv("DART_API_KEY", "fake-key")

        b = _from_dart("00126380", fs_div="CFS")
        assert b is not None
        assert captured["fs_div"] == "CFS"
        assert b.data_source == "dart_cfs"
        assert b.confidence == 0.80
        assert b.revenue_krw_mn == 300_000

    def test_invalid_fs_div_falls_back_to_ofs(self, monkeypatch):
        from features.compliance.financial_baseline import _from_dart

        captured = {}

        def _fake_get(url, params=None, timeout=None):
            captured["fs_div"] = (params or {}).get("fs_div")
            return _FakeResp({"status": "000", "list": []})

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setenv("DART_API_KEY", "fake-key")

        _from_dart("00126380", fs_div="WEIRD")
        assert captured["fs_div"] == "OFS"

    def test_revenue_only_uses_estimated_cogs(self, monkeypatch):
        """매출만 있으면 cogs = revenue * 0.7 (legacy behavior 유지)."""
        from features.compliance.financial_baseline import _from_dart

        def _fake_get(url, params=None, timeout=None):
            return _FakeResp({
                "status": "000",
                "list": [
                    {"account_id": "ifrs-full_Revenue", "account_nm": "매출액",
                     "thstrm_amount": "100000000000"},
                ],
            })

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setenv("DART_API_KEY", "fake-key")

        b = _from_dart("00126380")
        assert b is not None
        assert b.revenue_krw_mn == 100_000
        assert b.cogs_krw_mn == 70_000  # 100_000 * 0.7
