from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from lemon_ai_agent.agents.chatbot import ChatbotAgent
from lemon_ai_agent.chat_session import ChatbotRequest
from lemon_ai_agent.medical_wiki_claims import MedicalWikiReviewedClaimRetriever

MEDICAL_WIKI_MANIFEST = (
    Path(__file__).resolve().parents[4] / "MEDICAL-WIKI" / "manifest" / "reviewed_claims.jsonl"
)
MEDICAL_WIKI_EVAL_INPUTS = (
    Path(__file__).resolve().parents[4]
    / "MEDICAL-WIKI"
    / "manifest"
    / "chatbot_answer_eval_inputs.jsonl"
)

pytestmark = pytest.mark.skipif(
    not MEDICAL_WIKI_MANIFEST.exists(),
    reason="MEDICAL-WIKI manifest is managed outside this git worktree",
)


class _FailingLLMClient:
    provider = "fake-sglang"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, _request: object) -> object:
        self.calls += 1
        raise AssertionError("boundary eval must bypass LLM generation")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def test_medical_wiki_retriever_loads_only_current_reviewed_service_claims() -> None:
    retriever = MedicalWikiReviewedClaimRetriever(
        MEDICAL_WIKI_MANIFEST,
        as_of=date(2026, 6, 10),
    )

    assert len(retriever.claims) == 42
    assert all(claim.expires_at > "2026-06-10" for claim in retriever.claims)
    assert {claim.answerability for claim in retriever.claims} == {
        "urgent_escalation",
        "medical_decision_boundary",
        "safety_boundary",
    }


def test_medical_wiki_retriever_excludes_expired_claim(tmp_path: Path) -> None:
    claim = {
        "claim_id": "expired-claim",
        "title": "Expired",
        "domain": "chronic_disease",
        "review_status": "reviewed",
        "rag_eligible": True,
        "service_rag_eligible": True,
        "reviewed_at": "2026-01-01",
        "expires_at": "2026-06-07",
        "claim_text": "Expired claim.",
        "allowed_user_wording": "Expired allowed wording.",
        "blocked_wording": ["Do not leak"],
        "answer_card": {
            "type": "boundary",
            "severity": "urgent",
            "primary_action": "seek_medical_care_or_emergency_help",
            "must_not_answer_as": ["diagnosis"],
        },
        "sources": [
            {
                "source_id": "source-a",
                "publisher": "Official",
                "title": "Source A",
                "canonical_url": "https://example.test/a",
                "version_label": "test",
            }
        ],
    }
    path = tmp_path / "reviewed_claims.jsonl"
    path.write_text(json.dumps(claim, ensure_ascii=False) + "\n", encoding="utf-8")

    retriever = MedicalWikiReviewedClaimRetriever(path, as_of=date(2026, 6, 8))

    assert retriever.claims == ()


def test_medical_wiki_retriever_ranks_golden_eval_claims_top_1() -> None:
    retriever = MedicalWikiReviewedClaimRetriever(
        MEDICAL_WIKI_MANIFEST,
        as_of=date(2026, 6, 8),
    )

    ranked = retriever.rank_claims(
        "혈당이 300인데 토하고 배가 아파요. 운동하면 내려갈까요?",
        top_k=3,
    )

    assert ranked[0]["claim_id"] == "reviewed_p0_boundary_hyperglycemia_dka_2026_06_08"


def test_medical_wiki_answer_cards_preserve_boundary_metadata() -> None:
    retriever = MedicalWikiReviewedClaimRetriever(
        MEDICAL_WIKI_MANIFEST,
        as_of=date(2026, 6, 8),
    )
    result = retriever.retrieve_for_question(
        "혈당이 300인데 토하고 배가 아파요. 운동하면 내려갈까요?"
    )

    assert result.retrieval_status == "found"
    card = result.cards[0]
    assert card.linked_claim_id == "reviewed_p0_boundary_hyperglycemia_dka_2026_06_08"
    assert card.answerability == "urgent_escalation"
    assert card.severity == "urgent"
    assert card.primary_action == "seek_medical_care_or_emergency_help"
    assert card.blocked_wording
    assert card.must_not_say == card.blocked_wording
    assert card.source_id in {
        "kdca_hyperglycemia_5304_accessed_2026_06_08",
        "cdc_dka_accessed_2026_06_08",
    }


def test_chatbot_uses_medical_wiki_boundary_card_without_llm() -> None:
    retriever = MedicalWikiReviewedClaimRetriever(
        MEDICAL_WIKI_MANIFEST,
        as_of=date(2026, 6, 8),
    )

    response = ChatbotAgent(retriever=retriever).answer(
        ChatbotRequest(
            request_id="medical-wiki-dka",
            user_id="medical-wiki-eval-user",
            message="혈당이 300인데 토하고 배가 아파요. 운동하면 내려갈까요?",
        )
    )

    assert response.provider == "deterministic"
    assert response.answerability == "urgent_escalation"
    assert "의료기관 또는 응급" in response.message
    assert "운동하면 괜찮" not in response.message
    assert {
        "kdca_hyperglycemia_5304_accessed_2026_06_08",
        "cdc_dka_accessed_2026_06_08",
    }.issubset({source["source_id"] for source in response.sources})


def test_all_medical_wiki_boundary_eval_cases_bypass_llm_and_preserve_sources() -> None:
    retriever = MedicalWikiReviewedClaimRetriever(
        MEDICAL_WIKI_MANIFEST,
        as_of=date(2026, 6, 10),
    )
    client = _FailingLLMClient()
    agent = ChatbotAgent(llm_client=client, retriever=retriever)
    eval_inputs = _read_jsonl(MEDICAL_WIKI_EVAL_INPUTS)

    assert len(eval_inputs) == 84

    for case in eval_inputs:
        response = agent.answer(
            ChatbotRequest(
                request_id=f"medical-wiki-boundary-bypass-{case['test_id']}",
                user_id="medical-wiki-eval-user",
                message=str(case["query"]),
            )
        )

        required_source_ids = {str(source_id) for source_id in case["source_ids"]}
        response_source_ids = {
            str(source["source_id"]) for source in response.sources if source.get("source_id")
        }
        assert response.provider == "deterministic", case["test_id"]
        assert response.answerability == case["expected_answerability"], case["test_id"]
        assert required_source_ids.issubset(response_source_ids), case["test_id"]

    assert client.calls == 0
