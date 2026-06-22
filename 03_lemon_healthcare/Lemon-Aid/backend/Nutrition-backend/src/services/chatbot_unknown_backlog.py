"""Privacy-minimized unknown knowledge backlog helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from lemon_ai_agent.knowledge import analyze_chat_intent

from src.models.db.medical_source import MedicalUnknownKnowledgeEvent

UnknownKnowledgeEventStatus = Literal[
    "open",
    "reviewing",
    "promoted",
    "dismissed",
    "deprecated",
]
UNKNOWN_KNOWLEDGE_EVENT_STATUSES: tuple[UnknownKnowledgeEventStatus, ...] = (
    "open",
    "reviewing",
    "promoted",
    "dismissed",
    "deprecated",
)


def build_unknown_knowledge_event(
    *,
    message: str,
    answerability: str,
    retrieval_warnings: Sequence[str],
) -> MedicalUnknownKnowledgeEvent:
    """Build an unknown event without storing raw user or model text."""
    analysis = analyze_chat_intent(message)
    warnings = list(dict.fromkeys(str(warning) for warning in retrieval_warnings))
    return MedicalUnknownKnowledgeEvent(
        answerability=answerability,
        primary_intent=analysis.primary_intent,
        category=analysis.category,
        related_conditions=list(analysis.related_conditions),
        missing_topics=[_missing_topic(analysis.category, analysis.primary_intent)],
        retrieval_status=_retrieval_status_from_warnings(warnings),
        retrieval_warnings=warnings,
        needed_evidence_type=_needed_evidence_type(analysis.category),
        status="open",
    )


def record_unknown_knowledge_event(
    session: object,
    event: MedicalUnknownKnowledgeEvent,
) -> None:
    """Stage an unknown event if the current session supports persistence."""
    add = getattr(session, "add", None)
    if callable(add):
        add(event)


def update_unknown_knowledge_event_status(
    event: MedicalUnknownKnowledgeEvent,
    status: UnknownKnowledgeEventStatus,
) -> MedicalUnknownKnowledgeEvent:
    """Move one privacy-safe backlog event through the source-review lifecycle."""
    if status not in UNKNOWN_KNOWLEDGE_EVENT_STATUSES:
        raise ValueError("Unsupported unknown knowledge event status.")
    event.status = status
    return event


def _retrieval_status_from_warnings(warnings: Sequence[str]) -> str:
    if "source_stale" in warnings:
        return "stale_only"
    if "not_reviewed" in warnings or "not_reviewed_only" in warnings:
        return "not_reviewed_only"
    return "no_match"


def _needed_evidence_type(category: str) -> str:
    if category in {"medication_supplement_caution", "drug_or_interaction"}:
        return "supplement_drug_interaction"
    if category == "chronic_condition_context":
        return "chronic_condition_guidance"
    if category == "nutrition_analysis":
        return "nutrition_reference"
    if category == "supplement_question":
        return "supplement_reference"
    return "general_medical_review"


def _missing_topic(category: str, primary_intent: str) -> str:
    if category in {"medication_supplement_caution", "drug_or_interaction"}:
        return "supplement_drug_interaction"
    return primary_intent
