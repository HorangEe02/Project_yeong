"""Unknown chatbot backlog report tests."""

from __future__ import annotations

from src.models.db.medical_source import MedicalUnknownKnowledgeEvent
from src.services.chatbot_unknown_backlog_report import (
    chatbot_runtime_report_payload,
    summarize_unknown_knowledge_events,
    unknown_backlog_report_payload,
)


def test_unknown_backlog_report_aggregates_only_structured_metadata() -> None:
    """Verify backlog reporting helps triage gaps without raw question text."""
    events = [
        _event(
            category="medication_supplement_caution",
            primary_intent="medication",
            missing_topics=["supplement_drug_interaction"],
            needed_evidence_type="supplement_drug_interaction",
            retrieval_warnings=["no_reviewed_answer_card"],
        ),
        _event(
            category="medication_supplement_caution",
            primary_intent="medication",
            missing_topics=["supplement_drug_interaction"],
            needed_evidence_type="supplement_drug_interaction",
            retrieval_warnings=["no_reviewed_answer_card", "source_stale"],
            retrieval_status="stale_only",
        ),
        _event(
            category="nutrition_analysis",
            primary_intent="meal",
            missing_topics=["meal"],
            needed_evidence_type="nutrition_reference",
            related_conditions=["hypertension"],
        ),
    ]

    groups = summarize_unknown_knowledge_events(events)
    payload = unknown_backlog_report_payload(groups)

    assert payload["total_groups"] == 3
    assert payload["total_events"] == 3
    assert payload["groups"][0] == {
        "status": "open",
        "category": "medication_supplement_caution",
        "primary_intent": "medication",
        "missing_topic": "supplement_drug_interaction",
        "needed_evidence_type": "supplement_drug_interaction",
        "retrieval_status": "stale_only",
        "count": 1,
        "related_conditions": [],
        "retrieval_warnings": ["no_reviewed_answer_card", "source_stale"],
        "triage_priority": "P0",
        "next_action": "refresh_or_add_reviewed_source",
        "promotion_checklist": [
            "identify_official_or_reviewed_source",
            "record_source_version_and_expiry",
            "draft_allowed_and_blocked_wording",
            "add_answer_card_or_boundary_test",
        ],
    }

    raw_text = str(payload)
    assert "리튬" not in raw_text
    assert "셀레늄" not in raw_text
    assert "raw_question" not in raw_text
    assert "raw_prompt" not in raw_text
    assert "conversation" not in raw_text


def test_unknown_backlog_report_sorts_repeated_gaps_first() -> None:
    """Verify repeated missing topics float to the top of the operator report."""
    events = [
        _event(missing_topics=["meal"], needed_evidence_type="nutrition_reference"),
        _event(
            missing_topics=["supplement_drug_interaction"],
            needed_evidence_type="supplement_drug_interaction",
        ),
        _event(
            missing_topics=["supplement_drug_interaction"],
            needed_evidence_type="supplement_drug_interaction",
        ),
    ]

    payload = unknown_backlog_report_payload(summarize_unknown_knowledge_events(events))

    assert payload["groups"][0]["missing_topic"] == "supplement_drug_interaction"
    assert payload["groups"][0]["count"] == 2


def test_unknown_backlog_report_adds_triage_priority_and_next_action() -> None:
    """Verify operators can promote unknown gaps without reading raw questions."""
    events = [
        _event(
            missing_topics=["supplement_drug_interaction"],
            needed_evidence_type="supplement_drug_interaction",
            retrieval_warnings=["no_reviewed_answer_card"],
        ),
        _event(
            missing_topics=["supplement_drug_interaction"],
            needed_evidence_type="supplement_drug_interaction",
            retrieval_warnings=["source_stale"],
            retrieval_status="stale_only",
        ),
        _event(
            missing_topics=["meal"],
            needed_evidence_type="nutrition_reference",
        ),
    ]

    payload = unknown_backlog_report_payload(summarize_unknown_knowledge_events(events))

    priority_group = payload["groups"][0]
    assert priority_group["missing_topic"] == "supplement_drug_interaction"
    assert priority_group["triage_priority"] == "P0"
    assert priority_group["next_action"] == "refresh_or_add_reviewed_source"
    assert priority_group["promotion_checklist"] == [
        "identify_official_or_reviewed_source",
        "record_source_version_and_expiry",
        "draft_allowed_and_blocked_wording",
        "add_answer_card_or_boundary_test",
    ]


def test_unknown_backlog_report_includes_all_groups_by_default() -> None:
    """Verify operator reports are not top-N limited unless a limit is requested."""
    events = [
        _event(
            missing_topics=[f"missing_topic_{index:02d}"],
            needed_evidence_type="nutrition_reference",
        )
        for index in range(35)
    ]

    payload = unknown_backlog_report_payload(summarize_unknown_knowledge_events(events))

    assert payload["total_groups"] == 35
    assert len(payload["groups"]) == 35
    assert payload["total_events"] == 35


def test_unknown_backlog_report_can_still_be_limited_explicitly() -> None:
    """Verify optional group limits remain available for compact dashboards."""
    events = [
        _event(
            missing_topics=[f"missing_topic_{index:02d}"],
            needed_evidence_type="nutrition_reference",
        )
        for index in range(35)
    ]

    payload = unknown_backlog_report_payload(
        summarize_unknown_knowledge_events(events, group_limit=10)
    )

    assert payload["total_groups"] == 10
    assert len(payload["groups"]) == 10


def test_chatbot_runtime_report_payload_is_raw_free() -> None:
    """Verify runtime reporting aggregates safe metadata only."""
    payload = chatbot_runtime_report_payload(
        [
            {
                "answerability": "medical_decision_boundary",
                "provider": "deterministic",
                "safety_warnings": [
                    "Drug interaction boundary applied",
                    "boundary_code:p0_grapefruit_statin",
                ],
                "sources": [
                    {
                        "source_id": "mfds-drug-safety",
                        "review_status": "reviewed",
                        "expires_at": "2026-11-29",
                    }
                ],
                "message": "raw user-facing answer should not be copied",
                "raw_prompt": "hidden",
            },
            {
                "answerability": "unknown_no_reviewed_source",
                "provider": "deterministic",
                "safety_warnings": ["no_reviewed_answer_card"],
                "sources": [],
                "conversation": [{"role": "user", "content": "raw"}],
            },
        ]
    )

    assert payload == {
        "total_events": 2,
        "answerability": {
            "medical_decision_boundary": 1,
            "unknown_no_reviewed_source": 1,
        },
        "providers": {"deterministic": 2},
        "fallback_reasons": {
            "Drug interaction boundary applied": 1,
            "no_reviewed_answer_card": 1,
        },
        "source_expiry": {
            "no_sources": 1,
            "reviewed_with_expiry": 1,
        },
        "boundary_codes": {"p0_grapefruit_statin": 1},
    }
    assert "raw_prompt" not in str(payload)
    assert "conversation" not in str(payload)
    assert "raw user-facing answer" not in str(payload)


def _event(
    *,
    category: str = "medication_supplement_caution",
    primary_intent: str = "medication",
    missing_topics: list[str],
    needed_evidence_type: str,
    related_conditions: list[str] | None = None,
    retrieval_warnings: list[str] | None = None,
    retrieval_status: str = "no_match",
) -> MedicalUnknownKnowledgeEvent:
    return MedicalUnknownKnowledgeEvent(
        answerability="unknown_no_reviewed_source",
        primary_intent=primary_intent,
        category=category,
        related_conditions=related_conditions or [],
        missing_topics=missing_topics,
        retrieval_status=retrieval_status,
        retrieval_warnings=retrieval_warnings or ["no_reviewed_answer_card"],
        needed_evidence_type=needed_evidence_type,
        status="open",
    )
