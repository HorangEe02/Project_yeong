"""Chat Turn Module behavior tests."""

from __future__ import annotations

from pathlib import Path

from lemon_ai_agent.answer_card import KnowledgeRetrievalResult
from lemon_ai_agent.chat_session import ChatbotRequest, ChatTurn
from lemon_ai_agent.chat_turn import ChatTurnModule
from lemon_ai_agent.knowledge import ChatIntentAnalysis, MedicalKnowledgeItem

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class _VectorDocumentRetriever:
    def __init__(self) -> None:
        self.analysis: ChatIntentAnalysis | None = None

    def retrieve(self, analysis: ChatIntentAnalysis) -> KnowledgeRetrievalResult:
        self.analysis = analysis
        return KnowledgeRetrievalResult(
            cards=(),
            knowledge_items=(
                MedicalKnowledgeItem(
                    source="LangChain Document",
                    source_id="vector-doc-1",
                    topic="vector_search_result",
                    intent=analysis.primary_intent,
                    condition=None,
                    concrete_guidance="raw vector section text must not enter the plan",
                    caution_level="general",
                    evidence_type="official_guideline",
                    reviewed_status="reviewed",
                    source_url="https://example.invalid/vector-doc",
                ),
            ),
            missing_topics=(),
            warnings=("langchain_vector_result",),
            retrieval_status="found",
        )


def test_chat_turn_plans_boundary_questions_without_llm_knowledge_leakage() -> None:
    turn = ChatTurnModule().plan(
        ChatbotRequest(
            request_id="chat-turn-drug",
            user_id="local-dev-user",
            message="와파린 복용 중 비타민 K를 같이 먹어도 돼?",
        )
    )

    assert turn.policy.category == "drug_or_interaction"
    assert turn.requires_boundary_response is True
    assert turn.source_families == [
        "supplement_reference",
        "drug_safety_boundary",
        "chronic_condition",
    ]


def test_chat_turn_selects_reviewed_knowledge_for_diabetes_lifestyle() -> None:
    turn = ChatTurnModule().plan(
        ChatbotRequest(
            request_id="chat-turn-diabetes",
            user_id="local-dev-user",
            message="당뇨를 개선하려면 식단, 운동, 수면, 체중관리를 어떻게 해야 해?",
            context={"profile": {"chronic_conditions": ["diabetes"]}},
        )
    )

    sources = {item.source for item in turn.knowledge_items}
    assert turn.policy.category == "chronic_condition_context"
    assert turn.analysis.related_conditions == ("diabetes",)
    assert "CDC Diabetes Meal Planning" in sources
    assert "NIDDK Healthy Living with Diabetes" in sources
    assert "Semantic Scholar Graph API" not in sources


def test_chat_turn_marks_unknown_when_no_reviewed_answer_card_exists() -> None:
    """Unsupported health questions fail closed instead of using broad model knowledge."""
    turn = ChatTurnModule().plan(
        ChatbotRequest(
            request_id="chat-turn-unknown",
            user_id="local-dev-user",
            message="리튬 약과 타우린 영양제 같이 먹어도 돼?",
        )
    )

    assert turn.answerability == "unknown_no_reviewed_source"
    assert turn.answer_cards == ()
    assert turn.retrieval_status == "no_match"
    assert turn.requires_boundary_response is False


def test_chat_turn_marks_unreviewed_supplement_effect_question_unknown() -> None:
    """Unreviewed supplement effect questions must not borrow broad lifestyle cards."""
    turn = ChatTurnModule().plan(
        ChatbotRequest(
            request_id="chat-turn-creatine-sleep",
            user_id="local-dev-user",
            message="크레아틴을 먹으면 수면 질이 좋아져?",
        )
    )

    assert turn.policy.category == "supplement_question"
    assert turn.analysis.primary_intent == "supplement"
    assert turn.answerability == "unknown_no_reviewed_source"
    assert turn.answer_cards == ()
    assert turn.retrieval_status == "no_match"


def test_chat_turn_uses_recent_user_turn_for_brief_follow_up() -> None:
    """Short follow-up questions should keep the prior user topic for planning."""
    turn = ChatTurnModule().plan(
        ChatbotRequest(
            request_id="chat-turn-follow-up",
            user_id="local-dev-user",
            message="그럼 저녁은?",
            conversation=[
                ChatTurn(
                    role="user",
                    content="고혈압이 있는데 점심에 라면을 먹었어. 나트륨이 걱정돼.",
                    created_at="2026-06-01T12:30:00+09:00",
                ),
                ChatTurn(
                    role="assistant",
                    content="다음 끼니에서 국물과 짠 반찬을 줄이는 쪽으로 보세요.",
                    created_at="2026-06-01T12:31:00+09:00",
                ),
            ],
        )
    )

    assert turn.policy.category in {"nutrition_analysis", "chronic_condition_context"}
    assert turn.analysis.primary_intent == "meal"
    assert turn.analysis.related_conditions == ("hypertension",)
    assert any(card.topic == "sodium_dinner_adjustment" for card in turn.answer_cards)


def test_chat_turn_keeps_policy_intent_retrieval_and_answerability_bound_together() -> None:
    retriever = _VectorDocumentRetriever()

    turn = ChatTurnModule(retriever=retriever).plan(
        ChatbotRequest(
            request_id="chat-turn-plan-node-contract",
            user_id="local-dev-user",
            message="당뇨 식단은 어떻게 조절해야 해?",
            context={"profile": {"chronic_conditions": ["diabetes"]}},
        )
    )

    assert retriever.analysis is turn.analysis
    assert turn.policy.category == "chronic_condition_context"
    assert turn.analysis.related_conditions == ("diabetes",)
    assert turn.answerability == "unknown_no_reviewed_source"


def test_chat_turn_rejects_direct_langchain_or_vector_documents() -> None:
    turn = ChatTurnModule(retriever=_VectorDocumentRetriever()).plan(
        ChatbotRequest(
            request_id="chat-turn-vector-doc-guard",
            user_id="local-dev-user",
            message="당뇨 식단은 어떻게 조절해야 해?",
            context={"profile": {"chronic_conditions": ["diabetes"]}},
        )
    )

    assert turn.knowledge_items == ()
    assert turn.answer_cards == ()
    assert "retrieval_result_requires_answer_card_normalization" in turn.retrieval_warnings


def test_ai_agent_runtime_does_not_import_langchain_or_langgraph() -> None:
    source_root = BACKEND_ROOT / "ai_agent_chat" / "src" / "lemon_ai_agent"
    offenders: list[str] = []

    for path in source_root.rglob("*.py"):
        if path.name == "langsmith_exporter.py":
            continue
        text = path.read_text(encoding="utf-8").casefold()
        if "import langchain" in text or "from langchain" in text:
            offenders.append(str(path.relative_to(BACKEND_ROOT)))
        if "import langgraph" in text or "from langgraph" in text:
            offenders.append(str(path.relative_to(BACKEND_ROOT)))

    assert offenders == []
