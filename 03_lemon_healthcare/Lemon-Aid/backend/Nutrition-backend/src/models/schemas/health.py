"""Health device sync API contract schemas."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_HEALTH_QUALITY_FLAG_LENGTH = 48


class HealthDataSourcePlatform(StrEnum):
    """Supported health data source platforms.

    Attributes:
        IOS_HEALTHKIT: iOS HealthKit aggregate data.
        ANDROID_HEALTH_CONNECT: Android Health Connect aggregate data.
        MANUAL: User-entered fallback values.
    """

    IOS_HEALTHKIT = "ios_healthkit"
    ANDROID_HEALTH_CONNECT = "android_health_connect"
    MANUAL = "manual"


class BodyProfileSource(StrEnum):
    """Supported sources for versioned body profile snapshots.

    Attributes:
        MANUAL: User-entered profile values.
        HEALTHKIT: iOS HealthKit-derived profile values.
        HEALTH_CONNECT: Android Health Connect-derived profile values.
        CLINICIAN_DOCUMENT: User-confirmed values copied from a clinician document.
    """

    MANUAL = "manual"
    HEALTHKIT = "healthkit"
    HEALTH_CONNECT = "health_connect"
    CLINICIAN_DOCUMENT = "clinician_document"


class BodyProfileSex(StrEnum):
    """Algorithm-supported sex values for profile snapshots.

    Attributes:
        MALE: Male.
        FEMALE: Female.
    """

    MALE = "male"
    FEMALE = "female"


class PregnancyStatus(StrEnum):
    """Supported pregnancy status codes.

    Attributes:
        NOT_APPLICABLE: Pregnancy status is not applicable.
        NOT_PREGNANT: User indicated not pregnant.
        PREGNANT: User indicated pregnant.
        UNKNOWN: User did not provide a status.
    """

    NOT_APPLICABLE = "not_applicable"
    NOT_PREGNANT = "not_pregnant"
    PREGNANT = "pregnant"
    UNKNOWN = "unknown"


class LactationStatus(StrEnum):
    """Supported lactation status codes.

    Attributes:
        NOT_APPLICABLE: Lactation status is not applicable.
        NOT_LACTATING: User indicated not lactating.
        LACTATING: User indicated lactating.
        UNKNOWN: User did not provide a status.
    """

    NOT_APPLICABLE = "not_applicable"
    NOT_LACTATING = "not_lactating"
    LACTATING = "lactating"
    UNKNOWN = "unknown"


class ActivityLevel(StrEnum):
    """Supported activity-level codes used by nutrition algorithms.

    Attributes:
        SEDENTARY: Sedentary activity level.
        LOW_ACTIVE: Low active activity level.
        ACTIVE: Active activity level.
        VERY_ACTIVE: Very active activity level.
        UNKNOWN: Activity level is unknown.
    """

    SEDENTARY = "sedentary"
    LOW_ACTIVE = "low_active"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"
    UNKNOWN = "unknown"


class HealthMetricSourcePlatform(StrEnum):
    """Supported point-in-time health metric source platforms.

    Attributes:
        IOS_HEALTHKIT: iOS HealthKit sample.
        ANDROID_HEALTH_CONNECT: Android Health Connect sample.
        MANUAL: User-entered sample.
        DOCUMENT: User-confirmed document-derived sample.
    """

    IOS_HEALTHKIT = "ios_healthkit"
    ANDROID_HEALTH_CONNECT = "android_health_connect"
    MANUAL = "manual"
    DOCUMENT = "document"


class HealthMetricType(StrEnum):
    """Supported point-in-time health metric types.

    Attributes:
        STEPS: Step count.
        WEIGHT_KG: Body weight in kilograms.
        RESTING_HR_BPM: Resting heart rate in beats per minute.
        ACTIVE_ENERGY_KCAL: Active energy in kilocalories.
        BLOOD_PRESSURE_SYSTOLIC: Systolic blood pressure.
        BLOOD_PRESSURE_DIASTOLIC: Diastolic blood pressure.
        GLUCOSE_MG_DL: Blood glucose.
    """

    STEPS = "steps"
    WEIGHT_KG = "weight_kg"
    RESTING_HR_BPM = "resting_hr_bpm"
    ACTIVE_ENERGY_KCAL = "active_energy_kcal"
    BLOOD_PRESSURE_SYSTOLIC = "blood_pressure_systolic"
    BLOOD_PRESSURE_DIASTOLIC = "blood_pressure_diastolic"
    GLUCOSE_MG_DL = "glucose_mg_dl"


class HealthMetricUnit(StrEnum):
    """Supported units for point-in-time health metrics.

    Attributes:
        COUNT: Count unit.
        KG: Kilograms.
        BPM: Beats per minute.
        KCAL: Kilocalories.
        MMHG: Millimeters of mercury.
        MG_DL: Milligrams per deciliter.
    """

    COUNT = "count"
    KG = "kg"
    BPM = "bpm"
    KCAL = "kcal"
    MMHG = "mmHg"
    MG_DL = "mg/dL"


class HealthDailyAggregate(BaseModel):
    """One day of health data aggregate values.

    Attributes:
        measured_date: Local calendar date for the aggregate.
        source_platform: Platform that produced the values.
        steps: Daily step count.
        weight_kg: Body weight in kilograms.
        resting_heart_rate_bpm: Resting heart rate in beats per minute.
        active_energy_kcal: Active energy in kilocalories.
        source_record_hash: Optional client-side source hash for duplicate tracing.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    measured_date: date
    source_platform: HealthDataSourcePlatform
    steps: int | None = Field(default=None, ge=0, le=200000)
    weight_kg: float | None = Field(default=None, ge=20, le=300)
    resting_heart_rate_bpm: int | None = Field(default=None, ge=20, le=240)
    active_energy_kcal: float | None = Field(default=None, ge=0, le=20000)
    source_record_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )

    @model_validator(mode="after")
    def validate_health_daily_aggregate(self) -> HealthDailyAggregate:
        """Validate aggregate-level invariants.

        Returns:
            Validated aggregate model.

        Raises:
            ValueError: If no metric is present or the measured date is too far ahead.
        """
        if (
            self.steps is None
            and self.weight_kg is None
            and self.resting_heart_rate_bpm is None
            and self.active_energy_kcal is None
        ):
            raise ValueError("At least one health metric must be present.")
        if self.measured_date > datetime.now(UTC).date() + timedelta(days=1):
            raise ValueError("measured_date cannot be more than one day in the future.")
        return self


class HealthSyncRequest(BaseModel):
    """Request body for syncing health aggregates.

    Attributes:
        client_batch_id: Optional client idempotency key for safe retries.
        records: Daily aggregate records from the client. P1 stores aggregates,
            not raw high-frequency health samples.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_batch_id: str | None = Field(default=None, min_length=1, max_length=80)
    records: list[HealthDailyAggregate] = Field(min_length=1, max_length=366)


class HealthSyncResponse(BaseModel):
    """Response for a health aggregate sync request.

    Attributes:
        batch_id: Persisted health sync batch id.
        accepted_count: Number of accepted daily records.
        rejected_count: Number of rejected daily records.
        synced_at: Server-side sync timestamp.
    """

    batch_id: UUID | None = None
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    synced_at: datetime


class BodyProfileSnapshotCreate(BaseModel):
    """Request body for creating a versioned body profile snapshot.

    Attributes:
        effective_at: Time when this profile version starts applying.
        source: Source of the profile values.
        sex: Algorithm-supported sex value.
        birth_year: Minimal age derivation input.
        height_cm: Height in centimeters.
        weight_kg: Body weight in kilograms.
        waist_cm: Waist circumference in centimeters.
        pregnancy_status: Pregnancy status code.
        lactation_status: Lactation status code.
        activity_level: Activity-level code.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    effective_at: datetime | None = None
    source: BodyProfileSource = BodyProfileSource.MANUAL
    sex: BodyProfileSex | None = None
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    height_cm: Decimal | None = Field(default=None, ge=30, le=260, max_digits=5, decimal_places=2)
    weight_kg: Decimal | None = Field(default=None, ge=1, le=500, max_digits=5, decimal_places=2)
    waist_cm: Decimal | None = Field(default=None, ge=20, le=250, max_digits=5, decimal_places=2)
    pregnancy_status: PregnancyStatus | None = None
    lactation_status: LactationStatus | None = None
    activity_level: ActivityLevel | None = None

    @model_validator(mode="after")
    def validate_profile_has_value(self) -> BodyProfileSnapshotCreate:
        """Validate that at least one profile value is present.

        Returns:
            Validated create request.

        Raises:
            ValueError: If no profile field is present or the timestamp is too far ahead.
        """
        if (
            self.sex is None
            and self.birth_year is None
            and self.height_cm is None
            and self.weight_kg is None
            and self.waist_cm is None
            and self.pregnancy_status is None
            and self.lactation_status is None
            and self.activity_level is None
        ):
            raise ValueError("At least one body profile value must be present.")
        effective_at = self.effective_at or datetime.now(UTC)
        if effective_at > datetime.now(UTC) + timedelta(days=1):
            raise ValueError("effective_at cannot be more than one day in the future.")
        return self


class BodyProfileSnapshotResponse(BaseModel):
    """Response for a versioned body profile snapshot.

    Attributes:
        id: Profile snapshot identifier.
        effective_at: Time when this version starts applying.
        source: Source of the profile values.
        sex: Algorithm-supported sex value.
        birth_year: Minimal age derivation input.
        height_cm: Height in centimeters.
        weight_kg: Body weight in kilograms.
        waist_cm: Waist circumference in centimeters.
        pregnancy_status: Pregnancy status code.
        lactation_status: Lactation status code.
        activity_level: Activity-level code.
        superseded_at: Time when a newer profile superseded this snapshot.
        created_at: Server-side creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    effective_at: datetime
    source: BodyProfileSource
    sex: BodyProfileSex | None = None
    birth_year: int | None = None
    height_cm: Decimal | None = None
    weight_kg: Decimal | None = None
    waist_cm: Decimal | None = None
    pregnancy_status: PregnancyStatus | None = None
    lactation_status: LactationStatus | None = None
    activity_level: ActivityLevel | None = None
    superseded_at: datetime | None = None
    created_at: datetime | None = None


class HealthMetricSampleCreate(BaseModel):
    """Request body for creating one point-in-time health metric sample.

    Attributes:
        metric_type: Metric type code.
        measured_at: Time when the metric was measured.
        value_numeric: Numeric metric value in the declared unit.
        unit: Unit code for the metric value.
        source_platform: Metric source platform.
        source_record_hash: Optional client duplicate-detection hash.
        quality_flags: Safe quality flags.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    metric_type: HealthMetricType
    measured_at: datetime
    value_numeric: Decimal = Field(ge=0, max_digits=12, decimal_places=4)
    unit: HealthMetricUnit
    source_platform: HealthMetricSourcePlatform = HealthMetricSourcePlatform.MANUAL
    source_record_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )
    quality_flags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("quality_flags")
    @classmethod
    def validate_quality_flags(cls, value: list[str]) -> list[str]:
        """Validate metric quality flags are stable codes only.

        Args:
            value: Quality flag list.

        Returns:
            Validated quality flag list.

        Raises:
            ValueError: If a flag is not a bounded code.
        """
        for flag in value:
            if (
                not flag
                or len(flag) > MAX_HEALTH_QUALITY_FLAG_LENGTH
                or not flag.replace("_", "").replace("-", "").isalnum()
            ):
                raise ValueError("quality_flags must contain stable bounded codes.")
        return value

    @model_validator(mode="after")
    def validate_metric_sample(self) -> HealthMetricSampleCreate:
        """Validate timestamp and metric/unit compatibility.

        Returns:
            Validated metric sample request.

        Raises:
            ValueError: If the timestamp is too far ahead or unit does not match metric type.
        """
        if self.measured_at > datetime.now(UTC) + timedelta(days=1):
            raise ValueError("measured_at cannot be more than one day in the future.")
        expected_units: dict[HealthMetricType, HealthMetricUnit] = {
            HealthMetricType.STEPS: HealthMetricUnit.COUNT,
            HealthMetricType.WEIGHT_KG: HealthMetricUnit.KG,
            HealthMetricType.RESTING_HR_BPM: HealthMetricUnit.BPM,
            HealthMetricType.ACTIVE_ENERGY_KCAL: HealthMetricUnit.KCAL,
            HealthMetricType.BLOOD_PRESSURE_SYSTOLIC: HealthMetricUnit.MMHG,
            HealthMetricType.BLOOD_PRESSURE_DIASTOLIC: HealthMetricUnit.MMHG,
            HealthMetricType.GLUCOSE_MG_DL: HealthMetricUnit.MG_DL,
        }
        if self.unit != expected_units[self.metric_type]:
            raise ValueError("unit is not compatible with metric_type.")
        return self


class HealthMetricSampleResponse(BaseModel):
    """Response for a point-in-time health metric sample.

    Attributes:
        id: Metric sample identifier.
        metric_type: Metric type code.
        measured_at: Time when the metric was measured.
        value_numeric: Numeric metric value.
        unit: Unit code.
        source_platform: Metric source platform.
        quality_flags: Safe quality flags.
        created_at: Server-side creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    metric_type: HealthMetricType
    measured_at: datetime
    value_numeric: Decimal
    unit: HealthMetricUnit
    source_platform: HealthMetricSourcePlatform
    quality_flags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class HealthDailySummaryResponse(BaseModel):
    """Response for one current-user health daily summary row.

    Attributes:
        measured_date: User-local measured date.
        source_platform: Source platform.
        steps: Daily step count.
        weight_kg: Body weight.
        resting_heart_rate_bpm: Resting heart rate.
        active_energy_kcal: Active energy.
        synced_at: Server-side sync timestamp.
    """

    measured_date: date
    source_platform: HealthDataSourcePlatform
    steps: int | None = None
    weight_kg: Decimal | None = None
    resting_heart_rate_bpm: int | None = None
    active_energy_kcal: Decimal | None = None
    synced_at: datetime


class HealthDailySummaryListResponse(BaseModel):
    """Response for current-user daily health summaries.

    Attributes:
        summaries: Daily summary rows.
    """

    summaries: list[HealthDailySummaryResponse]


class EmptyLatestBodyProfileResponse(BaseModel):
    """Response returned when no body profile snapshot exists.

    Attributes:
        status: Stable not-ready marker.
    """

    status: Literal["not_ready"] = "not_ready"
