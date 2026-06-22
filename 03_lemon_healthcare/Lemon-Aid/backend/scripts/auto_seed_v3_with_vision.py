"""Auto-seed V3 product/serving fields with Ollama vision LLM (gemma4).

Reads each fixture image directly via Ollama vision chat API and extracts
``product_name``, ``manufacturer``, ``serving_size_text``, ``daily_servings``
into the V3 snapshot. Ingredients are NOT touched here — they are seeded by
``auto_seed_v3_with_llm.py`` separately via OCR text → text LLM.

Like the text-LLM seed script, ``source`` markers are kept conservative and the
``ground_truth_pending_human_review`` warning is preserved so the fixture stays
out of human-labeled progress until a human reviews.

Reference:
    outputs/todo-list/2026-05-21/b-persona-accuracy-report.md §5
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent / "Nutrition-backend"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

VISION_SEEDED_WARNING = "vision_seeded_by_gemma4"
"""V3 warnings에 추가될 토큰 — vision LLM이 product/serving 자동 시드 표시."""

VISION_PROMPT = (
    "이 한국 영양제 라벨 이미지에서 다음 정보를 JSON으로 추출하세요. "
    "JSON만 반환하고 markdown 코드 블록이나 설명을 포함하지 마세요. "
    "확실하지 않으면 해당 필드를 null로 두세요.\n"
    "{\n"
    '  "product_name": "<제품명, 한글/영문 그대로>",\n'
    '  "manufacturer": "<제조사명 또는 null>",\n'
    '  "serving_size_text": "<예: 1일 2캡슐 또는 1 tablet daily, 또는 null>",\n'
    '  "daily_servings": <1일 권장 횟수 정수 또는 null>\n'
    "}"
)


def _extract_json(content: str) -> dict[str, Any]:
    """Extract a JSON object from a possibly markdown-wrapped LLM response.

    Args:
        content: Raw response content from the vision LLM.

    Returns:
        Parsed JSON object, or an empty dict on failure.
    """
    stripped = content.strip()
    if stripped.startswith("```"):
        # Strip ```json ... ``` markdown wrapper
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


async def _call_vision(image_bytes: bytes, model: str, timeout_sec: int) -> dict[str, Any]:
    """Send the fixture image to an Ollama vision-capable model.

    Args:
        image_bytes: Raw image bytes (jpg/png/webp).
        model: Ollama model tag, e.g. ``gemma4:latest``.
        timeout_sec: Request timeout in seconds.

    Returns:
        Parsed product/serving JSON, or an empty dict on failure.
    """
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": VISION_PROMPT, "images": [image_b64]},
        ],
        "stream": False,
        "options": {"temperature": 0.0},
    }
    try:
        async with httpx.AsyncClient(timeout=float(timeout_sec)) as client:
            response = await client.post("http://127.0.0.1:11434/api/chat", json=payload)
        response.raise_for_status()
        body = response.json()
        content = body.get("message", {}).get("content", "")
        if not isinstance(content, str):
            return {}
        return _extract_json(content)
    except (httpx.HTTPError, json.JSONDecodeError):
        return {}


def _inject_product_serving(snapshot_path: Path, vision_data: dict[str, Any]) -> bool:
    """Update V3 snapshot product/serving fields from vision JSON.

    Args:
        snapshot_path: V3 snapshot path.
        vision_data: Parsed vision response.

    Returns:
        ``True`` when at least one field was updated, ``False`` otherwise.
    """
    if not vision_data:
        return False
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    changed = False

    product_name = vision_data.get("product_name")
    if isinstance(product_name, str) and product_name.strip():
        snapshot.setdefault("product", {})["product_name"] = product_name.strip()
        changed = True

    manufacturer = vision_data.get("manufacturer")
    if isinstance(manufacturer, str) and manufacturer.strip():
        snapshot.setdefault("product", {})["manufacturer"] = manufacturer.strip()
        changed = True

    serving_size_text = vision_data.get("serving_size_text")
    if isinstance(serving_size_text, str) and serving_size_text.strip():
        snapshot.setdefault("serving", {})["serving_size_text"] = serving_size_text.strip()
        changed = True

    daily_servings = vision_data.get("daily_servings")
    if isinstance(daily_servings, int) and daily_servings > 0:
        snapshot.setdefault("serving", {})["daily_servings"] = daily_servings
        changed = True

    if changed:
        warnings = snapshot.get("warnings", [])
        if isinstance(warnings, list) and VISION_SEEDED_WARNING not in warnings:
            warnings.append(VISION_SEEDED_WARNING)
            snapshot["warnings"] = warnings
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changed


async def _process(
    fixture: dict[str, Any],
    work_dir: Path,
    expected_dir: Path,
    model: str,
    timeout_sec: int,
) -> tuple[str, str]:
    """Process one fixture: vision call → V3 update.

    Args:
        fixture: Manifest case row.
        work_dir: Workspace dir holding ``images/``.
        expected_dir: Directory holding V3 snapshots.
        model: Vision model tag.
        timeout_sec: Request timeout.

    Returns:
        ``(fixture_id, status)`` where status is ``"ok"`` / ``"vision_empty"`` / ``"no_v3"``.
    """
    fixture_id = str(fixture.get("fixture_id"))
    image_rel = fixture.get("image_path")
    if not isinstance(image_rel, str):
        return fixture_id, "no_image_path"
    image_path = work_dir / image_rel
    chronic_id = fixture_id.replace("naver-live-", "naver-chronic-")
    target = expected_dir / f"{chronic_id}.snapshot_v3.json"
    if not target.exists():
        return fixture_id, "no_v3"
    image_bytes = image_path.read_bytes()
    vision_data = await _call_vision(image_bytes, model=model, timeout_sec=timeout_sec)
    if not vision_data:
        return fixture_id, "vision_empty"
    updated = _inject_product_serving(target, vision_data)
    return fixture_id, "ok" if updated else "vision_empty"


async def main_async() -> None:
    """Coroutine entry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-dir", required=True, type=Path)
    parser.add_argument("--model", default="gemma4:latest")
    parser.add_argument("--timeout-sec", type=int, default=300)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    work_dir = args.manifest.parent
    print(f"model={args.model} timeout={args.timeout_sec}s")

    statuses: list[tuple[str, str]] = []
    for case in manifest.get("cases", []):
        result = await _process(
            case,
            work_dir=work_dir,
            expected_dir=args.expected_dir,
            model=args.model,
            timeout_sec=args.timeout_sec,
        )
        print(f"  {result[0]:24} {result[1]}")
        statuses.append(result)
    print("---")
    print(f"Status: {dict(Counter(s[1] for s in statuses))}")


def main() -> None:
    """CLI entry."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
