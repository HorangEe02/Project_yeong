"""Read-only supplement and food taxonomy catalog services."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.meal import FoodCatalogItem, FoodCourse, FoodCuisine, FoodNutrition
from src.models.db.supplement import SupplementCategory
from src.models.schemas.taxonomy import (
    FoodCatalogItemListResponse,
    FoodCatalogItemReference,
    FoodCatalogItemSummary,
    FoodCourseSummary,
    FoodCuisineListResponse,
    FoodCuisineSummary,
    SupplementCategoryListResponse,
    SupplementCategorySummary,
)
from src.services.nutrition_scaling import PER_100G_KEYS


class TaxonomyFilterNotFoundError(ValueError):
    """Raised when a user-data taxonomy filter references no active catalog row."""


async def list_supplement_categories(
    session: AsyncSession,
    *,
    q: str | None,
    limit: int,
    offset: int,
) -> SupplementCategoryListResponse:
    """List active supplement categories for selection UIs.

    Args:
        session: Request-scoped async database session.
        q: Optional display-name or category-key substring.
        limit: Maximum row count.
        offset: Row offset.

    Returns:
        Paginated active supplement category response.
    """
    stmt = select(SupplementCategory).where(SupplementCategory.is_active.is_(True))
    query_text = _normalized_query(q)
    if query_text:
        pattern = _contains_pattern(query_text)
        stmt = stmt.where(
            or_(
                SupplementCategory.category_key.ilike(pattern),
                SupplementCategory.display_name.ilike(pattern),
            )
        )
    rows = await session.scalars(
        stmt.order_by(SupplementCategory.sort_order.asc(), SupplementCategory.display_name.asc())
        .limit(limit)
        .offset(offset)
    )
    return SupplementCategoryListResponse(
        results=[_supplement_category_summary(row) for row in rows.all()],
        limit=limit,
        offset=offset,
    )


async def resolve_supplement_category_filter(
    session: AsyncSession,
    *,
    category_key: str | None,
    category_id: UUID | None,
) -> SupplementCategory | None:
    """Resolve an optional active supplement category filter for user-data queries.

    Args:
        session: Request-scoped async database session.
        category_key: Optional category key.
        category_id: Optional category id.

    Returns:
        Active category row or None when no filter is supplied.

    Raises:
        TaxonomyFilterNotFoundError: If a supplied filter has no active match.
    """
    normalized_key = _normalized_query(category_key)
    if normalized_key is None and category_id is None:
        return None

    stmt = select(SupplementCategory).where(SupplementCategory.is_active.is_(True))
    if normalized_key is not None:
        stmt = stmt.where(SupplementCategory.category_key == normalized_key)
    if category_id is not None:
        stmt = stmt.where(SupplementCategory.id == category_id)
    category = await session.scalar(stmt)
    if category is None:
        raise TaxonomyFilterNotFoundError("Supplement category filter was not found.")
    return category


async def list_food_cuisines(session: AsyncSession) -> FoodCuisineListResponse:
    """List active food cuisines and active child courses.

    Args:
        session: Request-scoped async database session.

    Returns:
        Active cuisine catalog response with nested courses.
    """
    cuisines = list(
        (
            await session.scalars(
                select(FoodCuisine)
                .where(FoodCuisine.is_active.is_(True))
                .order_by(FoodCuisine.sort_order.asc(), FoodCuisine.display_name_ko.asc())
            )
        ).all()
    )
    cuisine_ids = [cuisine.id for cuisine in cuisines]
    courses_by_cuisine: dict[UUID, list[FoodCourseSummary]] = defaultdict(list)
    if cuisine_ids:
        courses = await session.scalars(
            select(FoodCourse)
            .where(
                FoodCourse.is_active.is_(True),
                FoodCourse.cuisine_id.in_(cuisine_ids),
            )
            .order_by(FoodCourse.cuisine_id.asc(), FoodCourse.sort_order.asc())
        )
        for course in courses.all():
            courses_by_cuisine[course.cuisine_id].append(_food_course_summary(course))

    return FoodCuisineListResponse(
        results=[
            FoodCuisineSummary(
                id=cuisine.id,
                cuisine_code=cuisine.cuisine_code,
                display_name_ko=cuisine.display_name_ko,
                display_name_en=cuisine.display_name_en,
                sort_order=cuisine.sort_order,
                courses=courses_by_cuisine.get(cuisine.id, []),
            )
            for cuisine in cuisines
        ]
    )


async def list_food_catalog_items(
    session: AsyncSession,
    *,
    cuisine_code: str | None,
    course_code: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> FoodCatalogItemListResponse:
    """List active food catalog items for selection UIs.

    Args:
        session: Request-scoped async database session.
        cuisine_code: Optional cuisine code filter.
        course_code: Optional course code filter.
        q: Optional canonical-name substring.
        limit: Maximum row count.
        offset: Row offset.

    Returns:
        Paginated active food catalog item response.
    """
    stmt = _active_food_catalog_select()
    stmt = _apply_food_catalog_filters(
        stmt,
        cuisine_code=cuisine_code,
        course_code=course_code,
        q=q,
    )
    result = await session.execute(
        stmt.order_by(
            FoodCuisine.sort_order.asc(),
            FoodCourse.sort_order.asc(),
            FoodCatalogItem.canonical_name_ko.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return FoodCatalogItemListResponse(
        results=[
            _food_catalog_item_summary(item, cuisine_code, course_code)
            for item, cuisine_code, course_code in result.all()
        ],
        limit=limit,
        offset=offset,
    )


async def validate_food_catalog_filters(
    session: AsyncSession,
    *,
    cuisine_code: str | None,
    course_code: str | None,
    food_catalog_item_id: UUID | None,
) -> None:
    """Validate taxonomy filters before applying them to user-owned meal queries.

    Args:
        session: Request-scoped async database session.
        cuisine_code: Optional cuisine code filter.
        course_code: Optional course code filter.
        food_catalog_item_id: Optional food catalog item id filter.

    Raises:
        TaxonomyFilterNotFoundError: If any supplied taxonomy filter has no active match.
    """
    normalized_cuisine = _normalized_query(cuisine_code)
    normalized_course = _normalized_query(course_code)
    if normalized_cuisine is not None:
        cuisine = await session.scalar(
            select(FoodCuisine).where(
                FoodCuisine.cuisine_code == normalized_cuisine,
                FoodCuisine.is_active.is_(True),
            )
        )
        if cuisine is None:
            raise TaxonomyFilterNotFoundError("Food cuisine filter was not found.")
    if normalized_course is not None:
        course_stmt = (
            select(FoodCourse)
            .join(FoodCuisine, FoodCourse.cuisine_id == FoodCuisine.id)
            .where(
                FoodCourse.course_code == normalized_course,
                FoodCourse.is_active.is_(True),
                FoodCuisine.is_active.is_(True),
            )
        )
        if normalized_cuisine is not None:
            course_stmt = course_stmt.where(FoodCuisine.cuisine_code == normalized_cuisine)
        course = await session.scalar(course_stmt)
        if course is None:
            raise TaxonomyFilterNotFoundError("Food course filter was not found.")
    if (
        food_catalog_item_id is not None
        and await load_food_catalog_item_reference(session, food_catalog_item_id) is None
    ):
        raise TaxonomyFilterNotFoundError("Food catalog item filter was not found.")


async def load_food_catalog_item_reference(
    session: AsyncSession,
    food_catalog_item_id: UUID,
) -> FoodCatalogItemReference | None:
    """Load one active food catalog item reference.

    Args:
        session: Request-scoped async database session.
        food_catalog_item_id: Food catalog item id.

    Returns:
        Safe catalog reference or None when inactive/missing.
    """
    refs = await load_food_catalog_item_references(session, [food_catalog_item_id])
    return refs.get(food_catalog_item_id)


async def load_food_catalog_item_references(
    session: AsyncSession,
    food_catalog_item_ids: Iterable[UUID],
) -> dict[UUID, FoodCatalogItemReference]:
    """Load active catalog references keyed by food catalog item id.

    Args:
        session: Request-scoped async database session.
        food_catalog_item_ids: Catalog item ids to resolve.

    Returns:
        Mapping from catalog item id to safe public reference.
    """
    ids = list(dict.fromkeys(food_catalog_item_ids))
    if not ids:
        return {}
    result = await session.execute(_active_food_catalog_select().where(FoodCatalogItem.id.in_(ids)))
    return {
        item.id: FoodCatalogItemReference(
            cuisine_code=cuisine_code,
            course_code=course_code,
            canonical_name_ko=item.canonical_name_ko,
            canonical_name_en=item.canonical_name_en,
        )
        for item, cuisine_code, course_code in result.all()
    }


async def load_food_nutrition_by_class_en(
    session: AsyncSession,
    class_en: str,
) -> FoodNutrition | None:
    """Load one active food nutrition row by detection class.

    Args:
        session: Request-scoped async database session.
        class_en: taxo59 model class name used as the detection join key.

    Returns:
        Active food nutrition row, or None when missing/inactive/blank.
    """
    normalized = _normalized_query(class_en)
    if normalized is None:
        return None
    rows = await load_food_nutrition_by_class_ens(session, [normalized])
    return rows.get(normalized)


async def load_food_nutrition_by_class_ens(
    session: AsyncSession,
    class_ens: Iterable[str],
) -> dict[str, FoodNutrition]:
    """Load active food nutrition rows keyed by detection class.

    Args:
        session: Request-scoped async database session.
        class_ens: taxo59 model class names to resolve.

    Returns:
        Mapping from class_en to its active food nutrition row.
    """
    normalized_keys = (_normalized_query(class_en) for class_en in class_ens)
    keys = list(dict.fromkeys(key for key in normalized_keys if key is not None))
    if not keys:
        return {}
    rows = await session.scalars(
        select(FoodNutrition).where(
            FoodNutrition.class_en.in_(keys),
            FoodNutrition.is_active.is_(True),
        )
    )
    return {row.class_en: row for row in rows.all()}


def food_nutrition_per_100g(row: FoodNutrition) -> dict[str, float | None]:
    """Map a food nutrition row to the per-100g nutrient dictionary.

    Args:
        row: Active food nutrition row.

    Returns:
        Mapping keyed by PER_100G_KEYS with Decimal columns cast to float and
        missing values preserved as None.
    """
    typed_values: dict[str, Decimal | None] = {
        "kcal": row.kcal_100g,
        "carb_g": row.carb_g,
        "sugar_g": row.sugar_g,
        "fat_g": row.fat_g,
        "protein_g": row.protein_g,
        "sodium_mg": row.sodium_mg,
        "cholesterol_mg": row.chol_mg,
        "saturated_fat_g": row.sat_fat_g,
        "trans_fat_g": row.trans_fat_g,
    }
    per_100g: dict[str, float | None] = {}
    for key in PER_100G_KEYS:
        value = typed_values.get(key)
        per_100g[key] = float(value) if value is not None else None
    return per_100g


def _active_food_catalog_select() -> Select[tuple[FoodCatalogItem, str, str]]:
    """Build the common active food catalog select.

    Returns:
        SQLAlchemy select returning item, cuisine code, and course code.
    """
    return (
        select(FoodCatalogItem, FoodCuisine.cuisine_code, FoodCourse.course_code)
        .join(FoodCuisine, FoodCatalogItem.cuisine_id == FoodCuisine.id)
        .join(FoodCourse, FoodCatalogItem.course_id == FoodCourse.id)
        .where(
            FoodCatalogItem.is_active.is_(True),
            FoodCuisine.is_active.is_(True),
            FoodCourse.is_active.is_(True),
        )
    )


def _apply_food_catalog_filters(
    stmt: Select[tuple[FoodCatalogItem, str, str]],
    *,
    cuisine_code: str | None,
    course_code: str | None,
    q: str | None,
) -> Select[tuple[FoodCatalogItem, str, str]]:
    """Apply public food catalog filters to a select statement."""
    normalized_cuisine = _normalized_query(cuisine_code)
    normalized_course = _normalized_query(course_code)
    query_text = _normalized_query(q)
    if normalized_cuisine is not None:
        stmt = stmt.where(FoodCuisine.cuisine_code == normalized_cuisine)
    if normalized_course is not None:
        stmt = stmt.where(FoodCourse.course_code == normalized_course)
    if query_text:
        pattern = _contains_pattern(query_text)
        stmt = stmt.where(
            or_(
                FoodCatalogItem.canonical_name_ko.ilike(pattern),
                FoodCatalogItem.canonical_name_en.ilike(pattern),
            )
        )
    return stmt


def _supplement_category_summary(category: SupplementCategory) -> SupplementCategorySummary:
    """Convert a supplement category ORM row into a safe public summary."""
    return SupplementCategorySummary(
        id=category.id,
        category_key=category.category_key,
        display_name=category.display_name,
        sort_order=category.sort_order,
    )


def _food_course_summary(course: FoodCourse) -> FoodCourseSummary:
    """Convert a food course ORM row into a safe public summary."""
    return FoodCourseSummary(
        id=course.id,
        course_code=course.course_code,
        display_name_ko=course.display_name_ko,
        display_name_en=course.display_name_en,
        sort_order=course.sort_order,
    )


def _food_catalog_item_summary(
    item: FoodCatalogItem,
    cuisine_code: str,
    course_code: str,
) -> FoodCatalogItemSummary:
    """Convert a food catalog ORM row into a safe public summary."""
    return FoodCatalogItemSummary(
        id=item.id,
        cuisine_code=cuisine_code,
        course_code=course_code,
        canonical_name_ko=item.canonical_name_ko,
        canonical_name_en=item.canonical_name_en,
        source=item.source,
    )


def _normalized_query(value: str | None) -> str | None:
    """Trim optional query text and normalize blanks to None."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _contains_pattern(value: str) -> str:
    """Return a bounded contains pattern for user-supplied search text."""
    return f"%{value}%"
