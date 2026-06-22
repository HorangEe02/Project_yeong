"""Meal explanation grounding tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from src.config import Settings
from src.models.schemas.meal import (
    MealAnalysisStatus,
    MealExplainRequest,
    MealFoodItemResponse,
    MealRecordResponse,
    MealType,
)
from src.models.schemas.taxonomy import FoodCatalogItemReference
from src.services.meal_explanation import explain_meal_record


def _settings(tmp_path: Path) -> Settings:
    """Return settings with local WIKI retrieval enabled.

    Args:
        tmp_path: Temporary WIKI root.

    Returns:
        Settings object for deterministic meal explanation tests.
    """
    return Settings(
        _env_file=None,
        llm_wiki_path=tmp_path,
        llm_wiki_retrieval_enabled=True,
        llm_wiki_max_sources=2,
        llm_wiki_excerpt_chars=240,
    )


def _meal() -> MealRecordResponse:
    """Return a confirmed meal response with taxonomy context.

    Returns:
        Meal response used to build sanitized WIKI retrieval queries.
    """
    now = datetime(2026, 6, 2, tzinfo=UTC)
    return MealRecordResponse(
        id=uuid4(),
        status=MealAnalysisStatus.CONFIRMED,
        meal_type=MealType.LUNCH,
        eaten_at=now,
        food_items=[
            MealFoodItemResponse(
                id=uuid4(),
                display_name="된장찌개",
                portion_amount=1,
                portion_unit="bowl",
                kcal=180,
                carb_g=18,
                protein_g=12,
                fat_g=6,
                sodium_mg=1600,
                food_catalog_item_id=uuid4(),
                catalog_item=FoodCatalogItemReference(
                    cuisine_code="korean",
                    course_code="soup_stew",
                    canonical_name_ko="된장찌개",
                    canonical_name_en="Doenjang jjigae",
                ),
                confidence=1,
                source="database_match",
            )
        ],
        nutrition_summary={
            "kcal": 180,
            "carb_g": 18,
            "protein_g": 12,
            "fat_g": 6,
            "sodium_mg": 1600,
        },
        confirmed_at=now,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_explain_meal_record_attaches_wiki_citations(tmp_path: Path) -> None:
    """Verify meal explanations cite local WIKI documents by relative path only."""
    (tmp_path / "korean-food.md").write_text(
        "# 한식 식단\n\n"
        "## 된장찌개\n"
        "된장찌개는 나트륨 확인이 필요한 국·찌개류 식단 예시입니다.",
        encoding="utf-8",
    )
    response = await explain_meal_record(
        _meal(),
        MealExplainRequest(use_local_llm=False),
        _settings(tmp_path),
    )

    assert response.llm_used is False
    assert response.source_citations
    assert response.source_citations[0].source_path == "korean-food.md"
    assert any(item.label == "주의" for item in response.guidance)
    serialized = response.model_dump_json()
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
