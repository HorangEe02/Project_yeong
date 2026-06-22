"""Food YOLO runner tests."""

from __future__ import annotations

from io import BytesIO
from typing import Any, ClassVar

import pytest
from PIL import Image
from src.vision.base import BoundingBox, VisionError
from src.vision.food_yolo import FoodDetection, FoodYoloDetector, food_model_label
from src.vision.taxonomy import normalize_food_vision_label, normalize_food_vision_label_set


class _Boxes:
    """Fake Ultralytics boxes object."""

    def __init__(self) -> None:
        """Create fake food detector boxes."""
        self.xyxy = [[-2, 1, 9, 7], [1, 1, 3, 3], [0, 0, 1, 1]]
        self.cls = [0, 1, 2]
        self.conf = [0.86, 0.40, 0.93]


class _Result:
    """Fake Ultralytics result object."""

    def __init__(self) -> None:
        """Create a result with boxes and names."""
        self.boxes = _Boxes()
        self.names = {0: "bibimbap", 1: "salad", 2: "rice_bowl"}


class _EmptyResult:
    """Fake empty Ultralytics result object."""

    boxes = None


class _FakeModel:
    """Fake Ultralytics model object."""

    names: ClassVar[dict[int, str]] = {0: "fallback_bibimbap"}

    def __init__(self, prediction_results: Any) -> None:
        """Initialize fake model output.

        Args:
            prediction_results: Value returned from ``predict``.
        """
        self.prediction_results = prediction_results

    def predict(self, *, source: Any, conf: float, verbose: bool) -> Any:
        """Return configured fake prediction results.

        Args:
            source: PIL image passed by the detector.
            conf: Confidence threshold.
            verbose: Verbose flag.

        Returns:
            Configured prediction results.
        """
        assert source.size == (10, 8)
        assert conf == 0.5
        assert verbose is False
        return self.prediction_results


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


def test_food_yolo_detector_normalizes_review_candidates() -> None:
    """Verify food YOLO emits bounded review-only candidates."""
    detector = FoodYoloDetector(
        model_path="/app/Food-backend/best.pt",
        model_label="food_yolo_local:best.pt",
        min_confidence=0.5,
        max_detections=5,
        model_factory=lambda _path: _FakeModel([_Result()]),
    )

    detections = detector.detect_foods(_png_bytes())

    assert detections == [
        FoodDetection(
            label="rice bowl",
            confidence=0.93,
            bbox=BoundingBox(
                x=0,
                y=0,
                width=1,
                height=1,
                confidence=0.93,
                label="rice bowl",
                model="food_yolo_local:best.pt",
            ),
            model="food_yolo_local:best.pt",
        ),
        FoodDetection(
            label="bibimbap",
            confidence=0.86,
            bbox=BoundingBox(
                x=0,
                y=1,
                width=9,
                height=6,
                confidence=0.86,
                label="bibimbap",
                model="food_yolo_local:best.pt",
            ),
            model="food_yolo_local:best.pt",
        ),
    ]


def test_food_yolo_detector_returns_empty_when_no_food_boxes() -> None:
    """Verify empty detector output degrades to manual-entry candidates."""
    detector = FoodYoloDetector(
        model_path="/app/Food-backend/best.pt",
        model_label="food_yolo_local:best.pt",
        min_confidence=0.5,
        max_detections=5,
        model_factory=lambda _path: _FakeModel([_EmptyResult()]),
    )

    assert detector.detect_foods(_png_bytes()) == []


def test_food_yolo_detector_wraps_model_load_errors() -> None:
    """Verify model load failures expose only a stable vision error."""

    def _failing_factory(_path: str) -> _FakeModel:
        raise RuntimeError("local path missing")

    detector = FoodYoloDetector(
        model_path="/app/Food-backend/best.pt",
        model_label="food_yolo_local:best.pt",
        min_confidence=0.5,
        max_detections=5,
        model_factory=_failing_factory,
    )

    with pytest.raises(VisionError, match="Food YOLO model could not be loaded"):
        detector.detect_foods(_png_bytes())


def test_food_model_label_uses_basename_only() -> None:
    """Verify model metadata does not expose local directory paths."""
    assert (
        food_model_label(
            "/app/Food-backend/private/best.pt",
            "food_yolo_local",
        )
        == "food_yolo_local:best.pt"
    )
    assert food_model_label(None, "food_yolo_local") is None


def test_food_vision_taxonomy_normalizes_region_role_aliases() -> None:
    """Verify meal-image YOLO role labels are stable and non-medical."""
    assert normalize_food_vision_label("meal area") == "meal_region"
    assert normalize_food_vision_label("Food Object") == "food_item"
    assert normalize_food_vision_label("menu-text-region") == "menu_text"
    assert normalize_food_vision_label("Nutrition Facts Panel") == "nutrition_label"
    assert normalize_food_vision_label("diagnosis") is None
    assert normalize_food_vision_label_set(
        ["plate", "food_item", "menu", "nutrition_information", "unknown"]
    ) == ["food_item", "meal_region", "menu_text", "nutrition_label"]
