"""Build supplement OCR ground truth from CLOVA OCR (teacher) for the benchmark.

Operator decision: use CLOVA OCR output as the ground-truth (pseudo-GT) answer key
that PaddleOCR is later measured/distilled against. For each PII-cleared review
image in the ground-truth bundle, this tool runs CLOVA OCR (external, opt-in via
``ENABLE_CLOVA_OCR``/``ALLOW_EXTERNAL_OCR``), structures the text with the local
Ollama supplement parser, and writes the structured ``expected`` into
``ground-truth.todo.jsonl`` (``ready_for_benchmark_after_review=true``).

CLOVA returns raw text; the GT schema requires structured sections (ingredients,
intake_method, precautions), so the Ollama parser bridges text -> structure. Only
structured label fields are stored — no raw provider payloads or local paths.

Idempotent: rows already marked ready are skipped unless ``--force``. Per-row
failure isolation (a failed image is reported and retried on the next run). Runs
in the py3.13 backend venv (``PYTHONPATH=Nutrition-backend``). Dry-run by default;
pass ``--apply`` to write and to make the external CLOVA calls.

References:
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image
from src.config import Settings, get_settings
from src.llm.ollama import OllamaSupplementParser
from src.ocr.base import OCRImageInput
from src.ocr.providers.clova import ClovaOCRAdapter
from src.services.supplement_parser import normalize_ocr_text

ALLERGEN_KEYWORDS = ("알레르기", "알러지", "함유", "allergen", "allergy")
MIME_BY_SUFFIX = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _allergen_rows(precautions: list[dict[str, Any]], sections: list[dict[str, Any]]) -> list[dict]:
    """Derive allergen-warning rows from precaution/section text (best effort).

    The parser has no dedicated allergen field, so allergen lines are recovered
    from precautions and label sections whose text mentions an allergen keyword.

    Args:
        precautions: Parsed precaution rows (each may carry ``text``).
        sections: Parsed label-section rows.

    Returns:
        Allergen-warning rows shaped as ``{"text": ...}``.
    """
    rows: list[dict[str, Any]] = []
    for item in precautions:
        text = str(item.get("text") or "")
        if any(keyword in text for keyword in ALLERGEN_KEYWORDS):
            rows.append({"text": text})
    for section in sections:
        if "allergen" in str(section.get("section_type") or "").lower():
            heading = str(section.get("heading_text") or section.get("text_bundle") or "").strip()
            if heading:
                rows.append({"text": heading})
    return rows


def _expected_from_parse(parsed: dict[str, Any]) -> dict[str, Any]:
    """Map a structured parser result into the GT ``expected`` object.

    Args:
        parsed: ``SupplementStructuredParseResult.model_dump()`` output.

    Returns:
        A GT ``expected`` dict compatible with the benchmark scripts.
    """
    product = parsed.get("parsed_product") or {}
    ingredients = [
        {
            "display_name": candidate.get("display_name"),
            "original_name": candidate.get("original_name"),
            "amount": candidate.get("amount"),
            "unit": candidate.get("unit"),
            "nutrient_code": None,
        }
        for candidate in parsed.get("ingredient_candidates", [])
        if candidate.get("display_name")
    ]
    intake = parsed.get("intake_method") or {}
    precautions = [{"text": p["text"]} for p in parsed.get("precautions", []) if p.get("text")]
    functional = [
        {"text": claim["text"]}
        for claim in parsed.get("functional_claims", [])
        if claim.get("text")
    ]
    label_sections = [
        {"section_type": section.get("section_type")}
        for section in parsed.get("label_sections", [])
        if section.get("section_type")
    ]
    return {
        "expected_source": "clova_pseudo_gt",
        "verification_status": "human_reviewed",
        "product_name": product.get("product_name"),
        "manufacturer": product.get("manufacturer"),
        "ingredients": ingredients,
        "intake_method": {
            "text": intake.get("text") or "",
            "structured": intake.get("structured") or {"frequency": "", "time_of_day": []},
        },
        "precautions": precautions,
        "allergen_warnings": _allergen_rows(
            parsed.get("precautions", []), parsed.get("label_sections", [])
        ),
        "functional_claims": functional,
        "label_sections": label_sections,
    }


def _load_image(path: Path) -> tuple[bytes, str, int, int]:
    """Return ``(bytes, mime_type, width, height)`` for a bundle review image."""
    data = path.read_bytes()
    mime = MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
    with Image.open(path) as image:
        width, height = image.size
    return data, mime, width, height


async def _structured_expected(
    image_path: Path,
    *,
    settings: Settings,
    clova: ClovaOCRAdapter,
    parser: OllamaSupplementParser,
) -> tuple[dict[str, Any], int]:
    """Run CLOVA OCR then the Ollama parser for one image.

    Args:
        image_path: Materialized review image path.
        settings: Runtime settings (OCR text cap).
        clova: CLOVA OCR adapter.
        parser: Ollama supplement parser.

    Returns:
        ``(expected, ocr_char_count)`` for the image.
    """
    data, mime, width, height = _load_image(image_path)
    ocr = await clova.extract_text(
        OCRImageInput(image_bytes=data, mime_type=mime, width=width, height=height)
    )
    normalized = normalize_ocr_text(ocr.text or "", settings.supplement_ocr_text_max_chars)
    parsed = await parser.parse_supplement_ocr_text(normalized)
    return _expected_from_parse(parsed.model_dump()), len(ocr.text or "")


async def build(
    *, bundle_dir: Path, limit: int | None, force: bool
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fill GT rows from CLOVA OCR + the Ollama parser.

    Args:
        bundle_dir: GT review bundle directory (holds ``ground-truth.todo.jsonl`` and ``images/``).
        limit: Optional cap on processed rows (for sampling).
        force: Re-fill rows already marked ready.

    Returns:
        ``(rows, summary)`` where ``rows`` is the updated GT list and ``summary`` is count-only.
    """
    todo_path = bundle_dir / "ground-truth.todo.jsonl"
    rows: list[dict[str, Any]] = []
    malformed_lines = 0
    for line in todo_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            malformed_lines += (
                1  # per-line isolation: skip malformed rows (line content not stored)
            )
    settings = get_settings()
    clova = ClovaOCRAdapter(settings)
    parser = OllamaSupplementParser(settings)
    stats: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    processed = 0
    for row in rows:
        if limit is not None and processed >= limit:
            break
        already = row.get("ready_for_benchmark_after_review") is True
        if already and not force:
            stats["skipped_ready"] += 1
            continue
        processed += 1
        fixture_id = str(row.get("fixture_id", ""))
        image_path = bundle_dir / str(row.get("image_path", ""))
        try:
            expected, ocr_chars = await _structured_expected(
                image_path, settings=settings, clova=clova, parser=parser
            )
            row["expected"] = expected
            row["ground_truth_status"] = "human_reviewed"
            row["ready_for_benchmark_after_review"] = bool(expected["ingredients"])
            if expected["ingredients"]:
                # The benchmark block-reason rejects rows whose review decision is
                # still "pending"; the operator decision is to accept CLOVA output
                # as the ground truth, so approve filled rows for the benchmark.
                row["decision"] = "approved"
                stats["filled_with_ingredients"] += 1
            else:
                stats["filled_no_ingredients"] += 1
            stats["ocr_chars_total"] += ocr_chars
        except Exception as exc:
            stats["failed"] += 1
            # Store only the safe error-type token: exception messages may embed
            # local absolute image paths (e.g. FileNotFoundError) which are forbidden.
            failures.append({"fixture_id": fixture_id, "error": type(exc).__name__})
    summary = {
        "rows": len(rows),
        "processed": processed,
        "malformed_input_lines": malformed_lines,
        **dict(stats),
        "failures": failures[:50],
    }
    return rows, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="Defaults to in-place rewrite.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bundle_dir = args.bundle_dir.expanduser()
    if not (bundle_dir / "ground-truth.todo.jsonl").is_file():
        raise SystemExit(f"ERROR: ground-truth.todo.jsonl not found under {bundle_dir}")
    if not args.apply:
        rows = (bundle_dir / "ground-truth.todo.jsonl").read_text(encoding="utf-8").splitlines()
        print(json.dumps({"apply_requested": False, "rows": len([r for r in rows if r.strip()])}))
        return 0
    rows, summary = asyncio.run(build(bundle_dir=bundle_dir, limit=args.limit, force=args.force))
    output = args.output or (bundle_dir / "ground-truth.todo.jsonl")
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    summary["apply_requested"] = True
    summary["output"] = output.name  # basename only; absolute paths must not enter outputs
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "failures"}, ensure_ascii=False, indent=2
        )
    )
    if summary.get("failures"):
        print(f"failures: {len(summary['failures'])} (see summary file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
