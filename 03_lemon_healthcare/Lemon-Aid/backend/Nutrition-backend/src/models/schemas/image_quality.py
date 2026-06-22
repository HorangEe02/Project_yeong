"""Schemas for supplement image quality and ROI training metadata."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ImageQualityStatus = Literal["acceptable", "needs_review", "retake_recommended", "blocked"]
ImageQualityReasonCode = Literal[
    "blurred_text",
    "glare_or_reflection",
    "low_light",
    "low_contrast",
    "too_small_text",
    "partial_table",
    "cover_only",
    "multi_product",
    "unsupported_layout",
    "roi_not_found",
]
ImageQualitySeverity = Literal["review", "retake", "blocked"]
ROIAnnotationLabel = Literal[
    "supplement_label",
    "supplement_bottle",
    "blister_pack",
    "supplement_facts_table",
    "ingredients_section",
    "precautions_section",
    "barcode_region",
    "brand_front_label",
]
DatasetSplit = Literal["train", "val", "test"]
JSONScalar = int | float | str | bool | None

ROI_TRAINING_CLASS_NAMES: tuple[ROIAnnotationLabel, ...] = (
    "supplement_label",
    "supplement_bottle",
    "blister_pack",
    "supplement_facts_table",
    "ingredients_section",
    "precautions_section",
    "barcode_region",
    "brand_front_label",
)


class QualityIssue(BaseModel):
    """One bounded image-quality issue for review or retake routing.

    Attributes:
        reason_code: Stable reason code for UI, audit, and metrics.
        severity: Review action severity. These are warning actions, not medical risk levels.
        message: Safe user-facing explanation without raw image or OCR text.
        evidence: Numeric or short categorical evidence for the issue.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason_code: ImageQualityReasonCode
    severity: ImageQualitySeverity
    message: str = Field(min_length=1, max_length=240)
    evidence: dict[str, JSONScalar] = Field(default_factory=dict, max_length=20)


class DetectedROI(BaseModel):
    """Sanitized ROI metadata used for OCR preprocessing and learning manifests.

    Attributes:
        label: ROI class label.
        x: Left coordinate in input-image pixels.
        y: Top coordinate in input-image pixels.
        width: Width in pixels.
        height: Height in pixels.
        confidence: Detector confidence.
        model: Detector model tag or artifact name.
        area_ratio: ROI area divided by full image area.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str | None = Field(default=None, max_length=80)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    model: str | None = Field(default=None, max_length=160)
    area_ratio: float | None = Field(default=None, ge=0, le=1)


class ImageQualityReport(BaseModel):
    """Deterministic supplement image quality summary.

    Attributes:
        status: Overall review state derived from quality issues.
        issues: Bounded issue list.
        metrics: Redacted numeric quality metrics.
        detected_rois: Sanitized ROI metadata.
        retake_reasons: Reason codes that should prompt a better image.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: ImageQualityStatus
    issues: list[QualityIssue] = Field(default_factory=list, max_length=20)
    metrics: dict[str, JSONScalar] = Field(default_factory=dict, max_length=40)
    detected_rois: list[DetectedROI] = Field(default_factory=list, max_length=20)
    retake_reasons: list[ImageQualityReasonCode] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_status_matches_issues(self) -> Self:
        """Validate the aggregate status is compatible with issue severities.

        Returns:
            Validated report.

        Raises:
            ValueError: If status contradicts issue severities.
        """
        severities = {issue.severity for issue in self.issues}
        if "blocked" in severities and self.status != "blocked":
            raise ValueError("blocked issues require status='blocked'.")
        if "retake" in severities and self.status not in {"retake_recommended", "blocked"}:
            raise ValueError("retake issues require retake_recommended or blocked status.")
        if severities and self.status == "acceptable":
            raise ValueError("acceptable reports cannot contain issues.")
        return self

    @field_validator("retake_reasons")
    @classmethod
    def normalize_retake_reasons(
        cls,
        values: list[ImageQualityReasonCode],
    ) -> list[ImageQualityReasonCode]:
        """Deduplicate retake reason codes while preserving order.

        Args:
            values: Candidate retake reasons.

        Returns:
            Deduplicated reason list.
        """
        normalized: list[ImageQualityReasonCode] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized


class ROITrainingBox(BaseModel):
    """One normalized ROI annotation in Ultralytics-compatible coordinates.

    Attributes:
        class_name: ROI annotation class.
        x_center: Normalized x center from 0.0 to 1.0.
        y_center: Normalized y center from 0.0 to 1.0.
        width: Normalized box width from 0.0 to 1.0.
        height: Normalized box height from 0.0 to 1.0.
        source_roi: Optional detector or annotator provenance.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    class_name: ROIAnnotationLabel
    x_center: float = Field(ge=0, le=1)
    y_center: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    source_roi: str | None = Field(default=None, max_length=80)


class ROITrainingManifestItem(BaseModel):
    """Consent-gated metadata row for ROI training or benchmark export.

    Attributes:
        image_id: Pseudonymous image id.
        image_hash: Image content hash or salted hash used for leakage checks.
        product_group_id: Product/barcode/session grouping key for split isolation.
        split_group: Group key that must not cross train/val/test splits.
        split: Dataset split.
        consent_scope: Consent names captured at export time.
        labels: Image-level labels and quality reason codes.
        boxes: ROI annotation boxes.
        quality_report: Optional deterministic quality report.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    image_id: str = Field(min_length=8, max_length=160)
    image_hash: str = Field(min_length=8, max_length=160)
    product_group_id: str = Field(min_length=1, max_length=160)
    split_group: str = Field(min_length=1, max_length=160)
    split: DatasetSplit
    consent_scope: list[str] = Field(min_length=1, max_length=20)
    labels: list[str] = Field(default_factory=list, max_length=40)
    boxes: list[ROITrainingBox] = Field(default_factory=list, max_length=80)
    quality_report: ImageQualityReport | None = None


class ROITrainingManifest(BaseModel):
    """Redacted ROI training manifest.

    Attributes:
        schema_version: Manifest schema version.
        class_names: Ordered class names used for YOLO label ids.
        items: Manifest rows.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["roi-training-manifest-v1"] = "roi-training-manifest-v1"
    class_names: list[ROIAnnotationLabel] = Field(
        default_factory=lambda: list(ROI_TRAINING_CLASS_NAMES),
        min_length=1,
        max_length=32,
    )
    items: list[ROITrainingManifestItem] = Field(default_factory=list)
