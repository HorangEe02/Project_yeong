"""Daily health score aggregation for the current-user dashboard.

The daily health score blends an activity subscore (reusing the v4 activity
algorithm) and a nutrition subscore (kcal-vs-TDEE and sodium heuristics) into a
single 0-100 score with a five-tier safe label. Both subscores are independently
optional: when only one is available its weight is renormalized to 1.0, and when
neither is available the score reports ``not_ready`` with a ``None`` score.

Pure helpers (:func:`_activity_subscore`, :func:`_nutrition_subscore`,
:func:`_combine`, :func:`_score_to_label`) are module-level so they can be unit
tested without a database session.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from src.algorithms.activity import calculate_activity_score
from src.algorithms.metabolism import calculate_bmr, calculate_tdee
from src.models.schemas.algorithm import ActivityScoreRequest
from src.models.schemas.dashboard import (
    DashboardHealthScoreSummary,
    DashboardScoreComponent,
    DashboardScoreComponents,
)
from src.models.schemas.user import Sex, UserProfile
from src.services.daily_health_score_explanation import wiki_citations_for_score
from src.services.health_profile import (
    get_latest_body_profile_snapshot,
    list_health_daily_summaries,
)
from src.services.meal_image_analysis import list_user_meal_records

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.config import Settings
    from src.models.db.health import BodyProfileSnapshot, HealthDailySummary
    from src.models.schemas.meal import MealRecordResponse
    from src.security.auth import AuthenticatedUser

DAILY_HEALTH_SCORE_ALGORITHM_VERSION = "daily-health-score-v1.0.0"
DAILY_HEALTH_SCORE_DISCLAIMERS = [
    "이 점수는 건강 관리 참고용이며 의학적 진단이 아닙니다.",
]

ACTIVITY_WEIGHT = 0.6
NUTRITION_WEIGHT = 0.4
SCORE_MIN = 0
SCORE_MAX = 100
ACTIVITY_SUBSCORE_CAP = 100.0

# Nutrition subscore: kcal ratio bands relative to TDEE.
NUTRITION_BASELINE = 100.0
KCAL_RATIO_OK_LOW = 0.8
KCAL_RATIO_OK_HIGH = 1.2
KCAL_RATIO_MILD_LOW = 0.6
KCAL_RATIO_MILD_HIGH = 1.4
KCAL_PENALTY_MILD = 10.0
KCAL_PENALTY_SEVERE = 20.0
# Nutrition subscore: sodium over-target penalty.
SODIUM_TARGET_MG = 2000.0
SODIUM_PENALTY_PER_STEP_MG = 1000.0
SODIUM_PENALTY_PER_STEP = 10.0
SODIUM_PENALTY_CAP = 30.0
LOW_STEPS_DRIVER_THRESHOLD = 4000
MAX_AGE_YEARS = 120
MIN_AGE_YEARS = 1

# Five-tier label boundaries (inclusive lower bounds).
LABEL_EXCELLENT = 90
LABEL_GOOD = 75
LABEL_MODERATE = 55
LABEL_WARNING = 35

ScoreLabel = Literal["excellent", "good", "moderate", "warning", "needs_attention"]

_LABEL_TEXT: dict[ScoreLabel, str] = {
    "excellent": "좋아요",
    "good": "양호",
    "moderate": "보통",
    "warning": "주의",
    "needs_attention": "참고",
}
_LABEL_MESSAGE: dict[ScoreLabel, str] = {
    "excellent": "오늘 건강 습관이 잘 유지되고 있어요.",
    "good": "전반적으로 좋아요. 한두 가지만 더 신경 써보세요.",
    "moderate": "오늘은 조금 더 움직이거나 식단을 챙겨보면 좋아요.",
    "warning": "활동·식단 관리에 신경 쓸 부분이 있어요.",
    "needs_attention": "오늘의 기록을 한 번 살펴보세요.",
}
_CHRONIC_FRAME = "건강 상태에 맞춘 활동은 전문가와 상의해 보세요."
_CHRONIC_FRAME_LABELS: frozenset[ScoreLabel] = frozenset({"warning", "needs_attention"})


@dataclass(frozen=True)
class _ActivityResult:
    """Activity subscore outcome.

    Attributes:
        subscore: Activity subscore on a 0-100 scale, or None when unavailable.
        drivers: Deduction reason codes contributed by the activity component.
    """

    subscore: float | None
    drivers: tuple[str, ...]


@dataclass(frozen=True)
class _NutritionResult:
    """Nutrition subscore outcome.

    Attributes:
        subscore: Nutrition subscore on a 0-100 scale, or None when unavailable.
        drivers: Deduction reason codes contributed by the nutrition component.
    """

    subscore: float | None
    drivers: tuple[str, ...]


async def build_daily_health_score(
    session: AsyncSession,
    user: AuthenticatedUser,
    as_of: date,
    settings: Settings,
    *,
    health_summaries: Sequence[HealthDailySummary] | None = None,
    health_context: Mapping[str, Any] | None = None,
) -> DashboardHealthScoreSummary:
    """Build the daily health score summary for the dashboard.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        as_of: Local date the score is computed for.
        settings: Runtime settings, including local WIKI retrieval controls.
        health_summaries: Optional pre-loaded daily summaries (newest first) to
            reuse the dashboard query; the ``as_of`` row is selected from them.
        health_context: Optional chronic-disease and smoking context with keys
            ``chronic_diseases`` (list[str]) and ``smoking_status`` (str).

    Returns:
        Daily health score summary with components, citations, and disclaimers.
    """
    profile_snapshot = await get_latest_body_profile_snapshot(session, user)
    today_summary = _select_summary_for_date(health_summaries, as_of)
    if today_summary is None and health_summaries is None:
        today_summary = await _load_summary_for_date(session, user, as_of)

    chronic_diseases, smoking_status = _normalize_health_context(health_context)

    activity = _activity_subscore(
        steps=today_summary.steps if today_summary is not None else None,
        profile_snapshot=profile_snapshot,
        as_of=as_of,
        chronic_diseases=chronic_diseases,
        smoking_status=smoking_status,
    )
    meals = await _today_confirmed_meals(session, user, as_of)
    nutrition = _nutrition_subscore(
        meals=meals,
        profile_snapshot=profile_snapshot,
        as_of=as_of,
    )

    score, label, weights = _combine(activity.subscore, nutrition.subscore)
    has_chronic = bool(chronic_diseases)
    drivers = (*activity.drivers, *nutrition.drivers)
    citations = await wiki_citations_for_score(drivers, settings)

    components = DashboardScoreComponents(
        activity=DashboardScoreComponent(
            available=activity.subscore is not None,
            subscore=activity.subscore,
            weight=weights[0],
        ),
        nutrition=DashboardScoreComponent(
            available=nutrition.subscore is not None,
            subscore=nutrition.subscore,
            weight=weights[1],
        ),
    )

    if score is None:
        return DashboardHealthScoreSummary(
            data_status="not_ready",
            score=None,
            label=None,
            label_text=None,
            message=None,
            components=components,
            source_citations=list(citations),
            disclaimers=list(DAILY_HEALTH_SCORE_DISCLAIMERS),
            algorithm_version=DAILY_HEALTH_SCORE_ALGORITHM_VERSION,
            measured_date=as_of,
        )

    assert label is not None
    return DashboardHealthScoreSummary(
        data_status="ready",
        score=score,
        label=label,
        label_text=_LABEL_TEXT[label],
        message=_label_message(label, has_chronic=has_chronic),
        components=components,
        source_citations=list(citations),
        disclaimers=list(DAILY_HEALTH_SCORE_DISCLAIMERS),
        algorithm_version=DAILY_HEALTH_SCORE_ALGORITHM_VERSION,
        measured_date=as_of,
    )


def _activity_subscore(
    *,
    steps: int | None,
    profile_snapshot: BodyProfileSnapshot | None,
    as_of: date,
    chronic_diseases: list[str],
    smoking_status: str,
) -> _ActivityResult:
    """Compute the activity subscore from same-day steps and the body profile.

    Reuses :func:`calculate_activity_score` and reads its ``v4_score`` capped at
    100. There is no cohort, so the percentile bonus is zero (empty group input),
    and there is no minute-level heart-rate data, so the algorithm's existing
    ``hr_factor`` fallback applies without any extra penalty here.

    Args:
        steps: Same-day step count, or None when unavailable.
        profile_snapshot: Latest body profile snapshot, or None.
        as_of: Local date used to derive age from ``birth_year``.
        chronic_diseases: Chronic-disease codes for the v4 multiplier.
        smoking_status: Smoking status for the v4 multiplier.

    Returns:
        Activity subscore and its deduction drivers. Subscore is None when steps
        or the minimal profile fields are missing.
    """
    drivers: list[str] = []
    if steps is None:
        return _ActivityResult(subscore=None, drivers=())

    profile = _activity_profile(
        profile_snapshot,
        as_of=as_of,
        chronic_diseases=chronic_diseases,
        smoking_status=smoking_status,
    )
    if profile is None:
        return _ActivityResult(subscore=None, drivers=())

    request = ActivityScoreRequest(
        profile=profile,
        daily_steps=steps,
        target_hr_minutes=None,
        group_v2_scores=[],
    )
    response = calculate_activity_score(request)
    subscore = min(response.v4_score, ACTIVITY_SUBSCORE_CAP)
    if steps < LOW_STEPS_DRIVER_THRESHOLD:
        drivers.append("low_steps")
    return _ActivityResult(subscore=subscore, drivers=tuple(drivers))


def _nutrition_subscore(
    *,
    meals: Sequence[MealRecordResponse],
    profile_snapshot: BodyProfileSnapshot | None,
    as_of: date,
) -> _NutritionResult:
    """Compute the nutrition subscore from same-day confirmed meals.

    Trusts only ``kcal`` and ``sodium_mg`` totals. The kcal penalty needs a TDEE
    estimate from the body profile; when the profile is insufficient, the kcal
    penalty is skipped (the sodium penalty still applies).

    Args:
        meals: Same-day confirmed meal records.
        profile_snapshot: Latest body profile snapshot, or None.
        as_of: Local date used to derive age for the TDEE estimate.

    Returns:
        Nutrition subscore and its deduction drivers. Subscore is None when there
        are no confirmed meals on ``as_of``.
    """
    if not meals:
        return _NutritionResult(subscore=None, drivers=())

    total_kcal, total_sodium_mg = _sum_meal_totals(meals)
    drivers: list[str] = []
    score = NUTRITION_BASELINE

    tdee = _estimate_tdee(profile_snapshot, as_of=as_of)
    if tdee is not None and tdee > 0 and total_kcal is not None:
        ratio = total_kcal / tdee
        penalty, kcal_driver = _kcal_penalty(ratio)
        score -= penalty
        if kcal_driver is not None:
            drivers.append(kcal_driver)

    if total_sodium_mg is not None and total_sodium_mg > SODIUM_TARGET_MG:
        over = total_sodium_mg - SODIUM_TARGET_MG
        steps = -(-over // SODIUM_PENALTY_PER_STEP_MG)  # ceil division
        penalty = min(steps * SODIUM_PENALTY_PER_STEP, SODIUM_PENALTY_CAP)
        score -= penalty
        drivers.append("sodium_over")

    bounded = float(max(float(SCORE_MIN), min(float(SCORE_MAX), score)))
    return _NutritionResult(subscore=bounded, drivers=tuple(drivers))


def _combine(
    activity_subscore: float | None,
    nutrition_subscore: float | None,
) -> tuple[int | None, ScoreLabel | None, tuple[float, float]]:
    """Combine activity and nutrition subscores into a final score.

    When both subscores exist the base weights ``0.6 / 0.4`` apply. When only one
    exists its weight renormalizes to ``1.0`` (the missing side weighs ``0``).
    When neither exists the score is ``None``.

    Args:
        activity_subscore: Activity subscore, or None.
        nutrition_subscore: Nutrition subscore, or None.

    Returns:
        Final 0-100 integer score (or None), its label (or None), and the
        effective ``(activity_weight, nutrition_weight)`` pair.
    """
    if activity_subscore is None and nutrition_subscore is None:
        return None, None, (0.0, 0.0)
    if activity_subscore is None:
        assert nutrition_subscore is not None
        score = round(nutrition_subscore)
        clamped = _clamp_score(score)
        return clamped, _score_to_label(clamped), (0.0, 1.0)
    if nutrition_subscore is None:
        score = round(activity_subscore)
        clamped = _clamp_score(score)
        return clamped, _score_to_label(clamped), (1.0, 0.0)

    raw = ACTIVITY_WEIGHT * activity_subscore + NUTRITION_WEIGHT * nutrition_subscore
    clamped = _clamp_score(round(raw))
    return clamped, _score_to_label(clamped), (ACTIVITY_WEIGHT, NUTRITION_WEIGHT)


def _score_to_label(score: int) -> ScoreLabel:
    """Map a 0-100 score to its five-tier label.

    Args:
        score: Final 0-100 score.

    Returns:
        Five-tier score label.
    """
    if score >= LABEL_EXCELLENT:
        return "excellent"
    if score >= LABEL_GOOD:
        return "good"
    if score >= LABEL_MODERATE:
        return "moderate"
    if score >= LABEL_WARNING:
        return "warning"
    return "needs_attention"


def _label_message(label: ScoreLabel, *, has_chronic: bool) -> str:
    """Return the safe user-facing message for a label.

    Args:
        label: Five-tier score label.
        has_chronic: Whether the user has chronic-disease context.

    Returns:
        Korean safe message, with a professional-consultation frame appended for
        chronic users on the lower-tier labels.
    """
    message = _LABEL_MESSAGE[label]
    if has_chronic and label in _CHRONIC_FRAME_LABELS:
        return f"{message} {_CHRONIC_FRAME}"
    return message


def _kcal_penalty(ratio: float) -> tuple[float, str | None]:
    """Return the kcal-ratio penalty and its driver code.

    Args:
        ratio: Consumed kcal divided by estimated TDEE.

    Returns:
        Penalty points and an optional driver code (None when no penalty).
    """
    if KCAL_RATIO_OK_LOW <= ratio <= KCAL_RATIO_OK_HIGH:
        return 0.0, None
    if KCAL_RATIO_MILD_LOW <= ratio < KCAL_RATIO_OK_LOW:
        return KCAL_PENALTY_MILD, "kcal_under"
    if KCAL_RATIO_OK_HIGH < ratio <= KCAL_RATIO_MILD_HIGH:
        return KCAL_PENALTY_MILD, "kcal_over"
    if ratio < KCAL_RATIO_MILD_LOW:
        return KCAL_PENALTY_SEVERE, "kcal_under"
    return KCAL_PENALTY_SEVERE, "kcal_over"


def _clamp_score(score: int) -> int:
    """Clamp a score into the 0-100 range.

    Args:
        score: Candidate integer score.

    Returns:
        Score clamped into ``[0, 100]``.
    """
    return max(SCORE_MIN, min(SCORE_MAX, score))


def _activity_profile(
    profile_snapshot: BodyProfileSnapshot | None,
    *,
    as_of: date,
    chronic_diseases: list[str],
    smoking_status: str,
) -> UserProfile | None:
    """Assemble a minimal activity ``UserProfile`` from the body profile.

    Args:
        profile_snapshot: Latest body profile snapshot, or None.
        as_of: Local date used to derive age from ``birth_year``.
        chronic_diseases: Chronic-disease codes for the v4 multiplier.
        smoking_status: Smoking status for the v4 multiplier.

    Returns:
        User profile, or None when sex, birth year, height, or weight is missing.
    """
    if profile_snapshot is None:
        return None
    age = _age_from_birth_year(profile_snapshot.birth_year, as_of)
    sex = _normalize_sex(profile_snapshot.sex)
    height_cm = _decimal_to_float(profile_snapshot.height_cm)
    weight_kg = _decimal_to_float(profile_snapshot.weight_kg)
    if age is None or sex is None or height_cm is None or weight_kg is None:
        return None
    try:
        return UserProfile(
            age=age,
            sex=sex,
            height_cm=height_cm,
            weight_kg=weight_kg,
            chronic_diseases=chronic_diseases,
            smoking_status=_normalize_smoking_status(smoking_status),
        )
    except ValueError:
        return None


def _estimate_tdee(
    profile_snapshot: BodyProfileSnapshot | None,
    *,
    as_of: date,
) -> float | None:
    """Estimate maintenance TDEE from the body profile.

    Args:
        profile_snapshot: Latest body profile snapshot, or None.
        as_of: Local date used to derive age from ``birth_year``.

    Returns:
        Estimated TDEE in kcal/day, or None when the profile is insufficient.
    """
    if profile_snapshot is None:
        return None
    age = _age_from_birth_year(profile_snapshot.birth_year, as_of)
    sex = _normalize_sex(profile_snapshot.sex)
    height_cm = _decimal_to_float(profile_snapshot.height_cm)
    weight_kg = _decimal_to_float(profile_snapshot.weight_kg)
    if age is None or sex is None or height_cm is None or weight_kg is None:
        return None
    try:
        bmr = calculate_bmr(weight_kg=weight_kg, height_cm=height_cm, age=age, sex=sex)
    except ValueError:
        return None
    return calculate_tdee(estimated_bmr=bmr, daily_steps=0)


def _sum_meal_totals(
    meals: Sequence[MealRecordResponse],
) -> tuple[float | None, float | None]:
    """Sum trusted kcal and sodium totals across confirmed meals.

    Only ``kcal`` and ``sodium_mg`` are trusted, read from each record's
    ``nutrition_summary`` (the confirmed ``totals`` block when present, otherwise
    a flat summary).

    Args:
        meals: Same-day confirmed meal records.

    Returns:
        ``(total_kcal, total_sodium_mg)``; each is None when no meal carries that
        trusted value.
    """
    total_kcal: float | None = None
    total_sodium_mg: float | None = None
    for meal in meals:
        totals = _trusted_totals(meal.nutrition_summary)
        kcal = _numeric(totals.get("kcal"))
        if kcal is not None:
            total_kcal = (total_kcal or 0.0) + kcal
        sodium = _numeric(totals.get("sodium_mg"))
        if sodium is not None:
            total_sodium_mg = (total_sodium_mg or 0.0) + sodium
    return total_kcal, total_sodium_mg


def _trusted_totals(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the nutrition totals mapping from a confirmed summary.

    Args:
        summary: Meal record ``nutrition_summary`` mapping.

    Returns:
        The nested ``totals`` mapping when present, otherwise the summary itself.
    """
    totals = summary.get("totals")
    if isinstance(totals, Mapping):
        return totals
    return summary


def _select_summary_for_date(
    health_summaries: Sequence[HealthDailySummary] | None,
    as_of: date,
) -> HealthDailySummary | None:
    """Select the same-day health summary from a preloaded sequence.

    Args:
        health_summaries: Preloaded summaries (newest first), or None.
        as_of: Local date to match.

    Returns:
        The first summary with a step count on ``as_of``, otherwise the first
        summary on ``as_of``, otherwise None.
    """
    if not health_summaries:
        return None
    same_day = [row for row in health_summaries if row.measured_date == as_of]
    if not same_day:
        return None
    with_steps = next((row for row in same_day if row.steps is not None), None)
    return with_steps or same_day[0]


async def _load_summary_for_date(
    session: AsyncSession,
    user: AuthenticatedUser,
    as_of: date,
) -> HealthDailySummary | None:
    """Load the same-day health summary when none was preloaded.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        as_of: Local date to match.

    Returns:
        The same-day summary preferring a row with steps, or None.
    """
    summaries = await list_health_daily_summaries(
        session,
        user,
        start_date=as_of,
        end_date=as_of,
        limit=10,
    )
    return _select_summary_for_date(summaries, as_of)


async def _today_confirmed_meals(
    session: AsyncSession,
    user: AuthenticatedUser,
    as_of: date,
) -> list[MealRecordResponse]:
    """Load same-day confirmed meal records via the meals service.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        as_of: Local date to match.

    Returns:
        Confirmed meal records eaten on ``as_of``.
    """
    day_start = datetime.combine(as_of, time.min, tzinfo=UTC)
    day_end = datetime.combine(as_of, time.max, tzinfo=UTC)
    listing = await list_user_meal_records(
        session=session,
        user=user,
        limit=100,
        offset=0,
        from_eaten_at=day_start,
        to_eaten_at=day_end,
    )
    return list(listing.results)


def _normalize_health_context(
    health_context: Mapping[str, Any] | None,
) -> tuple[list[str], str]:
    """Normalize optional chronic-disease and smoking context.

    Args:
        health_context: Optional context mapping, or None.

    Returns:
        ``(chronic_diseases, smoking_status)`` with safe defaults.
    """
    if not health_context:
        return [], "never"
    raw_diseases = health_context.get("chronic_diseases")
    chronic_diseases = (
        [code for code in raw_diseases if isinstance(code, str) and code.strip()]
        if isinstance(raw_diseases, list)
        else []
    )
    smoking_status = health_context.get("smoking_status")
    return chronic_diseases, smoking_status if isinstance(smoking_status, str) else "never"


def _normalize_smoking_status(smoking_status: str) -> str:
    """Return a smoking status accepted by the activity profile schema.

    Args:
        smoking_status: Candidate smoking status.

    Returns:
        The status when recognized, otherwise ``"never"``.
    """
    allowed = {
        "never",
        "former_lt_1y",
        "former_ge_1y",
        "current_light",
        "current_heavy",
    }
    return smoking_status if smoking_status in allowed else "never"


def _normalize_sex(sex: str | None) -> Sex | None:
    """Return a supported biological sex value, or None.

    Args:
        sex: Candidate sex string from the body profile.

    Returns:
        ``"male"`` or ``"female"`` when supported, otherwise None.
    """
    if sex in ("male", "female"):
        return sex
    return None


def _age_from_birth_year(birth_year: int | None, as_of: date) -> int | None:
    """Derive age from birth year relative to a reference date.

    Args:
        birth_year: Birth year, or None.
        as_of: Reference date.

    Returns:
        Non-negative age in years, or None when birth year is missing or invalid.
    """
    if birth_year is None:
        return None
    age = as_of.year - birth_year
    if age < 0 or age > MAX_AGE_YEARS:
        return None
    return max(age, MIN_AGE_YEARS)


def _decimal_to_float(value: Decimal | None) -> float | None:
    """Convert an optional Decimal to float.

    Args:
        value: Decimal value from an ORM row.

    Returns:
        Float value or None.
    """
    if value is None:
        return None
    return float(value)


def _numeric(value: Any) -> float | None:
    """Convert a primitive numeric value to float when possible.

    Args:
        value: Candidate value.

    Returns:
        Float value, or None when not numeric.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
