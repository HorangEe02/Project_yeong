"""P1 D1 — 법무 5분류 + 벌칙 추출 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────
# 5분류 (criminal / administrative / civil / contract / standardization)
# ─────────────────────────────────────────────────────────────
class TestClassifyLegal:
    def test_criminal_imprisonment(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {"item_title": "산안법", "new_value": "5년 이하 징역에 처한다"}
        assert "criminal" in classify_legal(ch)

    def test_criminal_imprisonment_or_fine(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {"item_title": "화관법", "new_value": "7년 이하 징역 또는 1억원 이하 벌금"}
        # 벌금은 criminal, 징역도 criminal — 한 번만
        classes = classify_legal(ch)
        assert classes == ["criminal"]

    def test_administrative_overaction(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {"item_title": "대기법", "new_value": "조업정지 또는 5천만원 이하 과징금"}
        classes = classify_legal(ch)
        assert "administrative" in classes
        assert "criminal" not in classes  # 징역·벌금 없음

    def test_administrative_atae(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {"item_title": "법", "new_value": "미보고시 1천만원 이하 과태료"}
        assert "administrative" in classify_legal(ch)

    def test_multi_class_criminal_and_administrative(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {
            "item_title": "산안법 38조",
            "new_value": "5년 이하 징역 또는 1억원 이하 벌금. 미보고 1천만원 이하 과태료.",
        }
        classes = classify_legal(ch)
        assert "criminal" in classes
        assert "administrative" in classes

    def test_civil_damages(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {"item_title": "PL", "new_value": "결함 시 손해배상 책임"}
        assert "civil" in classify_legal(ch)

    def test_contract_breach(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {"item_title": "OEM 계약", "new_value": "위반시 위약금 + 거래중지"}
        assert "contract" in classify_legal(ch)

    def test_standardization(self):
        from features.compliance.legal_classifier import classify_legal
        ch = {"item_title": "IATF 16949", "new_value": "정기검사 분기별 + KS 인증 필수"}
        assert "standardization" in classify_legal(ch)

    def test_priority_order(self):
        """다중 분류 시 priority 순서: criminal > administrative > civil > contract > standardization."""
        from features.compliance.legal_classifier import classify_legal
        ch = {
            "item_title": "복합",
            "new_value": "징역 5년, 과징금 1억원, 손해배상 책임, 계약해지, 인증취소",
        }
        classes = classify_legal(ch)
        assert classes[0] == "criminal"
        assert classes.index("administrative") < classes.index("civil")

    def test_empty_returns_empty_list(self):
        from features.compliance.legal_classifier import classify_legal
        assert classify_legal({}) == []
        assert classify_legal({"item_title": "", "new_value": ""}) == []


# ─────────────────────────────────────────────────────────────
# 벌칙 정규식 추출
# ─────────────────────────────────────────────────────────────
class TestExtractPenalty:
    def test_imprisonment_only(self):
        from features.compliance.legal_classifier import extract_penalty
        out = extract_penalty({"new_value": "5년 이하 징역"})
        assert out["max_imprisonment_years"] == 5
        assert "5년 이하 징역" in out["raw_text"]

    def test_fine_in_eok(self):
        from features.compliance.legal_classifier import extract_penalty
        out = extract_penalty({"new_value": "1억원 이하 벌금"})
        assert out["max_fine_krw_mn"] == 100  # 1억 = 100백만

    def test_fine_in_chunman(self):
        from features.compliance.legal_classifier import extract_penalty
        out = extract_penalty({"new_value": "5천만원 이하 과징금"})
        assert out["max_fine_krw_mn"] == 50  # 5천만 = 50백만

    def test_imprisonment_and_fine(self):
        from features.compliance.legal_classifier import extract_penalty
        out = extract_penalty({"new_value": "5년 이하 징역 또는 1억원 이하 벌금"})
        assert out["max_imprisonment_years"] == 5
        assert out["max_fine_krw_mn"] == 100
        assert "5년 이하 징역" in out["raw_text"]
        assert "1억" in out["raw_text"]

    def test_multiple_imprisonment_takes_max(self):
        from features.compliance.legal_classifier import extract_penalty
        out = extract_penalty({"new_value": "사망사고 7년 이하 징역, 부상 3년 이하 징역"})
        assert out["max_imprisonment_years"] == 7

    def test_multiplier_penalty(self):
        from features.compliance.legal_classifier import extract_penalty
        out = extract_penalty({"new_value": "초과 배출량 × 시장가격 3배 과징금"})
        assert out["max_multiplier"] == 3

    def test_no_match_returns_zeros(self):
        from features.compliance.legal_classifier import extract_penalty
        out = extract_penalty({"new_value": "본문에 벌칙 없음"})
        assert out["raw_text"] == ""
        assert out["max_imprisonment_years"] == 0
        assert out["max_fine_krw_mn"] == 0
        assert out["max_multiplier"] == 0


# ─────────────────────────────────────────────────────────────
# enrich_legal — in-place enrich 통합
# ─────────────────────────────────────────────────────────────
class TestEnrichLegal:
    def test_full_enrich(self):
        from features.compliance.legal_classifier import enrich_legal
        ch = {
            "item_title": "산안법 38조",
            "new_value": "5년 이하 징역 또는 1억원 이하 벌금. 미보고 1천만원 이하 과태료.",
            "old_value": "",
        }
        enrich_legal(ch)
        assert "criminal" in ch["legal_class"]
        assert "administrative" in ch["legal_class"]
        assert ch["penalty_severity_krw_mn"] == 100
        assert ch["penalty_imprisonment_years"] == 5
        assert "5년 이하 징역" in ch["penalty_extract"]

    def test_classify_change_pipeline_includes_legal(self, monkeypatch):
        """classify_change() 가 enrich_legal 을 호출해 결과를 부착."""
        import config
        monkeypatch.setattr(config, "OLLAMA_BASE_URL", "")  # rule fallback only
        from features.compliance.change_classifier import classify_change
        out = classify_change({
            "change_type": "added",
            "item_id": "L-X",
            "item_title": "관세 25% 부과 시행",
            "new_value": "위반시 5년 이하 징역, 1억원 이하 벌금",
            "old_value": "",
            "severity": "warning",
        })
        # classify_change 후 — legal 필드 모두 채워짐
        assert "criminal" in out["legal_class"]
        assert out["penalty_severity_krw_mn"] >= 100
        assert out["penalty_extract"]


# ─────────────────────────────────────────────────────────────
# DB persist — save_changes 가 legal 컬럼을 보존
# ─────────────────────────────────────────────────────────────
class TestPersistLegal:
    def test_save_changes_persists_legal_columns(self, tmp_path, monkeypatch):
        import features.compliance.change_detector as cd
        monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))

        ids = cd.save_changes([{
            "regulation_type": "test",
            "change_type": "added",
            "item_id": "X-1",
            "item_title": "t",
            "old_value": "",
            "new_value": "5년 이하 징역",
            "severity": "info",
            "summary_ko": "s",
            "grade": "HIGH",
            "affected_departments": [],
            "affected_plants": [],
            "legal_class": ["criminal"],
            "penalty_extract": "5년 이하 징역",
            "penalty_severity_krw_mn": 0,
        }])
        assert len(ids) == 1

        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "ch.db"))
        row = conn.execute(
            "SELECT legal_class, penalty_extract, penalty_severity_krw_mn FROM regulation_changes WHERE id = ?",
            (ids[0],),
        ).fetchone()
        conn.close()
        import json as _j
        assert _j.loads(row[0]) == ["criminal"]
        assert "5년 이하 징역" in row[1]
        assert row[2] == 0
