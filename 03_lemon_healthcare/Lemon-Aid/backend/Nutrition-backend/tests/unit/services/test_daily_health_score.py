"""Daily health score service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from src.algorithms.activity import calculate_activity_score
from src.config import Settings
from src.models.db.health import BodyProfileSnapshot, HealthDailySummary
from src.models.schemas.algorithm import ActivityScoreRequest
from src.models.schemas.meal import (
    MealAnalysisStatus,
    MealRecordListResponse,
    MealRecordResponse,
    MealType,
)
from src.models.schemas.user import UserProfile
from src.nutrition.deficiency_analysis import FORBIDDEN_TERMS
from src.services import daily_health_score
from src.services.daily_health_score import (
    DAILY_HEALTH_SCORE_ALGORITHM_VERSION,
    _activity_subscore,
    _combine,
    _nutrition_subscore,
    _score_to_label,
    build_daily_health_score,
)

# Spec forbids these user-facing terms in addition to the shared forbidden set.
_SPEC_FORBIDDEN_TERMS = (*FORBIDDEN_TERMS, "효능", "진단", "치료", "처방")

_AS_OF = date(2026, 6, 10)


def _settings(tmp_path: Any) -> Settings:
    """Return settings with WIKI retrieval disabled for deterministic tests.

    Args:
        tmp_path: Temporary path used as an empty WIKI root.

    Returns:
        Settings object that yields no WIKI citations.
    """
    return Settings(
        _env_file=None,
        llm_wiki_path=tmp_path,
        llm_wiki_retrieval_enabled=False,
        llm_wiki_max_sources=0,
    )


def _profile_snapshot(
    *,
    birth_year: int | None = 1976,
    sex: str | None = "female",
    height_cm: Decimal | None = Decimal("160.00"),
    weight_kg: Decimal | None = Decimal("60.00"),
) -> BodyProfileSnapshot:
    """Return a body profile snapshot fixture.

    Args:
        birth_year: Birth year used for age derivation.
        sex: Biological sex value.
        height_cm: Height in centimeters.
        weight_kg: Weight in kilograms.

    Returns:
        Body profile snapshot ORM object.
    """
    now = datetime.now(UTC)
    return BodyProfileSnapshot(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        effective_at=now,
        source="manual",
        sex=sex,
        birth_year=birth_year,
        height_cm=height_cm,
        weight_kg=weight_kg,
        consent_snapshot={},
        created_at=now,
        updated_at=now,
    )


def _meal(*, kcal: float | None, sodium_mg: float | None) -> MealRecordResponse:
    """Return a confirmed meal response with bounded nutrition totals.

    Args:
        kcal: Total kilocalories, or None to omit.
        sodium_mg: Total sodium in milligrams, or None to omit.

    Returns:
        Confirmed meal record response.
    """
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    totals: dict[str, float] = {}
    if kcal is not None:
        totals["kcal"] = kcal
    if sodium_mg is not None:
        totals["sodium_mg"] = sodium_mg
    return MealRecordResponse(
        id=uuid4(),
        status=MealAnalysisStatus.CONFIRMED,
        meal_type=MealType.LUNCH,
        eaten_at=now,
        food_items=[],
        nutrition_summary={
            "status": "user_confirmed",
            "items_count": 1,
            "totals": totals,
        },
        confirmed_at=now,
        created_at=now,
    )


def test_activity_subscore_uses_v4_score() -> None:
    """Verify the activity subscore equals the capped v4 activity score."""
    snapshot = _profile_snapshot()
    result = _activity_subscore(
        steps=8000,
        profile_snapshot=snapshot,
        as_of=_AS_OF,
        chronic_diseases=[],
        smoking_status="never",
    )

    expected = calculate_activity_score(
        ActivityScoreRequest(
            profile=UserProfile(age=50, sex="female", height_cm=160.0, weight_kg=60.0),
            daily_steps=8000,
            target_hr_minutes=None,
            group_v2_scores=[],
        )
    ).v4_score
    assert result.subscore == min(expected, 100.0)


def test_activity_subscore_no_hr_does_not_add_penalty() -> None:
    """Verify missing heart-rate data uses the algorithm fallback without extra penalty."""
    snapshot = _profile_snapshot()
    result = _activity_subscore(
        steps=8000,
        profile_snapshot=snapshot,
        as_of=_AS_OF,
        chronic_diseases=[],
        smoking_status="never",
    )

    # The activity algorithm applies its own None->0.7 hr_factor fallback; the
    # subscore must match the algorithm output with no additional deduction.
    response = calculate_activity_score(
        ActivityScoreRequest(
            profile=UserProfile(age=50, sex="female", height_cm=160.0, weight_kg=60.0),
            daily_steps=8000,
            target_hr_minutes=None,
            group_v2_scores=[],
        )
    )
    assert response.hr_factor == 0.7
    assert result.subscore == min(response.v4_score, 100.0)


def test_activity_subscore_without_steps_is_none() -> None:
    """Verify the activity subscore is None when no steps are available."""
    result = _activity_subscore(
        steps=None,
        profile_snapshot=_profile_snapshot(),
        as_of=_AS_OF,
        chronic_diseases=[],
        smoking_status="never",
    )

    assert result.subscore is None


def test_nutrition_subscore_in_band_has_no_penalty() -> None:
    """Verify a kcal ratio within [0.8, 1.2] yields the baseline nutrition subscore."""
    snapshot = _profile_snapshot()
    tdee = daily_health_score._estimate_tdee(snapshot, as_of=_AS_OF)
    assert tdee is not None
    meals = [_meal(kcal=tdee, sodium_mg=1000)]

    result = _nutrition_subscore(meals=meals, profile_snapshot=snapshot, as_of=_AS_OF)

    assert result.subscore == 100.0
    assert result.drivers == ()


def test_nutrition_subscore_high_sodium_deducts_twenty() -> None:
    """Verify 4000mg sodium deducts 20 points (two 1000mg steps over 2000mg)."""
    snapshot = _profile_snapshot()
    tdee = daily_health_score._estimate_tdee(snapshot, as_of=_AS_OF)
    assert tdee is not None
    meals = [_meal(kcal=tdee, sodium_mg=4000)]

    result = _nutrition_subscore(meals=meals, profile_snapshot=snapshot, as_of=_AS_OF)

    assert result.subscore == 80.0
    assert "sodium_over" in result.drivers


def test_nutrition_subscore_no_meals_is_none() -> None:
    """Verify the nutrition subscore is None when there are no confirmed meals."""
    result = _nutrition_subscore(meals=[], profile_snapshot=_profile_snapshot(), as_of=_AS_OF)

    assert result.subscore is None


def test_combine_renormalizes_when_one_side_missing() -> None:
    """Verify a single available subscore renormalizes to weight 1.0 and is ready."""
    score, label, weights = _combine(activity_subscore=82.0, nutrition_subscore=None)

    assert score == 82
    assert label == "good"
    assert weights == (1.0, 0.0)


def test_combine_both_missing_is_not_ready() -> None:
    """Verify both subscores missing yields a None score for the not-ready state."""
    score, label, weights = _combine(activity_subscore=None, nutrition_subscore=None)

    assert score is None
    assert label is None
    assert weights == (0.0, 0.0)


def test_combine_weighted_average_rounds() -> None:
    """Verify combining 82 and 72 yields round(0.6*82 + 0.4*72) == 78."""
    score, label, weights = _combine(activity_subscore=82.0, nutrition_subscore=72.0)

    assert score == 78
    assert label == "good"
    assert weights == (0.6, 0.4)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (90, "excellent"),
        (89, "good"),
        (75, "good"),
        (74, "moderate"),
        (55, "moderate"),
        (54, "warning"),
        (35, "warning"),
        (34, "needs_attention"),
    ],
)
def test_score_to_label_boundaries(score: int, expected: str) -> None:
    """Verify label boundaries at 90, 75, 55, and 35."""
    assert _score_to_label(score) == expected


@pytest.mark.asyncio
async def test_messages_are_free_of_forbidden_terms(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Verify every produced message avoids forbidden diagnostic wording."""
    snapshot = _profile_snapshot()
    tdee = daily_health_score._estimate_tdee(snapshot, as_of=_AS_OF)
    assert tdee is not None

    async def fake_profile(*_args: object, **_kwargs: object) -> BodyProfileSnapshot:
        return snapshot

    async def fake_meals(*_args: object, **_kwargs: object) -> MealRecordListResponse:
        return MealRecordListResponse(
            results=[_meal(kcal=tdee, sodium_mg=3000)],
            limit=100,
            offset=0,
        )

    monkeypatch.setattr(daily_health_score, "get_latest_body_profile_snapshot", fake_profile)
    monkeypatch.setattr(daily_health_score, "list_user_meal_records", fake_meals)

    summary = await build_daily_health_score(
        session=object(),
        user=object(),
        as_of=_AS_OF,
        settings=_settings(tmp_path),
        health_summaries=[],
        health_context={"chronic_diseases": ["diabetes"], "smoking_status": "never"},
    )

    # Claim-bearing user-facing strings must avoid forbidden wording. The fixed
    # disclaimer is exempt: it negates ("의학적 진단이 아닙니다") rather than claims.
    assert summary.message is not None
    assert summary.label_text is not None
    for claim in (summary.message, summary.label_text):
        for term in _SPEC_FORBIDDEN_TERMS:
            assert term not in claim


@pytest.mark.asyncio
async def test_chronic_context_adds_expert_frame(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Verify chronic context adds the expert-consultation frame without disease claims."""
    snapshot = _profile_snapshot()

    async def fake_profile(*_args: object, **_kwargs: object) -> BodyProfileSnapshot:
        return snapshot

    async def fake_meals(*_args: object, **_kwargs: object) -> MealRecordListResponse:
        # Very low steps and high sodium push the score into the warning tier.
        return MealRecordListResponse(
            results=[_meal(kcal=200, sodium_mg=6000)],
            limit=100,
            offset=0,
        )

    health_row = _health_summary(steps=500)
    monkeypatch.setattr(daily_health_score, "get_latest_body_profile_snapshot", fake_profile)
    monkeypatch.setattr(daily_health_score, "list_user_meal_records", fake_meals)

    summary = await build_daily_health_score(
        session=object(),
        user=object(),
        as_of=_AS_OF,
        settings=_settings(tmp_path),
        health_summaries=[health_row],
        health_context={"chronic_diseases": ["diabetes"], "smoking_status": "never"},
    )

    assert summary.label in ("warning", "needs_attention")
    assert summary.message is not None
    assert "전문가" in summary.message
    assert "질환 개선" not in summary.message


@pytest.mark.asyncio
async def test_algorithm_version_is_echoed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Verify the algorithm version constant is echoed on the summary."""

    async def fake_profile(*_args: object, **_kwargs: object) -> BodyProfileSnapshot | None:
        return None

    async def fake_meals(*_args: object, **_kwargs: object) -> MealRecordListResponse:
        return MealRecordListResponse(results=[], limit=100, offset=0)

    monkeypatch.setattr(daily_health_score, "get_latest_body_profile_snapshot", fake_profile)
    monkeypatch.setattr(daily_health_score, "list_user_meal_records", fake_meals)

    summary = await build_daily_health_score(
        session=object(),
        user=object(),
        as_of=_AS_OF,
        settings=_settings(tmp_path),
        health_summaries=[],
    )

    assert summary.algorithm_version == DAILY_HEALTH_SCORE_ALGORITHM_VERSION
    assert summary.data_status == "not_ready"
    assert summary.score is None


def _health_summary(*, steps: int) -> HealthDailySummary:
    """Return a same-day health summary fixture with a step count.

    Args:
        steps: Step count for the day.

    Returns:
        Health daily summary ORM object.
    """
    now = datetime.now(UTC)
    return HealthDailySummary(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        measured_date=_AS_OF,
        source_platform="manual",
        steps=steps,
        synced_at=now,
        created_at=now,
        updated_at=now,
    )
