"""Deterministic per-serving / per-portion nutrition scaling for food classes.

The taxo59 ``food_nutrition`` rows store per-100g class-average values plus an
average ``serving_g``. The app shows either a portion-specific estimate (when a
portion weight is known) or the class single-serving estimate. Scaling is pure
arithmetic so it is safe to run inline in the meal preview path.

``serving_value = per_100g_value * grams / 100``
"""

from __future__ import annotations

from decimal import Decimal

# Bounded per-100g nutrient keys. These match the ``per_100g`` keys already used
# in ``food_catalog_items.nutrition_reference`` so downstream payloads stay consistent.
PER_100G_KEYS: tuple[str, ...] = (
    "kcal",
    "carb_g",
    "sugar_g",
    "fat_g",
    "protein_g",
    "sodium_mg",
    "cholesterol_mg",
    "saturated_fat_g",
    "trans_fat_g",
)

_MAX_GRAMS = 5000.0  # guard against absurd portions producing unbounded totals


def compute_serving_nutrition(
    per_100g: dict[str, float | Decimal | None],
    *,
    serving_g: float | Decimal | None,
    portion_g: float | Decimal | None = None,
) -> dict[str, float]:
    """Scale per-100g nutrients to a portion weight.

    Args:
        per_100g: Mapping of nutrient key -> per-100g value (None entries skipped).
        serving_g: Class average single-serving weight in grams (fallback basis).
        portion_g: Optional explicit portion weight in grams; preferred when given.

    Returns:
        Mapping of nutrient key -> scaled value (rounded to 2 decimals). Empty when
        no usable gram basis is available.
    """
    grams = portion_g if portion_g is not None else serving_g
    if grams is None:
        return {}
    grams_value = float(grams)
    if grams_value <= 0 or grams_value > _MAX_GRAMS:
        return {}
    factor = grams_value / 100.0
    scaled: dict[str, float] = {}
    for key, value in per_100g.items():
        if value is None:
            continue
        scaled[key] = round(float(value) * factor, 2)
    return scaled
