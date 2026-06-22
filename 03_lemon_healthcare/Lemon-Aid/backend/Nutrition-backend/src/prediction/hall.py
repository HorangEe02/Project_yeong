"""Hall-lite dynamic weight prediction primitives.

The implementation intentionally keeps the current API boundary in kcal/day
while running Hall-lite energy calculations in kJ/day internally.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from src.algorithms.metabolism import calculate_bmr, calculate_tdee
from src.models.schemas.user import Sex
from src.prediction.body_composition import (
    BodyComposition,
    estimate_initial_composition,
)

KJ_PER_KCAL: Final[float] = 4.184
GAMMA_F_KJ_PER_KG_DAY: Final[float] = 13.0
GAMMA_L_KJ_PER_KG_DAY: Final[float] = 92.0
RHO_F_KJ_PER_KG: Final[float] = 39_500.0
RHO_L_KJ_PER_KG: Final[float] = 7_600.0
FORBES_C_MASS_KG: Final[float] = 10.4
FORBES_C_ENERGY_PARTITION_KG: Final[float] = FORBES_C_MASS_KG * RHO_L_KJ_PER_KG / RHO_F_KJ_PER_KG
BETA_TEF: Final[float] = 0.10
BETA_AT: Final[float] = 0.14
TAU_AT_DAYS: Final[float] = 14.0
MAX_SIMULATION_DAYS: Final[int] = 365
MIN_COMPARTMENT_MASS_KG: Final[float] = 0.1
ROUND_ENERGY_DECIMALS: Final[int] = 1
ROUND_WEIGHT_DECIMALS: Final[int] = 2
ROUND_COMPARTMENT_DECIMALS: Final[int] = 6
HALL_LITE_ALGORITHM_VERSION: Final[str] = "weight-hall-lite-v0.1.0"


class HallBaseline(BaseModel):
    """Initial energy baseline aligned with the existing BMR/TDEE functions.

    Attributes:
        initial_weight_kg: Starting body weight in kilograms.
        initial_bmr_kj: Existing Mifflin-St Jeor BMR converted to kJ/day.
        initial_tdee_kj: Existing activity-factor TDEE converted to kJ/day.
        baseline_intake_kj: Maintenance intake assumption in kJ/day.
        baseline_paee_kj: Physical activity energy expenditure in kJ/day.
        rmr_intercept_kj: Intercept preserving the existing baseline BMR.
    """

    model_config = ConfigDict(frozen=True)

    initial_weight_kg: float = Field(gt=0)
    initial_bmr_kj: float = Field(gt=0)
    initial_tdee_kj: float = Field(gt=0)
    baseline_intake_kj: float = Field(gt=0)
    baseline_paee_kj: float = Field(ge=0)
    rmr_intercept_kj: float


class DailyState(BaseModel):
    """One simulated day in the Hall-lite trajectory.

    Attributes:
        day: Simulated day index, starting at one.
        composition: End-of-day body composition.
        rmr_kcal: Resting metabolic rate in kcal/day.
        paee_kcal: Physical activity energy expenditure in kcal/day.
        tef_kcal: Thermic effect of food in kcal/day.
        adaptive_thermogenesis_kcal: Adaptive thermogenesis term in kcal/day.
        tdee_kcal: Total daily energy expenditure in kcal/day.
        intake_kcal: Target daily intake in kcal/day.
        energy_balance_kcal: Intake minus expenditure in kcal/day.
    """

    model_config = ConfigDict(frozen=True)

    day: int = Field(ge=1)
    composition: BodyComposition
    rmr_kcal: float
    paee_kcal: float
    tef_kcal: float
    adaptive_thermogenesis_kcal: float
    tdee_kcal: float
    intake_kcal: float
    energy_balance_kcal: float


class HallLiteResult(BaseModel):
    """Hall-lite prediction output independent from the public API schema.

    Attributes:
        starting_weight_kg: Starting body weight in kilograms.
        initial_composition: Initial estimated or measured body composition.
        final_composition: Final simulated body composition.
        daily_states: Optional saved daily states for tests and future charts.
        predicted_weight_kg: Final predicted body weight in kilograms.
        predicted_fat_mass_kg: Final simulated fat mass in kilograms.
        predicted_fat_free_mass_kg: Final simulated fat-free mass in kilograms.
        weight_change_kg: Difference between final and starting body weight.
        period_days: Number of simulated days.
        initial_bmr_kcal: Baseline BMR from the existing metabolism module.
        initial_tdee_kcal: Baseline TDEE from the existing metabolism module.
        cumulative_energy_balance_kcal: Sum of simulated daily energy balances.
        algorithm_version: Internal Hall-lite algorithm version.
    """

    model_config = ConfigDict(frozen=True)

    starting_weight_kg: float
    initial_composition: BodyComposition
    final_composition: BodyComposition
    daily_states: list[DailyState] = Field(default_factory=list)
    predicted_weight_kg: float
    predicted_fat_mass_kg: float
    predicted_fat_free_mass_kg: float
    weight_change_kg: float
    period_days: int
    initial_bmr_kcal: float
    initial_tdee_kcal: float
    cumulative_energy_balance_kcal: float
    algorithm_version: str = HALL_LITE_ALGORITHM_VERSION


def kcal_to_kj(value: float) -> float:
    """Convert kcal to kJ.

    Args:
        value: Energy value in kcal.

    Returns:
        Energy value in kJ.
    """
    return value * KJ_PER_KCAL


def kj_to_kcal(value: float) -> float:
    """Convert kJ to kcal.

    Args:
        value: Energy value in kJ.

    Returns:
        Energy value in kcal.
    """
    return value / KJ_PER_KCAL


def calculate_composition_rmr_kj(composition: BodyComposition) -> float:
    """Calculate the Hall composition RMR term in kJ/day.

    Args:
        composition: Current fat mass and fat-free mass.

    Returns:
        RMR component from FM/FFM coefficients in kJ/day.
    """
    return (
        GAMMA_F_KJ_PER_KG_DAY * composition.fat_mass_kg
        + GAMMA_L_KJ_PER_KG_DAY * composition.fat_free_mass_kg
    )


def build_baseline(
    *,
    composition: BodyComposition,
    height_cm: float,
    age: int,
    sex: Sex,
    daily_steps: int,
    walking_cadence_steps_per_min: float | None = None,
    walking_cadence_minutes: float = 0.0,
    exercise_average_heart_rate_bpm: float | None = None,
    heart_rate_exercise_minutes: float = 0.0,
) -> HallBaseline:
    """Build an initial baseline that preserves existing BMR/TDEE behavior.

    Args:
        composition: Initial body composition.
        height_cm: Height in centimeters.
        age: Age in years.
        sex: Biological sex accepted by the current algorithm schemas.
        daily_steps: Daily step count.
        walking_cadence_steps_per_min: Optional walking cadence in steps/min.
        walking_cadence_minutes: Minutes observed at the walking cadence.
        exercise_average_heart_rate_bpm: Average exercise heart rate in bpm.
        heart_rate_exercise_minutes: Minutes observed at that average heart rate.

    Returns:
        Baseline energy terms in kJ/day.
    """
    initial_bmr_kcal = calculate_bmr(
        weight_kg=composition.weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
    )
    initial_tdee_kcal = calculate_tdee(
        estimated_bmr=initial_bmr_kcal,
        daily_steps=daily_steps,
        weight_kg=composition.weight_kg,
        age=age,
        sex=sex,
        walking_cadence_steps_per_min=walking_cadence_steps_per_min,
        walking_cadence_minutes=walking_cadence_minutes,
        exercise_average_heart_rate_bpm=exercise_average_heart_rate_bpm,
        heart_rate_exercise_minutes=heart_rate_exercise_minutes,
    )
    initial_bmr_kj = kcal_to_kj(initial_bmr_kcal)
    initial_tdee_kj = kcal_to_kj(initial_tdee_kcal)
    baseline_intake_kj = initial_tdee_kj
    baseline_tef_kj = BETA_TEF * baseline_intake_kj
    baseline_paee_kj = max(0.0, initial_tdee_kj - initial_bmr_kj - baseline_tef_kj)
    rmr_intercept_kj = initial_bmr_kj - calculate_composition_rmr_kj(composition)

    return HallBaseline(
        initial_weight_kg=composition.weight_kg,
        initial_bmr_kj=initial_bmr_kj,
        initial_tdee_kj=initial_tdee_kj,
        baseline_intake_kj=baseline_intake_kj,
        baseline_paee_kj=baseline_paee_kj,
        rmr_intercept_kj=rmr_intercept_kj,
    )


def calculate_dynamic_rmr_kj(composition: BodyComposition, baseline: HallBaseline) -> float:
    """Calculate dynamic RMR while preserving the initial BMR intercept.

    Args:
        composition: Current body composition.
        baseline: Initial baseline with BMR intercept.

    Returns:
        Dynamic RMR in kJ/day.
    """
    return max(0.0, baseline.rmr_intercept_kj + calculate_composition_rmr_kj(composition))


def partition_energy_balance(
    energy_balance_kj: float,
    composition: BodyComposition,
) -> tuple[float, float]:
    """Split energy balance into fat mass and fat-free mass changes.

    Args:
        energy_balance_kj: Daily intake minus expenditure in kJ/day.
        composition: Current body composition.

    Returns:
        Tuple of ``(delta_fat_mass_kg, delta_fat_free_mass_kg)``.
    """
    p_lean_energy = FORBES_C_ENERGY_PARTITION_KG / (
        FORBES_C_ENERGY_PARTITION_KG + composition.fat_mass_kg
    )
    delta_fat_mass_kg = energy_balance_kj * (1.0 - p_lean_energy) / RHO_F_KJ_PER_KG
    delta_fat_free_mass_kg = energy_balance_kj * p_lean_energy / RHO_L_KJ_PER_KG
    return delta_fat_mass_kg, delta_fat_free_mass_kg


def _composition_from_masses(fat_mass_kg: float, fat_free_mass_kg: float) -> BodyComposition:
    """Build a simulated body composition from compartment masses.

    Args:
        fat_mass_kg: Simulated fat mass in kilograms.
        fat_free_mass_kg: Simulated fat-free mass in kilograms.

    Returns:
        Simulated body composition with rounded compartment values.
    """
    bounded_fat_mass_kg = max(MIN_COMPARTMENT_MASS_KG, fat_mass_kg)
    bounded_fat_free_mass_kg = max(MIN_COMPARTMENT_MASS_KG, fat_free_mass_kg)
    weight_kg = bounded_fat_mass_kg + bounded_fat_free_mass_kg
    body_fat_pct = bounded_fat_mass_kg / weight_kg * 100.0

    return BodyComposition(
        weight_kg=round(weight_kg, ROUND_COMPARTMENT_DECIMALS),
        fat_mass_kg=round(bounded_fat_mass_kg, ROUND_COMPARTMENT_DECIMALS),
        fat_free_mass_kg=round(bounded_fat_free_mass_kg, ROUND_COMPARTMENT_DECIMALS),
        body_fat_pct=round(body_fat_pct, ROUND_WEIGHT_DECIMALS),
        source="simulated",
    )


def step_one_day(
    *,
    day: int,
    composition: BodyComposition,
    baseline: HallBaseline,
    target_intake_kcal: float,
    adaptive_thermogenesis_kj: float,
) -> tuple[BodyComposition, DailyState, float]:
    """Advance one Hall-lite simulation day.

    Args:
        day: Simulated day index, starting at one.
        composition: Body composition at the beginning of the day.
        baseline: Initial energy baseline.
        target_intake_kcal: Scenario intake in kcal/day.
        adaptive_thermogenesis_kj: Current adaptive thermogenesis in kJ/day.

    Returns:
        New composition, saved daily state, and next adaptive thermogenesis.
    """
    target_intake_kj = kcal_to_kj(target_intake_kcal)
    rmr_kj = calculate_dynamic_rmr_kj(composition=composition, baseline=baseline)
    paee_kj = baseline.baseline_paee_kj * (composition.weight_kg / baseline.initial_weight_kg)
    tef_kj = BETA_TEF * target_intake_kj
    tdee_kj = rmr_kj + paee_kj + tef_kj + adaptive_thermogenesis_kj
    energy_balance_kj = target_intake_kj - tdee_kj
    delta_fat_mass_kg, delta_fat_free_mass_kg = partition_energy_balance(
        energy_balance_kj=energy_balance_kj,
        composition=composition,
    )
    new_composition = _composition_from_masses(
        fat_mass_kg=composition.fat_mass_kg + delta_fat_mass_kg,
        fat_free_mass_kg=composition.fat_free_mass_kg + delta_fat_free_mass_kg,
    )

    target_adaptive_thermogenesis_kj = BETA_AT * (target_intake_kj - baseline.baseline_intake_kj)
    next_adaptive_thermogenesis_kj = (
        adaptive_thermogenesis_kj
        + (target_adaptive_thermogenesis_kj - adaptive_thermogenesis_kj) / TAU_AT_DAYS
    )

    state = DailyState(
        day=day,
        composition=new_composition,
        rmr_kcal=round(kj_to_kcal(rmr_kj), ROUND_ENERGY_DECIMALS),
        paee_kcal=round(kj_to_kcal(paee_kj), ROUND_ENERGY_DECIMALS),
        tef_kcal=round(kj_to_kcal(tef_kj), ROUND_ENERGY_DECIMALS),
        adaptive_thermogenesis_kcal=round(
            kj_to_kcal(adaptive_thermogenesis_kj),
            ROUND_ENERGY_DECIMALS,
        ),
        tdee_kcal=round(kj_to_kcal(tdee_kj), ROUND_ENERGY_DECIMALS),
        intake_kcal=round(target_intake_kcal, ROUND_ENERGY_DECIMALS),
        energy_balance_kcal=round(kj_to_kcal(energy_balance_kj), ROUND_ENERGY_DECIMALS),
    )
    return new_composition, state, next_adaptive_thermogenesis_kj


def predict_with_hall(
    *,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    daily_steps: int,
    daily_intake_kcal: float,
    n_days: int,
    measured_body_fat_pct: float | None = None,
    walking_cadence_steps_per_min: float | None = None,
    walking_cadence_minutes: float = 0.0,
    exercise_average_heart_rate_bpm: float | None = None,
    heart_rate_exercise_minutes: float = 0.0,
    save_daily_states: bool = False,
) -> HallLiteResult:
    """Predict body weight with the Hall-lite dynamic simulator.

    Args:
        weight_kg: Starting body weight in kilograms.
        height_cm: Height in centimeters.
        age: Age in years.
        sex: Biological sex accepted by the current algorithm schemas.
        daily_steps: Daily step count.
        daily_intake_kcal: Scenario intake in kcal/day.
        n_days: Simulation period in days.
        measured_body_fat_pct: Optional measured body-fat percentage.
        walking_cadence_steps_per_min: Optional walking cadence in steps/min.
        walking_cadence_minutes: Minutes observed at the walking cadence.
        exercise_average_heart_rate_bpm: Average exercise heart rate in bpm.
        heart_rate_exercise_minutes: Minutes observed at that average heart rate.
        save_daily_states: Whether to retain daily states in the result.

    Returns:
        Internal Hall-lite prediction result.

    Raises:
        ValueError: If the simulation period or intake is outside supported bounds.
    """
    if not 1 <= n_days <= MAX_SIMULATION_DAYS:
        raise ValueError("n_days must be between 1 and 365")
    if daily_intake_kcal < 0:
        raise ValueError("daily_intake_kcal must be greater than or equal to 0")
    if daily_steps < 0:
        raise ValueError("daily_steps must be greater than or equal to 0")

    initial_composition = estimate_initial_composition(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        measured_body_fat_pct=measured_body_fat_pct,
    )
    baseline = build_baseline(
        composition=initial_composition,
        height_cm=height_cm,
        age=age,
        sex=sex,
        daily_steps=daily_steps,
        walking_cadence_steps_per_min=walking_cadence_steps_per_min,
        walking_cadence_minutes=walking_cadence_minutes,
        exercise_average_heart_rate_bpm=exercise_average_heart_rate_bpm,
        heart_rate_exercise_minutes=heart_rate_exercise_minutes,
    )

    composition = initial_composition
    adaptive_thermogenesis_kj = 0.0
    cumulative_energy_balance_kcal = 0.0
    daily_states: list[DailyState] = []

    for day in range(1, n_days + 1):
        composition, state, adaptive_thermogenesis_kj = step_one_day(
            day=day,
            composition=composition,
            baseline=baseline,
            target_intake_kcal=daily_intake_kcal,
            adaptive_thermogenesis_kj=adaptive_thermogenesis_kj,
        )
        cumulative_energy_balance_kcal += state.energy_balance_kcal
        if save_daily_states:
            daily_states.append(state)

    return HallLiteResult(
        starting_weight_kg=weight_kg,
        initial_composition=initial_composition,
        final_composition=composition,
        daily_states=daily_states,
        predicted_weight_kg=round(composition.weight_kg, ROUND_WEIGHT_DECIMALS),
        predicted_fat_mass_kg=round(composition.fat_mass_kg, ROUND_WEIGHT_DECIMALS),
        predicted_fat_free_mass_kg=round(
            composition.fat_free_mass_kg,
            ROUND_WEIGHT_DECIMALS,
        ),
        weight_change_kg=round(composition.weight_kg - weight_kg, ROUND_WEIGHT_DECIMALS),
        period_days=n_days,
        initial_bmr_kcal=round(kj_to_kcal(baseline.initial_bmr_kj), ROUND_ENERGY_DECIMALS),
        initial_tdee_kcal=round(kj_to_kcal(baseline.initial_tdee_kj), ROUND_ENERGY_DECIMALS),
        cumulative_energy_balance_kcal=round(
            cumulative_energy_balance_kcal,
            ROUND_ENERGY_DECIMALS,
        ),
    )
