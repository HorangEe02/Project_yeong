"""Build chatbot knowledge retrievers from reviewed DB evidence."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from lemon_ai_agent.answer_card import (
    EvidenceRecordMedicalKnowledgeRetriever,
    MedicalEvidenceAnswerCardRecord,
    MedicalKnowledgeRetriever,
)
from lemon_ai_agent.knowledge import SourceFamily
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.models.db.medical_source import MedicalEvidenceItem, MedicalSource, MedicalSourceVersion

_SOURCE_FAMILY_ALIASES: dict[str, SourceFamily] = {
    "general_medical": "general_medical",
    "public_health": "general_medical",
    "public_health_guidance": "general_medical",
    "chronic_condition": "chronic_condition",
    "chronic_condition_guidance": "chronic_condition",
    "nutrition_reference": "nutrition_reference",
    "reference_intake": "nutrition_reference",
    "supplement_reference": "supplement_reference",
    "supplement_guidance": "supplement_reference",
    "drug_safety_boundary": "drug_safety_boundary",
    "drug_safety": "drug_safety_boundary",
    "emergency_escalation": "emergency_escalation",
    "mental_health_escalation": "mental_health_escalation",
    "lifestyle_guideline": "lifestyle_guideline",
    "food_safety_allergy": "food_safety_allergy",
}


class ChatbotEvidenceRepository:
    """Load reviewed source/evidence rows needed to build AnswerCards."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_answer_card_records(self) -> tuple[MedicalEvidenceAnswerCardRecord, ...]:
        """Return evidence records with their source governance metadata."""
        statement = (
            select(
                MedicalEvidenceItem.id.label("evidence_id"),
                MedicalSource.id.label("source_id"),
                MedicalSource.title.label("source_title"),
                MedicalSource.canonical_url.label("source_url"),
                MedicalSource.source_family.label("source_family"),
                MedicalSourceVersion.id.label("source_version_id"),
                MedicalSourceVersion.version_label.label("version_label"),
                MedicalSourceVersion.review_status.label("source_review_status"),
                MedicalSourceVersion.reviewed_at.label("reviewed_at"),
                MedicalSourceVersion.expires_at.label("expires_at"),
                MedicalEvidenceItem.topic.label("topic"),
                MedicalEvidenceItem.audience.label("audience"),
                MedicalEvidenceItem.claim_summary.label("claim_summary"),
                MedicalEvidenceItem.allowed_user_wording.label("allowed_user_wording"),
                MedicalEvidenceItem.blocked_wording.label("blocked_wording"),
                MedicalEvidenceItem.applicability_note.label("applicability_note"),
                MedicalEvidenceItem.caution_level.label("caution_level"),
                MedicalEvidenceItem.review_status.label("evidence_review_status"),
                MedicalEvidenceItem.specific_examples.label("specific_examples"),
                MedicalEvidenceItem.checklist.label("checklist"),
                MedicalEvidenceItem.caution_conditions.label("caution_conditions"),
                MedicalEvidenceItem.must_not_say.label("must_not_say"),
            )
            .join(
                MedicalSourceVersion,
                MedicalSourceVersion.id == MedicalEvidenceItem.source_version_id,
            )
            .join(MedicalSource, MedicalSource.id == MedicalSourceVersion.source_id)
            .where(
                MedicalEvidenceItem.review_status == "reviewed",
                MedicalSourceVersion.review_status == "reviewed",
                MedicalSourceVersion.expires_at >= date.today(),
            )
            .order_by(MedicalEvidenceItem.topic.asc(), MedicalEvidenceItem.created_at.desc())
        )
        result = await self._session.execute(statement)
        return tuple(_row_to_record(row) for row in result.all() if _is_reviewed_current_row(row))


async def build_chatbot_medical_knowledge_retriever(
    session: AsyncSession,
    settings: Settings,
) -> MedicalKnowledgeRetriever | EvidenceRecordMedicalKnowledgeRetriever:
    """Build the chat retriever for the current runtime environment.

    Production-like environments answer only from DB evidence. Local/dev can use
    the registry fallback while DB evidence coverage is still being bootstrapped.
    """
    fallback = MedicalKnowledgeRetriever() if settings.environment != "production" else None
    try:
        records = await ChatbotEvidenceRepository(session).list_answer_card_records()
    except AttributeError:
        if fallback is not None:
            return fallback
        raise

    if records:
        return EvidenceRecordMedicalKnowledgeRetriever(records, fallback=fallback)
    if fallback is not None:
        return fallback
    return EvidenceRecordMedicalKnowledgeRetriever(())


def _row_to_record(row: Any) -> MedicalEvidenceAnswerCardRecord:
    return MedicalEvidenceAnswerCardRecord(
        evidence_id=str(row.evidence_id),
        source_id=str(row.source_id),
        source_title=str(row.source_title or ""),
        source_url=str(row.source_url or ""),
        source_family=_source_family(row.source_family),
        source_version_id=str(row.source_version_id),
        version_label=str(row.version_label),
        source_review_status=str(row.source_review_status),
        reviewed_at=row.reviewed_at.isoformat(),
        expires_at=row.expires_at.isoformat(),
        topic=str(row.topic),
        audience=str(row.audience),
        claim_summary=str(row.claim_summary),
        allowed_user_wording=str(row.allowed_user_wording),
        blocked_wording=str(row.blocked_wording),
        applicability_note=str(row.applicability_note) if row.applicability_note else None,
        caution_level=str(row.caution_level),
        evidence_review_status=str(row.evidence_review_status),
        specific_examples=_string_tuple(row.specific_examples),
        checklist=_string_tuple(row.checklist),
        caution_conditions=_string_tuple(row.caution_conditions),
        must_not_say=_string_tuple(row.must_not_say),
    )


def _is_reviewed_current_row(row: Any) -> bool:
    return (
        str(row.source_review_status) == "reviewed"
        and str(row.evidence_review_status) == "reviewed"
        and row.expires_at >= date.today()
    )


def _source_family(value: object) -> SourceFamily:
    normalized = str(value).strip().casefold()
    return _SOURCE_FAMILY_ALIASES.get(normalized, "general_medical")


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())
