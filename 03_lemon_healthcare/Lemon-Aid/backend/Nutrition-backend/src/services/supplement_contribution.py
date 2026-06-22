"""Deterministic supplement nutrient contribution calculation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.supplement import UserSupplement, UserSupplementIngredient
from src.models.schemas.supplement import SupplementServing
from src.models.schemas.supplement_recommendation import (
    SupplementContributionAggregate,
    SupplementContributionItem,
)
from src.models.schemas.user import UserProfile
from src.nutrition.kdris import lookup_kdris_reference
from src.nutrition.unit_converter import UnitConversionError, convert_amount, normalize_unit
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject


@dataclass(frozen=True)
class SupplementContributionSource:
    """Confirmed supplement and its confirmed ingredient rows.

    Attributes:
        supplement: User-confirmed supplement row.
        ingredients: Ingredient rows owned by the supplement.
    """

    supplement: UserSupplement
    ingredients: tuple[UserSupplementIngredient, ...]


@dataclass(frozen=True)
class SupplementContributionResult:
    """Calculated supplement contribution result.

    Attributes:
        aggregates: Nutrient-code contribution aggregates.
        warnings: Safe warning strings for skipped or partial inputs.
        selected_missing_count: Number of requested supplement ids not available to the owner.
    """

    aggregates: tuple[SupplementContributionAggregate, ...]
    warnings: tuple[str, ...]
    selected_missing_count: int = 0


async def load_supplement_contribution_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    selected_supplement_ids: Iterable[UUID] = (),
    include_all_active_supplements: bool = True,
    profile: UserProfile | None = None,
) -> SupplementContributionResult:
    """Load current-user supplements and calculate daily nutrient contributions.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        selected_supplement_ids: Optional supplement id subset.
        include_all_active_supplements: Whether to include all active rows when no subset is set.
        profile: Optional profile used to convert totals to KDRI reference units.

    Returns:
        Deterministic supplement contribution result.
    """
    selected_ids = tuple(dict.fromkeys(selected_supplement_ids))
    sources = await _load_contribution_sources(
        session,
        user,
        selected_supplement_ids=selected_ids,
        include_all_active_supplements=include_all_active_supplements,
    )
    result = calculate_supplement_contributions(sources, profile=profile)
    missing_count = max(0, len(selected_ids) - len({source.supplement.id for source in sources}))
    if missing_count <= 0:
        return result
    return SupplementContributionResult(
        aggregates=result.aggregates,
        warnings=(
            *result.warnings,
            f"selected_supplement_missing:{missing_count}",
        ),
        selected_missing_count=missing_count,
    )


async def _load_contribution_sources(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    selected_supplement_ids: tuple[UUID, ...],
    include_all_active_supplements: bool,
) -> tuple[SupplementContributionSource, ...]:
    """Load supplement rows and child ingredients for contribution calculation.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        selected_supplement_ids: Optional selected supplement ids.
        include_all_active_supplements: Whether to include all active rows without a subset.

    Returns:
        Supplement source rows grouped with ingredient rows.
    """
    if not selected_supplement_ids and not include_all_active_supplements:
        return ()

    owner_subject = build_owner_subject(user)
    statement = select(UserSupplement).where(
        UserSupplement.owner_subject == owner_subject,
        UserSupplement.deleted_at.is_(None),
    )
    if selected_supplement_ids:
        statement = statement.where(UserSupplement.id.in_(selected_supplement_ids))

    rows = list((await session.scalars(statement)).all())
    ingredient_map = await _load_ingredients_by_supplement_id(
        session,
        [row.id for row in rows],
    )
    return tuple(
        SupplementContributionSource(
            supplement=row,
            ingredients=tuple(ingredient_map.get(row.id, ())),
        )
        for row in rows
    )


async def _load_ingredients_by_supplement_id(
    session: AsyncSession,
    supplement_ids: list[UUID],
) -> dict[UUID, tuple[UserSupplementIngredient, ...]]:
    """Load ingredient rows grouped by supplement id.

    Args:
        session: Request-scoped async database session.
        supplement_ids: Parent supplement ids.

    Returns:
        Mapping of supplement id to ingredient rows.
    """
    if not supplement_ids:
        return {}
    result = await session.scalars(
        select(UserSupplementIngredient).where(
            UserSupplementIngredient.user_supplement_id.in_(supplement_ids)
        )
    )
    grouped: dict[UUID, list[UserSupplementIngredient]] = {}
    for ingredient in result.all():
        grouped.setdefault(ingredient.user_supplement_id, []).append(ingredient)
    return {
        supplement_id: tuple(sorted(rows, key=lambda row: row.sort_order))
        for supplement_id, rows in grouped.items()
    }


def calculate_supplement_contributions(
    sources: Iterable[SupplementContributionSource],
    *,
    profile: UserProfile | None = None,
) -> SupplementContributionResult:
    """Calculate nutrient-code daily contributions from confirmed supplements.

    Args:
        sources: Confirmed supplement rows and child ingredients.
        profile: Optional profile used to resolve KDRI reference units.

    Returns:
        Contribution aggregates and safe warnings.
    """
    warnings: list[str] = []
    grouped_items: dict[str, list[SupplementContributionItem]] = {}

    for source in sources:
        serving = _validated_serving(source.supplement, warnings)
        if serving is None:
            continue
        for ingredient in source.ingredients:
            item = _contribution_item(source.supplement, ingredient, serving, warnings)
            if item is None:
                continue
            grouped_items.setdefault(item.nutrient_code, []).append(item)

    aggregates = [
        _aggregate_contribution(nutrient_code, items, profile)
        for nutrient_code, items in sorted(grouped_items.items())
    ]
    return SupplementContributionResult(
        aggregates=tuple(aggregates),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _validated_serving(
    supplement: UserSupplement,
    warnings: list[str],
) -> SupplementServing | None:
    """Validate the stored serving snapshot before using it for calculation.

    Args:
        supplement: User-confirmed supplement row.
        warnings: Mutable safe warning list.

    Returns:
        Valid serving or None when unusable.
    """
    try:
        serving = SupplementServing.model_validate(supplement.serving_snapshot)
    except ValidationError:
        warnings.append(f"supplement_serving_invalid:{supplement.id}")
        return None
    if serving.daily_servings <= 0:
        warnings.append(f"supplement_daily_servings_review_needed:{supplement.id}")
        return None
    return serving


def _contribution_item(
    supplement: UserSupplement,
    ingredient: UserSupplementIngredient,
    serving: SupplementServing,
    warnings: list[str],
) -> SupplementContributionItem | None:
    """Build one contribution item when required fields are present.

    Args:
        supplement: Parent user supplement row.
        ingredient: Confirmed ingredient row.
        serving: Validated serving snapshot.
        warnings: Mutable safe warning list.

    Returns:
        Contribution item or None when required fields are missing.
    """
    if not ingredient.nutrient_code:
        warnings.append(f"ingredient_nutrient_code_missing:{ingredient.id}")
        return None
    if ingredient.amount is None:
        warnings.append(f"ingredient_amount_missing:{ingredient.id}")
        return None
    if not ingredient.unit:
        warnings.append(f"ingredient_unit_missing:{ingredient.id}")
        return None

    amount = _float_amount(ingredient.amount)
    daily_amount = amount * serving.daily_servings
    return SupplementContributionItem(
        supplement_id=supplement.id,
        supplement_name=supplement.display_name,
        ingredient_id=ingredient.id,
        display_name=ingredient.display_name,
        nutrient_code=ingredient.nutrient_code,
        amount_per_serving=amount,
        unit=normalize_unit(ingredient.unit),
        daily_servings=serving.daily_servings,
        daily_amount=daily_amount,
        source=ingredient.source,
        confidence=_float_amount(ingredient.confidence),
    )


def _aggregate_contribution(
    nutrient_code: str,
    items: list[SupplementContributionItem],
    profile: UserProfile | None,
) -> SupplementContributionAggregate:
    """Aggregate contribution items for one nutrient code.

    Args:
        nutrient_code: Internal nutrient code.
        items: Contribution items with the same nutrient code.
        profile: Optional profile for KDRI reference-unit conversion.

    Returns:
        Contribution aggregate.
    """
    original_unit_totals = _original_unit_totals(items)
    reference_unit: str | None = None
    nutrient_name: str | None = None
    total_daily_amount: float | None = None
    warnings: list[str] = []

    if profile is not None:
        reference = lookup_kdris_reference(
            nutrient_code=nutrient_code,
            age=profile.age,
            sex=profile.sex,
            pregnancy_status=profile.pregnancy_status,
        )
        if reference is None:
            warnings.append("kdri_reference_missing")
        else:
            reference_unit = reference.reference_unit
            nutrient_name = reference.nutrient_name
            converted: list[float] = []
            for item in items:
                try:
                    converted.append(
                        convert_amount(
                            amount=item.daily_amount,
                            from_unit=item.unit,
                            to_unit=reference.reference_unit,
                            nutrient_code=nutrient_code,
                        )
                    )
                except UnitConversionError:
                    warnings.append(
                        f"unit_conversion_failed:{item.unit}->{reference.reference_unit}"
                    )
            if len(converted) == len(items):
                total_daily_amount = round(sum(converted), 3)

    return SupplementContributionAggregate(
        nutrient_code=nutrient_code,
        nutrient_name=nutrient_name,
        reference_unit=reference_unit,
        total_daily_amount=total_daily_amount,
        original_unit_totals=original_unit_totals,
        contribution_count=len(items),
        supplement_ids=list(dict.fromkeys(item.supplement_id for item in items)),
        items=items,
        warnings=list(dict.fromkeys(warnings)),
    )


def _original_unit_totals(items: Iterable[SupplementContributionItem]) -> dict[str, float]:
    """Return deterministic daily totals by original unit.

    Args:
        items: Contribution items.

    Returns:
        Unit-keyed daily totals.
    """
    totals: dict[str, float] = {}
    for item in items:
        totals[item.unit] = totals.get(item.unit, 0.0) + item.daily_amount
    return {unit: round(total, 3) for unit, total in sorted(totals.items())}


def _float_amount(value: Decimal | float | int) -> float:
    """Convert a numeric ORM value to float.

    Args:
        value: Decimal, float, or int value.

    Returns:
        Float value.
    """
    return float(value)
