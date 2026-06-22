"""Health metric sync and daily summary ORM models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class HealthSyncBatch(TimestampMixin, Base):
    """Persist one current-user health data sync intake batch.

    Attributes:
        id: Stable sync batch identifier.
        owner_subject: Issuer-qualified authenticated subject.
        client_batch_id: Optional client idempotency key for replay protection.
        source_platform: Health data source platform.
        record_count: Number of records received from the client.
        accepted_count: Number of records accepted after validation.
        rejected_count: Number of records rejected after validation.
        input_snapshot: Sanitized bounded sync request metadata.
        result_snapshot: Sanitized bounded sync outcome metadata.
        synced_at: Time when the server accepted the batch.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "health_sync_batches"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject",
            "client_batch_id",
            name="uq_health_sync_batches_owner_client_batch",
        ),
        CheckConstraint(
            "source_platform IN ('ios_healthkit', 'android_health_connect', 'manual', 'mixed')",
            name="source_platform_allowed",
        ),
        CheckConstraint("record_count >= 0", name="record_count_nonnegative"),
        CheckConstraint("accepted_count >= 0", name="accepted_count_nonnegative"),
        CheckConstraint("rejected_count >= 0", name="rejected_count_nonnegative"),
        CheckConstraint(
            "accepted_count + rejected_count <= record_count",
            name="accepted_rejected_count_valid",
        ),
        Index("ix_health_sync_batches_owner_synced_at", "owner_subject", "synced_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    client_batch_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    result_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HealthDailySummary(TimestampMixin, Base):
    """Persist one owner-scoped daily health metric summary.

    Attributes:
        id: Stable health summary identifier.
        owner_subject: Issuer-qualified authenticated subject.
        measured_date: User-local date represented by the client.
        source_platform: Health data source platform.
        steps: Daily step count when available.
        weight_kg: Body weight in kilograms when available.
        resting_heart_rate_bpm: Resting heart rate when available.
        active_energy_kcal: Active energy estimate when available.
        source_record_hash: Optional hash for client-side duplicate detection.
        synced_at: Time when the server accepted the summary.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "health_daily_summaries"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject",
            "measured_date",
            "source_platform",
            name="uq_health_daily_summaries_owner_date_platform",
        ),
        CheckConstraint(
            "source_platform IN ('ios_healthkit', 'android_health_connect', 'manual')",
            name="source_platform_allowed",
        ),
        CheckConstraint(
            (
                "steps IS NOT NULL OR weight_kg IS NOT NULL OR "
                "resting_heart_rate_bpm IS NOT NULL OR active_energy_kcal IS NOT NULL"
            ),
            name="health_metric_present",
        ),
        CheckConstraint("steps IS NULL OR (steps >= 0 AND steps <= 200000)", name="steps_range"),
        CheckConstraint(
            "weight_kg IS NULL OR (weight_kg >= 20 AND weight_kg <= 300)",
            name="weight_kg_range",
        ),
        CheckConstraint(
            (
                "resting_heart_rate_bpm IS NULL OR "
                "(resting_heart_rate_bpm >= 20 AND resting_heart_rate_bpm <= 240)"
            ),
            name="resting_heart_rate_range",
        ),
        CheckConstraint(
            "active_energy_kcal IS NULL OR (active_energy_kcal >= 0 AND active_energy_kcal <= 20000)",
            name="active_energy_kcal_range",
        ),
        Index("ix_health_daily_summaries_owner_measured_date", "owner_subject", "measured_date"),
        Index(
            "ix_health_daily_summaries_owner_source_date",
            "owner_subject",
            "source_platform",
            "measured_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    measured_date: Mapped[date] = mapped_column(Date, nullable=False, primary_key=True)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    resting_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_energy_kcal: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    source_record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class BodyProfileSnapshot(TimestampMixin, Base):
    """Persist one versioned current-user body profile snapshot.

    Attributes:
        id: Stable profile snapshot identifier.
        owner_subject: Issuer-qualified authenticated subject.
        effective_at: Time when this profile version starts applying.
        source: Source of the profile values.
        sex: Biological sex value currently supported by algorithms.
        birth_year: Minimal age derivation input.
        height_cm: Height in centimeters.
        weight_kg: Body weight in kilograms.
        waist_cm: Waist circumference in centimeters.
        pregnancy_status: KDRIs-relevant pregnancy status code.
        lactation_status: KDRIs-relevant lactation status code.
        activity_level: Algorithm activity-level input.
        consent_snapshot: Consent type and policy-version snapshot.
        superseded_at: Time when a newer profile version superseded this row.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "body_profile_snapshots"
    __table_args__ = (
        CheckConstraint("owner_subject <> ''", name="body_profile_owner_subject_nonempty"),
        CheckConstraint(
            "source IN ('manual', 'healthkit', 'health_connect', 'clinician_document')",
            name="body_profile_source_allowed",
        ),
        CheckConstraint(
            "sex IS NULL OR sex IN ('male', 'female')", name="body_profile_sex_allowed"
        ),
        CheckConstraint(
            "birth_year IS NULL OR (birth_year >= 1900 AND birth_year <= 2100)",
            name="body_profile_birth_year_range",
        ),
        CheckConstraint(
            "height_cm IS NULL OR (height_cm >= 30 AND height_cm <= 260)",
            name="body_profile_height_cm_range",
        ),
        CheckConstraint(
            "weight_kg IS NULL OR (weight_kg >= 1 AND weight_kg <= 500)",
            name="body_profile_weight_kg_range",
        ),
        CheckConstraint(
            "waist_cm IS NULL OR (waist_cm >= 20 AND waist_cm <= 250)",
            name="body_profile_waist_cm_range",
        ),
        CheckConstraint(
            (
                "pregnancy_status IS NULL OR pregnancy_status IN "
                "('not_applicable', 'not_pregnant', 'pregnant', 'unknown')"
            ),
            name="body_profile_pregnancy_status_allowed",
        ),
        CheckConstraint(
            (
                "lactation_status IS NULL OR lactation_status IN "
                "('not_applicable', 'not_lactating', 'lactating', 'unknown')"
            ),
            name="body_profile_lactation_status_allowed",
        ),
        CheckConstraint(
            (
                "activity_level IS NULL OR activity_level IN "
                "('sedentary', 'low_active', 'active', 'very_active', 'unknown')"
            ),
            name="body_profile_activity_level_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(consent_snapshot) = 'object'",
            name="body_profile_consent_snapshot_object",
        ),
        Index(
            "ix_body_profile_snapshots_owner_effective_at",
            "owner_subject",
            "effective_at",
        ),
        Index(
            "ix_body_profile_snapshots_owner_superseded_at",
            "owner_subject",
            "superseded_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    waist_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    pregnancy_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lactation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class HealthMetricSample(TimestampMixin, Base):
    """Persist one current-user point-in-time health metric sample.

    Attributes:
        id: Stable metric sample identifier.
        owner_subject: Issuer-qualified authenticated subject.
        metric_type: Metric type code.
        measured_at: Time when the metric was measured.
        value_numeric: Numeric metric value in the declared unit.
        unit: Unit code for the value.
        source_platform: Metric source platform.
        source_record_hash: Optional client duplicate-detection hash.
        quality_flags: Stable safe quality flags.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "health_metric_samples"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject",
            "source_platform",
            "source_record_hash",
            name="uq_health_metric_samples_owner_source_hash",
        ),
        CheckConstraint("owner_subject <> ''", name="health_metric_owner_subject_nonempty"),
        CheckConstraint(
            (
                "metric_type IN ('steps', 'weight_kg', 'resting_hr_bpm', "
                "'active_energy_kcal', 'blood_pressure_systolic', "
                "'blood_pressure_diastolic', 'glucose_mg_dl')"
            ),
            name="health_metric_type_allowed",
        ),
        CheckConstraint("value_numeric >= 0", name="health_metric_value_nonnegative"),
        CheckConstraint(
            "unit IN ('count', 'kg', 'bpm', 'kcal', 'mmHg', 'mg/dL')",
            name="health_metric_unit_allowed",
        ),
        CheckConstraint(
            "source_platform IN ('ios_healthkit', 'android_health_connect', 'manual', 'document')",
            name="health_metric_source_platform_allowed",
        ),
        CheckConstraint(
            "source_record_hash IS NULL OR length(source_record_hash) = 64",
            name="health_metric_source_record_hash_length",
        ),
        CheckConstraint(
            "jsonb_typeof(quality_flags) = 'array'",
            name="health_metric_quality_flags_array",
        ),
        Index(
            "ix_health_metric_samples_owner_measured_at",
            "owner_subject",
            "measured_at",
        ),
        Index(
            "ix_health_metric_samples_owner_metric_measured_at",
            "owner_subject",
            "metric_type",
            "measured_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(40), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_numeric: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False)
    source_record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_flags: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
