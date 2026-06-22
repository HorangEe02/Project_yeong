"""Taxonomy catalog response schema tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.models.schemas.meal import MealFoodItemResponse
from src.models.schemas.supplement import SupplementServing, UserSupplementResponse
from src.models.schemas.taxonomy import (
    FoodCatalogItemReference,
    FoodCatalogItemSummary,
    FoodCourseSummary,
    FoodCuisineListResponse,
    FoodCuisineSummary,
    SupplementCategorySummary,
)


def test_taxonomy_catalog_schemas_serialize_safe_public_fields() -> None:
    """Verify taxonomy schemas expose catalog labels without raw provider payloads."""
    course = FoodCourseSummary(
        id=uuid4(),
        course_code="main",
        display_name_ko="메인",
        display_name_en="Main",
        sort_order=1,
    )
    cuisine_response = FoodCuisineListResponse(
        results=[
            FoodCuisineSummary(
                id=uuid4(),
                cuisine_code="korean",
                display_name_ko="한식",
                display_name_en="Korean",
                sort_order=1,
                courses=[course],
            )
        ]
    )
    food = FoodCatalogItemSummary(
        id=uuid4(),
        cuisine_code="korean",
        course_code="main",
        canonical_name_ko="된장찌개",
        canonical_name_en="Soybean Paste Stew",
        source="manual_seed",
    )

    dumped = cuisine_response.model_dump(mode="json")
    assert dumped["results"][0]["courses"][0]["course_code"] == "main"
    assert food.model_dump(mode="json")["canonical_name_ko"] == "된장찌개"


def test_user_record_schemas_include_taxonomy_summaries() -> None:
    """Verify user-facing supplement and meal schemas can attach taxonomy summaries."""
    supplement_category = SupplementCategorySummary(
        id=uuid4(),
        category_key="vitamin",
        display_name="비타민",
        sort_order=1,
    )
    supplement = UserSupplementResponse(
        id=uuid4(),
        display_name="Vitamin D",
        manufacturer="Example Labs",
        ingredients=[],
        serving=SupplementServing(amount=1.0, unit="tablet", daily_servings=1.0),
        intake_schedule=None,
        precaution_snapshot=[],
        evidence_refs=[],
        categories=[supplement_category],
        user_confirmed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    food_catalog_item_id = uuid4()
    meal_item = MealFoodItemResponse(
        id=uuid4(),
        display_name="된장찌개",
        portion_amount=1.0,
        portion_unit="bowl",
        kcal=180.0,
        carb_g=16.0,
        protein_g=11.0,
        fat_g=7.0,
        sodium_mg=900.0,
        food_catalog_item_id=food_catalog_item_id,
        catalog_item=FoodCatalogItemReference(
            cuisine_code="korean",
            course_code="soup_stew",
            canonical_name_ko="된장찌개",
            canonical_name_en="Soybean Paste Stew",
        ),
        confidence=None,
        source="manual",
    )

    assert supplement.categories[0].category_key == "vitamin"
    assert meal_item.catalog_item is not None
    assert meal_item.catalog_item.course_code == "soup_stew"
