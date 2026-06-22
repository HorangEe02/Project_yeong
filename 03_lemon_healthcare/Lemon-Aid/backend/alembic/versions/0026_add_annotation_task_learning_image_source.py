"""Allow annotation tasks to reference retained learning images.

Revision ID: 0026_add_annotation_task_learning_image_source
Revises: 0025_create_supplement_food_taxonomy_tables
Create Date: 2026-06-02 00:00:00.000000

The column lets consent-gated learning images become the source for human
review tasks without copying object URIs, raw OCR text, provider payloads, or
image paths into task snapshots.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_add_annotation_task_learning_image_source"
down_revision: str | Sequence[str] | None = "0025_create_supplement_food_taxonomy_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the optional learning image source reference to annotation tasks."""
    op.add_column(
        "annotation_tasks",
        sa.Column("learning_image_object_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_annotation_tasks_learning_image_object_id_learning_image_objects"),
        "annotation_tasks",
        "learning_image_objects",
        ["learning_image_object_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_annotation_tasks_learning_image_object_id",
        "annotation_tasks",
        ["learning_image_object_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the learning image source reference from annotation tasks."""
    op.drop_index("ix_annotation_tasks_learning_image_object_id", table_name="annotation_tasks")
    op.drop_constraint(
        op.f("fk_annotation_tasks_learning_image_object_id_learning_image_objects"),
        "annotation_tasks",
        type_="foreignkey",
    )
    op.drop_column("annotation_tasks", "learning_image_object_id")
