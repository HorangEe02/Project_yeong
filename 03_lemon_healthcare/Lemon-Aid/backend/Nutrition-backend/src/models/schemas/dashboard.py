"""Dashboard summary API contract schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DashboardNutrientSummary(BaseModel):
    """Nutrition summary for dashboard display.

    Attributes:
        data_status: Whether a persisted nutrition analysis is available.
        latest_result_id: Latest persisted nutrition result identifier.
        low_count: Number of nutrients below configured reference range.
        high_count: Number of nutrients above configured reference range.
        dataset_version: KDRIs dataset version used for the summary.
        source_manifest_version: Source manifest version used for the summary.
    """

    data_status: str = Field(default="not_ready", pattern=r"^(ready|not_ready)$")
    latest_result_id: UUID | None = None
    low_count: int = Field(ge=0)
    high_count: int = Field(ge=0)
    dataset_version: str | None = None
    source_manifest_version: str | None


class DashboardActivitySummary(BaseModel):
    """Activity summary for dashboard display.

    Attributes:
        data_status: Whether current-user activity data is available.
        latest_steps: Latest synced daily step count.
        latest_resting_heart_rate_bpm: Latest synced resting heart rate.
        latest_active_energy_kcal: Latest synced active energy estimate.
        latest_activity_score: Latest computed activity score.
        measured_date: Date for the latest activity values.
    """

    data_status: str = Field(default="not_ready", pattern=r"^(ready|not_ready)$")
    latest_steps: int | None = Field(default=None, ge=0)
    latest_resting_heart_rate_bpm: int | None = Field(default=None, ge=20, le=240)
    latest_active_energy_kcal: float | None = Field(default=None, ge=0, le=20000)
    latest_activity_score: float | None = Field(default=None, ge=0, le=120)
    measured_date: date | None = None


class DashboardWeightSummary(BaseModel):
    """Weight summary for dashboard display.

    Attributes:
        data_status: Whether current-user weight data is available.
        latest_weight_kg: Latest synced or entered weight.
        predicted_weight_kg: Latest short-term predicted weight.
        measured_date: Date for the latest weight value.
    """

    data_status: str = Field(default="not_ready", pattern=r"^(ready|not_ready)$")
    latest_weight_kg: float | None = Field(default=None, ge=20, le=300)
    predicted_weight_kg: float | None = Field(default=None, ge=20, le=300)
    measured_date: date | None = None


class DashboardSupplementSummary(BaseModel):
    """Supplement summary for dashboard display.

    Attributes:
        registered_count: Current-user registered supplement count.
        requires_review_count: Count of supplement records that need user review.
    """

    registered_count: int = Field(ge=0)
    requires_review_count: int = Field(ge=0)


class DashboardScoreComponent(BaseModel):
    """One weighted component of the daily health score.

    Attributes:
        available: Whether this component had enough data to contribute.
        subscore: Component subscore on a 0-100 scale, or None when unavailable.
        weight: Effective combination weight after renormalization.
    """

    available: bool
    subscore: float | None = Field(default=None, ge=0, le=100)
    weight: float = Field(ge=0, le=1)


class DashboardScoreComponents(BaseModel):
    """Daily health score components.

    Attributes:
        activity: Activity component summary.
        nutrition: Nutrition component summary.
    """

    activity: DashboardScoreComponent
    nutrition: DashboardScoreComponent


class DailyScoreSourceCitation(BaseModel):
    """Local WIKI source citation used to ground the daily health score.

    Attributes:
        title: Document title inferred from a Markdown heading or filename.
        source_path: Relative Markdown path under the configured WIKI root.
        heading: Best matching heading in the Markdown file.
        excerpt: Bounded excerpt used as retrieval context.
        score: Retrieval score for deterministic ordering.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    source_path: str = Field(min_length=1, max_length=260)
    heading: str | None = Field(default=None, max_length=160)
    excerpt: str = Field(max_length=900)
    score: float = Field(ge=0)


class DashboardHealthScoreSummary(BaseModel):
    """Daily health score summary for dashboard display.

    Attributes:
        data_status: Whether the daily health score could be computed.
        score: Combined 0-100 daily health score, or None when not ready.
        label: Five-tier score label, or None when not ready.
        label_text: Korean label text, or None when not ready.
        message: User-facing safe message, or None when not ready.
        components: Per-component availability and weighting.
        source_citations: Server-selected local WIKI citations.
        disclaimers: User-facing safety notices.
        algorithm_version: Daily health score algorithm contract version.
        measured_date: Local date the score was computed for.
    """

    data_status: str = Field(default="not_ready", pattern=r"^(ready|not_ready)$")
    score: int | None = Field(default=None, ge=0, le=100)
    label: Literal["excellent", "good", "moderate", "warning", "needs_attention"] | None = None
    label_text: str | None = None
    message: str | None = None
    components: DashboardScoreComponents
    source_citations: list[DailyScoreSourceCitation] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    algorithm_version: str
    measured_date: date | None = None


class DashboardSummaryResponse(BaseModel):
    """Current-user dashboard summary response.

    Attributes:
        as_of: Server-side summary timestamp.
        nutrition: Nutrition summary.
        activity: Activity summary.
        weight: Weight summary.
        supplements: Supplement summary.
        health_score: Daily health score summary.
        disclaimers: User-facing safety notices.
        algorithm_version: Dashboard aggregation contract version.
    """

    as_of: datetime
    nutrition: DashboardNutrientSummary
    activity: DashboardActivitySummary
    weight: DashboardWeightSummary
    supplements: DashboardSupplementSummary
    health_score: DashboardHealthScoreSummary
    disclaimers: list[str]
    algorithm_version: str
