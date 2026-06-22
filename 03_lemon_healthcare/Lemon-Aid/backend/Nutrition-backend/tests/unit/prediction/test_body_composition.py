"""Body composition estimator tests for Hall-lite."""

from __future__ import annotations

import pytest
from src.prediction.body_composition import (
    BodyComposition,
    estimate_body_fat_percentage,
    estimate_initial_composition,
)


def test_deurenberg_50f_example() -> None:
    """Verify the Deurenberg estimate used for the 50F baseline example."""
    body_fat_pct = estimate_body_fat_percentage(bmi=26.5, age=50, sex="female")

    assert body_fat_pct == pytest.approx(37.90)


def test_deurenberg_45m_example() -> None:
    """Verify the Deurenberg estimate for a male comparison example."""
    body_fat_pct = estimate_body_fat_percentage(bmi=26.7, age=45, sex="male")

    assert body_fat_pct == pytest.approx(26.19)


def test_estimate_initial_composition_uses_deurenberg_source() -> None:
    """Verify FM and FFM add up to total weight for estimated composition."""
    composition = estimate_initial_composition(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
    )

    assert composition.source == "deurenberg"
    assert composition.body_fat_pct == pytest.approx(37.98, abs=0.01)
    assert composition.fat_mass_kg + composition.fat_free_mass_kg == pytest.approx(68.0)


def test_estimate_initial_composition_prefers_measured_body_fat() -> None:
    """Verify a measured body-fat percentage is preferred over the estimate."""
    composition = estimate_initial_composition(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
        measured_body_fat_pct=30.0,
    )

    assert composition.source == "measured"
    assert composition.body_fat_pct == 30.0
    assert composition.fat_mass_kg == pytest.approx(20.4)
    assert composition.fat_free_mass_kg == pytest.approx(47.6)


def test_deurenberg_estimate_is_clamped_to_project_range() -> None:
    """Verify extreme estimates are clamped before simulation."""
    low = estimate_body_fat_percentage(bmi=10.0, age=18, sex="male")
    high = estimate_body_fat_percentage(bmi=60.0, age=80, sex="female")

    assert low == 5.0
    assert high == 50.0


def test_measured_body_fat_outside_supported_range_raises() -> None:
    """Verify measured values beyond the model guard fail explicitly."""
    with pytest.raises(ValueError, match="measured_body_fat_pct"):
        estimate_initial_composition(
            weight_kg=68.0,
            height_cm=160.0,
            age=50,
            sex="female",
            measured_body_fat_pct=80.0,
        )


def test_body_composition_accepts_simulated_source() -> None:
    """Verify Hall daily states can mark simulated compositions."""
    composition = BodyComposition(
        weight_kg=68.0,
        fat_mass_kg=25.0,
        fat_free_mass_kg=43.0,
        body_fat_pct=36.76,
        source="simulated",
    )

    assert composition.source == "simulated"
