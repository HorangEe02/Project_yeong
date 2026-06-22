"""Hall-lite dynamic weight prediction tests."""

from __future__ import annotations

import pytest
from src.prediction.body_composition import estimate_initial_composition
from src.prediction.hall import (
    BETA_AT,
    GAMMA_F_KJ_PER_KG_DAY,
    GAMMA_L_KJ_PER_KG_DAY,
    KJ_PER_KCAL,
    RHO_F_KJ_PER_KG,
    RHO_L_KJ_PER_KG,
    build_baseline,
    calculate_composition_rmr_kj,
    kcal_to_kj,
    kj_to_kcal,
    partition_energy_balance,
    predict_with_hall,
)
from src.prediction.weight import predict_weight_n_days


def test_kcal_kj_roundtrip() -> None:
    """Verify kcal/kJ conversions are reversible within floating-point tolerance."""
    kcal = 1745.0

    assert kj_to_kcal(kcal_to_kj(kcal)) == pytest.approx(kcal)
    assert pytest.approx(4.184) == KJ_PER_KCAL


def test_hall_lite_constants_are_kj_based() -> None:
    """Verify Hall-lite constants are pinned to kJ-based units."""
    assert GAMMA_F_KJ_PER_KG_DAY == 13.0
    assert GAMMA_L_KJ_PER_KG_DAY == 92.0
    assert RHO_F_KJ_PER_KG == 39_500.0
    assert RHO_L_KJ_PER_KG == 7_600.0
    assert BETA_AT == 0.14


def test_build_baseline_preserves_static_bmr_tdee() -> None:
    """Verify the dynamic baseline preserves existing BMR/TDEE outputs."""
    composition = estimate_initial_composition(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
    )
    baseline = build_baseline(
        composition=composition,
        height_cm=160.0,
        age=50,
        sex="female",
        daily_steps=6500,
    )

    assert kj_to_kcal(baseline.initial_bmr_kj) == pytest.approx(1269.0)
    assert kj_to_kcal(baseline.initial_tdee_kj) == pytest.approx(1745.0)
    assert baseline.rmr_intercept_kj + calculate_composition_rmr_kj(composition) == pytest.approx(
        baseline.initial_bmr_kj
    )


def test_partition_high_fat_mass_assigns_more_energy_to_fat() -> None:
    """Verify Forbes partition sends more energy change toward FM at higher FM."""
    low_fm = estimate_initial_composition(
        weight_kg=60.0,
        height_cm=180.0,
        age=30,
        sex="male",
        measured_body_fat_pct=12.0,
    )
    high_fm = estimate_initial_composition(
        weight_kg=100.0,
        height_cm=170.0,
        age=45,
        sex="female",
        measured_body_fat_pct=45.0,
    )

    low_delta_fm, _low_delta_ffm = partition_energy_balance(-1000.0, low_fm)
    high_delta_fm, _high_delta_ffm = partition_energy_balance(-1000.0, high_fm)

    assert abs(high_delta_fm) > abs(low_delta_fm)


def test_predict_maintenance_intake_stays_near_starting_weight() -> None:
    """Verify intake equal to baseline TDEE produces a stable trajectory."""
    result = predict_with_hall(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
        daily_steps=6500,
        daily_intake_kcal=1745.0,
        n_days=30,
    )

    assert result.initial_bmr_kcal == pytest.approx(1269.0)
    assert result.initial_tdee_kcal == pytest.approx(1745.0)
    assert result.predicted_weight_kg == pytest.approx(68.0, abs=0.01)
    assert result.weight_change_kg == pytest.approx(0.0, abs=0.01)


def test_predict_deficit_loses_weight_without_unbounded_drop() -> None:
    """Verify deficit predictions move downward without claiming precision."""
    hall = predict_with_hall(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
        daily_steps=6500,
        daily_intake_kcal=1500.0,
        n_days=90,
    )
    static = predict_weight_n_days(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
        daily_steps=6500,
        daily_intake_kcal=1500.0,
        days=90,
    )

    assert hall.predicted_weight_kg < 68.0
    assert hall.predicted_weight_kg > 60.0
    assert abs(hall.weight_change_kg) <= abs(static.theoretical_change_kg)


def test_adaptive_thermogenesis_moves_negative_during_deficit() -> None:
    """Verify adaptive thermogenesis reduces expenditure during a deficit."""
    result = predict_with_hall(
        weight_kg=68.0,
        height_cm=160.0,
        age=50,
        sex="female",
        daily_steps=6500,
        daily_intake_kcal=1500.0,
        n_days=30,
        save_daily_states=True,
    )

    assert result.daily_states
    assert result.daily_states[-1].adaptive_thermogenesis_kcal < 0.0


def test_predict_rejects_unsupported_period() -> None:
    """Verify unsupported simulation periods fail before producing output."""
    with pytest.raises(ValueError, match="n_days"):
        predict_with_hall(
            weight_kg=68.0,
            height_cm=160.0,
            age=50,
            sex="female",
            daily_steps=6500,
            daily_intake_kcal=1500.0,
            n_days=400,
        )
