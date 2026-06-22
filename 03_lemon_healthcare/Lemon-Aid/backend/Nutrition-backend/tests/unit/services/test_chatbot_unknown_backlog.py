"""Unknown knowledge backlog service tests."""

from __future__ import annotations

import pytest
from src.services.chatbot_unknown_backlog import (
    UNKNOWN_KNOWLEDGE_EVENT_STATUSES,
    build_unknown_knowledge_event,
    update_unknown_knowledge_event_status,
)


def test_build_unknown_knowledge_event_keeps_only_structured_metadata() -> None:
    """Verify unknown backlog payload excludes raw user or model text."""
    event = build_unknown_knowledge_event(
        message="리튬 약과 타우린 영양제 같이 먹어도 돼?",
        answerability="unknown_no_reviewed_source",
        retrieval_warnings=["no_reviewed_answer_card"],
    )

    assert event.answerability == "unknown_no_reviewed_source"
    assert event.primary_intent == "medication"
    assert event.category == "medication_supplement_caution"
    assert event.related_conditions == []
    assert event.missing_topics == ["supplement_drug_interaction"]
    assert event.retrieval_status == "no_match"
    assert event.retrieval_warnings == ["no_reviewed_answer_card"]
    assert event.needed_evidence_type == "supplement_drug_interaction"
    assert event.status == "open"

    raw_text = str(event.__dict__)
    assert "리튬" not in raw_text
    assert "타우린" not in raw_text
    assert "raw_prompt" not in raw_text
    assert "raw_ocr_text" not in raw_text


def test_unknown_knowledge_event_status_lifecycle_is_operator_safe() -> None:
    """Verify unknown topics can move through review without raw question text."""
    event = build_unknown_knowledge_event(
        message="세인트존스워트랑 항우울제 같이 먹어도 돼?",
        answerability="unknown_no_reviewed_source",
        retrieval_warnings=["no_reviewed_answer_card"],
    )

    assert UNKNOWN_KNOWLEDGE_EVENT_STATUSES == (
        "open",
        "reviewing",
        "promoted",
        "dismissed",
        "deprecated",
    )

    update_unknown_knowledge_event_status(event, "reviewing")
    assert event.status == "reviewing"

    update_unknown_knowledge_event_status(event, "promoted")
    assert event.status == "promoted"

    raw_text = str(event.__dict__)
    assert "세인트존스워트" not in raw_text
    assert "항우울제" not in raw_text


def test_unknown_knowledge_event_status_rejects_unsupported_value() -> None:
    """Verify arbitrary status strings cannot bypass the lifecycle contract."""
    event = build_unknown_knowledge_event(
        message="리튬 약과 타우린 영양제 같이 먹어도 돼?",
        answerability="unknown_no_reviewed_source",
        retrieval_warnings=["no_reviewed_answer_card"],
    )

    with pytest.raises(ValueError, match="Unsupported unknown knowledge event status"):
        update_unknown_knowledge_event_status(event, "raw_question_saved")  # type: ignore[arg-type]
