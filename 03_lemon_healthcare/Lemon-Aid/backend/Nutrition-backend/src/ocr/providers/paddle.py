"""Optional PaddleOCR local fallback provider for supplement labels."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol, cast

from src.config import Settings
from src.ocr.base import (
    OCRAdapter,
    OCRBlock,
    OCRBoundingPoly,
    OCRError,
    OCRImageInput,
    OCRPage,
    OCRParagraph,
    OCRResult,
    OCRVertex,
    OCRWord,
)
from src.ocr.preprocessing import OCRPreprocessingError, preprocess_local_ocr_image

PADDLE_OCR_PROVIDER = "paddleocr_local"
PADDLE_MOBILE_TEXT_DETECTION_MODEL = "PP-OCRv5_mobile_det"
PADDLE_SERVER_TEXT_DETECTION_MODEL = "PP-OCRv5_server_det"
PADDLE_SERVER_TEXT_RECOGNITION_MODEL = "PP-OCRv5_server_rec"
PADDLE_MOBILE_TEXT_RECOGNITION_MODELS = {
    "en": "en_PP-OCRv5_mobile_rec",
    "korean": "korean_PP-OCRv5_mobile_rec",
}
PADDLE_TEXT_KEYS = {"text", "inferText"}
PADDLE_SCORE_KEYS = {"score", "confidence", "inferConfidence"}
LEGACY_TEXT_SCORE_PAIR_LENGTH = 2
PADDLE_BOX_COORDINATE_COUNT = 4
PADDLE_POINT_COORDINATE_COUNT = 2

# Dedicated single-worker executor for the synchronous, CPU-bound PaddleOCR
# ``predict()`` call. A single worker serializes inference across requests — the
# lru_cached predictor is shared process-wide and PaddleOCR is not guaranteed
# thread-safe — and that serialization is immune to async cancellation: a
# cancelled/disconnected request leaves an orphan thread that keeps the worker
# busy, so the next ``predict()`` queues behind it instead of running concurrently
# on the shared predictor (an ``asyncio.Lock`` would release on cancel and break
# this). A module global (not a FastAPI-lifespan resource) so offline callers —
# unit tests and benchmark scripts that never start the app — work too. The worker
# thread is spawned lazily on first submit; it is non-daemon and atexit-joined, so
# no explicit shutdown is needed (in-flight inference drains on process exit).
_PADDLE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddle-ocr")


class PaddlePredictor(Protocol):
    """Protocol for the small PaddleOCR API surface used by this adapter."""

    def predict(self, image_path: str, **kwargs: object) -> Any:
        """Run OCR prediction for one local image path.

        Args:
            image_path: Local image path.
            kwargs: Optional PaddleOCR 3.x ``predict`` tuning parameters.

        Returns:
            Provider-specific prediction object.
        """
        ...


class PaddleOCRAdapter(OCRAdapter):
    """Local PaddleOCR fallback adapter.

    The adapter is optional and lazy-loads PaddleOCR only when the fallback path is
    explicitly enabled. It writes request bytes to a temporary file because the
    official PaddleOCR 3.x pipeline examples use file-path based ``predict`` calls.
    """

    def __init__(self, settings: Settings, predictor: PaddlePredictor | None = None) -> None:
        """Initialize the adapter.

        Args:
            settings: Runtime settings.
            predictor: Optional fake or prebuilt predictor for tests.
        """
        self._settings = settings
        self._predictor = predictor

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Extract text with a local PaddleOCR predictor.

        Args:
            image: Validated OCR image input.

        Returns:
            OCR result with joined text and averaged confidence when available.
            Low-confidence text is still returned so the preview pipeline can
            run parser/LLM review and expose a bounded confidence bucket.

        Raises:
            OCRError: If local OCR is disabled, unavailable, or returns no text.
        """
        if not self._settings.enable_local_ocr:
            raise OCRError("ENABLE_LOCAL_OCR=true is required for PaddleOCR fallback.")

        # Resolve the predictor on the event loop — a fast lru_cache lookup after the
        # one-time cold-start model load — then run the blocking OCR pipeline in the
        # dedicated single-worker thread so it never stalls the loop.
        predictor = self._predictor or _get_paddle_predictor(
            language=self._settings.local_ocr_language,
            device=self._settings.local_ocr_device,
            model_profile=self._settings.local_ocr_model_profile,
            text_recognition_model_dir=self._settings.local_ocr_text_recognition_model_dir,
            use_textline_orientation=self._settings.local_ocr_use_textline_orientation,
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _PADDLE_EXECUTOR, self._blocking_extract, predictor, image
        )

    def _blocking_extract(self, predictor: PaddlePredictor, image: OCRImageInput) -> OCRResult:
        """Run the synchronous PaddleOCR pipeline (executed in the worker thread).

        Owns the temporary-directory lifecycle inside the worker thread so a
        cancelled await (e.g. client disconnect) cannot delete the image file
        while ``predict()`` is still reading it.

        Args:
            predictor: Resolved PaddleOCR predictor.
            image: Validated OCR image input.

        Returns:
            OCR result with joined text and averaged confidence when available.

        Raises:
            OCRError: If preprocessing fails or no readable text is returned.
        """
        try:
            image_bytes, mime_type = preprocess_local_ocr_image(
                image.image_bytes,
                mime_type=image.mime_type,
                mode=self._settings.local_ocr_preprocess_mode,
            )
        except OCRPreprocessingError as exc:
            raise OCRError("PaddleOCR preprocessing failed.") from exc

        suffix = _suffix_for_mime_type(mime_type)
        with TemporaryDirectory(prefix="lemon-paddleocr-") as temporary_directory:
            image_path = Path(temporary_directory) / f"supplement_label{suffix}"
            image_path.write_bytes(image_bytes)
            prediction = predictor.predict(str(image_path), **_predict_kwargs(self._settings))

        fragments, scores = _collect_text_and_scores(prediction)
        pages = _collect_layout_pages(prediction, image)
        text = _build_reading_order_text(fragments=fragments, pages=pages)
        if not text:
            raise OCRError("PaddleOCR returned no readable text.")

        return OCRResult(
            text=text,
            provider=PADDLE_OCR_PROVIDER,
            confidence=_average_scores(scores),
            pages=pages,
        )


@lru_cache(maxsize=8)
def _get_paddle_predictor(
    *,
    language: str,
    device: str | None,
    model_profile: str = "mobile",
    text_recognition_model_dir: Path | None = None,
    use_textline_orientation: bool = False,
) -> PaddlePredictor:
    """Load and cache the PaddleOCR predictor.

    Args:
        language: OCR language setting.
        device: Optional runtime device such as ``cpu`` or ``gpu:0``.
        model_profile: OCR model profile. ``server_detection`` upgrades only
            detection while keeping the language-specific mobile recognizer.
        text_recognition_model_dir: Optional fine-tuned PaddleOCR inference
            recognizer directory. Cached separately so baseline and tuned models
            do not share a predictor.
        use_textline_orientation: Whether to enable PaddleOCR's textline
            orientation classifier. Cached separately per toggle so isolation
            measurements can flip the flag without polluting the prior cache.

    Returns:
        PaddleOCR predictor.

    Raises:
        OCRError: If PaddleOCR is not installed or cannot be initialized.
    """
    try:
        paddle_ocr_class = cast(Any, import_module("paddleocr")).PaddleOCR
    except ImportError as exc:
        raise OCRError("PaddleOCR is not installed. Install backend .[ocr-local].") from exc
    except Exception as exc:
        raise OCRError("PaddleOCR provider initialization failed.") from exc

    kwargs: dict[str, object] = {
        "lang": language,
        "text_detection_model_name": _text_detection_model_name(model_profile),
        "text_recognition_model_name": _text_recognition_model_name(
            language=language,
            model_profile=model_profile,
        ),
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": use_textline_orientation,
    }
    if device:
        kwargs["device"] = device
    if text_recognition_model_dir is not None:
        kwargs["text_recognition_model_dir"] = str(text_recognition_model_dir)
    try:
        return cast(PaddlePredictor, paddle_ocr_class(**kwargs))
    except Exception as exc:
        raise OCRError("PaddleOCR predictor initialization failed.") from exc


def _text_detection_model_name(model_profile: str) -> str:
    """Return the PaddleOCR detection model name for a model profile.

    Args:
        model_profile: Operator-selected local OCR model profile.

    Returns:
        PaddleOCR text detection model name.
    """
    if model_profile in {"server_detection", "server"}:
        return PADDLE_SERVER_TEXT_DETECTION_MODEL
    return PADDLE_MOBILE_TEXT_DETECTION_MODEL


def _text_recognition_model_name(*, language: str, model_profile: str) -> str:
    """Return the PaddleOCR recognition model name for a model profile.

    Args:
        language: PaddleOCR language code.
        model_profile: Operator-selected local OCR model profile.

    Returns:
        PaddleOCR text recognition model name.
    """
    if model_profile == "server":
        return PADDLE_SERVER_TEXT_RECOGNITION_MODEL
    return _mobile_text_recognition_model_name(language)


def _mobile_text_recognition_model_name(language: str) -> str:
    """Return a lightweight PP-OCRv5 recognition model for the OCR language.

    Args:
        language: PaddleOCR language code.

    Returns:
        Mobile recognition model name.
    """
    return PADDLE_MOBILE_TEXT_RECOGNITION_MODELS.get(language, "PP-OCRv5_mobile_rec")


def _suffix_for_mime_type(mime_type: str) -> str:
    """Return a safe image suffix for a MIME type.

    Args:
        mime_type: Validated image MIME type.

    Returns:
        File suffix used for the temporary image.
    """
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    return ".png"


def _predict_kwargs(settings: Settings) -> dict[str, object]:
    """Build optional PaddleOCR 3.x prediction-time tuning parameters.

    Args:
        settings: Runtime settings.

    Returns:
        Keyword arguments for ``PaddleOCR.predict``. Empty means the upstream
        pipeline defaults are preserved.
    """
    kwargs: dict[str, object] = {}
    if settings.local_ocr_text_det_limit_side_len is not None:
        kwargs["text_det_limit_side_len"] = settings.local_ocr_text_det_limit_side_len
    if settings.local_ocr_text_det_limit_type is not None:
        kwargs["text_det_limit_type"] = settings.local_ocr_text_det_limit_type
    # DB detection thresholds — official PP-OCR pipeline predict() params
    # (text_det_thresh 0.3 / text_det_box_thresh 0.6 / text_det_unclip_ratio 2.0):
    # https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-ChatOCRv4.en.md
    if settings.local_ocr_text_det_thresh is not None:
        kwargs["text_det_thresh"] = settings.local_ocr_text_det_thresh
    if settings.local_ocr_text_det_box_thresh is not None:
        kwargs["text_det_box_thresh"] = settings.local_ocr_text_det_box_thresh
    if settings.local_ocr_text_det_unclip_ratio is not None:
        kwargs["text_det_unclip_ratio"] = settings.local_ocr_text_det_unclip_ratio
    if settings.local_ocr_text_rec_score_thresh is not None:
        kwargs["text_rec_score_thresh"] = settings.local_ocr_text_rec_score_thresh
    return kwargs


def _collect_text_and_scores(value: object) -> tuple[list[str], list[float]]:
    """Collect OCR text fragments and confidence scores from provider output.

    Args:
        value: PaddleOCR output in dict/list/object form.

    Returns:
        Text fragments and bounded scores.
    """
    fragments: list[str] = []
    scores: list[float] = []
    _walk_prediction(value, fragments=fragments, scores=scores)
    return _dedupe_preserve_order(fragments), scores


def _walk_prediction(value: object, *, fragments: list[str], scores: list[float]) -> None:
    """Recursively walk common PaddleOCR result shapes.

    Args:
        value: Provider output fragment.
        fragments: Accumulator for text fragments.
        scores: Accumulator for confidence scores.
    """
    if isinstance(value, dict):
        _collect_from_mapping(value, fragments=fragments, scores=scores)
        for nested_value in value.values():
            _walk_prediction(nested_value, fragments=fragments, scores=scores)
        return

    if isinstance(value, list | tuple):
        _collect_legacy_tuple(value, fragments=fragments, scores=scores)
        for item in value:
            _walk_prediction(item, fragments=fragments, scores=scores)
        return

    json_value = getattr(value, "json", None)
    if isinstance(json_value, dict):
        _walk_prediction(json_value, fragments=fragments, scores=scores)
        return
    if callable(json_value):
        try:
            parsed = json_value()
        except Exception:
            parsed = None
        if parsed is not None:
            _walk_prediction(parsed, fragments=fragments, scores=scores)
            return

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            parsed = to_dict()
        except Exception:
            parsed = None
        if parsed is not None:
            _walk_prediction(parsed, fragments=fragments, scores=scores)


def _collect_from_mapping(
    value: dict[object, object],
    *,
    fragments: list[str],
    scores: list[float],
) -> None:
    """Collect text and confidence fields from a mapping.

    Args:
        value: Result mapping.
        fragments: Accumulator for text fragments.
        scores: Accumulator for confidence scores.
    """
    _collect_aligned_texts_and_scores(value, fragments=fragments, scores=scores)
    for key, nested_value in value.items():
        if key in {"rec_texts", "texts", "rec_scores", "scores"}:
            continue
        if key in PADDLE_TEXT_KEYS and isinstance(nested_value, str):
            fragments.append(nested_value)
        elif key in PADDLE_SCORE_KEYS:
            scores.extend(_score_values([nested_value]))


def _collect_aligned_texts_and_scores(
    value: dict[object, object],
    *,
    fragments: list[str],
    scores: list[float],
) -> None:
    """Collect PaddleOCR text/score arrays with matching indices.

    Args:
        value: Result mapping.
        fragments: Accumulator for text fragments.
        scores: Accumulator for confidence scores.
    """
    for text_key, score_key in (("rec_texts", "rec_scores"), ("texts", "scores")):
        raw_texts = value.get(text_key)
        if not isinstance(raw_texts, list):
            continue
        raw_scores = value.get(score_key)
        for index, text in enumerate(raw_texts):
            if not isinstance(text, str) or not text.strip():
                continue
            fragments.append(text)
            if isinstance(raw_scores, list) and index < len(raw_scores):
                scores.extend(_score_values([raw_scores[index]]))


def _collect_legacy_tuple(
    value: Sequence[object],
    *,
    fragments: list[str],
    scores: list[float],
) -> None:
    """Collect legacy PaddleOCR tuple values such as ``(text, score)``.

    Args:
        value: Sequence value.
        fragments: Accumulator for text fragments.
        scores: Accumulator for confidence scores.
    """
    if len(value) != LEGACY_TEXT_SCORE_PAIR_LENGTH:
        return
    text_candidate, score_candidate = value
    if isinstance(text_candidate, str):
        fragments.append(text_candidate)
        scores.extend(_score_values([score_candidate]))


def _score_values(values: list[object]) -> list[float]:
    """Return bounded score floats from raw values.

    Args:
        values: Candidate values.

    Returns:
        Values in the inclusive range 0.0 to 1.0.
    """
    scores: list[float] = []
    for value in values:
        if isinstance(value, int | float) and 0 <= value <= 1:
            scores.append(float(value))
    return scores


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Trim and deduplicate text fragments.

    Args:
        values: Raw text fragments.

    Returns:
        Non-empty fragments in first-seen order.
    """
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        deduped.append(stripped)
        seen.add(stripped)
    return deduped


def _average_scores(scores: list[float]) -> float | None:
    """Average scores when present.

    Args:
        scores: Bounded confidence scores.

    Returns:
        Average score or None.
    """
    if not scores:
        return None
    return sum(scores) / len(scores)


def _build_reading_order_text(*, fragments: list[str], pages: tuple[OCRPage, ...]) -> str:
    """Build parser-friendly OCR text from layout when Paddle returns coordinates.

    Dense supplement facts labels often contain table-like rows. PaddleOCR 3.x
    can return line coordinates, so same-row blocks are joined with tabs before
    the local LLM parser sees the text. If layout is unavailable, the provider
    text order is preserved.

    Args:
        fragments: Provider text fragments in PaddleOCR output order.
        pages: Normalized OCR layout pages.

    Returns:
        Text for downstream parsing.
    """
    layout_text = _layout_text_for_parser(pages)
    if layout_text:
        return layout_text
    return "\n".join(fragments).strip()


def _layout_text_for_parser(pages: tuple[OCRPage, ...]) -> str:
    """Return row-grouped OCR text from normalized pages.

    Args:
        pages: OCR layout pages.

    Returns:
        Newline-delimited reading order text, or an empty string when layout is
        unavailable.
    """
    rows: list[str] = []
    for page in pages:
        rows.extend(_layout_rows_for_page(page))
    return "\n".join(row for row in rows if row).strip()


def _layout_rows_for_page(page: OCRPage) -> list[str]:
    """Group one OCR page into top-to-bottom, left-to-right text rows.

    Args:
        page: OCR page.

    Returns:
        Row text. Multiple blocks on the same row are tab-separated.
    """
    positioned: list[tuple[float, float, float, str]] = []
    unpositioned: list[str] = []
    for block in page.blocks:
        text = block.text.strip()
        if not text:
            continue
        position = _block_position(block)
        if position is None:
            unpositioned.append(text)
            continue
        x_min, y_center, height = position
        positioned.append((y_center, x_min, height, text))

    if not positioned:
        return unpositioned

    rows = _group_positioned_blocks(positioned)
    if unpositioned:
        rows.extend(unpositioned)
    return rows


def _block_position(block: OCRBlock) -> tuple[float, float, float] | None:
    """Return sortable block geometry.

    Args:
        block: OCR block.

    Returns:
        ``(x_min, y_center, height)`` or ``None`` when the block has no usable
        coordinates.
    """
    if block.bounding_box is None or not block.bounding_box.vertices:
        return None
    x_values = [vertex.x for vertex in block.bounding_box.vertices]
    y_values = [vertex.y for vertex in block.bounding_box.vertices]
    y_min = min(y_values)
    y_max = max(y_values)
    return min(x_values), (y_min + y_max) / 2, max(y_max - y_min, 1.0)


def _group_positioned_blocks(blocks: list[tuple[float, float, float, str]]) -> list[str]:
    """Group positioned OCR blocks into visual rows.

    Args:
        blocks: Tuples of ``(y_center, x_min, height, text)``.

    Returns:
        Row text in visual reading order.
    """
    rows: list[list[tuple[float, float, float, str]]] = []
    for block in sorted(blocks, key=lambda item: (item[0], item[1])):
        target_row = _matching_row(rows, block)
        if target_row is None:
            rows.append([block])
        else:
            target_row.append(block)
    return ["\t".join(item[3] for item in sorted(row, key=lambda item: item[1])) for row in rows]


def _matching_row(
    rows: list[list[tuple[float, float, float, str]]],
    block: tuple[float, float, float, str],
) -> list[tuple[float, float, float, str]] | None:
    """Return the first row close enough to accept a block.

    Args:
        rows: Existing visual rows.
        block: Candidate positioned block.

    Returns:
        Matching row or ``None``.
    """
    y_center, _x_min, height, _text = block
    for row in rows:
        row_center = sum(item[0] for item in row) / len(row)
        row_height = sum(item[2] for item in row) / len(row)
        tolerance = max(2.0, max(row_height, height) * 0.65)
        if abs(y_center - row_center) <= tolerance:
            return row
    return None


def _collect_layout_pages(value: object, image: OCRImageInput) -> tuple[OCRPage, ...]:
    """Collect PaddleOCR layout lines into provider-neutral OCR pages.

    Args:
        value: PaddleOCR output in dict/list/object form.
        image: Validated OCR image input used for page dimensions.

    Returns:
        Normalized OCR pages. Empty when Paddle returned flat text only.
    """
    pages: list[OCRPage] = []
    _walk_layout_pages(value, image=image, pages=pages)
    return tuple(pages)


def _walk_layout_pages(
    value: object,
    *,
    image: OCRImageInput,
    pages: list[OCRPage],
) -> None:
    """Recursively walk common PaddleOCR result shapes for layout fields."""
    if isinstance(value, dict):
        page = _page_from_mapping(value, image)
        if page is not None:
            pages.append(page)
            return
        for nested_value in value.values():
            _walk_layout_pages(nested_value, image=image, pages=pages)
        return

    if isinstance(value, list | tuple):
        for item in value:
            _walk_layout_pages(item, image=image, pages=pages)
        return

    parsed = _object_as_mapping(value)
    if parsed is not None:
        _walk_layout_pages(parsed, image=image, pages=pages)


def _object_as_mapping(value: object) -> dict[object, object] | None:
    """Return dict-like provider object data without exposing provider payload."""
    json_value = getattr(value, "json", None)
    if isinstance(json_value, dict):
        return json_value
    if callable(json_value):
        try:
            parsed = json_value()
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            parsed = to_dict()
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    return None


def _page_from_mapping(value: dict[object, object], image: OCRImageInput) -> OCRPage | None:
    """Build one OCR page from PaddleOCR line-level fields when present."""
    raw_texts = value.get("rec_texts")
    if not isinstance(raw_texts, list):
        return None
    text_items = [
        (raw_index, item.strip())
        for raw_index, item in enumerate(raw_texts)
        if isinstance(item, str) and item.strip()
    ]
    if not text_items:
        return None
    scores = _score_values(
        value.get("rec_scores") if isinstance(value.get("rec_scores"), list) else []
    )
    raw_polys = value.get("rec_polys") if "rec_polys" in value else value.get("dt_polys")
    raw_boxes = value.get("rec_boxes")
    blocks = tuple(
        _line_block(
            text=text,
            confidence=scores[raw_index] if raw_index < len(scores) else None,
            bounding_box=_line_bounding_poly(raw_polys, raw_boxes, raw_index),
            index=block_index,
        )
        for block_index, (raw_index, text) in enumerate(text_items)
    )
    return OCRPage(
        width=image.width,
        height=image.height,
        confidence=_average_scores(scores),
        blocks=blocks,
    )


def _line_block(
    *,
    text: str,
    confidence: float | None,
    bounding_box: OCRBoundingPoly | None,
    index: int,
) -> OCRBlock:
    """Build a line-level block from one PaddleOCR recognized text line."""
    word = OCRWord(
        text=text,
        confidence=confidence,
        bounding_box=bounding_box,
        block_index=index,
        paragraph_index=0,
        word_index=0,
    )
    paragraph = OCRParagraph(
        text=text,
        confidence=confidence,
        bounding_box=bounding_box,
        words=(word,),
    )
    return OCRBlock(
        text=text,
        confidence=confidence,
        bounding_box=bounding_box,
        block_type="TEXT",
        paragraphs=(paragraph,),
    )


def _line_bounding_poly(
    raw_polys: object,
    raw_boxes: object,
    index: int,
) -> OCRBoundingPoly | None:
    """Return a line bounding polygon from PaddleOCR polygon or box fields."""
    poly_value = _indexed_value(raw_polys, index)
    poly = _poly_from_points(poly_value)
    if poly is not None:
        return poly
    box_value = _indexed_value(raw_boxes, index)
    return _poly_from_box(box_value)


def _indexed_value(value: object, index: int) -> object | None:
    """Return one indexed provider value from list-like or ndarray-like objects."""
    if isinstance(value, list | tuple):
        return value[index] if index < len(value) else None
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            return value[index]  # type: ignore[index]
        except Exception:
            return None
    return None


def _poly_from_points(value: object) -> OCRBoundingPoly | None:
    """Convert four-point PaddleOCR polygons into OCRBoundingPoly."""
    points = _nested_numeric_pairs(value)
    if not points:
        return None
    return OCRBoundingPoly(vertices=tuple(OCRVertex(x=float(x), y=float(y)) for x, y in points))


def _poly_from_box(value: object) -> OCRBoundingPoly | None:
    """Convert PaddleOCR rec_boxes [x_min, y_min, x_max, y_max] into a polygon."""
    values = _numeric_sequence(value)
    if len(values) != PADDLE_BOX_COORDINATE_COUNT:
        return None
    x_min, y_min, x_max, y_max = values
    return OCRBoundingPoly(
        vertices=(
            OCRVertex(x=x_min, y=y_min),
            OCRVertex(x=x_max, y=y_min),
            OCRVertex(x=x_max, y=y_max),
            OCRVertex(x=x_min, y=y_max),
        )
    )


def _nested_numeric_pairs(value: object) -> list[tuple[float, float]]:
    """Return coordinate pairs from nested list or ndarray-like values."""
    if not isinstance(value, list | tuple):
        tolist = getattr(value, "tolist", None)
        if callable(tolist):
            try:
                value = tolist()
            except Exception:
                return []
    if not isinstance(value, list | tuple):
        return []
    points: list[tuple[float, float]] = []
    for raw_point in value:
        coordinates = _numeric_sequence(raw_point)
        if len(coordinates) >= PADDLE_POINT_COORDINATE_COUNT:
            points.append((coordinates[0], coordinates[1]))
    return points


def _numeric_sequence(value: object) -> list[float]:
    """Return numeric items from a list-like value."""
    if not isinstance(value, list | tuple):
        tolist = getattr(value, "tolist", None)
        if callable(tolist):
            try:
                value = tolist()
            except Exception:
                return []
    if not isinstance(value, list | tuple):
        return []
    return [float(item) for item in value if isinstance(item, int | float)]
