"""Meal, food item, and food image analysis ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class FoodCuisine(TimestampMixin, Base):
    """Persist a top-level food cuisine taxonomy entry.

    Attributes:
        id: Stable cuisine identifier.
        cuisine_code: Stable machine key such as korean or western.
        display_name_ko: Korean user-facing cuisine label.
        display_name_en: English cuisine label for search/imports.
        sort_order: Display and deterministic processing order.
        is_active: Whether the cuisine should be used in classification.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "food_cuisines"
    __table_args__ = (
        UniqueConstraint("cuisine_code", name="uq_food_cuisines_cuisine_code"),
        CheckConstraint("cuisine_code <> ''", name="cuisine_code_nonempty"),
        CheckConstraint("display_name_ko <> ''", name="display_name_ko_nonempty"),
        CheckConstraint("display_name_en <> ''", name="display_name_en_nonempty"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_food_cuisines_active_sort", "is_active", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    cuisine_code: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name_ko: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name_en: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FoodCourse(TimestampMixin, Base):
    """Persist a cuisine-specific course/category entry.

    Attributes:
        id: Stable course identifier.
        cuisine_id: Parent cuisine identifier.
        course_code: Cuisine-local machine key such as soup_stew.
        display_name_ko: Korean user-facing course label.
        display_name_en: English course label for search/imports.
        sort_order: Display and deterministic processing order.
        is_active: Whether the course should be used in classification.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "food_courses"
    __table_args__ = (
        UniqueConstraint("cuisine_id", "course_code", name="uq_food_courses_cuisine_course"),
        CheckConstraint("course_code <> ''", name="course_code_nonempty"),
        CheckConstraint("display_name_ko <> ''", name="display_name_ko_nonempty"),
        CheckConstraint("display_name_en <> ''", name="display_name_en_nonempty"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_food_courses_cuisine_sort", "cuisine_id", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    cuisine_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("food_cuisines.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_code: Mapped[str] = mapped_column(String(60), nullable=False)
    display_name_ko: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name_en: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FoodCatalogItem(TimestampMixin, Base):
    """Persist a canonical food item under a cuisine and course.

    Attributes:
        id: Stable food catalog item identifier.
        cuisine_id: Parent cuisine identifier.
        course_id: Parent course identifier.
        canonical_name_ko: Korean canonical food name, e.g. 된장찌개.
        canonical_name_en: Optional English food name.
        aliases: Bounded alternate names used for search/matching.
        nutrition_reference: Optional curated nutrition values per serving.
        source: Import source such as manual_seed or external_dataset.
        source_payload: Sanitized source metadata; no raw images or provider payloads.
        is_active: Whether the food item should be used for classification/matching.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "food_catalog_items"
    __table_args__ = (
        UniqueConstraint(
            "cuisine_id",
            "course_id",
            "canonical_name_ko",
            name="uq_food_catalog_items_cuisine_course_name",
        ),
        CheckConstraint("canonical_name_ko <> ''", name="canonical_name_ko_nonempty"),
        CheckConstraint("jsonb_typeof(aliases) = 'array'", name="aliases_array"),
        CheckConstraint(
            "jsonb_typeof(nutrition_reference) = 'object'",
            name="nutrition_reference_object",
        ),
        CheckConstraint("jsonb_typeof(source_payload) = 'object'", name="source_payload_object"),
        CheckConstraint("source <> ''", name="source_nonempty"),
        Index("ix_food_catalog_items_cuisine_course", "cuisine_id", "course_id"),
        Index("ix_food_catalog_items_name_ko", "canonical_name_ko"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    cuisine_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("food_cuisines.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("food_courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_name_ko: Mapped[str] = mapped_column(String(120), nullable=False)
    canonical_name_en: Mapped[str | None] = mapped_column(String(160), nullable=True)
    aliases: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    nutrition_reference: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FoodNutrition(TimestampMixin, Base):
    """Persist taxo59 per-100g class-average nutrition keyed by detection class.

    Attributes:
        class_en: taxo59 model class name; the detection->nutrition join key.
        food_catalog_item_id: Optional link to the curated catalog item (via aliases).
        class_ko: Korean display name.
        n_source_codes: Count of AIHub source food codes averaged into the class.
        serving_g: Average single-serving weight in grams for 1-serving scaling.
        kcal_100g: Energy per 100g (kcal).
        carb_g: Carbohydrate per 100g (g).
        sugar_g: Sugars per 100g (g).
        fat_g: Fat per 100g (g).
        protein_g: Protein per 100g (g).
        sodium_mg: Sodium per 100g (mg).
        chol_mg: Cholesterol per 100g (mg).
        sat_fat_g: Saturated fat per 100g (g).
        trans_fat_g: Trans fat per 100g (g).
        source: Import source label such as aihub_taxo59_csv.
        source_manifest_version: Source data manifest version.
        is_active: Whether the nutrition row should be used.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "food_nutrition"
    __table_args__ = (
        CheckConstraint("class_en <> ''", name="ck_food_nutrition_class_en_nonempty"),
        CheckConstraint("class_ko <> ''", name="ck_food_nutrition_class_ko_nonempty"),
        CheckConstraint("source <> ''", name="ck_food_nutrition_source_nonempty"),
        CheckConstraint(
            "serving_g IS NULL OR serving_g > 0",
            name="ck_food_nutrition_serving_g_positive",
        ),
        Index("ix_food_nutrition_food_catalog_item_id", "food_catalog_item_id"),
    )

    class_en: Mapped[str] = mapped_column(String(40), primary_key=True)
    food_catalog_item_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("food_catalog_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    class_ko: Mapped[str] = mapped_column(String(60), nullable=False)
    n_source_codes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    serving_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    kcal_100g: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    carb_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    sugar_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    sodium_mg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    chol_mg: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    sat_fat_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    trans_fat_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MealRecord(TimestampMixin, Base):
    """Persist one current-user meal record.

    Attributes:
        id: Stable meal record identifier.
        owner_subject: Issuer-qualified authenticated subject.
        client_request_id: Optional client idempotency key.
        eaten_at: User-selected meal time.
        meal_type: Meal bucket such as breakfast or snack.
        source: Meal capture source.
        status: Meal lifecycle status.
        nutrition_summary: User-confirmed bounded nutrition summary.
        confidence: Optional automated estimate confidence from 0.0 to 1.0.
        confirmed_at: Time when the user confirmed values.
        deleted_at: Soft-delete timestamp.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "meal_records"
    __table_args__ = (
        CheckConstraint("owner_subject <> ''", name="owner_subject_nonempty"),
        CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'unknown')",
            name="meal_type_allowed",
        ),
        CheckConstraint(
            "source IN ('camera', 'gallery', 'manual', 'imported')",
            name="meal_source_allowed",
        ),
        CheckConstraint(
            "status IN ('requires_confirmation', 'confirmed', 'deleted', 'failed')",
            name="meal_status_allowed",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="meal_confidence_range",
        ),
        CheckConstraint(
            "jsonb_typeof(nutrition_summary) = 'object'",
            name="nutrition_summary_object",
        ),
        Index("ix_meal_records_owner_eaten_at", "owner_subject", "eaten_at"),
        Index("ix_meal_records_owner_status", "owner_subject", "status"),
        Index("ix_meal_records_owner_deleted_at", "owner_subject", "deleted_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    nutrition_summary: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MealFoodItem(TimestampMixin, Base):
    """Persist one user-confirmed or review-pending food item in a meal.

    Attributes:
        id: Stable meal food item identifier.
        meal_id: Parent meal record identifier.
        food_name_text: User-confirmed bounded food name.
        food_catalog_item_id: Optional curated food taxonomy item identifier.
        canonical_food_id: Optional future curated food-master identifier.
        portion_amount: User-confirmed portion amount.
        portion_unit: User-confirmed portion unit.
        kcal: Estimated or confirmed calories.
        carb_g: Estimated or confirmed carbohydrate grams.
        protein_g: Estimated or confirmed protein grams.
        fat_g: Estimated or confirmed fat grams.
        sodium_mg: Estimated or confirmed sodium milligrams.
        source: Item source.
        confidence: Optional automated estimate confidence from 0.0 to 1.0.
        sort_order: Display order.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "meal_food_items"
    __table_args__ = (
        CheckConstraint("food_name_text <> ''", name="food_name_text_nonempty"),
        CheckConstraint(
            "portion_amount IS NULL OR portion_amount >= 0", name="portion_nonnegative"
        ),
        CheckConstraint("kcal IS NULL OR kcal >= 0", name="kcal_nonnegative"),
        CheckConstraint("carb_g IS NULL OR carb_g >= 0", name="carb_g_nonnegative"),
        CheckConstraint("protein_g IS NULL OR protein_g >= 0", name="protein_g_nonnegative"),
        CheckConstraint("fat_g IS NULL OR fat_g >= 0", name="fat_g_nonnegative"),
        CheckConstraint("sodium_mg IS NULL OR sodium_mg >= 0", name="sodium_mg_nonnegative"),
        CheckConstraint(
            "source IN ('vision', 'manual', 'database_match')",
            name="meal_food_source_allowed",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="meal_food_confidence_range",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_meal_food_items_meal_id", "meal_id"),
        Index("ix_meal_food_items_food_catalog_item_id", "food_catalog_item_id"),
        Index("ix_meal_food_items_canonical_food_id", "canonical_food_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    meal_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("meal_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    food_name_text: Mapped[str] = mapped_column(String(160), nullable=False)
    food_catalog_item_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("food_catalog_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    canonical_food_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    portion_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    portion_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kcal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    carb_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sodium_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FoodImageAnalysisRun(TimestampMixin, Base):
    """Persist sanitized food image analysis preview metadata.

    Attributes:
        id: Stable food image analysis run identifier.
        owner_subject: Issuer-qualified authenticated subject.
        client_request_id: Optional client idempotency key.
        media_object_id: Optional retained private media object identifier.
        meal_id: Optional confirmed meal record identifier.
        image_sha256: SHA-256 hash of uploaded image bytes.
        image_mime_type: Accepted image MIME type.
        image_size_bytes: Uploaded image size in bytes.
        detector_model: YOLO/food detector model tag.
        classifier_model: Food classifier model tag.
        status: Preview lifecycle status.
        detected_items_snapshot: Sanitized labels/boxes/confidences only.
        nutrition_estimate_snapshot: Bounded pre-confirmation nutrition estimate.
        warning_codes: Stable warning codes without raw image/provider payloads.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "food_image_analysis_runs"
    __table_args__ = (
        CheckConstraint("owner_subject <> ''", name="owner_subject_nonempty"),
        CheckConstraint("length(image_sha256) = 64", name="image_sha256_length"),
        CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="image_mime_type_allowed",
        ),
        CheckConstraint("image_size_bytes > 0", name="image_size_positive"),
        CheckConstraint(
            "status IN ('requires_confirmation', 'confirmed', 'failed')",
            name="food_image_status_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(detected_items_snapshot) = 'object'",
            name="detected_items_snapshot_object",
        ),
        CheckConstraint(
            "jsonb_typeof(nutrition_estimate_snapshot) = 'object'",
            name="nutrition_estimate_snapshot_object",
        ),
        CheckConstraint(
            "jsonb_typeof(warning_codes) = 'array'",
            name="warning_codes_array",
        ),
        Index(
            "ix_food_image_analysis_runs_owner_created_at",
            "owner_subject",
            "created_at",
        ),
        Index(
            "ix_food_image_analysis_runs_owner_status_created_at",
            "owner_subject",
            "status",
            "created_at",
        ),
        Index("ix_food_image_analysis_runs_media_object_id", "media_object_id"),
        Index("ix_food_image_analysis_runs_meal_id", "meal_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    media_object_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("media_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    meal_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("meal_records.id", ondelete="CASCADE"),
        nullable=True,
    )
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    image_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    detector_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    classifier_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    detected_items_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    nutrition_estimate_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    warning_codes: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
