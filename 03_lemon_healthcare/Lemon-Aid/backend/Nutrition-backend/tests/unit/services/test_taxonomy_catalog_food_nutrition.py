"""Food nutrition catalog repository and mapper tests."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.db.meal import FoodNutrition
from src.services.nutrition_scaling import PER_100G_KEYS
from src.services.taxonomy_catalog import (
    food_nutrition_per_100g,
    load_food_nutrition_by_class_en,
    load_food_nutrition_by_class_ens,
)


class _ScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, rows: Sequence[object]) -> None:
        """Store configured rows.

        Args:
            rows: Rows returned by ``all``.
        """
        self.rows = list(rows)

    def all(self) -> list[object]:
        """Return configured rows.

        Returns:
            Rows configured for the fake result.
        """
        return self.rows


class _FakeNutritionSession:
    """Fake async session returning configured food nutrition rows."""

    def __init__(self, rows: list[FoodNutrition]) -> None:
        """Initialize the fake session.

        Args:
            rows: Active food nutrition rows the query should return.
        """
        self.rows = rows
        self.scalars_calls = 0

    async def scalars(self, _statement: object) -> _ScalarResult:
        """Return the configured rows as a fake scalar result.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Fake scalar result.
        """
        self.scalars_calls += 1
        return _ScalarResult(self.rows)


def _row(class_en: str = "fried-chicken") -> FoodNutrition:
    """Return a seeded-style food nutrition row.

    Args:
        class_en: taxo59 class name used as the primary key.

    Returns:
        Active food nutrition row mirroring migration 0027 seed values.
    """
    return FoodNutrition(
        class_en=class_en,
        class_ko="후라이드치킨",
        n_source_codes=43,
        serving_g=Decimal("217.0"),
        kcal_100g=Decimal("236.26"),
        carb_g=Decimal("21.37"),
        sugar_g=Decimal("4.98"),
        fat_g=Decimal("11.69"),
        protein_g=Decimal("11.37"),
        sodium_mg=Decimal("355.92"),
        chol_mg=Decimal("14.93"),
        sat_fat_g=Decimal("0.4"),
        trans_fat_g=Decimal("0.83"),
        source="aihub_taxo59_csv",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_load_food_nutrition_by_class_en_returns_match() -> None:
    """Verify a single active class lookup returns its nutrition row."""
    session = _FakeNutritionSession([_row()])

    row = await load_food_nutrition_by_class_en(cast(AsyncSession, session), "fried-chicken")

    assert row is not None
    assert row.class_en == "fried-chicken"


@pytest.mark.asyncio
async def test_load_food_nutrition_by_class_en_missing_returns_none() -> None:
    """Verify an unmatched class lookup returns None."""
    session = _FakeNutritionSession([])

    row = await load_food_nutrition_by_class_en(cast(AsyncSession, session), "fried-chicken")

    assert row is None


@pytest.mark.asyncio
async def test_load_food_nutrition_by_class_en_blank_skips_query() -> None:
    """Verify blank class names short-circuit without a database round trip."""
    session = _FakeNutritionSession([_row()])

    row = await load_food_nutrition_by_class_en(cast(AsyncSession, session), "   ")

    assert row is None
    assert session.scalars_calls == 0


@pytest.mark.asyncio
async def test_load_food_nutrition_by_class_ens_keys_by_class_en() -> None:
    """Verify the batch lookup returns a mapping keyed by class_en."""
    rows = [_row("fried-chicken"), _row("mixed-rice-bowl")]
    session = _FakeNutritionSession(rows)

    result = await load_food_nutrition_by_class_ens(
        cast(AsyncSession, session),
        ["fried-chicken", "mixed-rice-bowl"],
    )

    assert set(result) == {"fried-chicken", "mixed-rice-bowl"}
    assert result["fried-chicken"].class_en == "fried-chicken"


@pytest.mark.asyncio
async def test_load_food_nutrition_by_class_ens_empty_input_skips_query() -> None:
    """Verify empty or blank-only inputs return an empty mapping without querying."""
    session = _FakeNutritionSession([_row()])

    result = await load_food_nutrition_by_class_ens(cast(AsyncSession, session), ["", "  "])

    assert result == {}
    assert session.scalars_calls == 0


def test_food_nutrition_per_100g_maps_typed_columns() -> None:
    """Verify typed columns map to PER_100G_KEYS with Decimal cast to float."""
    per_100g = food_nutrition_per_100g(_row())

    assert set(per_100g) == set(PER_100G_KEYS)
    assert per_100g["kcal"] == 236.26
    assert per_100g["cholesterol_mg"] == 14.93
    assert per_100g["saturated_fat_g"] == 0.4
    assert all(value is None or isinstance(value, float) for value in per_100g.values())


def test_food_nutrition_per_100g_preserves_none() -> None:
    """Verify missing typed columns stay None in the per-100g mapping."""
    row = _row("fried-rice")
    row.kcal_100g = Decimal("176.6")
    row.trans_fat_g = None
    row.sugar_g = None

    per_100g = food_nutrition_per_100g(row)

    assert per_100g["kcal"] == 176.6
    assert per_100g["trans_fat_g"] is None
    assert per_100g["sugar_g"] is None
