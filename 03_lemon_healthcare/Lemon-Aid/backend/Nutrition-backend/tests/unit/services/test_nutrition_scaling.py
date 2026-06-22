"""Per-serving nutrition scaling helper tests."""

from __future__ import annotations

from decimal import Decimal

from src.services.nutrition_scaling import PER_100G_KEYS, compute_serving_nutrition


def test_compute_serving_nutrition_scales_by_serving_grams() -> None:
    """Verify per-100g values scale by the class serving weight."""
    result = compute_serving_nutrition(
        {"kcal": 236.26, "protein_g": 11.37},
        serving_g=217.0,
    )

    # value * grams / 100; 236.26 * 217.0 / 100 = 512.68 (rounded to 2 places).
    assert result == {"kcal": 512.68, "protein_g": 24.67}


def test_compute_serving_nutrition_prefers_portion_over_serving() -> None:
    """Verify an explicit portion weight overrides the class serving weight."""
    result = compute_serving_nutrition(
        {"kcal": 100.0},
        serving_g=200.0,
        portion_g=50.0,
    )

    assert result == {"kcal": 50.0}


def test_compute_serving_nutrition_accepts_decimal_inputs() -> None:
    """Verify Decimal per-100g and gram inputs are handled without error."""
    result = compute_serving_nutrition(
        {"kcal": Decimal("176.6"), "carb_g": Decimal("31.5")},
        serving_g=Decimal("247.0"),
    )

    assert result == {"kcal": 436.20, "carb_g": 77.81}


def test_compute_serving_nutrition_skips_none_values() -> None:
    """Verify None per-100g entries are dropped from the scaled result."""
    result = compute_serving_nutrition(
        {"kcal": 100.0, "trans_fat_g": None},
        serving_g=100.0,
    )

    assert result == {"kcal": 100.0}
    assert "trans_fat_g" not in result


def test_compute_serving_nutrition_returns_empty_without_gram_basis() -> None:
    """Verify a missing gram basis yields an empty estimate."""
    assert compute_serving_nutrition({"kcal": 100.0}, serving_g=None) == {}


def test_compute_serving_nutrition_returns_empty_for_nonpositive_grams() -> None:
    """Verify zero or negative gram bases produce no estimate."""
    assert compute_serving_nutrition({"kcal": 100.0}, serving_g=0.0) == {}
    assert compute_serving_nutrition({"kcal": 100.0}, serving_g=-25.0) == {}


def test_compute_serving_nutrition_returns_empty_for_over_max_grams() -> None:
    """Verify absurd portions above the guard ceiling produce no estimate."""
    assert compute_serving_nutrition({"kcal": 100.0}, serving_g=10_000.0) == {}
    assert compute_serving_nutrition({"kcal": 100.0}, portion_g=10_000.0, serving_g=200.0) == {}


def test_per_100g_keys_are_stable_and_unique() -> None:
    """Verify the bounded per-100g key contract stays stable and unique."""
    assert "kcal" in PER_100G_KEYS
    assert "cholesterol_mg" in PER_100G_KEYS
    assert len(set(PER_100G_KEYS)) == len(PER_100G_KEYS)
