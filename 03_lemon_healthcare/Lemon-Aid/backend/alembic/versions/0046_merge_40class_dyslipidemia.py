"""Merge the 40-class nutrition upsert branch into the main migration head.

0045_upsert_food_nutrition_40class_v2 branches off 0044_normalize_check_constraint_names,
creating a second head alongside the main chain. This joins it with the current head
(0046_supplement_analysis_processing_status, which descends from the dyslipidemia seed)
so ``alembic upgrade head`` resolves to a single head again.

Revision ID: 0046_merge_40class_dyslipidemia
Revises: 0045_upsert_food_nutrition_40class_v2, 0046_supplement_analysis_processing_status
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0046_merge_40class_dyslipidemia"
down_revision: tuple[str, str] = (
    "0045_upsert_food_nutrition_40class_v2",
    "0046_supplement_analysis_processing_status",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
