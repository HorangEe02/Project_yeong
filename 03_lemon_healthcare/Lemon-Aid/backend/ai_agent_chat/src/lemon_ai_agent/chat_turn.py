from __future__ import annotations

from dataclasses import dataclass

from lemon_ai_agent.answer_card import (
    Answerability,
    AnswerCard,
    KnowledgeRetrievalResult,
    MedicalKnowledgeRetriever,
    RetrievalStatus,
    answerability_for_analysis,
    unique_source_metadata,
)
from lemon_ai_agent.answer_plan import AnalysisPlan, AnswerPlan, AnswerPlanBuilder
from lemon_ai_agent.chat_session import ChatbotRequest
from lemon_ai_agent.knowledge import (
    AnswerPolicy,
    ChatIntentAnalysis,
    MedicalKnowledgeItem,
    analyze_chat_intent,
    policy_for_question,
)

_FOLLOW_UP_TERMS = (
    "그럼",
    "그러면",
    "그건",
    "그거",
    "이건",
    "이거",
    "저건",
    "저거",
    "왜",
    "자세히",
    "더",
    "저녁",
    "아침",
    "점심",
    "간식",
    "식단",
    "영양제도",
    "같이",
    "먹어도",
    "어떻게",
    "추천",
    "then",
    "why",
    "more",
    "that",
    "this",
)
_BRIEF_FOLLOW_UP_MAX_CHARS = 40
_UNNORMALIZED_RETRIEVAL_MARKERS = (
    "langchain",
    "langgraph",
    "vector",
    "document",
)


@dataclass(frozen=True)
class ChatTurnPlan:
    request: ChatbotRequest
    policy: AnswerPolicy
    analysis: ChatIntentAnalysis
    knowledge_items: tuple[MedicalKnowledgeItem, ...]
    answer_cards: tuple[AnswerCard, ...]
    answerability: Answerability
    retrieval_status: RetrievalStatus
    answer_plan: AnswerPlan
    analysis_plan: AnalysisPlan
    retrieval_warnings: tuple[str, ...] = ()

    @property
    def source_families(self) -> list[str]:
        return list(self.policy.source_families)

    @property
    def sources(self) -> list[dict[str, str]]:
        return unique_source_metadata(self.answer_cards)

    @property
    def requires_boundary_response(self) -> bool:
        return self.answerability in {
            "urgent_escalation",
            "medical_decision_boundary",
            "safety_boundary",
        }


class ChatTurnModule:
    """Builds the policy, intent, and reviewed knowledge plan for one chat turn."""

    def __init__(self, retriever: MedicalKnowledgeRetriever | None = None) -> None:
        self._retriever = retriever or MedicalKnowledgeRetriever()
        self._plan_builder = AnswerPlanBuilder()

    def plan(self, request: ChatbotRequest) -> ChatTurnPlan:
        planning_question = _continuity_planning_question(request)
        policy = policy_for_question(planning_question, request.context)
        analysis = analyze_chat_intent(planning_question, request.context)
        retrieval = self._retriever.retrieve(analysis)
        knowledge_items, retrieval_warnings = _normalized_retrieval_items(retrieval)
        answerability = _answerability_for_retrieval(analysis, retrieval.cards)
        answer_plan = self._plan_builder.build_answer_plan(
            request,
            analysis,
            retrieval.cards,
        )
        analysis_plan = self._plan_builder.build_analysis_plan(request, answer_plan)
        return ChatTurnPlan(
            request=request,
            policy=policy,
            analysis=analysis,
            knowledge_items=knowledge_items,
            answer_cards=retrieval.cards,
            answerability=answerability,
            retrieval_status=retrieval.retrieval_status,
            answer_plan=answer_plan,
            analysis_plan=analysis_plan,
            retrieval_warnings=retrieval_warnings,
        )


def _continuity_planning_question(request: ChatbotRequest) -> str:
    """Add recent user turns for short follow-ups before policy/retrieval planning.

    The full conversation is not persisted here and assistant text is ignored.
    This only prevents brief references like "그럼 저녁은?" from losing the
    user-supplied health/food/medication topic from the previous turn.
    """
    message = request.message.strip()
    if not request.conversation or not _is_follow_up_message(message):
        return message

    recent_user_turns = [
        turn.content.strip()
        for turn in request.conversation[-6:]
        if turn.role == "user" and turn.content.strip()
    ]
    if not recent_user_turns:
        return message
    return "\n".join((*recent_user_turns[-3:], message))


def _is_follow_up_message(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    if not normalized:
        return False
    return len(normalized) <= _BRIEF_FOLLOW_UP_MAX_CHARS or any(
        term in normalized for term in _FOLLOW_UP_TERMS
    )


def _answerability_for_retrieval(
    analysis: ChatIntentAnalysis,
    cards: tuple[AnswerCard, ...],
) -> Answerability:
    if cards:
        top_card_answerability = cards[0].answerability
        if top_card_answerability in {
            "urgent_escalation",
            "medical_decision_boundary",
            "safety_boundary",
            "answerable_with_caution",
            "answerable",
        }:
            return top_card_answerability
    return answerability_for_analysis(analysis, has_cards=bool(cards))


def _normalized_retrieval_items(
    retrieval: KnowledgeRetrievalResult,
) -> tuple[tuple[MedicalKnowledgeItem, ...], tuple[str, ...]]:
    safe_items = tuple(
        item for item in retrieval.knowledge_items if not _looks_like_raw_vector_result(item)
    )
    if len(safe_items) == len(retrieval.knowledge_items):
        return safe_items, retrieval.warnings
    warnings = (
        *retrieval.warnings,
        "retrieval_result_requires_answer_card_normalization",
    )
    return safe_items, tuple(dict.fromkeys(warnings))


def _looks_like_raw_vector_result(item: MedicalKnowledgeItem) -> bool:
    text = " ".join(
        (
            item.source,
            item.source_id,
            item.topic,
            item.concrete_guidance,
        )
    ).casefold()
    return any(marker in text for marker in _UNNORMALIZED_RETRIEVAL_MARKERS)
