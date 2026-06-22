"""Auto-seed V3 ground-truth snapshots with LLM-extracted ingredients.

For each fixture in a chronic manifest, run PaddleOCR → qwen3.5:9b LLM, extract
the ingredient list (display_name, amount, unit, confidence) directly from the
raw JSON response, and inject it into the V3 snapshot at
``tests/fixtures/supplement_labels/expected/<fixture_id>.snapshot_v3.json``.

The ``source`` of each injected ingredient stays ``"ocr_llm_preview"`` so the
fixture is **not** counted as human-labeled by ``validate_ground_truth.py`` —
the human reviewer still needs to confirm each row and switch source to
``"manual"``.

Why bypass the existing parser:
    The full ``SupplementStructuredParseResultV2`` schema validation rejects
    extra fields (e.g. ``evidence_spans[].bbox``) that recent Ollama models
    emit. This helper accepts the LLM's JSON loosely and projects only the
    ingredient names + amounts onto the V3 schema, which is enough to seed
    the user's review workflow.

Reference:
    outputs/todo-list/2026-05-21/b-persona-accuracy-report.md §5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent / "Nutrition-backend"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.config import get_settings  # noqa: E402
from src.llm.ollama import _build_chat_payload  # noqa: E402
from src.ocr.base import OCRImageInput  # noqa: E402
from src.ocr.providers.paddle import PaddleOCRAdapter  # noqa: E402

AUTO_SEEDED_WARNING = "auto_seeded_by_qwen3_5_9b"
"""Warning token added when LLM seeds ingredients."""


def _normalize_name(display_name: str) -> str:
    """Lowercase + collapse whitespace for a comparable normalized name.

    Args:
        display_name: Raw ingredient display name.

    Returns:
        Normalized identifier suitable for ``normalized_name`` fields.
    """
    return " ".join(display_name.casefold().split())


async def _extract_text(image_path: Path, settings: Any) -> str:
    """Run PaddleOCR on a single image and return the recognized text.

    Args:
        image_path: Source image path.
        settings: Application settings (provides PaddleOCR feature flags).

    Returns:
        Recognized text. Empty string when extraction fails.
    """
    adapter = PaddleOCRAdapter(settings)
    image_bytes = image_path.read_bytes()
    with Image.open(BytesIO(image_bytes)) as im:
        width, height = im.size
        mime_type = Image.MIME.get(im.format or "", "image/png")
    result = await adapter.extract_text(
        OCRImageInput(
            image_bytes=image_bytes,
            mime_type=mime_type,
            width=width,
            height=height,
        )
    )
    return (result.text or "").strip()


async def _call_llm(text: str, settings: Any) -> dict[str, Any]:
    """Call Ollama and return the parsed JSON response payload.

    Args:
        text: OCR text to send to the LLM.
        settings: Application settings (Ollama base url, model, timeout).

    Returns:
        Parsed JSON response, or an empty dict on failure.
    """
    payload = _build_chat_payload(text, settings)
    try:
        async with httpx.AsyncClient(timeout=float(settings.ollama_timeout_sec)) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            )
        response.raise_for_status()
        body = response.json()
        content = body.get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            return {}
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return {}
        return parsed
    except (httpx.HTTPError, json.JSONDecodeError):
        return {}


def _project_ingredients(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Project Ollama JSON ingredients onto V3 schema field set.

    Drops extra fields (``amount_text``, ``source``, ``evidence_refs``) and
    fills V3-required defaults so the result is schema-valid.

    Args:
        raw: Parsed LLM JSON payload.

    Returns:
        Ingredient list shaped for ``SupplementSnapshotIngredientV3``.
    """
    candidates = raw.get("ingredients")
    if not isinstance(candidates, list):
        return []
    projected: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        display_name = item.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            continue
        amount = item.get("amount")
        unit = item.get("unit")
        confidence = item.get("confidence")
        projected.append(
            {
                "display_name": display_name.strip(),
                "normalized_name": _normalize_name(display_name),
                "nutrient_code_candidates": [],
                "amount": amount if isinstance(amount, int | float) else None,
                "unit": unit if isinstance(unit, str) else None,
                "daily_amount": None,
                "daily_unit": None,
                "confidence": confidence if isinstance(confidence, int | float) else 0.5,
                "source": "ocr_llm_preview",
                "evidence_refs": [],
            }
        )
    return projected


def _inject_ingredients(snapshot_path: Path, ingredients: list[dict[str, Any]]) -> None:
    """Replace the ``ingredients`` field of a V3 snapshot in place.

    Adds the ``auto_seeded_by_qwen3_5_9b`` warning so the reviewer can tell the
    fixture went through an automated pre-fill. Keeps the
    ``ground_truth_pending_human_review`` warning so it stays out of the
    human-labeled progress count.

    Args:
        snapshot_path: Existing V3 snapshot path.
        ingredients: Projected ingredient list to inject.
    """
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["ingredients"] = ingredients
    warnings = snapshot.get("warnings", [])
    if isinstance(warnings, list) and AUTO_SEEDED_WARNING not in warnings:
        warnings.append(AUTO_SEEDED_WARNING)
        snapshot["warnings"] = warnings
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


async def _process_fixture(
    fixture: dict[str, Any],
    work_dir: Path,
    expected_dir: Path,
    settings: Any,
) -> tuple[str, str, int]:
    """Process one fixture end-to-end: OCR → LLM → V3 inject.

    Args:
        fixture: Manifest case row.
        work_dir: Workspace containing copied images.
        expected_dir: Directory holding ``*.snapshot_v3.json`` files.
        settings: Application settings.

    Returns:
        Tuple ``(fixture_id, status, ingredient_count)`` where ``status`` is
        one of ``"ok"``, ``"ocr_empty"``, ``"llm_empty"``, or ``"no_v3"``.
    """
    fixture_id = str(fixture.get("fixture_id"))
    image_rel = fixture.get("image_path")
    if not isinstance(image_rel, str):
        return fixture_id, "no_image_path", 0
    image_path = work_dir / image_rel
    try:
        text = await _extract_text(image_path, settings)
    except Exception as exc:
        return fixture_id, f"ocr_error:{type(exc).__name__}", 0
    if not text:
        return fixture_id, "ocr_empty", 0
    raw = await _call_llm(text, settings)
    ingredients = _project_ingredients(raw)
    if not ingredients:
        return fixture_id, "llm_empty", 0
    # fixture_id 가 naver-live-* 이지만 V3 skeleton 은 naver-chronic-* 으로 생성됨
    chronic_id = fixture_id.replace("naver-live-", "naver-chronic-")
    target = expected_dir / f"{chronic_id}.snapshot_v3.json"
    if not target.exists():
        return fixture_id, "no_v3", 0
    _inject_ingredients(target, ingredients)
    return fixture_id, "ok", len(ingredients)


async def main_async() -> None:
    """Coroutine entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-dir", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    work_dir = args.manifest.parent
    settings = get_settings()
    print(f"model={settings.ollama_model}, timeout={settings.ollama_timeout_sec}s")

    results: list[tuple[str, str, int]] = []
    for case in manifest.get("cases", []):
        result = await _process_fixture(case, work_dir, args.expected_dir, settings)
        print(f"  {result[0]:24} {result[1]:12} {result[2]} ingredients")
        results.append(result)

    print("---")
    status_counts = Counter(r[1] for r in results)
    print(f"Status: {dict(status_counts)}")
    print(f"OK: {status_counts.get('ok', 0)}/{len(results)}")


def main() -> None:
    """CLI entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
