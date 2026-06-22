"""Build a held-out STRUCTURED-extraction eval summary (field-level, not char-LCS).

This is the structured counterpart to ``build_paddleocr_text_extraction_eval_summary``.
The char-level normalized-text metric is structurally precision-capped when the OCR
reads the whole label but the ground truth covers only a few sections (see
``docs/ocr_baseline_reports/2026-06-08-text-f1-improvement-design.md``). The product
question — "did we extract the required fields correctly?" — is answered by the
FIELD-level metric (``field_match_ratio`` = per-field rapidfuzz match), which is what
this summary isolates so the structured-extraction gate can be separated from the
text gate.

Input = a ``paddleocr_clova_eval`` JSON (carrying ``per_image`` field-level metrics)
plus the benchmark split assignment (to filter the held-out split). Only ratios and
counts are emitted; no raw OCR text, payloads, or absolute paths.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-structured-extraction-eval-summary-v1"
FIELD_HALF_THRESHOLD = 0.5


def _round(value: float, places: int = 4) -> float:
    """Round a ratio for redacted reporting."""
    return round(float(value), places)


def build_summary(
    *,
    eval_json: dict[str, Any],
    split_rows: list[dict[str, Any]],
    eval_split: str,
    provider: str,
    leakage_check_passed: bool,
    privacy_review_cleared: bool,
) -> dict[str, Any]:
    """Compute a held-out field-level structured-extraction summary.

    Args:
        eval_json: ``paddleocr_clova_eval`` output containing ``per_image``.
        split_rows: Benchmark split assignment rows (fixture_id -> split/sections).
        eval_split: Split to evaluate (e.g. ``holdout``).
        provider: Target provider label.
        leakage_check_passed: Operator attestation that the split is leakage-safe.
        privacy_review_cleared: Operator attestation that inputs are PII-cleared.

    Returns:
        Redacted structured-extraction summary dict.
    """
    split_by_fixture = {r.get("fixture_id"): r.get("split") for r in split_rows}
    per_image = eval_json.get("per_image") or []
    rows = [e for e in per_image if split_by_fixture.get(e.get("fixture_id")) == eval_split]

    fixture_count = len(rows)
    field_matched = sum(int(e.get("field_matched", 0)) for e in rows)
    field_total = sum(int(e.get("field_total", 0)) for e in rows)
    ing_found = sum(int(e.get("ingredient_found", 0)) for e in rows)
    ing_total = sum(int(e.get("ingredient_total", 0)) for e in rows)
    macro = (
        sum(float(e.get("field_match_ratio", 0.0)) for e in rows) / fixture_count
        if fixture_count
        else 0.0
    )
    micro = field_matched / field_total if field_total else 0.0
    ing_recall = ing_found / ing_total if ing_total else 0.0
    # failure-mode counts (diagnostic; aligns with the v2 hard-case taxonomy)
    field_zero = sum(1 for e in rows if float(e.get("field_match_ratio", 0.0)) == 0.0)
    field_lt50 = sum(
        1 for e in rows if float(e.get("field_match_ratio", 0.0)) < FIELD_HALF_THRESHOLD
    )
    ing_all_missed = sum(
        1
        for e in rows
        if int(e.get("ingredient_total", 0)) > 0 and int(e.get("ingredient_found", 0)) == 0
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "eval_split": eval_split,
        "fixture_count": fixture_count,
        "metrics": {
            "field_match_ratio_macro": _round(macro),
            "field_match_ratio_micro": _round(micro),
            "ingredient_recall": _round(ing_recall),
        },
        "failure_modes": {
            "field_zero": field_zero,
            "field_lt50": field_lt50,
            "ingredient_all_missed": ing_all_missed,
        },
        "leakage_check_passed": bool(leakage_check_passed),
        "privacy_review_cleared": bool(privacy_review_cleared),
        "recognition_model_dir_present": (
            bool(eval_json.get("recognition_model_dir_present"))
            or eval_json.get("recognition_model_dir") is not None
        ),
    }


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--eval-json", required=True, type=Path, help="paddleocr_clova_eval output JSON."
    )
    ap.add_argument("--splits", required=True, type=Path, help="Benchmark split assignment JSONL.")
    ap.add_argument("--eval-split", default="holdout")
    ap.add_argument("--provider", default="paddleocr_local")
    ap.add_argument("--leakage-check-passed", action="store_true")
    ap.add_argument("--privacy-review-cleared", action="store_true")
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()

    eval_json = json.loads(a.eval_json.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in a.splits.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = build_summary(
        eval_json=eval_json,
        split_rows=rows,
        eval_split=a.eval_split,
        provider=a.provider,
        leakage_check_passed=a.leakage_check_passed,
        privacy_review_cleared=a.privacy_review_cleared,
    )
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
