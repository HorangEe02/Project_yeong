"""P1 D4 — RAG (Indexer + QA + Module C 통합) 단위 테스트."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────
# 청크 분할
# ─────────────────────────────────────────────────────────────
class TestChunkText:
    def test_short_text_single_chunk(self):
        from features.compliance.regulation_indexer import _chunk_text
        chunks = _chunk_text("짧은 본문입니다.", max_chars=400)
        assert chunks == ["짧은 본문입니다."]

    def test_empty_returns_empty_list(self):
        from features.compliance.regulation_indexer import _chunk_text
        assert _chunk_text("") == []
        assert _chunk_text(None) == []

    def test_long_text_split(self):
        from features.compliance.regulation_indexer import _chunk_text
        long = "한 문장입니다. " * 100
        chunks = _chunk_text(long, max_chars=200)
        assert len(chunks) >= 2

    def test_split_at_period(self):
        from features.compliance.regulation_indexer import _chunk_text
        text = ("첫째 문장입니다. " * 30) + ("둘째 문장입니다. " * 30)
        chunks = _chunk_text(text, max_chars=300)
        assert len(chunks) >= 2
        # 마침표 경계 분할 — 첫 청크 끝에 마침표
        assert chunks[0].rstrip().endswith(".")


# ─────────────────────────────────────────────────────────────
# 신입 모드 판단
# ─────────────────────────────────────────────────────────────
class TestIsNovice:
    def test_recent_hire_is_novice(self):
        from features.compliance.regulation_qa import is_novice

        class _U:
            hire_date = (date.today() - timedelta(days=30)).isoformat()

        assert is_novice(_U()) is True

    def test_old_hire_not_novice(self):
        from features.compliance.regulation_qa import is_novice

        class _U:
            hire_date = (date.today() - timedelta(days=365 * 5)).isoformat()

        assert is_novice(_U()) is False

    def test_dict_user(self):
        from features.compliance.regulation_qa import is_novice
        recent = (date.today() - timedelta(days=10)).isoformat()
        assert is_novice({"hire_date": recent}) is True

    def test_no_hire_date_not_novice(self):
        from features.compliance.regulation_qa import is_novice
        assert is_novice({}) is False
        assert is_novice(None) is False

    def test_invalid_date_not_novice(self):
        from features.compliance.regulation_qa import is_novice
        assert is_novice({"hire_date": "garbage"}) is False


# ─────────────────────────────────────────────────────────────
# answer_question
# ─────────────────────────────────────────────────────────────
class TestAnswerQuestion:
    def test_rag_miss_returns_safe_answer(self):
        from features.compliance.regulation_qa import answer_question
        with patch("features.compliance.regulation_indexer.search", return_value=[]):
            out = answer_question("완전히 없는 규제", user=None)
        assert out["rag_hit"] is False
        assert out["citations"] == []
        # 안전 응답 — 가짜 답변 X
        assert "확신" in out["answer"] or "문의" in out["answer"]

    def test_rag_hit_includes_citations(self):
        from features.compliance.regulation_qa import answer_question
        fake_hits = [{
            "document": "산안법 38조 본문",
            "metadata": {
                "change_id": 1, "regulation_type": "domestic_law",
                "item_id": "KR-OSHA-001", "item_title": "산업안전보건법",
                "grade": "HIGH", "legal_class": "criminal",
            },
            "distance": 0.1,
        }]
        with patch("features.compliance.regulation_indexer.search", return_value=fake_hits):
            with patch("features.compliance.regulation_qa._call_ollama", return_value="안전 조치 의무화."):
                out = answer_question("산안법 38조", user=None)
        assert out["rag_hit"] is True
        assert len(out["citations"]) == 1
        assert out["citations"][0]["item_id"] == "KR-OSHA-001"
        assert "안전 조치" in out["answer"]
        assert "산업안전보건법" in out["answer"]  # 인용 출처 포함

    def test_llm_unavailable_falls_back_to_search_results(self):
        from features.compliance.regulation_qa import answer_question
        fake_hits = [{
            "document": "본문 내용",
            "metadata": {"item_title": "테스트 규제", "item_id": "X-1", "regulation_type": "t",
                         "change_id": 1, "grade": "MEDIUM"},
            "distance": 0.2,
        }]
        with patch("features.compliance.regulation_indexer.search", return_value=fake_hits):
            with patch("features.compliance.regulation_qa._call_ollama", return_value=None):
                out = answer_question("테스트", user=None)
        assert out["rag_hit"] is True
        assert "본문 내용" in out["answer"]  # 검색 결과 그대로 노출
        assert "LLM 답변 생성 미가용" in out["answer"]

    def test_novice_mode_flag_set(self):
        from features.compliance.regulation_qa import answer_question

        class _NoviceUser:
            hire_date = (date.today() - timedelta(days=30)).isoformat()

        with patch("features.compliance.regulation_indexer.search", return_value=[]):
            out = answer_question("질문", user=_NoviceUser())
        assert out["novice_mode"] is True


# ─────────────────────────────────────────────────────────────
# Module C — 액션 디텍터 + 핸들러
# ─────────────────────────────────────────────────────────────
class TestActionDetector:
    def test_regulation_qa_keyword_풀어서(self):
        from features.onboarding.work_actions import detect_actions
        actions = detect_actions("산안법 38조 풀어서 설명해")
        assert any(a.action_type == "regulation_qa" for a in actions)

    def test_regulation_qa_keyword_위반하면(self):
        from features.onboarding.work_actions import detect_actions
        actions = detect_actions("이 규제 위반하면 어떻게 됨?")
        assert any(a.action_type == "regulation_qa" for a in actions)

    def test_regulation_qa_pattern_쉽게(self):
        from features.onboarding.work_actions import detect_actions
        actions = detect_actions("화관법 쉽게 알려줘")
        assert any(a.action_type == "regulation_qa" for a in actions)

    def test_regulation_qa_priority_higher_than_status(self):
        """regulation_qa 매칭되면 regulation_status 보다 우선."""
        from features.onboarding.work_actions import detect_actions
        actions = detect_actions("산안법 풀어서 설명해 — 법규 컴플라이언스 관련")
        # 두 개 다 매칭되지만 같은 kind('compliance') → 가장 높은 우선순위 (qa) 만 노출
        compliance_actions = [a for a in actions if a.kind == "compliance"]
        assert len(compliance_actions) == 1
        assert compliance_actions[0].action_type == "regulation_qa"


class TestHandleRegulationQA:
    def test_rag_miss_payload(self):
        from features.onboarding.action_handlers import handle_regulation_qa
        with patch("features.compliance.regulation_indexer.search", return_value=[]):
            payload = handle_regulation_qa("없는 질문", user=None)
        assert payload["rag_hit"] is False
        assert payload["title"] == "규제 Q&A"
        assert "확신" in payload["answer"] or "문의" in payload["answer"]

    def test_novice_title_label(self):
        from features.onboarding.action_handlers import handle_regulation_qa

        class _U:
            hire_date = (date.today() - timedelta(days=30)).isoformat()

        with patch("features.compliance.regulation_indexer.search", return_value=[]):
            payload = handle_regulation_qa("질문", user=_U())
        assert "신입 모드" in payload["title"]
        assert payload["novice_mode"] is True

    def test_summarize_for_llm_regulation_qa(self):
        from features.onboarding.action_handlers import summarize_payload_for_llm
        payload = {
            "answer": "산안법 38조는 안전 조치 의무화입니다. ...",
            "citations": [{"change_id": 1, "item_title": "산안법", "item_id": "X-1",
                           "regulation_type": "t", "grade": "HIGH"}],
            "novice_mode": True,
            "rag_hit": True,
        }
        text = summarize_payload_for_llm("compliance", payload)
        assert "Q&A" in text
        assert "신입 모드" in text
        assert "1건" in text  # 인용 출처 카운트
        assert "출처에 없는 내용 추가 금지" in text


# ─────────────────────────────────────────────────────────────
# Indexer collection_stats — graceful when chromadb absent
# ─────────────────────────────────────────────────────────────
class TestIndexerStats:
    def test_collection_stats_returns_dict(self):
        from features.compliance.regulation_indexer import collection_stats
        s = collection_stats()
        assert "available" in s
        assert "count" in s
        assert isinstance(s["count"], int)
