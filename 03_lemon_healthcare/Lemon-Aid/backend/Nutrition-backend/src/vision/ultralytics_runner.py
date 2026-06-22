"""Optional Ultralytics YOLO runner for supplement ROI detection."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from typing import Any, Protocol, cast

from PIL import Image, UnidentifiedImageError

from src.utils.image_safety import ImageSafetyError, safe_load_with_bomb_guard
from src.vision.base import BoundingBox, VisionError
from src.vision.preprocessing import VisionPreprocessingError, clamp_bounding_box
from src.vision.taxonomy import VISION_SECTION_LABELS, label_priority, normalize_vision_label

XYXY_COORDINATE_COUNT = 4


class _PredictModel(Protocol):
    """Small protocol for the Ultralytics model methods used by this runner."""

    names: Any

    def predict(self, *, source: Any, conf: float, verbose: bool) -> Any:
        """Run object detection.

        Args:
            source: Decoded PIL image.
            conf: Minimum confidence.
            verbose: Whether the model should print prediction logs.

        Returns:
            Ultralytics prediction results.
        """
        ...


ModelFactory = Callable[[str], _PredictModel]


class UltralyticsYoloRunner:
    """Run a gated Ultralytics object detector and normalize ROI boxes.

    The runner intentionally exposes only bounding-box metadata. Product names,
    ingredients, supplement amounts, and dosage facts are outside the object
    detection contract and must remain in OCR/text parsing paths.
    """

    def __init__(
        self,
        *,
        model_name: str,
        allowed_labels: set[str],
        min_confidence: float,
        max_detections: int,
        model_factory: ModelFactory | None = None,
    ) -> None:
        """Initialize the optional YOLO runner.

        Args:
            model_name: Local model path or model tag configured for ROI detection.
            allowed_labels: Canonical ROI labels accepted by the pipeline.
            min_confidence: Minimum detection confidence accepted as an OCR ROI.
            max_detections: Maximum ROI boxes returned, keeping the highest-priority
                sections (priority dominant, confidence as tie-breaker).
            model_factory: Optional test factory. Production uses ``ultralytics.YOLO``.

        Raises:
            ValueError: If ``max_detections`` is not positive.
        """
        if max_detections <= 0:
            raise ValueError("max_detections must be > 0")
        self.model_name = model_name
        self.allowed_labels = allowed_labels
        self.min_confidence = min_confidence
        self.max_detections = max_detections
        self.model_factory = model_factory
        self._model: _PredictModel | None = None

    def detect_regions(self, image_bytes: bytes) -> list[BoundingBox]:
        """Detect allowed supplement ROI boxes from validated image bytes.

        Args:
            image_bytes: Validated JPEG/PNG/WebP image bytes.

        Returns:
            Allowed, clamped bounding boxes sorted by caller-owned selection logic.

        Raises:
            VisionError: If the model cannot run or no allowed boxes can be normalized.
        """
        image, image_width, image_height = _decode_image(image_bytes)
        model = self._load_model()
        names = _extract_model_names(model)
        _validate_model_class_contract(
            names=names,
            allowed_labels=self.allowed_labels,
        )
        try:
            prediction_results = model.predict(
                source=image,
                conf=self.min_confidence,
                verbose=False,
            )
        except Exception as exc:
            raise VisionError("Ultralytics YOLO prediction failed.") from exc
        return _normalize_prediction_results(
            prediction_results=prediction_results,
            names=names,
            image_width=image_width,
            image_height=image_height,
            allowed_labels=self.allowed_labels,
            min_confidence=self.min_confidence,
            max_detections=self.max_detections,
            model_name=self.model_name,
        )

    def _load_model(self) -> _PredictModel:
        """Load the optional Ultralytics model lazily.

        Returns:
            Loaded model object.

        Raises:
            VisionError: If the optional dependency is unavailable.
        """
        if self._model is not None:
            return self._model
        factory = self.model_factory or _load_ultralytics_yolo
        self._model = factory(self.model_name)
        return self._model


def _load_ultralytics_yolo(model_name: str) -> _PredictModel:
    """Load ``ultralytics.YOLO`` only when the gated runner is used.

    Args:
        model_name: Local model path or model tag.

    Returns:
        Ultralytics YOLO model instance.

    Raises:
        VisionError: If the optional dependency is not installed.
    """
    try:
        yolo_class = cast(Any, import_module("ultralytics")).YOLO
    except ImportError as exc:
        raise VisionError("Install backend .[vision] before enabling YOLO detection.") from exc
    return cast(_PredictModel, yolo_class(model_name))


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
        raise VisionError("Image cannot be decoded for YOLO detection.") from exc

    try:
        with decoded as image:
            width, height = image.size
            return image.convert("RGB"), width, height
    except (OSError, UnidentifiedImageError) as exc:
        raise VisionError("Image cannot be decoded for YOLO detection.") from exc


def _normalize_prediction_results(
    *,
    prediction_results: Any,
    names: Mapping[Any, Any] | Sequence[Any] | None,
    image_width: int,
    image_height: int,
    allowed_labels: set[str],
    min_confidence: float,
    max_detections: int,
    model_name: str,
) -> list[BoundingBox]:
    """Normalize Ultralytics boxes into the internal ``BoundingBox`` contract.

    Args:
        prediction_results: Raw result list returned by Ultralytics.
        names: Model class-id to label mapping.
        image_width: Source image width.
        image_height: Source image height.
        allowed_labels: Canonical ROI labels accepted by the pipeline.
        min_confidence: Minimum confidence.
        max_detections: Maximum boxes returned, keeping the highest-priority sections.
        model_name: Model tag or path for metadata.

    Returns:
        Normalized bounding boxes ordered by section priority (confidence as
        tie-breaker) and capped at ``max_detections``, matching the downstream
        ``select_best_label_region`` / ``_ordered_ocr_regions`` ranking so the cap
        never drops a higher-priority section in favor of a lower-priority one.

    Raises:
        VisionError: If the result shape is unsupported or no allowed boxes remain.
    """
    result = _first_result(prediction_results)
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        raise VisionError("Ultralytics YOLO result did not include boxes.")

    coordinates = _as_list(getattr(boxes, "xyxy", None))
    class_ids = _as_list(getattr(boxes, "cls", None))
    confidences = _as_list(getattr(boxes, "conf", None))

    regions: list[BoundingBox] = []
    for index, coordinate in enumerate(coordinates):
        label = _label_for_class(_item_at(class_ids, index), names)
        canonical_label = normalize_vision_label(label or "")
        if canonical_label is None or canonical_label not in allowed_labels:
            continue

        confidence = _float_or_none(_item_at(confidences, index))
        if confidence is None or confidence < min_confidence:
            continue

        box = _box_from_xyxy(
            coordinate,
            confidence=confidence,
            label=canonical_label,
            model_name=model_name,
        )
        try:
            regions.append(
                clamp_bounding_box(
                    box,
                    image_width=image_width,
                    image_height=image_height,
                )
            )
        except VisionPreprocessingError:
            continue

    if not regions:
        raise VisionError("YOLO did not detect an allowed supplement ROI.")
    # Truncate with the same (priority, -confidence) key the downstream selectors use
    # (preprocessing.select_best_label_region, _ordered_ocr_regions) so a high-priority
    # section is never crowded out of the source cap by lower-priority high-confidence boxes.
    regions.sort(key=lambda region: (label_priority(region.label), -region.confidence))
    return regions[:max_detections]


def _first_result(prediction_results: Any) -> Any:
    """Return the first result object from an Ultralytics prediction output.

    Args:
        prediction_results: Raw prediction output.

    Returns:
        First result object.

    Raises:
        VisionError: If the output is empty.
    """
    if isinstance(prediction_results, Sequence) and not isinstance(prediction_results, str | bytes):
        if not prediction_results:
            raise VisionError("Ultralytics YOLO returned no results.")
        return prediction_results[0]
    return prediction_results


def _extract_model_names(model: _PredictModel) -> Mapping[Any, Any] | Sequence[Any] | None:
    """Extract model class names from a loaded detector.

    Args:
        model: Loaded model object.

    Returns:
        Model class labels, when exposed by the detector.
    """
    try:
        names = getattr(model, "names", None)
    except AttributeError:
        return None
    if isinstance(names, Mapping | Sequence) and not isinstance(names, str | bytes):
        return names
    return None


def _validate_model_class_contract(
    *,
    names: Mapping[Any, Any] | Sequence[Any] | None,
    allowed_labels: set[str],
) -> None:
    """Fail closed when a YOLO model is not a supplement section detector.

    Args:
        names: Model class-id to label mapping exposed by Ultralytics.
        allowed_labels: Canonical ROI labels accepted by the pipeline.

    Raises:
        VisionError: If class names are missing or incompatible with supplement ROI OCR.
    """
    supported_labels = _supported_supplement_labels(names)
    if not supported_labels:
        raise VisionError("YOLO model class names do not match supplement ROI taxonomy.")
    if not (supported_labels & allowed_labels):
        raise VisionError(
            "YOLO model class names do not match configured VISION_ROI_ALLOWED_CLASSES."
        )
    if not (supported_labels & VISION_SECTION_LABELS):
        raise VisionError("YOLO model must expose supplement section ROI classes.")


def _supported_supplement_labels(
    names: Mapping[Any, Any] | Sequence[Any] | None,
) -> set[str]:
    """Return supplement ROI labels exposed by a loaded YOLO model.

    Args:
        names: Model class-id to label mapping exposed by Ultralytics.

    Returns:
        Canonical supplement ROI labels present in the model class names.
    """
    if names is None:
        return set()
    return {
        normalized
        for label in _iter_model_name_values(names)
        if (normalized := normalize_vision_label(label)) is not None
    }


def _iter_model_name_values(names: Mapping[Any, Any] | Sequence[Any]) -> list[str]:
    """Extract string label values from a model class-name mapping.

    Args:
        names: Mapping or sequence exposed by the loaded detector.

    Returns:
        Raw string labels.
    """
    values = names.values() if isinstance(names, Mapping) else names
    return [value for value in values if isinstance(value, str)]


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
        listed = tolist()
        return listed if isinstance(listed, list) else [listed]
    if isinstance(normalized, list):
        return normalized
    if isinstance(normalized, tuple):
        return list(normalized)
    return [normalized]


def _item_at(values: list[Any], index: int) -> Any:
    """Return a list item by index without raising ``IndexError``.

    Args:
        values: Candidate list.
        index: Desired item index.

    Returns:
        Item value or None.
    """
    if index >= len(values):
        return None
    return values[index]


def _label_for_class(
    class_value: Any,
    names: Mapping[Any, Any] | Sequence[Any] | None,
) -> str | None:
    """Resolve a class id into a raw model label.

    Args:
        class_value: Raw class id from Ultralytics boxes.
        names: Class-id to label mapping or sequence.

    Returns:
        Model label or None.
    """
    class_id = _int_or_none(class_value)
    if class_id is None or names is None:
        return None
    value: Any
    if isinstance(names, Mapping):
        value = names.get(class_id)
        if value is None:
            value = names.get(str(class_id))
    elif 0 <= class_id < len(names):
        value = names[class_id]
    else:
        value = None
    return value.strip() if isinstance(value, str) else None


def _box_from_xyxy(
    coordinate: Any,
    *,
    confidence: float,
    label: str,
    model_name: str,
) -> BoundingBox:
    """Build a bounding box from Ultralytics ``xyxy`` coordinates.

    Args:
        coordinate: Four-value coordinate sequence.
        confidence: Detector confidence.
        label: Canonical ROI label.
        model_name: Detector model tag or path.

    Returns:
        Internal bounding box.

    Raises:
        VisionError: If coordinates cannot be interpreted.
    """
    values = _as_list(coordinate)
    if len(values) < XYXY_COORDINATE_COUNT:
        raise VisionError("Ultralytics YOLO box coordinates are invalid.")
    x1 = _float_or_none(values[0])
    y1 = _float_or_none(values[1])
    x2 = _float_or_none(values[2])
    y2 = _float_or_none(values[3])
    if x1 is None or y1 is None or x2 is None or y2 is None:
        raise VisionError("Ultralytics YOLO box coordinates are not numeric.")
    return BoundingBox(
        x=round(x1),
        y=round(y1),
        width=round(x2 - x1),
        height=round(y2 - y1),
        confidence=confidence,
        label=label,
        model=model_name,
    )


def _float_or_none(value: Any) -> float | None:
    """Convert a candidate value to float.

    Args:
        value: Candidate numeric value.

    Returns:
        Float value or None.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    """Convert a candidate class id to int.

    Args:
        value: Candidate class id.

    Returns:
        Integer value or None.
    """
    numeric = _float_or_none(value)
    if numeric is None:
        return None
    return int(numeric)
