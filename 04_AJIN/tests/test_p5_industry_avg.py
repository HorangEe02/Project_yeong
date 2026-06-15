"""P5 §4 — DART 5개사 다회사 평균 industry_avg 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    import features.compliance.financial_baseline as fb
    monkeypatch.setattr(fb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fb, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(fb, "INTERNAL_CSV_PATH", tmp_path / "internal.csv")
    monkeypatch.delenv("DART_CORP_CODE", raising=False)
    monkeypatch.delenv("INDUSTRY_PEER_CORP_CODES", raising=False)


class _FakeResp:
    def __init__(self, body: dict, status_code: int = 200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._body


def _success_body(revenue: int, cogs: int) -> dict:
    return {
        "status": "000",
        "list": [
            {"account_id": "ifrs-full_Revenue", "account_nm": "매출액",
             "thstrm_amount": str(revenue * 1_000_000)},
            {"account_id": "ifrs-full_CostOfSales", "account_nm": "매출원가",
             "thstrm_amount": str(cogs * 1_000_000)},
        ],
    }


class TestIndustryAvg:
    def test_no_api_key_returns_none(self, monkeypatch):
        from features.compliance.financial_baseline import _from_industry_avg
        monkeypatch.delenv("DART_API_KEY", raising=False)
        assert _from_industry_avg() is None

    def test_five_peers_average(self, monkeypatch):
        from features.compliance.financial_baseline import _from_industry_avg
        monkeypatch.setenv("DART_API_KEY", "fake")
        # 5개 회사 모두 다른 매출/원가 — 평균 산출 검증
        peer_data = {
            "00164742": _success_body(100_000, 70_000),
            "00164779": _success_body(150_000, 105_000),
            "00126362": _success_body(120_000, 84_000),
            "00126369": _success_body(200_000, 140_000),
            "00164725": _success_body(80_000, 56_000),
        }

        def _fake_get(url, params=None, timeout=None):
            cc = (params or {}).get("corp_code")
            return _FakeResp(peer_data.get(cc, {"status": "020"}))

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        b = _from_industry_avg()
        assert b is not None
        assert b.data_source == "industry_avg"
        assert b.confidence == 0.50
        assert b.revenue_krw_mn == (100_000 + 150_000 + 120_000 + 200_000 + 80_000) // 5
        assert b.cogs_krw_mn == (70_000 + 105_000 + 84_000 + 140_000 + 56_000) // 5
        assert "5peers" in b.emissions["source"]

    def test_three_peers_partial_average(self, monkeypatch):
        """5개 중 3개만 fetch 성공 → 부분 평균. 회사 수 표시."""
        from features.compliance.financial_baseline import _from_industry_avg
        monkeypatch.setenv("DART_API_KEY", "fake")
        peer_data = {
            "00164742": _success_body(100_000, 70_000),
            "00164779": _success_body(200_000, 140_000),
            "00126362": _success_body(150_000, 105_000),
            # 나머지 2개는 에러
        }

        def _fake_get(url, params=None, timeout=None):
            cc = (params or {}).get("corp_code")
            return _FakeResp(peer_data.get(cc, {"status": "020"}))

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        b = _from_industry_avg()
        assert b is not None
        assert "3peers" in b.emissions["source"]
        assert b.revenue_krw_mn == (100_000 + 200_000 + 150_000) // 3

    def test_fewer_than_three_returns_none(self, monkeypatch):
        from features.compliance.financial_baseline import _from_industry_avg
        monkeypatch.setenv("DART_API_KEY", "fake")
        peer_data = {
            "00164742": _success_body(100_000, 70_000),
            # 1개만 성공 → 신뢰 안 됨, None
        }

        def _fake_get(url, params=None, timeout=None):
            cc = (params or {}).get("corp_code")
            return _FakeResp(peer_data.get(cc, {"status": "020"}))

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        assert _from_industry_avg() is None

    def test_env_override_corp_codes(self, monkeypatch):
        """INDUSTRY_PEER_CORP_CODES env 로 오버라이드 가능."""
        from features.compliance.financial_baseline import _peer_corp_codes
        monkeypatch.setenv("INDUSTRY_PEER_CORP_CODES", "11111111, 22222222 ,33333333")
        codes = _peer_corp_codes()
        assert codes == ["11111111", "22222222", "33333333"]
