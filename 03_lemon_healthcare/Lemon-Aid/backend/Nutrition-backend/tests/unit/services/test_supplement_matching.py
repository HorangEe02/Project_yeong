"""Supplement product matching service tests."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.db.supplement import SupplementProduct, SupplementProductIngredient
from src.models.schemas.supplement import UserSupplementCreate
from src.services.supplement_matching import match_supplement_product, normalize_supplement_text


class _ScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, rows: Sequence[object]) -> None:
        self.rows = list(rows)

    def all(self) -> list[object]:
        """Return fake rows.

        Returns:
            Rows configured for the fake result.
        """
        return self.rows


class _FakeMatchSession:
    """Fake async session that returns products and ingredients in order."""

    def __init__(
        self,
        products: list[SupplementProduct],
        ingredients: list[SupplementProductIngredient],
    ) -> None:
        self._results = [_ScalarResult(products), _ScalarResult(ingredients)]

    async def scalars(self, _statement: object) -> _ScalarResult:
        """Return the next fake scalar result.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Fake scalar result.
        """
        return self._results.pop(0)


def _request(display_name: str = "Vitamin D 1000 IU") -> UserSupplementCreate:
    """Return a confirmed supplement request fixture.

    Args:
        display_name: User-confirmed supplement name.

    Returns:
        User supplement creation request.
    """
    return UserSupplementCreate.model_validate(
        {
            "display_name": display_name,
            "manufacturer": "Sample Nutrition",
            "ingredients": [
                {
                    "display_name": "Vitamin D",
                    "nutrient_code": "vitamin_d_ug",
                    "amount": 25,
                    "unit": "ug",
                    "confidence": 1,
                    "source": "user_confirmed",
                }
            ],
            "serving": {"amount": 1, "unit": "capsule", "daily_servings": 1},
            "user_confirmed": True,
        }
    )


def _product(product_name: str = "Vitamin D 1000 IU") -> SupplementProduct:
    """Return a reference supplement product fixture.

    Args:
        product_name: Product display name.

    Returns:
        Supplement product row.
    """
    return SupplementProduct(
        id=uuid4(),
        source_provider="mfds",
        source_product_id="P-001",
        product_name=product_name,
        normalized_product_name=normalize_supplement_text(product_name),
        manufacturer="Sample Nutrition",
        source_payload={},
        source_manifest_version="mfds-2026-05",
    )


def _ingredient(product_id: object) -> SupplementProductIngredient:
    """Return a reference supplement ingredient fixture.

    Args:
        product_id: Parent product identifier.

    Returns:
        Supplement product ingredient row.
    """
    return SupplementProductIngredient(
        id=uuid4(),
        product_id=product_id,
        standard_name="Vitamin D",
        nutrient_code="vitamin_d_ug",
        amount=Decimal("25"),
        unit="ug",
        source_payload={},
        sort_order=0,
    )


def test_normalize_supplement_text_collapses_case_and_symbols() -> None:
    """Verify text normalization is stable for product matching."""
    assert normalize_supplement_text("  Vitamin-D  1000 IU!! ") == "vitamin d 1000 iu"


@pytest.mark.asyncio
async def test_match_supplement_product_accepts_conservative_exact_match() -> None:
    """Verify exact product/manufacturer/ingredient matches are auto-accepted."""
    product = _product()
    session = _FakeMatchSession([product], [_ingredient(product.id)])

    result = await match_supplement_product(cast(AsyncSession, session), _request())

    assert result.matched_product_id == product.id
    assert result.matched_source_manifest_version == "mfds-2026-05"
    assert result.candidates[0].source_id == "mfds:P-001"
    assert result.candidates[0].match_score >= 0.92


@pytest.mark.asyncio
async def test_match_supplement_product_keeps_weak_match_as_candidate_only() -> None:
    """Verify weak fuzzy matches do not become authoritative product links."""
    product = _product("Calcium Complex")
    session = _FakeMatchSession([product], [_ingredient(product.id)])

    result = await match_supplement_product(cast(AsyncSession, session), _request())

    assert result.matched_product_id is None
    assert result.candidates
