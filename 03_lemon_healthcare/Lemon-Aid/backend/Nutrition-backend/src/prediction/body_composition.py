"""Body composition estimates for Hall-lite weight prediction."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.user import Sex

BodyCompositionSource = Literal["deurenberg", "measured", "simulated"]

DEURENBERG_BMI_COEF: Final[float] = 1.20
DEURENBERG_AGE_COEF: Final[float] = 0.23
DEURENBERG_MALE_SEX_COEF: Final[float] = 10.8
DEURENBERG_CONST: Final[float] = 5.4
DEURENBERG_MIN_BODY_FAT_PCT: Final[float] = 5.0
DEURENBERG_MAX_BODY_FAT_PCT: Final[float] = 50.0
MEASURED_MIN_BODY_FAT_PCT: Final[float] = 0.0
MEASURED_MAX_BODY_FAT_PCT: Final[float] = 70.0
ROUND_BODY_FAT_PCT_DECIMALS: Final[int] = 2
ROUND_COMPARTMENT_KG_DECIMALS: Final[int] = 3


class BodyComposition(BaseModel):
    """Fat mass and fat-free mass estimate for dynamic weight simulation.

    Attributes:
        weight_kg: Total body weight in kilograms.
        fat_mass_kg: Estimated fat mass in kilograms.
        fat_free_mass_kg: Estimated fat-free mass in kilograms.
        body_fat_pct: Estimated or measured body-fat percentage.
        source: Origin of the body composition estimate.
    """

    model_config = ConfigDict(frozen=True)

    weight_kg: float = Field(gt=0)
    fat_mass_kg: float = Field(ge=0)
    fat_free_mass_kg: float = Field(ge=0)
    body_fat_pct: float = Field(ge=0, le=MEASURED_MAX_BODY_FAT_PCT)
    source: BodyCompositionSource


def estimate_body_fat_percentage(bmi: float, age: int, sex: Sex) -> float:
    """Estimate adult body-fat percentage with the Deurenberg BMI equation.

    Args:
        bmi: Body mass index in kg/m^2.
        age: Age in years.
        sex: Biological sex accepted by the current algorithm schemas.

    Returns:
        Estimated body-fat percentage clamped to the project range.

    Raises:
        ValueError: If BMI is not positive or age is less than one.
    """
    if bmi <= 0:
        raise ValueError("bmi must be greater than 0")
    if age < 1:
        raise ValueError("age must be greater than or equal to 1")

    sex_factor = 1.0 if sex == "male" else 0.0
    body_fat_pct = (
        DEURENBERG_BMI_COEF * bmi
        + DEURENBERG_AGE_COEF * age
        - DEURENBERG_MALE_SEX_COEF * sex_factor
        - DEURENBERG_CONST
    )
    clamped = max(
        DEURENBERG_MIN_BODY_FAT_PCT,
        min(DEURENBERG_MAX_BODY_FAT_PCT, body_fat_pct),
    )
    return round(clamped, ROUND_BODY_FAT_PCT_DECIMALS)


def estimate_initial_composition(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    measured_body_fat_pct: float | None = None,
) -> BodyComposition:
    """Estimate initial fat mass and fat-free mass for Hall-lite simulation.

    Args:
        weight_kg: Current body weight in kilograms.
        height_cm: Height in centimeters.
        age: Age in years.
        sex: Biological sex accepted by the current algorithm schemas.
        measured_body_fat_pct: Optional measured body-fat percentage.

    Returns:
        Initial body composition with measured values preferred over estimates.

    Raises:
        ValueError: If weight, height, or measured body-fat percentage is invalid.
    """
    if weight_kg <= 0:
        raise ValueError("weight_kg must be greater than 0")
    if height_cm <= 0:
        raise ValueError("height_cm must be greater than 0")

    if measured_body_fat_pct is not None:
        if not MEASURED_MIN_BODY_FAT_PCT <= measured_body_fat_pct <= MEASURED_MAX_BODY_FAT_PCT:
            raise ValueError("measured_body_fat_pct must be between 0 and 70")
        body_fat_pct = round(measured_body_fat_pct, ROUND_BODY_FAT_PCT_DECIMALS)
        source: BodyCompositionSource = "measured"
    else:
        height_m = height_cm / 100.0
        bmi = weight_kg / (height_m * height_m)
        body_fat_pct = estimate_body_fat_percentage(bmi=bmi, age=age, sex=sex)
        source = "deurenberg"

    fat_mass_kg = round(
        weight_kg * body_fat_pct / 100.0,
        ROUND_COMPARTMENT_KG_DECIMALS,
    )
    fat_free_mass_kg = round(weight_kg - fat_mass_kg, ROUND_COMPARTMENT_KG_DECIMALS)

    return BodyComposition(
        weight_kg=weight_kg,
        fat_mass_kg=fat_mass_kg,
        fat_free_mass_kg=fat_free_mass_kg,
        body_fat_pct=body_fat_pct,
        source=source,
    )
