"""Optional DINOv3 food classifier adapter for meal image previews."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import util
from pathlib import Path
from typing import Any, Protocol, cast

from PIL import Image, UnidentifiedImageError

from src.utils.image_safety import ImageSafetyError, safe_load_with_bomb_guard
from src.vision.base import BoundingBox, VisionError
from src.vision.preprocessing import VisionPreprocessingError, clamp_bounding_box

logger = logging.getLogger(__name__)

XYXY_COORDINATE_COUNT = 4


class _FoodClassifierModule(Protocol):
    """Protocol for the imported team food classifier module."""

    FoodClassifier: type[Any]


@dataclass(frozen=True)
class FoodClassification:
    """Sanitized DINO food classification output.

    Attributes:
        name_en: Classifier English class key.
        display_name: User-facing class name, usually Korean.
        confidence: Classifier confidence from 0.0 to 1.0.
        bbox: Optional gate detector bounding box in source image coordinates.
        model: Sanitized classifier model label.
        nutrition: Optional per-100g nutrition row from the 40-class table.
    """

    name_en: str
    display_name: str
    confidence: float
    bbox: BoundingBox | None
    model: str
    nutrition: Mapping[str, object] | None


class FoodDinoClassifier:
    """Load and run the imported exp16b + DINOv3 single-dish classifier lazily."""

    def __init__(
        self,
        *,
        module_dir: str,
        exp16b_model_path: str,
        probe_path: str,
        nutrition_csv_path: str,
        model_label: str,
        detector_confidence: float,
        max_px: int,
        enable_food_filter: bool = False,
        food_filter_threshold: float = 0.5,
        food_filter_model_id: str = "openai/clip-vit-base-patch16",
    ) -> None:
        """Initialize the adapter without loading heavy ML dependencies.

        Args:
            module_dir: Directory containing the imported ``food_classifier.py``.
            exp16b_model_path: Local exp16b YOLO gate weight path.
            probe_path: Local DINOv3 linear probe checkpoint path.
            nutrition_csv_path: Local 40-class nutrition CSV path.
            model_label: Sanitized classifier label exposed in metadata.
            detector_confidence: Food gate confidence threshold passed to the team classifier.
            max_px: Maximum image side length passed to the team classifier.
            enable_food_filter: Enable the CLIP non-food filter between the YOLO gate
                and DINOv3 classification (off by default).
            food_filter_threshold: CLIP food-probability cutoff for the filter.
            food_filter_model_id: HuggingFace CLIP model id for the filter.
        """
        self.module_dir = Path(module_dir)
        self.exp16b_model_path = exp16b_model_path
        self.probe_path = probe_path
        self.nutrition_csv_path = nutrition_csv_path
        self.model_label = model_label
        self.detector_confidence = detector_confidence
        self.max_px = max_px
        self.enable_food_filter = enable_food_filter
        self.food_filter_threshold = food_filter_threshold
        self.food_filter_model_id = food_filter_model_id
        self._classifier: Any | None = None

    def classify_food(self, image_bytes: bytes) -> FoodClassification | None:
        """Classify a validated food image into one review-only food candidate.

        Args:
            image_bytes: Request-local normalized JPEG/PNG/WebP image bytes.

        Returns:
            Sanitized classification result, or None when the gate finds no food.

        Raises:
            VisionError: If the module, model, or prediction cannot run.
        """
        image, image_width, image_height = _decode_image(image_bytes)
        classifier = self._load_classifier()
        started = time.perf_counter()
        try:
            raw_result = classifier.analyze(image)
        except Exception as exc:
            raise VisionError("Food DINO classifier prediction failed.") from exc
        # PII-free latency signal (duration + flag only) so the CLIP stage cost is
        # observable in logs before/after enabling the non-food filter.
        logger.info(
            "food_classify total_ms=%d filter_enabled=%s",
            int((time.perf_counter() - started) * 1000),
            self.enable_food_filter,
        )
        if raw_result is None:
            return None
        if not isinstance(raw_result, dict):
            raise VisionError("Food DINO classifier returned an invalid result.")

        name_en = _required_string(raw_result.get("name_en"), "name_en")
        display_name = _required_string(raw_result.get("name_ko"), "name_ko")
        confidence = _required_confidence(raw_result.get("conf"))
        bbox = _classification_box(
            raw_result.get("box"),
            image_width=image_width,
            image_height=image_height,
            confidence=confidence,
            label=name_en,
            model=self.model_label,
        )
        nutrition = raw_result.get("nutrition")
        if nutrition is not None and not isinstance(nutrition, Mapping):
            nutrition = None

        return FoodClassification(
            name_en=name_en,
            display_name=display_name,
            confidence=confidence,
            bbox=bbox,
            model=self.model_label,
            nutrition=cast(Mapping[str, object] | None, nutrition),
        )

    def _load_classifier(self) -> Any:
        """Load the team classifier and heavy dependencies on first use.

        Returns:
            Imported ``FoodClassifier`` instance.

        Raises:
            VisionError: If the module or optional ML dependencies are unavailable.
        """
        if self._classifier is not None:
            return self._classifier
        module = _load_food_classifier_module(self.module_dir)
        try:
            self._classifier = module.FoodClassifier(
                exp16b_path=self.exp16b_model_path,
                probe_path=self.probe_path,
                nutrition_csv=self.nutrition_csv_path,
                det_conf=self.detector_confidence,
                max_px=self.max_px,
                enable_food_filter=self.enable_food_filter,
                food_filter_threshold=self.food_filter_threshold,
                food_filter_model_id=self.food_filter_model_id,
            )
        except Exception as exc:
            raise VisionError("Food DINO classifier could not be loaded.") from exc
        return self._classifier

    def ensure_loaded(self) -> None:
        """Eagerly load the YOLO gate + DINOv3 models (idempotent).

        Raises:
            VisionError: If the team module or model weights cannot be loaded.
        """
        self._load_classifier()

    def warmup(self) -> None:
        """Load every model now so the first request does not pay the cost.

        Loads YOLO + DINOv3; when the CLIP non-food filter is enabled, eagerly builds
        the lazy ~600MB CLIP filter too. A throwaway image cannot warm the filter — the
        YOLO gate rejects it before ``analyze`` reaches the filter — so the team module's
        lazy filter build is triggered directly. Best-effort: the team build is itself
        fail-open, and the request path still degrades to "no classifier" on any failure.
        """
        classifier = self._load_classifier()
        if not self.enable_food_filter:
            return
        # ``_get_food_filter`` is the team module's lazy, fail-open CLIP builder.
        build_clip_filter = getattr(classifier, "_get_food_filter", None)
        if callable(build_clip_filter):
            build_clip_filter()


def food_classifier_model_label(configured_label: str, probe_path: str | None) -> str | None:
    """Return a sanitized classifier model label for API metadata.

    Args:
        configured_label: Operator-provided public model label.
        probe_path: Local probe checkpoint path.

    Returns:
        Sanitized metadata label, or None when no probe path is configured.
    """
    if probe_path is None or not probe_path.strip():
        return None
    safe_label = configured_label.strip() or "food_dino_classifier"
    return f"{safe_label}:{Path(probe_path).name}"


_SHARED_LOCK = threading.Lock()
_SHARED_CLASSIFIERS: dict[tuple[object, ...], FoodDinoClassifier] = {}


def get_shared_food_dino_classifier(
    *,
    module_dir: str,
    exp16b_model_path: str,
    probe_path: str,
    nutrition_csv_path: str,
    model_label: str,
    detector_confidence: float,
    max_px: int,
    enable_food_filter: bool = False,
    food_filter_threshold: float = 0.5,
    food_filter_model_id: str = "openai/clip-vit-base-patch16",
) -> FoodDinoClassifier:
    """Return a process-shared classifier, loaded once, keyed on its configuration.

    The meal pipeline otherwise builds a fresh classifier per request, reloading
    YOLO+DINOv3 (and the ~600MB CLIP filter) every time. Caching one instance per
    configuration — built and eagerly loaded under a lock — means the heavy models load
    once per process. Eager load failures are swallowed (the instance is still cached and
    retries lazily on use, where the meal service already fails open), so this never
    raises into the request path. Tests inject their own classifier via the
    ``food_classifier`` parameter and bypass this entirely.

    Args:
        Mirror :class:`FoodDinoClassifier`.

    Returns:
        The shared classifier instance for this configuration.
    """
    key: tuple[object, ...] = (
        module_dir,
        exp16b_model_path,
        probe_path,
        nutrition_csv_path,
        model_label,
        round(detector_confidence, 4),
        max_px,
        enable_food_filter,
        round(food_filter_threshold, 4),
        food_filter_model_id,
    )
    instance = _SHARED_CLASSIFIERS.get(key)
    if instance is not None:
        return instance
    with _SHARED_LOCK:
        instance = _SHARED_CLASSIFIERS.get(key)
        if instance is None:
            instance = FoodDinoClassifier(
                module_dir=module_dir,
                exp16b_model_path=exp16b_model_path,
                probe_path=probe_path,
                nutrition_csv_path=nutrition_csv_path,
                model_label=model_label,
                detector_confidence=detector_confidence,
                max_px=max_px,
                enable_food_filter=enable_food_filter,
                food_filter_threshold=food_filter_threshold,
                food_filter_model_id=food_filter_model_id,
            )
            try:
                instance.ensure_loaded()
            except VisionError:
                logger.warning(
                    "Shared food classifier eager load failed; retrying lazily per request.",
                    exc_info=True,
                )
            _SHARED_CLASSIFIERS[key] = instance
    return instance


def _load_food_classifier_module(module_dir: Path) -> _FoodClassifierModule:
    """Import ``food_classifier.py`` from the canonical Food-backend module.

    Args:
        module_dir: Directory containing ``food_classifier.py``.

    Returns:
        Imported module exposing ``FoodClassifier``.

    Raises:
        VisionError: If the module file cannot be imported.
    """
    module_path = module_dir / "food_classifier.py"
    if not module_path.is_file():
        raise VisionError("Food classifier module is not available in the backend image.")
    spec = util.spec_from_file_location("lemon_team_food_classifier", module_path)
    if spec is None or spec.loader is None:
        raise VisionError("Food classifier module could not be loaded.")
    module = util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as exc:
        raise VisionError(
            "Install backend vision dependencies before enabling the food DINO classifier."
        ) from exc
    except Exception as exc:
        raise VisionError("Food classifier module import failed.") from exc
    if not hasattr(module, "FoodClassifier"):
        raise VisionError("Food classifier module does not expose FoodClassifier.")
    return cast(_FoodClassifierModule, module)


def _decode_image(image_bytes: bytes) -> tuple[Image.Image, int, int]:
    """Decode image bytes into an RGB image for classification.

    Args:
        image_bytes: Validated image bytes.

    Returns:
        RGB image and decoded source dimensions.

    Raises:
        VisionError: If the image cannot be decoded.
    """
    try:
        decoded = safe_load_with_bomb_guard(image_bytes)
    except ImageSafetyError as exc:
        raise VisionError("Image cannot be decoded for food classification.") from exc
    try:
        with decoded as image:
            width, height = image.size
            return image.convert("RGB"), int(width), int(height)
    except (OSError, UnidentifiedImageError) as exc:
        raise VisionError("Image cannot be decoded for food classification.") from exc


def _classification_box(
    raw_box: object,
    *,
    image_width: int,
    image_height: int,
    confidence: float,
    label: str,
    model: str,
) -> BoundingBox | None:
    """Convert an optional xyxy gate box into a bounded pixel box.

    Args:
        raw_box: Team classifier ``box`` payload.
        image_width: Source image width.
        image_height: Source image height.
        confidence: Classification confidence used for metadata.
        label: Classified food label.
        model: Public classifier model label.

    Returns:
        Clamped bounding box or None when the payload is absent/invalid.
    """
    if not isinstance(raw_box, list | tuple) or len(raw_box) != XYXY_COORDINATE_COUNT:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in raw_box)
        box = BoundingBox(
            x=round(x1),
            y=round(y1),
            width=round(x2 - x1),
            height=round(y2 - y1),
            confidence=confidence,
            label=label,
            model=model,
        )
        return clamp_bounding_box(box, image_width=image_width, image_height=image_height)
    except (TypeError, ValueError, VisionPreprocessingError):
        return None


def _required_string(value: object, field_name: str) -> str:
    """Return a non-empty string field from a classifier result.

    Args:
        value: Candidate value.
        field_name: Field name used in the error message.

    Returns:
        Trimmed string.

    Raises:
        VisionError: If the value is missing or empty.
    """
    if not isinstance(value, str) or not value.strip():
        raise VisionError(f"Food DINO classifier returned invalid {field_name}.")
    return value.strip()


def _required_confidence(value: object) -> float:
    """Return a bounded confidence value from a classifier result.

    Args:
        value: Candidate confidence.

    Returns:
        Confidence clipped to the API range.

    Raises:
        VisionError: If the value is not numeric.
    """
    if not isinstance(value, int | float):
        raise VisionError("Food DINO classifier returned invalid confidence.")
    return max(0.0, min(float(value), 1.0))
