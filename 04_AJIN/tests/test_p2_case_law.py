"""P2 D8 — 외부 판례 RAG 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────
# fetch_cases_for_keyword
# ─────────────────────────────────────────────────────────────
class TestFetchCases:
    def test_no_credentials_returns_empty(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "LAW_GO_KR_OC", "")
        from features.compliance.case_law_indexer import fetch_cases_for_keyword
        assert fetch_cases_for_keyword("산안법") == []

    def test_normalizes_response(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "LAW_GO_KR_OC", "test-oc")

        fake_response = {
            "PrecSearch": {
                "prec": [
                    {
                        "판례일련번호": "12345",
                        "법원명": "대법원",
                        "선고일자": "20240315",
                        "사건명": "산업안전 위반 사건",
                        "판례내용": "본문 ...",
                    },
                ],
            },
        }

        def _fake_fetch(url):
            assert "target=prec" in url
            return fake_response

        monkeypatch.setattr("features.compliance._http.fetch_json", _fake_fetch)

        from features.compliance.case_law_indexer import fetch_cases_for_keyword
        cases = fetch_cases_for_keyword("산업안전", display=10)
        assert len(cases) == 1
        c = cases[0]
        assert c["case_id"] == "12345"
        assert c["court"] == "대법원"
        assert c["date"] == "2024-03-15"  # 정규화된 ISO 형식
        assert "산업안전" in c["title"] or c["title"]

    def test_external_failure_returns_empty(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "LAW_GO_KR_OC", "test-oc")

        def _raise(url):
            raise RuntimeError("network down")

        monkeypatch.setattr("features.compliance._http.fetch_json", _raise)

        from features.compliance.case_law_indexer import fetch_cases_for_keyword
        # graceful — 빈 list 반환
        assert fetch_cases_for_keyword("산안법") == []


# ─────────────────────────────────────────────────────────────
# find_similar / find_similar_for_change
# ─────────────────────────────────────────────────────────────
class TestFindSimilar:
    def test_empty_query_returns_empty(self):
        from features.compliance.case_law_indexer import find_similar
        assert find_similar("") == []
        assert find_similar(None or "") == []  # type: ignore[arg-type]

    def test_empty_change_returns_empty(self):
        from features.compliance.case_law_indexer import find_similar_for_change
        assert find_similar_for_change({}) == []
        assert find_similar_for_change({"item_title": ""}) == []

    def test_similarity_threshold_filters_low_score(self):
        """유사도 < 0.7 결과는 제외 — 무관 판례 시간 낭비 방지."""
        from features.compliance.case_law_indexer import find_similar

        class _Coll:
            def query(self, **kw):
                # 결과 2개: 하나는 distance 0.1 (sim 0.9, 통과), 하나는 0.5 (sim 0.5, 컷)
                return {
                    "metadatas": [[
                        {"case_id": "1", "court": "대법원", "date": "2024-01-01", "title": "고", "full_url": ""},
                        {"case_id": "2", "court": "대법원", "date": "2024-01-02", "title": "저", "full_url": ""},
                    ]],
                    "documents": [["high sim doc", "low sim doc"]],
                    "distances": [[0.1, 0.5]],
                }

        with patch("features.compliance.case_law_indexer._get_collection", return_value=_Coll()):
            hits = find_similar("query")
        assert len(hits) == 1
        assert hits[0]["case_id"] == "1"
        assert hits[0]["similarity"] >= 0.7

    def test_no_collection_returns_empty(self):
        from features.compliance.case_law_indexer import find_similar
        with patch("features.compliance.case_law_indexer._get_collection", return_value=None):
            assert find_similar("산안법") == []


# ─────────────────────────────────────────────────────────────
# collection_stats
# ─────────────────────────────────────────────────────────────
class TestCollectionStats:
    def test_returns_available_and_count(self):
        from features.compliance.case_law_indexer import collection_stats
        s = collection_stats()
        assert "available" in s
        assert "count" in s
        assert isinstance(s["count"], int)


# ─────────────────────────────────────────────────────────────
# Format helpers
# ─────────────────────────────────────────────────────────────
class TestFormatDate:
    def test_format_yyyymmdd(self):
        from features.compliance.case_law_indexer import _format_yyyymmdd
        assert _format_yyyymmdd("20240315") == "2024-03-15"
        assert _format_yyyymmdd("") == ""
        assert _format_yyyymmdd(None) == ""
        # Already-formatted dates pass through
        assert _format_yyyymmdd("2024-03-15") == "2024-03-15"
