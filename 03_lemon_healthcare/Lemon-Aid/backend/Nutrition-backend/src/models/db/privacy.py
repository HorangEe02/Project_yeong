"""Privacy, consent, deletion, and audit ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class ConsentPolicy(TimestampMixin, Base):
    """Persist a versioned consent policy definition.

    Attributes:
        id: Stable policy identifier.
        consent_type: Functional consent bucket.
        version: Policy version string displayed and stored with records.
        title: Human-readable policy title.
        content_hash: SHA-256 hash of reviewed policy text.
        required: Whether the consent gates a protected feature.
        effective_at: Time when the policy version became active.
        retired_at: Optional retirement time for superseded policies.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "consent_policies"
    __table_args__ = (
        UniqueConstraint(
            "consent_type", "version", name="uq_consent_policies_consent_type_version"
        ),
        Index("ix_consent_policies_type_effective_at", "consent_type", "effective_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    consent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentRecord(TimestampMixin, Base):
    """Persist an append-only consent grant or revocation event.

    Attributes:
        id: Stable consent event identifier.
        owner_subject: Issuer-qualified authenticated subject.
        consent_type: Functional consent bucket.
        policy_version: Policy version accepted or revoked by the user.
        granted: True for grants, False for revocations.
        occurred_at: Time when the consent event occurred.
        revoked_at: Revocation timestamp for revocation events.
        request_id: Optional bounded request correlation identifier.
        ip_hash: HMAC of the request IP address.
        user_agent_hash: HMAC of the request User-Agent.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "consent_records"
    __table_args__ = (
        Index(
            "ix_consent_records_owner_consent_occurred_at",
            "owner_subject",
            "consent_type",
            "occurred_at",
        ),
        Index("ix_consent_records_owner_occurred_at", "owner_subject", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DeletionRequest(TimestampMixin, Base):
    """Persist a user data deletion request without storing raw subject IDs.

    Attributes:
        id: Stable deletion request identifier.
        owner_subject_hash: HMAC of the issuer-qualified authenticated subject.
        request_type: Deletion request scope.
        status: Processing status.
        requested_at: Time when the deletion request was received.
        completed_at: Completion time for immediately processed requests.
        deleted_counts: Counts of deleted records by resource type.
        failure_reason: Sanitized failure reason for failed requests.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "deletion_requests"
    __table_args__ = (
        CheckConstraint("request_type IN ('all_user_data')", name="deletion_request_type_allowed"),
        CheckConstraint(
            "status IN ('completed', 'failed')", name="deletion_request_status_allowed"
        ),
        Index("ix_deletion_requests_owner_requested_at", "owner_subject_hash", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_counts: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class AuditLog(TimestampMixin, Base):
    """Persist sanitized security and privacy audit events.

    Attributes:
        id: Stable audit event identifier.
        actor_subject_hash: HMAC of the issuer-qualified authenticated subject.
        action: Event action name.
        resource_type: Resource category affected by the event.
        resource_id: Optional public or opaque resource identifier.
        outcome: Event outcome.
        request_id: Optional bounded request correlation identifier.
        ip_hash: HMAC of the request IP address.
        user_agent_hash: HMAC of the request User-Agent.
        event_metadata: Sanitized metadata that excludes raw health snapshots and tokens.
        record_hash: HMAC over the audit event payload for tamper-evidence.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'failed', 'not_found', 'blocked')", name="audit_outcome_allowed"
        ),
        Index("ix_audit_logs_actor_created_at", "actor_subject_hash", "created_at"),
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
        Index("ix_audit_logs_resource_created_at", "resource_type", "resource_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
