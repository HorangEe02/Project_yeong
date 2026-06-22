"""Public taxonomy catalog API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplementCategorySummary(BaseModel):
    """Safe supplement category summary for catalog and user records.

    Attributes:
        id: Curated category identifier.
        category_key: Stable machine key derived from the source folder.
        display_name: User-facing category label.
        sort_order: Display order.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_key: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    sort_order: int = Field(ge=0)


class SupplementCategoryListResponse(BaseModel):
    """Paginated supplement category catalog response.

    Attributes:
        results: Active supplement categories.
        limit: Maximum requested row count.
        offset: Requested row offset.
    """

    results: list[SupplementCategorySummary]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class FoodCourseSummary(BaseModel):
    """Safe food course summary nested under one cuisine.

    Attributes:
        id: Curated course identifier.
        course_code: Cuisine-local course key.
        display_name_ko: Korean user-facing course label.
        display_name_en: English course label.
        sort_order: Display order within the cuisine.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_code: str = Field(min_length=1, max_length=60)
    display_name_ko: str = Field(min_length=1, max_length=80)
    display_name_en: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(ge=0)


class FoodCuisineSummary(BaseModel):
    """Safe food cuisine summary with active child courses.

    Attributes:
        id: Curated cuisine identifier.
        cuisine_code: Stable cuisine key.
        display_name_ko: Korean user-facing cuisine label.
        display_name_en: English cuisine label.
        sort_order: Display order.
        courses: Active courses under this cuisine.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cuisine_code: str = Field(min_length=1, max_length=40)
    display_name_ko: str = Field(min_length=1, max_length=80)
    display_name_en: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(ge=0)
    courses: list[FoodCourseSummary] = Field(default_factory=list)


class FoodCuisineListResponse(BaseModel):
    """Food cuisine catalog response.

    Attributes:
        results: Active cuisines with active child courses.
    """

    results: list[FoodCuisineSummary]


class FoodCatalogItemSummary(BaseModel):
    """Safe food catalog item summary for lookup lists.

    Attributes:
        id: Curated food catalog item identifier.
        cuisine_code: Parent cuisine code.
        course_code: Parent course code.
        canonical_name_ko: Korean canonical food name.
        canonical_name_en: Optional English canonical food name.
        source: Sanitized catalog source marker.
    """

    id: UUID
    cuisine_code: str = Field(min_length=1, max_length=40)
    course_code: str = Field(min_length=1, max_length=60)
    canonical_name_ko: str = Field(min_length=1, max_length=120)
    canonical_name_en: str | None = Field(default=None, max_length=160)
    source: str = Field(min_length=1, max_length=64)


class FoodCatalogItemListResponse(BaseModel):
    """Paginated food catalog item lookup response.

    Attributes:
        results: Active food catalog items.
        limit: Maximum requested row count.
        offset: Requested row offset.
    """

    results: list[FoodCatalogItemSummary]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class FoodCatalogItemReference(BaseModel):
    """Catalog reference attached to a current-user meal food item.

    Attributes:
        cuisine_code: Parent cuisine code.
        course_code: Parent course code.
        canonical_name_ko: Korean canonical food name.
        canonical_name_en: Optional English canonical food name.
    """

    cuisine_code: str = Field(min_length=1, max_length=40)
    course_code: str = Field(min_length=1, max_length=60)
    canonical_name_ko: str = Field(min_length=1, max_length=120)
    canonical_name_en: str | None = Field(default=None, max_length=160)
