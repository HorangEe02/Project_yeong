"""Localize user-facing supplement-label text sections to Korean (KR-market display).

OCR'd foreign-language (e.g. English) labels surface English precaution / intake /
functional-claim text in the analysis result. For the Korean-market launch this
localizes those display sections to Korean with a focused local-LLM (Ollama)
translation pass — kept separate from structured parsing, since the section text is
verbatim OCR (not model-generated) and is recovered by deterministic fallbacks.

Design constraints:
- Best-effort: any failure (config, transport, schema, timeout) leaves the original
  text intact — localization never breaks analysis.
- Korean-dominant text is never sent to the model (no needless call / no cost).
- One model call translates all sections together (order-preserved), so latency is a
  single round-trip regardless of how many sections were extracted.
- The chat call is injected (``chat``) so this module is unit-testable without a model
  and decoupled from the live client.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)

# Async callable performing one Ollama /api/chat request (e.g. OllamaChatClient.post_chat).
ChatCallable = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]

_HANGUL_START = "가"
_HANGUL_END = "힣"

# Sections whose visible ``text`` is shown verbatim to the user and so must read Korean.
_LIST_SECTION_KEYS = ("precautions", "functional_claims")

# Minimum ASCII letters before a section is considered worth translating (skips units
# like "mg"/"IU" and mostly-Korean text with a stray Latin token).
_MIN_LATIN_LETTERS = 3

# Minimum single-word precaution fragments (English or Korean) before they are
# coalesced into one item.
_MIN_PRECAUTION_FRAGMENTS = 2

# A Korean (non-Latin) single word-box only counts as a fragment candidate when it is
# this short; the run / sentence-final logic below decides what actually merges. Korean
# OCR word-boxes ("어린이,", "주의하십시오") are short.
_MAX_KOREAN_FRAGMENT_CHARS = 16

# A fragment ending with one of these closes a broken-sentence run, so a following
# complete caution starts its own run instead of being swept into the merge.
_SENTENCE_FINAL_PUNCT = (".", "。", "!", "?")
_KOREAN_SENTENCE_FINAL_SUFFIXES = ("다", "요", "오")

_PROMPT = (
    "다음은 영양제 라벨에서 추출한 사용자 표시용 문구들이다. 각 문구를 자연스럽고 정확한 "
    "한국어로 번역하라. 의미를 보존하고, 의료적 단정·과장 없이 라벨 문구 톤을 유지한다. "
    "이미 한국어인 문구는 그대로 둔다. 입력과 같은 개수·같은 순서로 번역만 담아 JSON으로 "
    ' 반환한다. 형식: {"translations": ["...", ...]}. 마크다운 없이 JSON만.\n\n입력:\n'
)


def is_english_dominant(text: str) -> bool:
    """Return whether the text is Latin-dominant enough to be worth translating.

    Args:
        text: Candidate display text.

    Returns:
        True when ASCII letters clearly outnumber Hangul syllables (a foreign-language
        section); False for Korean-dominant or non-textual values.
    """
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    hangul = sum(1 for char in text if _HANGUL_START <= char <= _HANGUL_END)
    return latin >= _MIN_LATIN_LETTERS and latin > hangul


def build_translation_payload(texts: list[str], model: str) -> dict[str, Any]:
    """Build the Ollama /api/chat payload that translates the texts to Korean."""
    numbered = "\n".join(f"{index + 1}. {text}" for index, text in enumerate(texts))
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [{"role": "user", "content": _PROMPT + numbered}],
    }


def _message_content(data: Mapping[str, Any]) -> str:
    """Extract the assistant message content from an Ollama chat response."""
    message = data.get("message")
    if isinstance(message, Mapping):
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def parse_translations(content: str, expected: int) -> list[str] | None:
    """Parse the model's JSON content into exactly ``expected`` non-empty translations.

    Args:
        content: Raw assistant message content (expected JSON).
        expected: Number of input texts that must be translated.

    Returns:
        The translations in order, or None when the output is malformed, the count
        does not match, or any entry is blank (best-effort: caller keeps originals).
    """
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    rows = obj.get("translations") if isinstance(obj, Mapping) else obj
    if not isinstance(rows, list) or len(rows) != expected:
        return None
    out: list[str] = []
    for row in rows:
        if not isinstance(row, str) or not row.strip():
            return None
        out.append(row.strip())
    return out


def _collect_targets(snapshot: dict[str, Any]) -> list[tuple[str, int | None]]:
    """Return (section_key, list_index|None) locations of English-dominant section text."""
    targets: list[tuple[str, int | None]] = []
    intake = snapshot.get("intake_method")
    if (
        isinstance(intake, dict)
        and isinstance(intake.get("text"), str)
        and is_english_dominant(intake["text"])
    ):
        targets.append(("intake_method", None))
    for key in _LIST_SECTION_KEYS:
        value = snapshot.get(key)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if (
                isinstance(item, dict)
                and isinstance(item.get("text"), str)
                and is_english_dominant(item["text"])
            ):
                targets.append((key, index))
    return targets


def _text_at(snapshot: dict[str, Any], key: str, index: int | None) -> str:
    """Read the section text for a collected target location."""
    if index is None:
        return snapshot[key]["text"]
    return snapshot[key][index]["text"]


def _set_text_at(snapshot: dict[str, Any], key: str, index: int | None, text: str) -> None:
    """Write the translated text back into the snapshot at a target location."""
    if index is None:
        snapshot[key]["text"] = text
    else:
        snapshot[key][index]["text"] = text


def _is_precaution_fragment(text: str) -> bool:
    """Return whether a precaution item looks like one OCR word-box fragment.

    A fragment is a single whitespace-delimited token: an English word-box
    ("Consult", "children.") or a short Korean word-box ("어린이,", "주의하십시오")
    that OCR split out of one caution sentence. Multi-word items are treated as
    complete cautions and are never merged.
    """
    stripped = text.strip()
    if not stripped or len(stripped.split()) != 1:
        return False
    if is_english_dominant(stripped):
        return True
    has_hangul = any(_HANGUL_START <= char <= _HANGUL_END for char in stripped)
    return has_hangul and len(stripped) <= _MAX_KOREAN_FRAGMENT_CHARS


def _is_sentence_final(text: str) -> bool:
    """Return whether a fragment ends a sentence (and so closes a run).

    A complete short caution ("냉장보관하십시오.") ends a sentence; a true interior
    fragment ("어린이," / "임산부,") does not. Closing the run here keeps a standalone
    complete caution from being swept into a neighboring broken sentence.
    """
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped.endswith(_SENTENCE_FINAL_PUNCT) or stripped.endswith(
        _KOREAN_SENTENCE_FINAL_SUFFIXES
    )


def _merge_fragment_run(run: list[dict[str, Any]]) -> dict[str, Any]:
    """Join one run of same-sentence fragments, escalating to the strongest severity."""
    joined = " ".join(item["text"].strip() for item in run)
    merged = {**run[0], "text": joined}
    rank = {"warning": 2, "caution": 1}
    strongest = max(
        (item.get("severity") for item in run),
        key=lambda severity: rank.get(severity, 0),
        default=None,
    )
    if strongest is not None and rank.get(strongest, 0) > rank.get(run[0].get("severity"), 0):
        merged["severity"] = strongest
    return merged


def _coalesce_precaution_fragments(snapshot: dict[str, Any]) -> bool:
    """Merge word-box precaution fragments (English or Korean) into one item.

    Word-level OCR boxes can split a single precaution sentence into several
    single-token items — English ("Consult" / "pregnant," / ... / "children.") or
    Korean ("어린이," / "임산부," / "...주의하십시오") — which then render as disjointed
    fragments (or translate word-by-word). Joining them into the first fragment's slot
    (preserving order and any complete, multi-word precautions) yields one coherent
    sentence. Mutates ``snapshot``.

    Returns:
        True when two or more fragments were merged.
    """
    precautions = snapshot.get("precautions")
    if not isinstance(precautions, list) or len(precautions) < _MIN_PRECAUTION_FRAGMENTS:
        return False

    new_list: list[Any] = []
    run: list[dict[str, Any]] = []
    changed = False

    def _flush() -> None:
        nonlocal changed
        if len(run) >= _MIN_PRECAUTION_FRAGMENTS:
            new_list.append(_merge_fragment_run(run))
            changed = True
        else:
            new_list.extend(run)
        run.clear()

    for item in precautions:
        is_fragment = (
            isinstance(item, dict)
            and isinstance(item.get("text"), str)
            and _is_precaution_fragment(item["text"])
        )
        if not is_fragment:
            _flush()
            new_list.append(item)
            continue
        run.append(item)
        # A sentence-final piece ends the broken sentence; close the run so a following
        # complete caution starts its own run and is never swept into this one.
        if _is_sentence_final(item["text"]):
            _flush()
    _flush()

    if changed:
        snapshot["precautions"] = new_list
    return changed


async def _translate_texts(texts: list[str], *, chat: ChatCallable, model: str) -> list[str] | None:
    """Translate texts in one batched call; None when the response is unusable."""
    if not texts:
        return []
    try:
        data = await chat(build_translation_payload(texts, model))
    except Exception:
        logger.warning("Supplement localization chat call failed.", exc_info=True)
        return None
    translations = parse_translations(_message_content(data), len(texts))
    if translations is None:
        logger.warning(
            "Supplement localization returned an unusable response for %d text(s).", len(texts)
        )
    return translations


async def localize_snapshot_to_korean(
    snapshot: dict[str, Any],
    *,
    chat: ChatCallable,
    model: str,
) -> dict[str, Any]:
    """Return a snapshot whose English display sections are translated to Korean.

    Translates ``precautions[].text``, ``intake_method.text`` and
    ``functional_claims[].text`` when they are English-dominant. Fragmented precaution
    items (English or Korean, from word-level OCR boxes) are first coalesced into one
    item so the result reads as a single sentence. Best-effort: when nothing needs
    translating the input snapshot is returned unchanged. If the batched call returns
    an unusable response, each section is retried on its own so one bad item does not
    leave everything in English; any item that still fails keeps its original text.

    Args:
        snapshot: Parsed snapshot dict (not mutated; a copy is returned on change).
        chat: Injected async Ollama chat callable.
        model: Translation model name.

    Returns:
        The snapshot with localized section text, or the original on no-op/failure.
    """
    work = deepcopy(snapshot)
    coalesced = _coalesce_precaution_fragments(work)
    targets = _collect_targets(work)
    if not targets:
        return work if coalesced else snapshot
    texts = [_text_at(work, key, index) for key, index in targets]
    translations = await _translate_texts(texts, chat=chat, model=model)
    if translations is None:
        logger.info(
            "Supplement localization falling back to per-item translation (%d text(s)).", len(texts)
        )
        translations = []
        for text in texts:
            single = await _translate_texts([text], chat=chat, model=model)
            translations.append(single[0] if single else text)
    for (key, index), translated in zip(targets, translations, strict=True):
        _set_text_at(work, key, index, translated)
    return work
