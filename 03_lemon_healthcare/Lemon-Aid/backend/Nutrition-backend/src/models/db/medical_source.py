"""Medical source governance ORM models."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class MedicalSource(TimestampMixin, Base):
    """Persist a reviewed medical source registry entry."""

    __tablename__ = "medical_sources"
    __table_args__ = (
        CheckConstraint(
            (
                "source_type IN ("
                "'guideline', 'public_health', 'regulator', "
                "'reference_intake', 'paper', 'internal_review'"
                ")"
            ),
            name="source_type",
        ),
        CheckConstraint(
            "default_review_status IN ('draft', 'reviewed', 'deprecated', 'paper_candidate')",
            name="default_review_status",
        ),
        Index("ix_medical_sources_family_status", "source_family", "default_review_status"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_family: Mapped[str] = mapped_column(String(80), nullable=False)
    publisher: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    default_review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    owner: Mapped[str] = mapped_column(String(120), nullable=False)


class MedicalSourceVersion(TimestampMixin, Base):
    """Persist reviewed versions and stale-source dates for one source."""

    __tablename__ = "medical_source_versions"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'deprecated', 'paper_candidate')",
            name="review_status",
        ),
        Index(
            "ix_medical_source_versions_source_status_expires",
            "source_id",
            "review_status",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("medical_sources.id"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String(80), nullable=False)
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    reviewed_at: Mapped[date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[date] = mapped_column(Date, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class MedicalEvidenceItem(TimestampMixin, Base):
    """Persist reviewed claim wording boundaries for user-facing guidance."""

    __tablename__ = "medical_evidence_items"
    __table_args__ = (
        CheckConstraint(
            "caution_level IN ('info', 'caution', 'professional_review', 'blocked')",
            name="caution_level",
        ),
        CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'deprecated', 'paper_candidate')",
            name="review_status",
        ),
        Index(
            "ix_medical_evidence_items_topic_audience_status",
            "topic",
            "audience",
            "review_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("medical_source_versions.id"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    audience: Mapped[str] = mapped_column(String(80), nullable=False)
    claim_summary: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_user_wording: Mapped[str] = mapped_column(Text, nullable=False)
    blocked_wording: Mapped[str] = mapped_column(Text, nullable=False)
    applicability_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    specific_examples: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    checklist: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    caution_conditions: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    must_not_say: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    caution_level: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str | None] = mapped_column(String(80), nullable=True)


class MedicalPolicyBoundary(TimestampMixin, Base):
    """Persist reviewed safety boundaries shared by runtime classifiers."""

    __tablename__ = "medical_policy_boundaries"
    __table_args__ = (
        CheckConstraint(
            "response_status IN ('blocked', 'professional_review', 'caution', 'needs_more_info')",
            name="response_status",
        ),
        CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'deprecated')",
            name="review_status",
        ),
        Index("ix_medical_policy_boundaries_code_status", "boundary_code", "review_status"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    boundary_code: Mapped[str] = mapped_column(String(120), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    trigger_intent: Mapped[str] = mapped_column(String(120), nullable=False)
    response_status: Mapped[str] = mapped_column(String(32), nullable=False)
    required_warning_code: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_response_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    blocked_response_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    source_version_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("medical_source_versions.id"),
        nullable=True,
    )
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)


class MedicalRagChunk(TimestampMixin, Base):
    """Persist reviewed RAG snippet metadata without raw scrape or OCR payloads."""

    __tablename__ = "medical_rag_chunks"
    __table_args__ = (
        CheckConstraint(
            "embedding_status IN ('not_indexed', 'indexed', 'stale', 'disabled')",
            name="embedding_status",
        ),
        CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'deprecated')",
            name="review_status",
        ),
        Index(
            "ix_medical_rag_chunks_status_embedding_expires",
            "review_status",
            "embedding_status",
            "expires_at",
        ),
        Index("ix_medical_rag_chunks_chunk_hash", "chunk_hash", unique=True),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    evidence_item_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("medical_evidence_items.id"),
        nullable=False,
    )
    source_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("medical_source_versions.id"),
        nullable=False,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[date] = mapped_column(Date, nullable=False)


class MedicalUnknownKnowledgeEvent(TimestampMixin, Base):
    """Persist privacy-minimized unknown chatbot topic events for source review."""

    __tablename__ = "chatbot_unknown_knowledge_events"
    __table_args__ = (
        CheckConstraint(
            "answerability = 'unknown_no_reviewed_source'",
            name="answerability",
        ),
        CheckConstraint(
            "retrieval_status IN ('no_match', 'stale_only', 'not_reviewed_only')",
            name="retrieval_status",
        ),
        CheckConstraint(
            "status IN ('open', 'reviewing', 'promoted', 'dismissed', 'deprecated')",
            name="status",
        ),
        Index(
            "ix_chatbot_unknown_knowledge_events_status_category_created",
            "status",
            "category",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    answerability: Mapped[str] = mapped_column(String(48), nullable=False)
    primary_intent: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    related_conditions: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    missing_topics: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    retrieval_status: Mapped[str] = mapped_column(String(48), nullable=False)
    retrieval_warnings: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    needed_evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
