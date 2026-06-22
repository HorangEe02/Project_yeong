"""Supplement product, preview, and user-confirmed supplement ORM models."""

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
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class SupplementProduct(TimestampMixin, Base):
    """Persist a reference supplement product from MFDS or local curated data.

    Attributes:
        id: Stable product identifier.
        source_provider: Provider namespace such as mfds or local.
        source_product_id: Provider-specific product identifier.
        product_name: Product display name from the source.
        normalized_product_name: Search-normalized product name.
        manufacturer: Product manufacturer when available.
        category: Product category when available.
        source_payload: Sanitized original source row or API payload.
        source_manifest_version: Source manifest version used for import.
        imported_at: Time when the source row was imported.
        is_active: Whether the reference product should be used for matching.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "supplement_products"
    __table_args__ = (
        UniqueConstraint(
            "source_provider",
            "source_product_id",
            name="uq_supplement_products_source_provider_product_id",
        ),
        CheckConstraint("source_provider <> ''", name="source_provider_nonempty"),
        CheckConstraint("source_product_id <> ''", name="source_product_id_nonempty"),
        Index("ix_supplement_products_normalized_name", "normalized_product_name"),
        Index("ix_supplement_products_manufacturer", "manufacturer"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    product_name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_product_name: Mapped[str] = mapped_column(String(240), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    source_manifest_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SupplementCategory(TimestampMixin, Base):
    """Persist a curated supplement category imported from local image folders.

    Attributes:
        id: Stable category identifier.
        category_key: Stable folder-derived category key.
        display_name: User-facing category label.
        source_folder_name: Original source folder name, including brackets.
        source_path: Repo-relative source folder path when imported from fixtures.
        source_payload: Sanitized import metadata.
        source_manifest_version: Source manifest version used for import.
        sort_order: Display and deterministic processing order.
        is_active: Whether the category should be used for classification.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "supplement_categories"
    __table_args__ = (
        UniqueConstraint("category_key", name="uq_supplement_categories_category_key"),
        CheckConstraint("category_key <> ''", name="category_key_nonempty"),
        CheckConstraint("display_name <> ''", name="display_name_nonempty"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_supplement_categories_display_name", "display_name"),
        Index("ix_supplement_categories_active_sort", "is_active", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    category_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_folder_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    source_manifest_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SupplementProductCategory(TimestampMixin, Base):
    """Map reference supplement products to one or more curated categories.

    Attributes:
        id: Stable product-category mapping identifier.
        product_id: Reference supplement product identifier.
        category_id: Curated supplement category identifier.
        source: Mapping source such as folder_import, manual, or classifier.
        confidence: Optional automated mapping confidence from 0.0 to 1.0.
        is_primary: Whether this category should be displayed first.
        source_payload: Sanitized import or classifier metadata.
        sort_order: Display and deterministic processing order.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "supplement_product_categories"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "category_id",
            name="uq_supplement_product_categories_product_category",
        ),
        CheckConstraint("source <> ''", name="source_nonempty"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_supplement_product_categories_product_id", "product_id"),
        Index("ix_supplement_product_categories_category_id", "category_id"),
        Index("ix_supplement_product_categories_primary", "product_id", "is_primary"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SupplementProductIngredient(TimestampMixin, Base):
    """Persist one ingredient row for a reference supplement product.

    Attributes:
        id: Stable ingredient identifier.
        product_id: Reference product identifier.
        standard_name: Source-normalized ingredient name.
        nutrient_code: Internal nutrient code when mapped to KDRIs/nutrient catalog.
        amount: Ingredient amount per serving when available.
        unit: Ingredient unit when available.
        daily_value_percent: Percentage of the daily reference intake
            (%DV / 영양성분기준치) when present on the label.
        source_payload: Sanitized original source ingredient payload.
        sort_order: Display and deterministic processing order.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "supplement_product_ingredients"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_nonnegative"),
        CheckConstraint(
            "daily_value_percent IS NULL OR daily_value_percent >= 0",
            name="daily_value_percent_nonnegative",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_supplement_product_ingredients_product_id", "product_id"),
        Index("ix_supplement_product_ingredients_nutrient_code", "nutrient_code"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    standard_name: Mapped[str] = mapped_column(String(160), nullable=False)
    nutrient_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    daily_value_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    source_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SupplementAnalysisRun(TimestampMixin, Base):
    """Persist an OCR/LLM supplement preview before user confirmation.

    Attributes:
        id: Stable analysis run identifier.
        owner_subject: Issuer-qualified authenticated subject.
        client_request_id: Optional client idempotency key.
        status: Preview lifecycle status.
        image_sha256: SHA-256 hash of the uploaded label image bytes.
        image_mime_type: Accepted image MIME type.
        image_size_bytes: Uploaded image size in bytes.
        ocr_provider: OCR provider used for the preview.
        ocr_confidence: OCR confidence from 0.0 to 1.0.
        ocr_text_hash: SHA-256 hash of OCR text without storing raw OCR text.
        parsed_snapshot: Structured OCR/LLM parsing result.
        match_snapshot: Product and ingredient matching result.
        warnings: Safe warning strings for user confirmation.
        algorithm_version: Parser contract or algorithm version.
        source_manifest_version: Reference source manifest version.
        expires_at: Time after which the preview should not be confirmed.
        confirmed_at: Time when this preview was confirmed into a user supplement.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "supplement_analysis_runs"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject",
            "client_request_id",
            name="uq_supplement_analysis_runs_owner_client_request",
        ),
        CheckConstraint(
            "status IN ('processing', 'requires_confirmation', 'confirmed', 'expired', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="image_mime_type_allowed",
        ),
        CheckConstraint("image_size_bytes > 0", name="image_size_positive"),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="ocr_confidence_range",
        ),
        Index("ix_supplement_analysis_runs_owner_created_at", "owner_subject", "created_at"),
        Index(
            "ix_supplement_analysis_runs_owner_status_created_at",
            "owner_subject",
            "status",
            "created_at",
        ),
        Index("ix_supplement_analysis_runs_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    image_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    ocr_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parsed_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    match_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    warnings: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSupplement(TimestampMixin, Base):
    """Persist a user-confirmed supplement record.

    Attributes:
        id: Stable user supplement identifier.
        owner_subject: Issuer-qualified authenticated subject.
        source_analysis_run_id: Optional preview run that produced this record.
        matched_product_id: Optional reference product selected by matching or user review.
        display_name: User-confirmed supplement display name.
        manufacturer: User-confirmed manufacturer.
        category_key: User-chosen curated supplement category key (None when unset).
        serving_snapshot: User-confirmed serving values.
        intake_schedule: User-confirmed intake schedule.
        precaution_snapshot: User-confirmed label precautions only.
        evidence_refs: Bounded preview evidence ids supporting confirmed values.
        user_confirmed_at: Time when the user confirmed values.
        deleted_at: Soft-delete timestamp for current-user hiding and future audit.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "user_supplements"
    __table_args__ = (
        CheckConstraint("display_name <> ''", name="display_name_nonempty"),
        CheckConstraint("jsonb_typeof(evidence_refs) = 'array'", name="evidence_refs_array"),
        CheckConstraint(
            "jsonb_typeof(precaution_snapshot) = 'array'",
            name="precaution_snapshot_array",
        ),
        CheckConstraint(
            "category_key IS NULL OR category_key <> ''",
            name="category_key_nonempty",
        ),
        Index("ix_user_supplements_owner_created_at", "owner_subject", "created_at"),
        Index("ix_user_supplements_owner_deleted_at", "owner_subject", "deleted_at"),
        Index("ix_user_supplements_source_analysis_run_id", "source_analysis_run_id"),
        Index("ix_user_supplements_matched_product_id", "matched_product_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    source_analysis_run_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    matched_product_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("supplement_products.id", ondelete="SET NULL"),
        nullable=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    # User-chosen curated category key (references supplement_categories.category_key
    # by value; soft reference validated in the registration service, not an FK, so
    # catalog churn never blocks a stored record). None when the user did not pick one.
    category_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serving_snapshot: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    intake_schedule: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    precaution_snapshot: Mapped[list[str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=list
    )
    evidence_refs: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    user_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSupplementIngredient(TimestampMixin, Base):
    """Persist one user-confirmed supplement ingredient.

    Attributes:
        id: Stable user supplement ingredient identifier.
        user_supplement_id: Parent user supplement identifier.
        display_name: User-confirmed ingredient name.
        nutrient_code: Internal nutrient code when mapped.
        amount: User-confirmed amount.
        unit: User-confirmed unit.
        daily_value_percent: User-confirmed %DV (영양성분기준치) when present on the label.
        confidence: Confidence retained from extraction or 1.0 for user edits.
        source: Source label such as user_confirmed or ocr_llm_preview.
        sort_order: Display and deterministic processing order.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "user_supplement_ingredients"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_nonnegative"),
        CheckConstraint(
            "daily_value_percent IS NULL OR daily_value_percent >= 0",
            name="daily_value_percent_nonnegative",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_user_supplement_ingredients_supplement_id", "user_supplement_id"),
        Index("ix_user_supplement_ingredients_nutrient_code", "nutrient_code"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_supplement_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("user_supplements.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    nutrient_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    daily_value_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
