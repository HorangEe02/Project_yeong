"""P2 D7 — 계약 영향 분석 단위 테스트."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_contract_db(monkeypatch, tmp_path):
    import features.compliance.contract_indexer as ci
    monkeypatch.setattr(ci, "DB_PATH", tmp_path / "contracts.db")
    ci.init_contracts_db()
    return ci


@pytest.fixture
def sample_contract_text():
    return """
계약서

제1조 (목적) 본 계약은 자동차 부품의 공급에 관한 사항을 정함을 목적으로 한다.

제5조 (관세) 양 당사자는 관세 변동시 단가를 재협상한다.
관세 25% 이상 부과 시 본 조항 자동 발동.

제12조 (안전 기준) 공급자는 IATF 16949 인증을 유지하고 PPAP 양식을 제출한다.

제20조 (위약금) 본 계약 위반시 위약금 1억원을 지급한다.
"""


# ─────────────────────────────────────────────────────────────
# 조항 분리
# ─────────────────────────────────────────────────────────────
class TestSplitClauses:
    def test_split_korean_clauses(self, sample_contract_text):
        from features.compliance.contract_indexer import split_into_clauses
        clauses = split_into_clauses(sample_contract_text)
        assert len(clauses) == 4
        assert clauses[0]["clause_no"] == "제1조"
        assert "목적" in clauses[0]["title"]
        assert clauses[1]["clause_no"] == "제5조"
        assert "관세" in clauses[1]["body"]

    def test_split_english_clauses(self):
        from features.compliance.contract_indexer import split_into_clauses
        text = """
Article 1. Purpose. This contract...
Article 2. Tariff. Both parties shall...
Article 3.5. Quality. ISO 9001...
"""
        clauses = split_into_clauses(text)
        assert len(clauses) >= 3
        assert any("Article 1" in c["clause_no"] for c in clauses)

    def test_no_headers_returns_single(self):
        from features.compliance.contract_indexer import split_into_clauses
        clauses = split_into_clauses("그냥 본문 텍스트")
        assert len(clauses) == 1
        assert clauses[0]["clause_no"] == ""

    def test_empty_returns_empty(self):
        from features.compliance.contract_indexer import split_into_clauses
        assert split_into_clauses("") == []


# ─────────────────────────────────────────────────────────────
# 키워드 추출
# ─────────────────────────────────────────────────────────────
class TestExtractKeywords:
    def test_finds_domain_keywords(self):
        from features.compliance.contract_indexer import extract_keywords
        kws = extract_keywords("관세 변동시 단가를 재협상하고 IATF 16949 인증 유지")
        assert "관세" in kws
        assert "단가" in kws
        assert "IATF" in kws

    def test_no_match_empty(self):
        from features.compliance.contract_indexer import extract_keywords
        assert extract_keywords("다른 일반 텍스트") == []


# ─────────────────────────────────────────────────────────────
# Ingest + match_contracts
# ─────────────────────────────────────────────────────────────
class TestIngestContract:
    def test_ingest_txt_file(self, tmp_contract_db, sample_contract_text, tmp_path):
        from features.compliance.contract_indexer import ingest_contract, list_contracts

        txt = tmp_path / "contract.txt"
        txt.write_text(sample_contract_text, encoding="utf-8")

        out = ingest_contract(
            file_path=str(txt),
            contract_id="HMC-001",
            counterparty="현대차",
            contract_type="OEM",
            effective_date="2024-01-01",
            annual_value_krw_mn=10000,
        )
        assert out["ok"] is True
        assert out["clause_count"] == 4

        lst = list_contracts()
        assert len(lst) == 1
        assert lst[0]["contract_id"] == "HMC-001"
        assert lst[0]["counterparty"] == "현대차"

    def test_ingest_nonexistent_file(self, tmp_contract_db):
        from features.compliance.contract_indexer import ingest_contract
        out = ingest_contract(file_path="/nonexistent.pdf", contract_id="X-1")
        assert out["ok"] is False
        assert "미존재" in out["error"]

    def test_ingest_unsupported_extension(self, tmp_contract_db, tmp_path):
        from features.compliance.contract_indexer import ingest_contract
        f = tmp_path / "contract.xyz"
        f.write_text("dummy")
        out = ingest_contract(file_path=str(f), contract_id="X-1")
        assert out["ok"] is False
        assert "확장자" in out["error"]


class TestMatchContracts:
    def test_keyword_overlap_match(self, tmp_contract_db, sample_contract_text, tmp_path):
        from features.compliance.contract_indexer import ingest_contract, match_contracts

        txt = tmp_path / "c.txt"
        txt.write_text(sample_contract_text, encoding="utf-8")
        ingest_contract(file_path=str(txt), contract_id="HMC-001", counterparty="현대차")

        # 변경에 '관세' 키워드 포함 → 제5조 매칭
        hits = match_contracts({
            "item_title": "자동차 부품 관세 25% 부과",
            "new_value": "관세 변동 시 단가 재협상",
        })
        assert len(hits) >= 1
        # 매칭에 제5조가 포함되어야 함
        assert any(h.get("clause_no") == "제5조" for h in hits)

    def test_empty_change_returns_empty(self, tmp_contract_db):
        from features.compliance.contract_indexer import match_contracts
        assert match_contracts({}) == []
        assert match_contracts({"item_title": ""}) == []


class TestListContracts:
    def test_search_by_counterparty(self, tmp_contract_db, sample_contract_text, tmp_path):
        from features.compliance.contract_indexer import ingest_contract, list_contracts

        txt = tmp_path / "c.txt"
        txt.write_text(sample_contract_text, encoding="utf-8")
        ingest_contract(file_path=str(txt), contract_id="HMC-001", counterparty="현대차")
        ingest_contract(file_path=str(txt), contract_id="KIA-001", counterparty="기아")

        all_lst = list_contracts()
        assert len(all_lst) == 2

        hyundai = list_contracts(search="현대")
        assert len(hyundai) == 1
        assert hyundai[0]["contract_id"] == "HMC-001"
