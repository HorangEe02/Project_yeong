"""PaddleOCR fallback provider tests."""

from __future__ import annotations

import asyncio
import sys
import threading
import time
import types
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from src.config import Settings
from src.ocr.base import OCRError, OCRImageInput
from src.ocr.providers.paddle import (
    PADDLE_MOBILE_TEXT_DETECTION_MODEL,
    PADDLE_OCR_PROVIDER,
    PADDLE_SERVER_TEXT_DETECTION_MODEL,
    PADDLE_SERVER_TEXT_RECOGNITION_MODEL,
    PaddleOCRAdapter,
    _get_paddle_predictor,
)


class _FakePaddlePredictor:
    """Fake PaddleOCR predictor."""

    def __init__(self, prediction: object) -> None:
        self.prediction = prediction
        self.received_path: str | None = None
        self.received_kwargs: dict[str, object] = {}

    def predict(self, image_path: str, **kwargs: object) -> object:
        """Capture the image path and return configured prediction data.

        Args:
            image_path: Temporary image path.
            kwargs: PaddleOCR prediction-time tuning parameters.

        Returns:
            Fake prediction data.
        """
        self.received_path = image_path
        self.received_kwargs = dict(kwargs)
        return self.prediction


class _ReadingFakePaddlePredictor(_FakePaddlePredictor):
    """Fake predictor that records temporary OCR input bytes."""

    def __init__(self, prediction: object) -> None:
        """Initialize prediction and captured-byte storage."""
        super().__init__(prediction)
        self.received_bytes: bytes | None = None

    def predict(self, image_path: str, **kwargs: object) -> object:
        """Capture temporary file bytes and return configured prediction data."""
        self.received_path = image_path
        self.received_kwargs = dict(kwargs)
        with Path(image_path).open("rb") as file:
            self.received_bytes = file.read()
        return self.prediction


def _image_input() -> OCRImageInput:
    """Return a minimal OCR image input.

    Returns:
        OCR image input.
    """
    return OCRImageInput(
        image_bytes=b"fake-png-bytes",
        mime_type="image/png",
        width=10,
        height=8,
    )


def _valid_png_image_input() -> OCRImageInput:
    """Return a valid PNG OCR image input for preprocessing tests."""
    buffer = BytesIO()
    Image.new("RGB", (20, 12), (240, 240, 240)).save(buffer, format="PNG")
    return OCRImageInput(
        image_bytes=buffer.getvalue(),
        mime_type="image/png",
        width=20,
        height=12,
    )


@pytest.mark.asyncio
async def test_paddle_adapter_flattens_prediction_text_and_scores() -> None:
    """Verify PaddleOCR fallback normalizes common 3.x prediction fields."""
    predictor = _FakePaddlePredictor(
        [{"rec_texts": ["비타민 D 1000", "비타민 D 25 ug"], "rec_scores": [0.92, 0.88]}]
    )
    adapter = PaddleOCRAdapter(
        Settings(_env_file=None, enable_local_ocr=True, local_ocr_preprocess_mode="none"),
        predictor=predictor,
    )

    result = await adapter.extract_text(_image_input())

    assert result.provider == PADDLE_OCR_PROVIDER
    assert result.text == "비타민 D 1000\n비타민 D 25 ug"
    assert result.confidence == pytest.approx(0.90)
    assert predictor.received_path is not None


@pytest.mark.asyncio
async def test_paddle_adapter_normalizes_line_layout_from_rec_polys() -> None:
    """Verify PaddleOCR rec_texts and rec_polys become OCR layout pages."""
    predictor = _FakePaddlePredictor(
        [
            {
                "rec_texts": ["비타민 D 1000", "비타민 D 25 ug"],
                "rec_scores": [0.92, 0.88],
                "rec_polys": [
                    [[1, 2], [9, 2], [9, 4], [1, 4]],
                    [[1, 5], [9, 5], [9, 7], [1, 7]],
                ],
            }
        ]
    )
    adapter = PaddleOCRAdapter(
        Settings(_env_file=None, enable_local_ocr=True, local_ocr_preprocess_mode="none"),
        predictor=predictor,
    )

    result = await adapter.extract_text(_image_input())

    assert result.provider == PADDLE_OCR_PROVIDER
    assert result.text == "비타민 D 1000\n비타민 D 25 ug"
    assert len(result.pages) == 1
    page = result.pages[0]
    assert page.width == 10
    assert page.height == 8
    assert page.confidence == pytest.approx(0.90)
    assert [block.text for block in page.blocks] == ["비타민 D 1000", "비타민 D 25 ug"]
    assert page.blocks[0].block_type == "TEXT"
    assert page.blocks[0].paragraphs[0].words[0].text == "비타민 D 1000"
    assert page.blocks[0].paragraphs[0].words[0].block_index == 0
    assert page.blocks[1].paragraphs[0].words[0].block_index == 1
    assert page.blocks[0].bounding_box is not None
    assert page.blocks[0].bounding_box.vertices[0].x == 1
    assert page.blocks[0].bounding_box.vertices[0].y == 2


@pytest.mark.asyncio
async def test_paddle_adapter_builds_row_grouped_text_for_parser() -> None:
    """Verify same-row layout cells are ordered before OCR text reaches the parser."""
    predictor = _FakePaddlePredictor(
        [
            {
                "rec_texts": ["10 mg", "아연", "50%", "25 μg", "비타민 D"],
                "rec_scores": [0.92, 0.93, 0.91, 0.88, 0.90],
                "rec_polys": [
                    [[4, 2], [6, 2], [6, 4], [4, 4]],
                    [[1, 2], [3, 2], [3, 4], [1, 4]],
                    [[7, 2], [9, 2], [9, 4], [7, 4]],
                    [[4, 8], [6, 8], [6, 10], [4, 10]],
                    [[1, 8], [3, 8], [3, 10], [1, 10]],
                ],
            }
        ]
    )
    adapter = PaddleOCRAdapter(
        Settings(_env_file=None, enable_local_ocr=True, local_ocr_preprocess_mode="none"),
        predictor=predictor,
    )

    result = await adapter.extract_text(_image_input())

    assert result.text == "아연\t10 mg\t50%\n비타민 D\t25 μg"


@pytest.mark.asyncio
async def test_paddle_adapter_normalizes_line_layout_from_rec_boxes() -> None:
    """Verify PaddleOCR rec_boxes fallback produces rectangular layout polygons."""
    predictor = _FakePaddlePredictor(
        [
            {
                "rec_texts": ["", "아연 10 mg"],
                "rec_scores": [0.50, 0.91],
                "rec_boxes": [[0, 0, 1, 1], [2, 3, 8, 6]],
            }
        ]
    )
    adapter = PaddleOCRAdapter(
        Settings(_env_file=None, enable_local_ocr=True, local_ocr_preprocess_mode="none"),
        predictor=predictor,
    )

    result = await adapter.extract_text(_image_input())

    assert result.text == "아연 10 mg"
    assert len(result.pages) == 1
    word = result.pages[0].blocks[0].paragraphs[0].words[0]
    assert word.text == "아연 10 mg"
    assert word.confidence == pytest.approx(0.91)
    assert word.block_index == 0
    assert word.bounding_box is not None
    assert [(vertex.x, vertex.y) for vertex in word.bounding_box.vertices] == [
        (2, 3),
        (8, 3),
        (8, 6),
        (2, 6),
    ]


@pytest.mark.asyncio
async def test_paddle_adapter_preprocess_mode_reencodes_temp_png_only() -> None:
    """Verify opt-in preprocessing changes only the local temporary OCR input."""
    predictor = _ReadingFakePaddlePredictor([{"rec_texts": ["아연 10 mg"], "rec_scores": [0.91]}])
    adapter = PaddleOCRAdapter(
        Settings(
            _env_file=None,
            enable_local_ocr=True,
            local_ocr_preprocess_mode="autocontrast",
        ),
        predictor=predictor,
    )

    result = await adapter.extract_text(_valid_png_image_input())

    assert result.text == "아연 10 mg"
    assert predictor.received_path is not None
    assert predictor.received_path.endswith(".png")
    assert predictor.received_bytes is not None
    assert predictor.received_bytes.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_paddle_adapter_preprocess_failure_is_bounded() -> None:
    """Verify invalid images fail with a bounded preprocessing error."""
    adapter = PaddleOCRAdapter(
        Settings(
            _env_file=None,
            enable_local_ocr=True,
            local_ocr_preprocess_mode="grayscale_autocontrast",
        ),
        predictor=_FakePaddlePredictor([]),
    )

    with pytest.raises(OCRError, match="preprocessing failed"):
        await adapter.extract_text(_image_input())


@pytest.mark.asyncio
async def test_paddle_adapter_forwards_predict_tuning_kwargs() -> None:
    """Verify operator OCR tuning flags are passed to PaddleOCR predict()."""
    predictor = _FakePaddlePredictor([{"rec_texts": ["아연 10 mg"], "rec_scores": [0.91]}])
    adapter = PaddleOCRAdapter(
        Settings(
            _env_file=None,
            enable_local_ocr=True,
            local_ocr_preprocess_mode="none",
            local_ocr_text_det_limit_side_len=1216,
            local_ocr_text_det_limit_type="max",
            local_ocr_text_det_thresh=0.2,
            local_ocr_text_det_box_thresh=0.5,
            local_ocr_text_det_unclip_ratio=3.0,
            local_ocr_text_rec_score_thresh=0.15,
        ),
        predictor=predictor,
    )

    result = await adapter.extract_text(_image_input())

    assert result.text == "아연 10 mg"
    assert predictor.received_kwargs == {
        "text_det_limit_side_len": 1216,
        "text_det_limit_type": "max",
        "text_det_thresh": 0.2,
        "text_det_box_thresh": 0.5,
        "text_det_unclip_ratio": 3.0,
        "text_rec_score_thresh": 0.15,
    }


@pytest.mark.asyncio
async def test_paddle_adapter_omits_unset_detection_thresholds() -> None:
    """Verify None-default DB detection thresholds are not forwarded.

    text_det_box_thresh and text_det_unclip_ratio now default to the adopted
    Lemon-Aid values (covered by dedicated tests below); text_det_thresh remains
    None-default so it keeps the upstream pipeline default and is not forwarded.
    """
    predictor = _FakePaddlePredictor([{"rec_texts": ["비타민"], "rec_scores": [0.88]}])
    adapter = PaddleOCRAdapter(
        Settings(
            _env_file=None,
            enable_local_ocr=True,
            local_ocr_preprocess_mode="none",
        ),
        predictor=predictor,
    )

    await adapter.extract_text(_image_input())

    # None settings keep the upstream defaults — no key forwarded.
    assert "text_det_thresh" not in predictor.received_kwargs


@pytest.mark.asyncio
async def test_paddle_adapter_forwards_adopted_box_thresh_default() -> None:
    """Verify the adopted box_thresh default (0.4) is forwarded when left unset.

    Team decision 2026-06-14: box_thresh=0.4 is the held-out detection-sweep
    winner and is now the code default (upstream PaddleOCR default is 0.6).
    """
    predictor = _FakePaddlePredictor([{"rec_texts": ["엽산"], "rec_scores": [0.9]}])
    adapter = PaddleOCRAdapter(
        Settings(
            _env_file=None,
            enable_local_ocr=True,
            local_ocr_preprocess_mode="none",
        ),
        predictor=predictor,
    )

    await adapter.extract_text(_image_input())

    assert predictor.received_kwargs["text_det_box_thresh"] == 0.4


@pytest.mark.asyncio
async def test_paddle_adapter_forwards_adopted_unclip_ratio_default() -> None:
    """Verify the adopted unclip_ratio default (3.0) is forwarded when left unset."""
    predictor = _FakePaddlePredictor([{"rec_texts": ["엽산"], "rec_scores": [0.9]}])
    adapter = PaddleOCRAdapter(
        Settings(
            _env_file=None,
            enable_local_ocr=True,
            local_ocr_preprocess_mode="none",
        ),
        predictor=predictor,
    )

    await adapter.extract_text(_image_input())

    assert predictor.received_kwargs["text_det_unclip_ratio"] == 3.0


@pytest.mark.asyncio
async def test_paddle_adapter_requires_local_ocr_gate() -> None:
    """Verify the adapter fails closed when ENABLE_LOCAL_OCR is explicitly disabled."""
    adapter = PaddleOCRAdapter(
        Settings(_env_file=None, enable_local_ocr=False),
        predictor=_FakePaddlePredictor([]),
    )

    with pytest.raises(OCRError, match="ENABLE_LOCAL_OCR"):
        await adapter.extract_text(_image_input())


@pytest.mark.asyncio
async def test_paddle_adapter_returns_low_confidence_prediction_for_review() -> None:
    """Verify weak OCR text is preserved for parser and user review."""
    adapter = PaddleOCRAdapter(
        Settings(
            _env_file=None,
            enable_local_ocr=True,
            local_ocr_preprocess_mode="none",
            local_ocr_confidence_threshold=0.75,
        ),
        predictor=_FakePaddlePredictor([{"rec_texts": ["흐린 텍스트"], "rec_scores": [0.50]}]),
    )

    result = await adapter.extract_text(_image_input())

    assert result.provider == PADDLE_OCR_PROVIDER
    assert result.text == "흐린 텍스트"
    assert result.confidence == pytest.approx(0.50)


class _RecordingFakePaddleOCR:
    """Fake PaddleOCR class capturing constructor kwargs for assertions."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def predict(self, image_path: str, **kwargs: object) -> object:  # noqa: ARG002
        """Return an empty prediction for kwarg-focused tests."""
        return []


@pytest.fixture
def _fake_paddleocr_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the ``paddleocr`` module with a kwargs-recording fake.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    The lru_cache around ``_get_paddle_predictor`` is cleared before and after
    so toggle states do not leak between tests.
    """
    fake_module = types.ModuleType("paddleocr")
    fake_module.PaddleOCR = _RecordingFakePaddleOCR  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)
    _get_paddle_predictor.cache_clear()
    yield
    _get_paddle_predictor.cache_clear()


def test_predictor_forwards_textline_orientation_when_disabled(
    _fake_paddleocr_module: None,
) -> None:
    """Verify the default settings keep PaddleOCR textline orientation off."""
    predictor = _get_paddle_predictor(
        language="korean",
        device=None,
        use_textline_orientation=False,
    )
    assert predictor.kwargs["use_textline_orientation"] is False  # type: ignore[attr-defined]
    assert predictor.kwargs["text_detection_model_name"] == PADDLE_MOBILE_TEXT_DETECTION_MODEL  # type: ignore[attr-defined]
    assert predictor.kwargs["text_recognition_model_name"] == "korean_PP-OCRv5_mobile_rec"  # type: ignore[attr-defined]


def test_predictor_wraps_import_time_provider_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify PaddleOCR import-time runtime failures become bounded OCR errors.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """

    def _raise_permission_error(module_name: str) -> object:
        """Raise a runtime import failure for the requested module.

        Args:
            module_name: Imported module name.

        Raises:
            PermissionError: Simulated provider cache permission failure.
        """
        raise PermissionError(f"{module_name} cache unavailable")

    monkeypatch.setattr("src.ocr.providers.paddle.import_module", _raise_permission_error)
    _get_paddle_predictor.cache_clear()
    try:
        with pytest.raises(OCRError, match="provider initialization"):
            _get_paddle_predictor(language="korean", device=None)
    finally:
        _get_paddle_predictor.cache_clear()


def test_predictor_forwards_textline_orientation_when_enabled(
    _fake_paddleocr_module: None,
) -> None:
    """Verify operators can enable textline orientation for isolation runs."""
    predictor = _get_paddle_predictor(
        language="korean",
        device=None,
        use_textline_orientation=True,
    )
    assert predictor.kwargs["use_textline_orientation"] is True  # type: ignore[attr-defined]


def test_predictor_server_detection_profile_keeps_korean_mobile_recognition(
    _fake_paddleocr_module: None,
) -> None:
    """Verify server detection can be isolated from Korean recognition changes."""
    predictor = _get_paddle_predictor(
        language="korean",
        device=None,
        model_profile="server_detection",
    )

    assert predictor.kwargs["text_detection_model_name"] == PADDLE_SERVER_TEXT_DETECTION_MODEL  # type: ignore[attr-defined]
    assert predictor.kwargs["text_recognition_model_name"] == "korean_PP-OCRv5_mobile_rec"  # type: ignore[attr-defined]


def test_predictor_forwards_custom_text_recognition_model_dir(
    _fake_paddleocr_module: None,
    tmp_path: Path,
) -> None:
    """Verify a fine-tuned recognizer inference directory is passed to PaddleOCR."""
    model_dir = tmp_path / "supplement-rec-inference"

    predictor = _get_paddle_predictor(
        language="korean",
        device=None,
        text_recognition_model_dir=model_dir,
    )

    assert predictor.kwargs["text_recognition_model_name"] == "korean_PP-OCRv5_mobile_rec"  # type: ignore[attr-defined]
    assert predictor.kwargs["text_recognition_model_dir"] == str(model_dir)  # type: ignore[attr-defined]


def test_predictor_server_profile_uses_server_detection_and_recognition(
    _fake_paddleocr_module: None,
) -> None:
    """Verify the explicit server profile changes both PaddleOCR model stages."""
    predictor = _get_paddle_predictor(
        language="korean",
        device=None,
        model_profile="server",
    )

    assert predictor.kwargs["text_detection_model_name"] == PADDLE_SERVER_TEXT_DETECTION_MODEL  # type: ignore[attr-defined]
    assert predictor.kwargs["text_recognition_model_name"] == PADDLE_SERVER_TEXT_RECOGNITION_MODEL  # type: ignore[attr-defined]


def test_predictor_cache_separates_model_profiles(
    _fake_paddleocr_module: None,
) -> None:
    """Verify profile comparisons do not reuse a prior cached predictor."""
    mobile_predictor = _get_paddle_predictor(
        language="korean",
        device=None,
        model_profile="mobile",
    )
    server_detection_predictor = _get_paddle_predictor(
        language="korean",
        device=None,
        model_profile="server_detection",
    )

    assert mobile_predictor is not server_detection_predictor


def test_predictor_caches_orientation_toggle_separately(
    _fake_paddleocr_module: None,
) -> None:
    """Verify the toggle is part of the cache key so flipped runs do not collide."""
    off = _get_paddle_predictor(
        language="korean",
        device=None,
        use_textline_orientation=False,
    )
    on = _get_paddle_predictor(
        language="korean",
        device=None,
        use_textline_orientation=True,
    )
    assert off is not on


@pytest.mark.asyncio
async def test_paddle_adapter_propagates_textline_orientation_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the adapter forwards the settings flag into the cached predictor."""
    fake_module = types.ModuleType("paddleocr")
    fake_module.PaddleOCR = _RecordingFakePaddleOCR  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)
    _get_paddle_predictor.cache_clear()
    try:
        adapter = PaddleOCRAdapter(
            Settings(
                _env_file=None,
                enable_local_ocr=True,
                local_ocr_preprocess_mode="none",
                local_ocr_use_textline_orientation=True,
            )
        )
        with pytest.raises(OCRError, match="readable text"):
            await adapter.extract_text(_image_input())

        predictor = _get_paddle_predictor(
            language="korean",
            device=None,
            use_textline_orientation=True,
        )
        assert predictor.kwargs["use_textline_orientation"] is True  # type: ignore[attr-defined]
    finally:
        _get_paddle_predictor.cache_clear()


@pytest.mark.asyncio
async def test_paddle_adapter_propagates_custom_recognition_model_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify adapter settings can select a fine-tuned recognizer directory."""
    fake_module = types.ModuleType("paddleocr")
    fake_module.PaddleOCR = _RecordingFakePaddleOCR  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)
    _get_paddle_predictor.cache_clear()
    model_dir = tmp_path / "supplement-rec-inference"
    try:
        adapter = PaddleOCRAdapter(
            Settings(
                _env_file=None,
                enable_local_ocr=True,
                local_ocr_preprocess_mode="none",
                local_ocr_text_recognition_model_dir=model_dir,
            )
        )
        with pytest.raises(OCRError, match="readable text"):
            await adapter.extract_text(_image_input())

        predictor = _get_paddle_predictor(
            language="korean",
            device=None,
            text_recognition_model_dir=model_dir,
        )
        assert predictor.kwargs["text_recognition_model_dir"] == str(model_dir)  # type: ignore[attr-defined]
    finally:
        _get_paddle_predictor.cache_clear()


@pytest.mark.asyncio
async def test_extract_text_runs_predict_off_the_event_loop() -> None:
    """The blocking predict runs in a worker thread, keeping the event loop responsive."""
    started = threading.Event()
    release = threading.Event()

    class _BlockingPredictor:
        def predict(self, _image_path: str, **_kwargs: object) -> object:
            started.set()
            # If predict ran ON the event loop, the loop could never reach
            # release.set() below, so this wait would time out and fail the test.
            if not release.wait(timeout=5):
                raise AssertionError("predict was not released — event loop was blocked")
            return [{"rec_texts": ["비타민 D"], "rec_scores": [0.9]}]

    adapter = PaddleOCRAdapter(
        Settings(_env_file=None, enable_local_ocr=True, local_ocr_preprocess_mode="none"),
        predictor=_BlockingPredictor(),
    )
    task = asyncio.create_task(adapter.extract_text(_image_input()))
    # Wait off the loop until predict has started in its worker thread.
    await asyncio.to_thread(started.wait, 5)
    # Releasing from the loop only succeeds if the loop was never blocked by predict.
    release.set()
    result = await task

    assert result.text == "비타민 D"


@pytest.mark.asyncio
async def test_concurrent_extract_text_calls_are_serialized() -> None:
    """The single-worker executor serializes predicts on the shared predictor."""
    lock = threading.Lock()
    state = {"active": 0, "max_active": 0}

    class _RecordingPredictor:
        def predict(self, _image_path: str, **_kwargs: object) -> object:
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.05)
            with lock:
                state["active"] -= 1
            return [{"rec_texts": ["X"], "rec_scores": [0.9]}]

    settings = Settings(_env_file=None, enable_local_ocr=True, local_ocr_preprocess_mode="none")
    # One predictor instance shared across adapters, mirroring the lru_cached predictor.
    predictor = _RecordingPredictor()
    adapters = [PaddleOCRAdapter(settings, predictor=predictor) for _ in range(4)]

    results = await asyncio.gather(*(adapter.extract_text(_image_input()) for adapter in adapters))

    assert all(result.text == "X" for result in results)
    # Two predicts must never run concurrently on the shared, non-thread-safe predictor.
    assert state["max_active"] == 1
