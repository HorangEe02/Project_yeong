"""YOLO ROI detector tests."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from PIL import Image
from src.config import Settings
from src.vision.base import BoundingBox, VisionError
from src.vision.taxonomy import normalize_vision_label
from src.vision.ultralytics_runner import UltralyticsYoloRunner
from src.vision.yolo import YoloLabelDetector


class _FakeRunner:
    """Fake detector runner for `YoloLabelDetector` tests."""

    def __init__(self, regions: list[BoundingBox]) -> None:
        self.regions = regions
        self.received_image_bytes: bytes | None = None

    def detect_regions(self, image_bytes: bytes) -> list[BoundingBox]:
        """Return configured regions while capturing the input.

        Args:
            image_bytes: Validated image bytes.

        Returns:
            Configured bounding boxes.
        """
        self.received_image_bytes = image_bytes
        return self.regions


class _Boxes:
    """Fake Ultralytics boxes object."""

    def __init__(self) -> None:
        self.xyxy = [[-1, 1, 9, 7], [0, 0, 5, 4], [1, 1, 4, 4]]
        self.cls = [1, 2, 0]
        self.conf = [0.86, 0.91, 0.40]


class _Result:
    """Fake Ultralytics result object."""

    def __init__(self) -> None:
        self.boxes = _Boxes()


class _FakeModel:
    """Fake Ultralytics model object."""

    def __init__(self) -> None:
        self.names: dict[int, str] = {
            0: "supplement_label",
            1: "Supplement Facts Panel",
            2: "person",
        }
        self.prediction_called = False

    def predict(self, *, source: Any, conf: float, verbose: bool) -> list[_Result]:
        """Return a fake result list matching the Ultralytics result shape.

        Args:
            source: PIL image passed by the runner.
            conf: Confidence threshold.
            verbose: Verbose flag.

        Returns:
            Fake result list.
        """
        assert source.size == (10, 8)
        assert 0.0 <= conf <= 1.0
        assert verbose is False
        self.prediction_called = True
        return [_Result()]


class _CocoModel:
    """Fake COCO model that must not be accepted as supplement detector."""

    def __init__(self) -> None:
        self.names: dict[int, str] = {0: "person", 1: "bicycle"}

    def predict(self, *, source: Any, conf: float, verbose: bool) -> list[_Result]:
        """Raise if called; incompatible models should fail before inference.

        Args:
            source: Unused source image.
            conf: Unused confidence threshold.
            verbose: Unused verbose flag.

        Raises:
            AssertionError: Always, because prediction should not run.
        """
        _ = (source, conf, verbose)
        raise AssertionError("COCO model should fail before prediction")


class _LabelOnlyModel:
    """Fake supplement object model without section ROI labels."""

    def __init__(self) -> None:
        self.names: dict[int, str] = {0: "supplement_label", 1: "supplement_bottle"}

    def predict(self, *, source: Any, conf: float, verbose: bool) -> list[_Result]:
        """Raise if called; label-only models are not section detectors.

        Args:
            source: Unused source image.
            conf: Unused confidence threshold.
            verbose: Unused verbose flag.

        Raises:
            AssertionError: Always, because prediction should not run.
        """
        _ = (source, conf, verbose)
        raise AssertionError("Label-only model should fail before prediction")


class _NoNamesModel:
    """Fake model with no class names metadata."""

    def predict(self, *, source: Any, conf: float, verbose: bool) -> list[_Result]:
        """Raise if called; model names are required for safety.

        Args:
            source: Unused source image.
            conf: Unused confidence threshold.
            verbose: Unused verbose flag.

        Raises:
            AssertionError: Always, because prediction should not run.
        """
        _ = (source, conf, verbose)
        raise AssertionError("Model without names should fail before prediction")


class _ManyBoxes:
    """Fake Ultralytics boxes object exceeding the detection cap."""

    def __init__(self) -> None:
        self.xyxy = [[0, 0, 4, 4], [1, 1, 5, 5], [2, 2, 6, 6], [0, 0, 3, 3], [1, 1, 4, 4]]
        self.cls = [0, 1, 2, 3, 4]
        self.conf = [0.55, 0.95, 0.70, 0.85, 0.60]


class _ManyResult:
    """Fake Ultralytics result wrapping multiple accepted section boxes."""

    def __init__(self) -> None:
        self.boxes = _ManyBoxes()


class _ManySectionModel:
    """Fake section detector returning more accepted boxes than the cap."""

    def __init__(self) -> None:
        self.names: dict[int, str] = {
            0: "product_identity",
            1: "supplement_facts",
            2: "ingredient_amounts",
            3: "precautions",
            4: "intake_method",
        }

    def predict(self, *, source: Any, conf: float, verbose: bool) -> list[_ManyResult]:
        """Return five accepted section boxes for truncation tests.

        Args:
            source: PIL image passed by the runner.
            conf: Confidence threshold.
            verbose: Verbose flag.

        Returns:
            Fake result list with five section boxes.
        """
        _ = (source, conf, verbose)
        return [_ManyResult()]


def _many_section_model_factory(_name: str) -> _ManySectionModel:
    """Return a fake section detector with more boxes than the cap.

    Args:
        _name: Model name accepted for parity with the production model factory.

    Returns:
        Fake section model.
    """
    return _ManySectionModel()


def _settings(
    *,
    enable_vision_classifier: bool = True,
    vision_roi_allowed_classes: list[str] | None = None,
) -> Settings:
    """Return settings for detector tests.

    Args:
        enable_vision_classifier: Whether the gated YOLO channel is enabled.
        vision_roi_allowed_classes: Optional ROI taxonomy override.

    Returns:
        Settings object.
    """
    if vision_roi_allowed_classes is None:
        return Settings(enable_vision_classifier=enable_vision_classifier)
    return Settings(
        enable_vision_classifier=enable_vision_classifier,
        vision_roi_allowed_classes=vision_roi_allowed_classes,
    )


def _fake_model_factory(_name: str) -> _FakeModel:
    """Return a fake YOLO model for runner tests.

    Args:
        _name: Model name accepted for parity with the production model factory.

    Returns:
        Fake model satisfying the runner protocol.
    """
    return _FakeModel()


def _coco_model_factory(_name: str) -> _CocoModel:
    """Return a fake COCO detector.

    Args:
        _name: Model name accepted for parity with the production model factory.

    Returns:
        Fake COCO model.
    """
    return _CocoModel()


def _label_only_model_factory(_name: str) -> _LabelOnlyModel:
    """Return a fake supplement object detector without section labels.

    Args:
        _name: Model name accepted for parity with the production model factory.

    Returns:
        Fake label-only model.
    """
    return _LabelOnlyModel()


def _no_names_model_factory(_name: str) -> _NoNamesModel:
    """Return a fake model without class names.

    Args:
        _name: Model name accepted for parity with the production model factory.

    Returns:
        Fake model without names metadata.
    """
    return _NoNamesModel()


def _png_bytes(width: int = 10, height: int = 8) -> bytes:
    """Return a PNG fixture.

    Args:
        width: Image width.
        height: Image height.

    Returns:
        Encoded PNG bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_yolo_label_detector_rejects_when_feature_flag_disabled() -> None:
    """Verify YOLO inference is fail-closed when the feature flag is false."""
    detector = YoloLabelDetector(Settings(), runner=_FakeRunner([]))

    with pytest.raises(VisionError, match="ENABLE_VISION_CLASSIFIER=false"):
        await detector.detect_label_region(_png_bytes())


@pytest.mark.asyncio
async def test_yolo_label_detector_selects_best_label_region() -> None:
    """Verify the detector returns ROI metadata rather than text facts."""
    regions = [
        BoundingBox(
            x=0,
            y=0,
            width=10,
            height=8,
            confidence=0.99,
            label="supplement_bottle",
        ),
        BoundingBox(
            x=2,
            y=1,
            width=4,
            height=3,
            confidence=0.55,
            label="supplement_label",
        ),
    ]
    runner = _FakeRunner(regions)
    detector = YoloLabelDetector(_settings(), runner=runner)

    region = await detector.detect_label_region(_png_bytes())

    assert region.label == "supplement_label"
    assert region.model is None
    assert runner.received_image_bytes is not None
    assert await detector.detect_regions(_png_bytes()) == regions


@pytest.mark.asyncio
async def test_yolo_label_detector_rejects_unknown_allowed_labels() -> None:
    """Verify an invalid ROI taxonomy cannot silently enable detection."""
    detector = YoloLabelDetector(
        _settings(vision_roi_allowed_classes=["nutrition_facts_text"]),
        runner=None,
    )

    with pytest.raises(VisionError, match="VISION_ROI_ALLOWED_CLASSES"):
        await detector.detect_label_region(_png_bytes())


def test_ultralytics_runner_normalizes_allowed_boxes_without_text_extraction() -> None:
    """Verify Ultralytics boxes become bounded ROI metadata only."""
    runner = UltralyticsYoloRunner(
        model_name="local-supplement-roi.pt",
        allowed_labels={"supplement_facts", "supplement_label", "blister_pack"},
        min_confidence=0.5,
        max_detections=16,
        model_factory=_fake_model_factory,
    )

    regions = runner.detect_regions(_png_bytes())

    assert regions == [
        BoundingBox(
            x=0,
            y=1,
            width=9,
            height=6,
            confidence=0.86,
            label="supplement_facts",
            model="local-supplement-roi.pt",
        )
    ]


def test_vision_taxonomy_normalizes_section_roi_aliases() -> None:
    """Verify custom YOLO section labels survive normalization for OCR routing."""
    assert normalize_vision_label("Supplement Facts Panel") == "supplement_facts"
    assert normalize_vision_label("allergy-warning") == "allergen_warning"
    assert normalize_vision_label("Suggested Use") == "intake_method"
    assert normalize_vision_label("ingredient rows") == "ingredient_amounts"
    assert normalize_vision_label("Other Ingredients") == "other_ingredients"


def test_ultralytics_runner_fails_closed_without_allowed_boxes() -> None:
    """Verify unknown classes are ignored and produce a stable vision error."""
    runner = UltralyticsYoloRunner(
        model_name="local-supplement-roi.pt",
        allowed_labels={"supplement_facts"},
        min_confidence=0.95,
        max_detections=16,
        model_factory=_fake_model_factory,
    )

    with pytest.raises(VisionError, match="allowed supplement ROI"):
        runner.detect_regions(_png_bytes())


def test_ultralytics_runner_rejects_coco_model_before_prediction() -> None:
    """Verify COCO class names cannot masquerade as supplement section detection."""
    runner = UltralyticsYoloRunner(
        model_name="yolo26n.pt",
        allowed_labels={"supplement_facts", "precautions"},
        min_confidence=0.5,
        max_detections=16,
        model_factory=_coco_model_factory,
    )

    with pytest.raises(VisionError, match="supplement ROI taxonomy"):
        runner.detect_regions(_png_bytes())


def test_ultralytics_runner_rejects_label_only_model_before_prediction() -> None:
    """Verify a bottle/label model is not enough for section-level OCR routing."""
    runner = UltralyticsYoloRunner(
        model_name="local-supplement-label.pt",
        allowed_labels={"supplement_label", "supplement_bottle"},
        min_confidence=0.5,
        max_detections=16,
        model_factory=_label_only_model_factory,
    )

    with pytest.raises(VisionError, match="section ROI classes"):
        runner.detect_regions(_png_bytes())


def test_ultralytics_runner_rejects_model_without_class_names() -> None:
    """Verify class-name metadata is required before YOLO inference runs."""
    runner = UltralyticsYoloRunner(
        model_name="local-supplement-roi.pt",
        allowed_labels={"supplement_facts", "precautions"},
        min_confidence=0.5,
        max_detections=16,
        model_factory=_no_names_model_factory,
    )

    with pytest.raises(VisionError, match="supplement ROI taxonomy"):
        runner.detect_regions(_png_bytes())


def test_ultralytics_runner_truncates_to_max_detections_by_priority() -> None:
    """Verify the cap keeps the highest-priority sections, not the highest confidence.

    The fixture's ``product_identity`` box has the LOWEST confidence (0.55) but the
    HIGHEST priority (0). It must survive the cap while higher-confidence but
    lower-priority sections are dropped, matching the downstream selection contract.
    """
    runner = UltralyticsYoloRunner(
        model_name="local-supplement-section.pt",
        allowed_labels={
            "product_identity",
            "supplement_facts",
            "ingredient_amounts",
            "precautions",
            "intake_method",
        },
        min_confidence=0.5,
        max_detections=2,
        model_factory=_many_section_model_factory,
    )

    regions = runner.detect_regions(_png_bytes())

    assert len(regions) == 2
    # Priority-ordered: product_identity (prio 0) first despite its 0.55 confidence,
    # then supplement_facts (prio 1). precautions (0.85) and ingredient_amounts (0.70)
    # are dropped because their priority is lower even though their confidence is higher.
    assert [region.label for region in regions] == ["product_identity", "supplement_facts"]


def test_ultralytics_runner_rejects_non_positive_max_detections() -> None:
    """Verify a non-positive detection cap is rejected at construction."""
    with pytest.raises(ValueError, match="max_detections"):
        UltralyticsYoloRunner(
            model_name="local-supplement-section.pt",
            allowed_labels={"supplement_facts"},
            min_confidence=0.5,
            max_detections=0,
            model_factory=_fake_model_factory,
        )
