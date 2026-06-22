"""Unknown chatbot knowledge backlog reporting helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.medical_source import MedicalUnknownKnowledgeEvent

REPEATED_UNKNOWN_GAP_THRESHOLD = 3


@dataclass(frozen=True)
class UnknownKnowledgeBacklogGroup:
    """Aggregated, privacy-safe unknown knowledge backlog bucket."""

    status: str
    category: str
    primary_intent: str
    missing_topic: str
    needed_evidence_type: str
    retrieval_status: str
    count: int
    related_conditions: tuple[str, ...]
    retrieval_warnings: tuple[str, ...]


async def list_unknown_knowledge_backlog_groups(
    session: AsyncSession,
    *,
    status: str = "open",
    row_limit: int | None = None,
    group_limit: int | None = None,
) -> tuple[UnknownKnowledgeBacklogGroup, ...]:
    """Load recent unknown events and aggregate them without exposing raw text."""
    statement = (
        select(MedicalUnknownKnowledgeEvent)
        .where(MedicalUnknownKnowledgeEvent.status == status)
        .order_by(desc(MedicalUnknownKnowledgeEvent.created_at))
    )
    if row_limit is not None:
        statement = statement.limit(row_limit)
    result = await session.execute(statement)
    events = result.scalars().all()
    return summarize_unknown_knowledge_events(events, group_limit=group_limit)


def summarize_unknown_knowledge_events(
    events: Iterable[MedicalUnknownKnowledgeEvent],
    *,
    group_limit: int | None = None,
) -> tuple[UnknownKnowledgeBacklogGroup, ...]:
    """Aggregate unknown events by the evidence gap operators need to fill."""
    buckets: dict[tuple[str, str, str, str, str, str], int] = Counter()
    conditions: dict[tuple[str, str, str, str, str, str], set[str]] = defaultdict(set)
    warnings: dict[tuple[str, str, str, str, str, str], set[str]] = defaultdict(set)

    for event in events:
        topics = _string_list(getattr(event, "missing_topics", [])) or ("unknown_topic",)
        for topic in topics:
            key = (
                str(event.status),
                str(event.category),
                str(event.primary_intent),
                topic,
                str(event.needed_evidence_type),
                str(event.retrieval_status),
            )
            buckets[key] += 1
            conditions[key].update(_string_list(getattr(event, "related_conditions", [])))
            warnings[key].update(_string_list(getattr(event, "retrieval_warnings", [])))

    groups = [
        UnknownKnowledgeBacklogGroup(
            status=status,
            category=category,
            primary_intent=primary_intent,
            missing_topic=missing_topic,
            needed_evidence_type=needed_evidence_type,
            retrieval_status=retrieval_status,
            count=count,
            related_conditions=tuple(sorted(conditions[key])),
            retrieval_warnings=tuple(sorted(warnings[key])),
        )
        for key, count in buckets.items()
        for status, category, primary_intent, missing_topic, needed_evidence_type, retrieval_status in [
            key
        ]
    ]
    sorted_groups = sorted(
        groups,
        key=lambda group: (
            _triage_priority_rank(group),
            _next_action_rank(group),
            -group.count,
            group.needed_evidence_type,
            group.missing_topic,
            group.category,
        ),
    )
    if group_limit is not None:
        sorted_groups = sorted_groups[:group_limit]
    return tuple(sorted_groups)


def unknown_backlog_report_payload(
    groups: Sequence[UnknownKnowledgeBacklogGroup],
) -> dict[str, Any]:
    """Return a JSON-serializable report that contains no raw question text."""
    return {
        "total_groups": len(groups),
        "total_events": sum(group.count for group in groups),
        "groups": [
            {
                "status": group.status,
                "category": group.category,
                "primary_intent": group.primary_intent,
                "missing_topic": group.missing_topic,
                "needed_evidence_type": group.needed_evidence_type,
                "retrieval_status": group.retrieval_status,
                "count": group.count,
                "related_conditions": list(group.related_conditions),
                "retrieval_warnings": list(group.retrieval_warnings),
                "triage_priority": _triage_priority(group),
                "next_action": _next_action(group),
                "promotion_checklist": _promotion_checklist(),
            }
            for group in groups
        ],
    }


def chatbot_runtime_report_payload(
    events: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize chatbot runtime outcomes without raw prompt or response text."""
    answerability: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    fallback_reasons: Counter[str] = Counter()
    source_expiry: Counter[str] = Counter()
    boundary_codes: Counter[str] = Counter()

    total_events = 0
    for event in events:
        total_events += 1
        answerability[str(event.get("answerability") or "unknown")] += 1
        providers[str(event.get("provider") or "unknown")] += 1
        source_expiry[_source_expiry_status(event.get("sources"))] += 1
        for warning in _string_list(event.get("safety_warnings")):
            if warning.startswith("boundary_code:"):
                boundary_codes[warning.removeprefix("boundary_code:")] += 1
                continue
            fallback_reasons[_fallback_reason(warning)] += 1

    return {
        "total_events": total_events,
        "answerability": dict(sorted(answerability.items())),
        "providers": dict(sorted(providers.items())),
        "fallback_reasons": dict(sorted(fallback_reasons.items())),
        "source_expiry": dict(sorted(source_expiry.items())),
        "boundary_codes": dict(sorted(boundary_codes.items())),
    }


def _fallback_reason(warning: str) -> str:
    if warning in {
        "no_reviewed_answer_card",
        "source_stale",
        "needs_structured_lookup",
        "needs_specific_medication_name",
        "Chatbot response contract not followed",
        "label_only_supplement_requires_reviewed_evidence",
        "Drug interaction boundary applied",
    }:
        return warning
    if "schema" in warning.casefold():
        return "schema_parse_failed"
    if "forbidden" in warning.casefold():
        return "unsupported_fact_fallback"
    return "other"


def _triage_priority(group: UnknownKnowledgeBacklogGroup) -> str:
    if (
        group.needed_evidence_type == "supplement_drug_interaction"
        or "interaction" in group.missing_topic
        or group.retrieval_status == "stale_only"
    ):
        return "P0"
    if group.count >= REPEATED_UNKNOWN_GAP_THRESHOLD or group.category in {
        "medication_supplement_caution",
        "drug_or_interaction",
    }:
        return "P1"
    return "P2"


def _triage_priority_rank(group: UnknownKnowledgeBacklogGroup) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}[_triage_priority(group)]


def _next_action(group: UnknownKnowledgeBacklogGroup) -> str:
    if group.retrieval_status == "stale_only" or "source_stale" in group.retrieval_warnings:
        return "refresh_or_add_reviewed_source"
    if _triage_priority(group) == "P0":
        return "add_reviewed_boundary_or_caution_card"
    if group.needed_evidence_type == "nutrition_reference":
        return "add_reviewed_nutrition_answer_card"
    return "triage_reviewed_source_candidate"


def _next_action_rank(group: UnknownKnowledgeBacklogGroup) -> int:
    action = _next_action(group)
    return {
        "refresh_or_add_reviewed_source": 0,
        "add_reviewed_boundary_or_caution_card": 1,
        "add_reviewed_nutrition_answer_card": 2,
        "triage_reviewed_source_candidate": 3,
    }[action]


def _promotion_checklist() -> list[str]:
    return [
        "identify_official_or_reviewed_source",
        "record_source_version_and_expiry",
        "draft_allowed_and_blocked_wording",
        "add_answer_card_or_boundary_test",
    ]


def _source_expiry_status(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "no_sources"
    statuses: set[str] = set()
    for source in value:
        if not isinstance(source, Mapping):
            statuses.add("unknown")
            continue
        review_status = str(source.get("review_status") or "")
        expires_at = str(source.get("expires_at") or "")
        if review_status != "reviewed":
            statuses.add("not_reviewed")
        elif not expires_at:
            statuses.add("missing_expiry")
        else:
            statuses.add("reviewed_with_expiry")
    if "not_reviewed" in statuses:
        return "not_reviewed"
    if "missing_expiry" in statuses:
        return "missing_expiry"
    if "unknown" in statuses:
        return "unknown"
    return "reviewed_with_expiry"


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value if str(item))
