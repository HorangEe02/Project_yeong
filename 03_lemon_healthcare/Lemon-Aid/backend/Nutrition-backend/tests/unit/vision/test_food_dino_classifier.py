"""FoodDinoClassifier passes the optional CLIP food-filter settings through.

The adapter lazily imports the heavy team classifier, so these tests stub the module
loader and assert the new ``enable_food_filter`` / threshold / model-id kwargs reach the
team ``FoodClassifier`` (and default to off).
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from src.vision import food_dino_classifier
from src.vision.food_dino_classifier import FoodDinoClassifier


class _FakeFoodClassifier:
    """Records the kwargs the adapter constructs it with."""

    last_kwargs: ClassVar[dict[str, Any]] = {}
    filter_builds: ClassVar[int] = 0

    def __init__(self, **kwargs: Any) -> None:
        _FakeFoodClassifier.last_kwargs = dict(kwargs)

    def analyze(self, _image: Any) -> None:
        return None

    def _get_food_filter(self) -> None:
        # Mirrors the team module's lazy CLIP-filter builder so warm-up can be asserted.
        _FakeFoodClassifier.filter_builds += 1


class _FakeModule:
    FoodClassifier = _FakeFoodClassifier


def _adapter(**overrides: Any) -> FoodDinoClassifier:
    kwargs: dict[str, Any] = {
        "module_dir": "/unused",
        "exp16b_model_path": "/x/best.pt",
        "probe_path": "/x/probe.pt",
        "nutrition_csv_path": "/x/n.csv",
        "model_label": "food_dino_exp16b",
        "detector_confidence": 0.1,
        "max_px": 896,
    }
    kwargs.update(overrides)
    return FoodDinoClassifier(**kwargs)


def test_clip_filter_settings_are_passed_to_team_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        food_dino_classifier, "_load_food_classifier_module", lambda _dir: _FakeModule
    )
    adapter = _adapter(
        enable_food_filter=True,
        food_filter_threshold=0.7,
        food_filter_model_id="openai/clip-vit-large-patch14",
    )

    adapter._load_classifier()

    kwargs = _FakeFoodClassifier.last_kwargs
    assert kwargs["enable_food_filter"] is True
    assert kwargs["food_filter_threshold"] == 0.7
    assert kwargs["food_filter_model_id"] == "openai/clip-vit-large-patch14"
    # The existing classifier kwargs still flow through.
    assert kwargs["det_conf"] == 0.1
    assert kwargs["max_px"] == 896


def test_clip_filter_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        food_dino_classifier, "_load_food_classifier_module", lambda _dir: _FakeModule
    )
    adapter = _adapter()

    adapter._load_classifier()

    kwargs = _FakeFoodClassifier.last_kwargs
    assert kwargs["enable_food_filter"] is False
    assert kwargs["food_filter_threshold"] == 0.5
    assert kwargs["food_filter_model_id"] == "openai/clip-vit-base-patch16"


@pytest.fixture(autouse=True)
def _clear_shared_classifiers() -> Any:
    """Isolate the process-shared classifier cache between tests."""
    food_dino_classifier._SHARED_CLASSIFIERS.clear()
    yield
    food_dino_classifier._SHARED_CLASSIFIERS.clear()


def test_get_shared_food_dino_classifier_caches_by_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        food_dino_classifier, "_load_food_classifier_module", lambda _dir: _FakeModule
    )
    first = food_dino_classifier.get_shared_food_dino_classifier(
        module_dir="/u", **_SHARED_FACTORY_KWARGS
    )
    second = food_dino_classifier.get_shared_food_dino_classifier(
        module_dir="/u", **_SHARED_FACTORY_KWARGS
    )
    assert first is second  # same config -> one shared, pre-loaded instance
    other = food_dino_classifier.get_shared_food_dino_classifier(
        module_dir="/u", **{**_SHARED_FACTORY_KWARGS, "model_label": "different"}
    )
    assert other is not first  # different config -> distinct instance


def test_get_shared_food_dino_classifier_is_fail_open_on_load_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(_dir: Any) -> None:
        raise food_dino_classifier.VisionError("module unavailable")

    monkeypatch.setattr(food_dino_classifier, "_load_food_classifier_module", _raise)
    # Eager load fails, but the factory must not raise into the request path.
    instance = food_dino_classifier.get_shared_food_dino_classifier(
        module_dir="/u", **_SHARED_FACTORY_KWARGS
    )
    assert isinstance(instance, FoodDinoClassifier)
    # Cached so the failing load is attempted once, not rebuilt per request.
    again = food_dino_classifier.get_shared_food_dino_classifier(
        module_dir="/u", **_SHARED_FACTORY_KWARGS
    )
    assert again is instance


def test_warmup_builds_clip_filter_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        food_dino_classifier, "_load_food_classifier_module", lambda _dir: _FakeModule
    )
    # A blank dummy image would be rejected by the YOLO gate before analyze() reaches the
    # filter, so warm-up must build the CLIP filter directly via _get_food_filter.
    _FakeFoodClassifier.filter_builds = 0
    _adapter(enable_food_filter=True).warmup()
    assert _FakeFoodClassifier.filter_builds == 1  # filter on -> CLIP filter built at warm-up

    _FakeFoodClassifier.filter_builds = 0
    _adapter().warmup()
    assert _FakeFoodClassifier.filter_builds == 0  # filter off -> not built


_SHARED_FACTORY_KWARGS: dict[str, Any] = {
    "exp16b_model_path": "/x/best.pt",
    "probe_path": "/x/probe.pt",
    "nutrition_csv_path": "/x/n.csv",
    "model_label": "food_dino_exp16b",
    "detector_confidence": 0.1,
    "max_px": 896,
}
