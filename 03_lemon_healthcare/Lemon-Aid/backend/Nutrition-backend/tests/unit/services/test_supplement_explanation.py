"""Supplement explanation grounding tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from src.config import Settings
from src.models.schemas.supplement_recommendation import (
    SupplementContributionAggregate,
    SupplementContributionItem,
    SupplementImpactDataStatus,
    SupplementImpactPreviewResponse,
    SupplementRecommendationExplainRequest,
)
from src.services import supplement_explanation
from src.services.supplement_explanation import explain_supplement_recommendation


def _settings(tmp_path: Path) -> Settings:
    """Return settings with local WIKI retrieval enabled.

    Args:
        tmp_path: Temporary WIKI root.

    Returns:
        Settings object for deterministic explanation tests.
    """
    return Settings(
        _env_file=None,
        llm_wiki_path=tmp_path,
        llm_wiki_retrieval_enabled=True,
        llm_wiki_max_sources=2,
        llm_wiki_excerpt_chars=240,
    )


def _preview() -> SupplementImpactPreviewResponse:
    """Return a deterministic impact preview containing Vitamin D context.

    Returns:
        Preview response used to build a sanitized WIKI query.
    """
    supplement_id = uuid4()
    ingredient_id = uuid4()
    return SupplementImpactPreviewResponse(
        reference_version="2026",
        source_manifest_version=None,
        data_status=SupplementImpactDataStatus.PARTIAL,
        current_supplement_contributions=[
            SupplementContributionAggregate(
                nutrient_code="vitamin_d",
                nutrient_name="비타민 D",
                reference_unit="mcg",
                total_daily_amount=25,
                original_unit_totals={"mcg": 25},
                contribution_count=1,
                supplement_ids=[supplement_id],
                items=[
                    SupplementContributionItem(
                        supplement_id=supplement_id,
                        supplement_name="비타민 D 테스트",
                        ingredient_id=ingredient_id,
                        display_name="Vitamin D",
                        nutrient_code="vitamin_d",
                        amount_per_serving=25,
                        unit="mcg",
                        daily_servings=1,
                        daily_amount=25,
                        source="user_confirmed",
                        confidence=1,
                    )
                ],
                warnings=[],
            )
        ],
        deficiency_support_candidates=[],
        excess_or_duplicate_risks=[],
        missing_profile_fields=[],
        safe_user_message="비타민 D 섭취 정보 확인이 필요합니다.",
        clinical_disclaimer="의료적 진단·처방이 아닌 건강관리 참고 정보입니다.",
        warnings=[],
        requires_user_confirmation=True,
    )


@pytest.mark.asyncio
async def test_explain_supplement_recommendation_attaches_wiki_citations(
    tmp_path: Path,
) -> None:
    """Verify deterministic explanation responses include relative WIKI sources."""
    (tmp_path / "vitamin-d.md").write_text(
        "# 비타민 D\n\n"
        "## 확인 필요\n"
        "비타민 D는 개인 상태와 기존 복용 정보를 함께 확인해야 하는 영양소입니다.",
        encoding="utf-8",
    )
    request = SupplementRecommendationExplainRequest(
        preview=_preview(),
        use_local_llm=False,
    )

    response = await explain_supplement_recommendation(request, _settings(tmp_path))

    assert response.llm_used is False
    assert len(response.source_citations) == 1
    assert response.source_citations[0].source_path == "vitamin-d.md"
    assert response.source_citations[0].title == "비타민 D"
    serialized = response.model_dump_json()
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized


def test_analysis_context_ingredient_summary_preserves_original_name() -> None:
    """Verify local explanation wording keeps Korean display and OCR original names."""
    summary = supplement_explanation._format_context_ingredients(
        [
            {
                "display_name": "글루코사민 염산염",
                "original_name": "Glucosamine Hydrochloride",
                "amount_text": "1500 mg",
            }
        ]
    )

    assert summary == "글루코사민 염산염(Glucosamine Hydrochloride) 1500 mg"
