"""Gated YOLO detector for supplement-label ROI detection."""

from __future__ import annotations

from typing import Protocol

from src.config import Settings
from src.vision.base import BoundingBox, VisionAdapter, VisionError
from src.vision.preprocessing import VisionPreprocessingError, select_best_label_region
from src.vision.taxonomy import normalize_vision_label
from src.vision.ultralytics_runner import UltralyticsYoloRunner


class YoloRegionRunner(Protocol):
    """Protocol for detector runners that produce ROI bounding boxes."""

    def detect_regions(self, image_bytes: bytes) -> list[BoundingBox]:
        """Detect candidate supplement ROI boxes.

        Args:
            image_bytes: Validated image bytes.

        Returns:
            Candidate bounding boxes.
        """
        ...


class YoloLabelDetector(VisionAdapter):
    """YOLO detector entry point for gated ROI-only object detection.

    The detector returns only configured supplement object or label-section bounding
    boxes for OCR preprocessing. It must not return or infer product names,
    ingredients, amounts, dosage, health effects, or risk judgments.
    """

    def __init__(
        self,
        settings: Settings,
        runner: YoloRegionRunner | None = None,
    ) -> None:
        """Initialize the gated detector.

        Args:
            settings: Runtime settings containing the vision feature flag and model tag.
            runner: Optional injected runner for tests. Production lazy-loads Ultralytics.
        """
        self.settings = settings
        self.runner = runner

    async def detect_label_region(self, image_bytes: bytes) -> BoundingBox:
        """Detect a supplement label region when the vision gate is fully enabled.

        Args:
            image_bytes: Validated image bytes.

        Returns:
            Detected label-region bounding box.

        Raises:
            VisionError: If disabled, not configured, or no valid ROI is detected.
        """
        regions = await self.detect_regions(image_bytes)
        try:
            return select_best_label_region(regions)
        except VisionPreprocessingError as exc:
            raise VisionError("YOLO did not produce a usable supplement ROI.") from exc

    async def detect_regions(self, image_bytes: bytes) -> list[BoundingBox]:
        """Detect candidate supplement regions for OCR preprocessing.

        Args:
            image_bytes: Validated image bytes.

        Returns:
            Candidate bounding boxes from the configured YOLO runner.

        Raises:
            VisionError: If disabled, not configured, or the runner fails.
        """
        if not self.settings.enable_vision_classifier:
            raise VisionError("YOLO label detection is disabled by ENABLE_VISION_CLASSIFIER=false.")

        active_runner = self.runner or UltralyticsYoloRunner(
            model_name=self.settings.vision_classifier_model,
            allowed_labels=_allowed_labels(self.settings.vision_roi_allowed_classes),
            min_confidence=self.settings.vision_roi_min_confidence,
            max_detections=self.settings.vision_roi_max_detections,
        )
        return active_runner.detect_regions(image_bytes)


def _allowed_labels(configured_labels: list[str]) -> set[str]:
    """Normalize configured labels into canonical YOLO ROI labels.

    Args:
        configured_labels: Labels from runtime settings.

    Returns:
        Canonical label set.

    Raises:
        VisionError: If no configured labels map into the supported ROI taxonomy.
    """
    allowed = {
        normalized
        for configured_label in configured_labels
        if (normalized := normalize_vision_label(configured_label)) is not None
    }
    if not allowed:
        raise VisionError("VISION_ROI_ALLOWED_CLASSES does not include any supported ROI labels.")
    return allowed
