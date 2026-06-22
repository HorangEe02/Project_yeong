"""Optional Ultralytics YOLO runner for food image detection."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

from PIL import Image, UnidentifiedImageError

from src.utils.image_safety import ImageSafetyError, safe_load_with_bomb_guard
from src.vision.base import BoundingBox, VisionError
from src.vision.preprocessing import VisionPreprocessingError, clamp_bounding_box

XYXY_COORDINATE_COUNT = 4


class _PredictModel(Protocol):
    """Small protocol for the Ultralytics model methods used by this runner."""

    names: Any

    def predict(self, *, source: Any, conf: float, verbose: bool) -> Any:
        """Run object detection.

        Args:
            source: Decoded PIL image.
            conf: Minimum confidence.
            verbose: Whether model prediction logs should be printed.

        Returns:
            Ultralytics prediction results.
        """
        ...


ModelFactory = Callable[[str], _PredictModel]


@dataclass(frozen=True)
class FoodDetection:
    """Sanitized food detector output.

    Attributes:
        label: Model class label for user review.
        confidence: Model confidence from 0.0 to 1.0.
        bbox: Pixel-space object box metadata.
        model: Sanitized detector model label.
    """

    label: str
    confidence: float
    bbox: BoundingBox
    model: str


class FoodYoloDetector:
    """Run a local Ultralytics food detector and expose review-only candidates.

    The detector produces food labels, confidence, and bounding boxes only. It
    does not infer nutrition facts, treatment claims, dosage guidance, or
    medical risk.
    """

    def __init__(
        self,
        *,
        model_path: str,
        model_label: str,
        min_confidence: float,
        max_detections: int,
        model_factory: ModelFactory | None = None,
    ) -> None:
        """Initialize a food YOLO detector.

        Args:
            model_path: Local YOLO model path or model tag.
            model_label: Sanitized label exposed in pipeline metadata.
            min_confidence: Minimum detection confidence.
            max_detections: Maximum candidates returned to the review UI.
            model_factory: Optional test factory. Production uses ``ultralytics.YOLO``.

        Raises:
            ValueError: If ``max_detections`` is not positive.
        """
        if max_detections <= 0:
            raise ValueError("max_detections must be > 0")
        self.model_path = model_path
        self.model_label = model_label
        self.min_confidence = min_confidence
        self.max_detections = max_detections
        self.model_factory = model_factory
        self._model: _PredictModel | None = None

    def detect_foods(self, image_bytes: bytes) -> list[FoodDetection]:
        """Detect review-only food candidates from validated image bytes.

        Args:
            image_bytes: Validated JPEG/PNG/WebP image bytes.

        Returns:
            Food detection candidates sorted by confidence. Empty list means no
            reviewable food object was found.

        Raises:
            VisionError: If the model cannot load or prediction fails.
        """
        image, image_width, image_height = _decode_image(image_bytes)
        model = self._load_model()
        try:
            prediction_results = model.predict(
                source=image,
                conf=self.min_confidence,
                verbose=False,
            )
        except Exception as exc:
            raise VisionError("Food YOLO prediction failed.") from exc

        return _normalize_prediction_results(
            prediction_results=prediction_results,
            names=_extract_names(prediction_results, model),
            image_width=image_width,
            image_height=image_height,
            min_confidence=self.min_confidence,
            max_detections=self.max_detections,
            model_label=self.model_label,
        )

    def _load_model(self) -> _PredictModel:
        """Load the optional Ultralytics model lazily.

        Returns:
            Loaded model object.

        Raises:
            VisionError: If the optional dependency or model is unavailable.
        """
        if self._model is not None:
            return self._model
        factory = self.model_factory or _load_ultralytics_yolo
        try:
            self._model = factory(self.model_path)
        except VisionError:
            raise
        except Exception as exc:
            raise VisionError("Food YOLO model could not be loaded.") from exc
        return self._model


def food_model_label(model_path: str | None, configured_label: str) -> str | None:
    """Return a sanitized food detector model label for metadata.

    Args:
        model_path: Configured local model path.
        configured_label: Operator-provided public model label.

    Returns:
        Sanitized metadata label, or None if no model path is configured.
    """
    if model_path is None or not model_path.strip():
        return None
    safe_label = configured_label.strip() or "food_yolo_local"
    return f"{safe_label}:{Path(model_path).name}"


def _load_ultralytics_yolo(model_path: str) -> _PredictModel:
    """Load ``ultralytics.YOLO`` only when food detection is enabled.

    Args:
        model_path: Local model path or model tag.

    Returns:
        Ultralytics YOLO model instance.

    Raises:
        VisionError: If the optional dependency is not installed.
    """
    try:
        yolo_class = cast(Any, import_module("ultralytics")).YOLO
    except ImportError as exc:
        raise VisionError("Install backend .[vision] before enabling food YOLO.") from exc
    return cast(_PredictModel, yolo_class(model_path))


def _decode_image(image_bytes: bytes) -> tuple[Image.Image, int, int]:
    """Decode image bytes into an RGB PIL image for object detection.

    Args:
        image_bytes: Validated image bytes.

    Returns:
        RGB image and decoded dimensions.

    Raises:
        VisionError: If the image cannot be decoded.
    """
    try:
        decoded = safe_load_with_bomb_guard(image_bytes)
    except ImageSafetyError as exc:
        raise VisionError("Image cannot be decoded for food YOLO.") from exc
    try:
        with decoded as image:
            width, height = image.size
            return image.convert("RGB"), width, height
    except (OSError, UnidentifiedImageError) as exc:
        raise VisionError("Image cannot be decoded for food YOLO.") from exc


def _normalize_prediction_results(
    *,
    prediction_results: Any,
    names: Mapping[Any, Any] | Sequence[Any] | None,
    image_width: int,
    image_height: int,
    min_confidence: float,
    max_detections: int,
    model_label: str,
) -> list[FoodDetection]:
    """Normalize Ultralytics boxes into food review candidates.

    Args:
        prediction_results: Raw result list returned by Ultralytics.
        names: Class-id to label mapping.
        image_width: Source image width.
        image_height: Source image height.
        min_confidence: Minimum accepted confidence.
        max_detections: Maximum returned candidate count.
        model_label: Sanitized detector model label.

    Returns:
        Food detections sorted by confidence.
    """
    result = _first_result(prediction_results)
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    coordinates = _as_list(getattr(boxes, "xyxy", None))
    class_ids = _as_list(getattr(boxes, "cls", None))
    confidences = _as_list(getattr(boxes, "conf", None))

    detections: list[FoodDetection] = []
    for index, coordinate in enumerate(coordinates):
        confidence = _float_or_none(_item_at(confidences, index))
        if confidence is None or confidence < min_confidence:
            continue
        label = _label_for_class(_item_at(class_ids, index), names)
        box = _box_from_xyxy(
            coordinate,
            confidence=confidence,
            label=label,
            model_label=model_label,
        )
        try:
            clamped = clamp_bounding_box(box, image_width=image_width, image_height=image_height)
        except VisionPreprocessingError:
            continue
        detections.append(
            FoodDetection(
                label=label,
                confidence=confidence,
                bbox=clamped,
                model=model_label,
            )
        )

    detections.sort(key=lambda detection: detection.confidence, reverse=True)
    return detections[:max_detections]


def _first_result(prediction_results: Any) -> Any:
    """Return the first result object from an Ultralytics prediction output.

    Args:
        prediction_results: Raw prediction output.

    Returns:
        First result object or the input object when it is not a list.
    """
    if isinstance(prediction_results, Sequence) and not isinstance(prediction_results, str | bytes):
        if not prediction_results:
            return None
        return prediction_results[0]
    return prediction_results


def _extract_names(
    prediction_results: Any,
    model: _PredictModel,
) -> Mapping[Any, Any] | Sequence[Any] | None:
    """Extract class names from the result or loaded model.

    Args:
        prediction_results: Raw prediction output.
        model: Loaded model object.

    Returns:
        Class labels, if exposed by the detector.
    """
    result = _first_result(prediction_results)
    for candidate in (getattr(result, "names", None), getattr(model, "names", None)):
        if isinstance(candidate, Mapping | Sequence) and not isinstance(candidate, str | bytes):
            return candidate
    return None


def _as_list(value: Any) -> list[Any]:
    """Convert a tensor-like value into a Python list.

    Args:
        value: Tensor, ndarray, list, tuple, or scalar value.

    Returns:
        Python list representation.
    """
    if value is None:
        return []
    normalized = value
    for method_name in ("detach", "cpu"):
        method = getattr(normalized, method_name, None)
        if callable(method):
            normalized = method()
    tolist = getattr(normalized, "tolist", None)
    if callable(tolist):
        converted = tolist()
        return converted if isinstance(converted, list) else [converted]
    if isinstance(normalized, list):
        return normalized
    if isinstance(normalized, tuple):
        return list(normalized)
    return [normalized]


def _item_at(values: list[Any], index: int) -> Any:
    """Return a list item or None.

    Args:
        values: Candidate list.
        index: Desired item index.

    Returns:
        Item when present.
    """
    return values[index] if index < len(values) else None


def _float_or_none(value: Any) -> float | None:
    """Return a float when conversion is possible.

    Args:
        value: Candidate scalar.

    Returns:
        Float value or None.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _label_for_class(
    class_id: Any,
    names: Mapping[Any, Any] | Sequence[Any] | None,
) -> str:
    """Resolve a class id into a review label.

    Args:
        class_id: Detector class id.
        names: Optional detector names mapping/list.

    Returns:
        Sanitized label.
    """
    class_index = _int_or_none(class_id)
    raw_label: Any = None
    if class_index is not None and names is not None:
        if isinstance(names, Mapping):
            raw_label = names.get(class_index) or names.get(str(class_index))
        elif 0 <= class_index < len(names):
            raw_label = names[class_index]
    if raw_label is None and class_index is not None:
        raw_label = f"class_{class_index}"
    return _sanitize_label(str(raw_label or "unknown_food"))


def _int_or_none(value: Any) -> int | None:
    """Return an int when conversion is possible.

    Args:
        value: Candidate scalar.

    Returns:
        Integer value or None.
    """
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _sanitize_label(value: str) -> str:
    """Normalize a detector label for safe user review.

    Args:
        value: Raw detector label.

    Returns:
        Bounded label string.
    """
    normalized = value.strip().replace("_", " ")
    if not normalized:
        return "unknown food"
    return normalized[:120]


def _box_from_xyxy(
    coordinate: Any,
    *,
    confidence: float,
    label: str,
    model_label: str,
) -> BoundingBox:
    """Build a BoundingBox from an Ultralytics xyxy coordinate row.

    Args:
        coordinate: Sequence-like ``[x1, y1, x2, y2]``.
        confidence: Detection confidence.
        label: Detection label.
        model_label: Detector model label.

    Returns:
        Bounding box metadata.

    Raises:
        VisionPreprocessingError: If coordinates are malformed.
    """
    values = _as_list(coordinate)
    if len(values) < XYXY_COORDINATE_COUNT:
        raise VisionPreprocessingError("Food YOLO box is missing coordinates.")
    x_min, y_min, x_max, y_max = (round(float(values[i])) for i in range(4))
    if x_min >= x_max or y_min >= y_max:
        raise VisionPreprocessingError("Food YOLO box has invalid coordinate order.")
    return BoundingBox(
        x=x_min,
        y=y_min,
        width=x_max - x_min,
        height=y_max - y_min,
        confidence=confidence,
        label=label,
        model=model_label,
    )
