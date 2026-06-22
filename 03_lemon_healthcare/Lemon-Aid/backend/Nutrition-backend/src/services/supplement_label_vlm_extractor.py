"""gemma4:e4b layout-structured supplement-label extraction head (Lever 4).

The 0.85/0.90 redesign uses a document-VLM as a *structuring* head, not an
OCR-free recognizer: a live evaluation showed gemma4:e4b reads ingredient names
but drops/invents amounts on real photos, so this head is fed the OCR text
(source of truth for the glyphs) plus an optional ROI crop (layout context) and
asked to reconstruct ``name | amount | unit | %DV`` rows. Every amount it
proposes is then routed through :mod:`supplement_span_grounding`, so a
hallucinated number can never survive — schema constrains shape, span-grounding
constrains truth ("never guess an amount").

The Ollama chat call is INJECTED (``chat``) so this module is decoupled from the
live client and from the analysis pipeline, and is unit-testable without a model.
A produced :class:`VlmExtractionResult` is meant to be folded into the existing
``evidence_union`` merge as one additive candidate — never the sole source.
This module logs no raw OCR text and stores nothing.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from src.services.supplement_span_grounding import (
    IngredientAmount,
    apply_span_grounding,
)

# Async callable that performs one Ollama /api/chat request and returns the raw
# response mapping (e.g. ``OllamaChatClient.post_chat``). Injected for testability.
ChatCallable = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]

DEFAULT_VISION_MODEL = "gemma4:e4b"

_PROMPT = (
    "다음은 영양제 라벨의 OCR 텍스트(와 선택적 라벨 이미지)다. 라벨에 실제로 보이는 "
    "성분만 추출해 JSON으로만 반환하라. 형식: "
    '{"ingredients":[{"display_name":string, "amount":number|null, '
    '"unit":string|null, "daily_value_percent":number|null}]}. '
    "OCR 텍스트에 보이지 않는 함량/단위는 절대 지어내지 말고 null. 마크다운 없이 JSON만.\n\n"
    "OCR 텍스트:\n"
)


@dataclass(frozen=True)
class VlmExtractionResult:
    """Span-grounded output of the VLM structuring head.

    Attributes:
        candidates: Span-grounded ingredient rows (ungrounded amounts nulled).
        raw_row_count: How many rows the model proposed before grounding.
        grounded_amount_count: Rows whose proposed amount survived grounding.
        dropped_amount_count: Rows whose amount was dropped as ungrounded.
        model: Model name used.
    """

    candidates: list[IngredientAmount]
    raw_row_count: int
    grounded_amount_count: int
    dropped_amount_count: int
    model: str


def build_chat_payload(
    *,
    ocr_text: str,
    image_b64: str | None,
    model: str = DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    """Build the Ollama /api/chat payload for the structuring head.

    Args:
        ocr_text: OCR text the model must ground its amounts in.
        image_b64: Optional base64 ROI crop for layout context.
        model: Vision model name.

    Returns:
        A JSON-mode, temperature-0 chat payload; the user message carries the
        prompt + OCR text and, when provided, the ROI crop image.
    """
    message: dict[str, Any] = {"role": "user", "content": _PROMPT + ocr_text}
    if image_b64:
        message["images"] = [image_b64]
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [message],
    }


def _message_content(data: Mapping[str, Any]) -> str:
    """Extract the assistant message content from an Ollama chat response."""
    message = data.get("message")
    if isinstance(message, Mapping):
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def _coerce_amount(value: Any) -> float | None:
    """Coerce a model-proposed amount to float, or None when absent/non-numeric."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def parse_rows(content: str) -> list[IngredientAmount]:
    """Parse the model's JSON content into ingredient rows.

    Args:
        content: Raw assistant message content (expected JSON).

    Returns:
        Parsed rows, or an empty list when the content is not the expected shape
        (malformed JSON is swallowed — the head is one non-critical candidate).
    """
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(obj, Mapping):
        rows = obj.get("ingredients")
    elif isinstance(obj, list):
        rows = obj
    else:
        rows = None
    if not isinstance(rows, list):
        return []
    out: list[IngredientAmount] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = row.get("display_name")
        if not isinstance(name, str) or not name.strip():
            continue
        unit = row.get("unit")
        out.append(
            IngredientAmount(
                display_name=name.strip(),
                amount=_coerce_amount(row.get("amount")),
                unit=unit.strip() if isinstance(unit, str) and unit.strip() else None,
            )
        )
    return out


async def extract_label_ingredients(
    *,
    ocr_text: str,
    chat: ChatCallable,
    image_b64: str | None = None,
    model: str = DEFAULT_VISION_MODEL,
) -> VlmExtractionResult:
    """Run the gemma structuring head and span-ground every proposed amount.

    Args:
        ocr_text: OCR text the model must ground its amounts in.
        chat: Injected async Ollama chat callable.
        image_b64: Optional base64 ROI crop for layout context.
        model: Vision model name.

    Returns:
        A :class:`VlmExtractionResult` whose candidate amounts are all grounded in
        ``ocr_text`` (ungrounded amounts nulled, ingredient names retained).
    """
    payload = build_chat_payload(ocr_text=ocr_text, image_b64=image_b64, model=model)
    data = await chat(payload)
    rows = parse_rows(_message_content(data))
    decisions = apply_span_grounding(rows, ocr_text)
    candidates = [decision.item for decision in decisions]
    dropped = sum(1 for decision in decisions if not decision.grounded)
    return VlmExtractionResult(
        candidates=candidates,
        raw_row_count=len(rows),
        grounded_amount_count=len(rows) - dropped,
        dropped_amount_count=dropped,
        model=model,
    )
