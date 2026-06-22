"""Oracle text-ceiling rung: the field_match a PERFECT recognizer could reach.

One rung of the oracle ladder (2026-06-19 0.85/0.90 gate redesign, Step 2). It
feeds the GT structured-reference text itself back in as the OCR hypothesis — i.e.
perfect recognition — and scores it with the IDENTICAL field_match /
ingredient_recall metric the live ``paddleocr_clova_eval`` uses. The result is the
CEILING: the maximum field_match achievable if the recognizer made zero errors.

Comparing this ceiling to the 0.85/0.90 gate isolates the binding constraint:

  * ceiling certified >= gate  -> the metric, normalization, and GT field coverage
    can reach the gate, so the remaining gap to a real recognizer run is recognition
    error — a recognizer lever (training, ROI, fusion) can close it.
  * ceiling < gate             -> even perfect recognition fails the gate, so the
    binding constraint is metric normalization, alias coverage, or GT field
    coverage. A recognizer retrain cannot reach the gate; fix those first.

This rung complements the recognition-ceiling rung (``build_roi_first_oracle_bundle``
+ a recognizer run), which holds detection perfect and measures recognition. Run
both and read the ladder bottom-up: if THIS ceiling already misses the gate, no
recognizer work matters yet.

Reuses the canonical metric functions from ``paddleocr_clova_eval`` (so the ceiling
is directly comparable to a recognizer run on the same bundle) and the Wilson
lower-bound discipline from ``eval_statistics`` (so a small holdout cannot
over-claim a ceiling it has not earned). No images, no OCR, no model load.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:  # direct run with scripts/ on sys.path (PYTHONPATH=Nutrition-backend)
    from eval_statistics import MetricDecision, metric_decision
    from paddleocr_clova_eval import (
        FIELD_MATCH_THRESHOLD,
        _field_match_ratio,
        _field_units,
        _ingredient_recall,
        _normalize_for_metric,
        _structured_reference,
    )
except ImportError:  # imported as scripts.* (pytest, backend root on sys.path)
    from scripts.eval_statistics import MetricDecision, metric_decision
    from scripts.paddleocr_clova_eval import (
        FIELD_MATCH_THRESHOLD,
        _field_match_ratio,
        _field_units,
        _ingredient_recall,
        _normalize_for_metric,
        _structured_reference,
    )

# field_match_RATIO gate targets (distinct from FIELD_MATCH_THRESHOLD, the per-unit
# rapidfuzz partial-ratio cutoff used inside _field_match_ratio).
GATE_TARGETS = (0.85, 0.90)


def load_ready_rows(bundle_dir: Path) -> list[dict[str, Any]]:
    """Return the benchmark-ready GT rows from a bundle (mirrors the eval filter).

    Args:
        bundle_dir: Bundle directory containing ``ground-truth.todo.jsonl``.

    Returns:
        Rows that are reviewed-ready and carry a structured ``expected`` object.
    """
    todo = bundle_dir / "ground-truth.todo.jsonl"
    rows: list[dict[str, Any]] = []
    for line in todo.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("ready_for_benchmark_after_review") is True and isinstance(
            row.get("expected"), dict
        ):
            rows.append(row)
    return rows


def _decision_dict(decision: MetricDecision) -> dict[str, Any]:
    """Render a :class:`MetricDecision` as a JSON-friendly mapping."""
    return {
        "point": round(decision.point, 4),
        "lower_bound": round(decision.lower_bound, 4),
        "upper_bound": round(decision.upper_bound, 4),
        "threshold": decision.threshold,
        "point_met": decision.point_met,
        "certified": decision.certified,
    }


def score_ceiling(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Score the perfect-recognition field_match ceiling for the GT rows.

    For each row the hypothesis is the GT structured-reference text itself, so the
    only thing that can keep a field unit from matching is the metric's own
    normalization/alias handling — not recognition.

    Args:
        rows: Benchmark-ready GT rows (each with a structured ``expected``).

    Returns:
        Aggregated ceiling metrics plus per-gate Wilson-certified decisions.
    """
    field_ratio_sum = 0.0
    field_matched_total = 0
    field_unit_total = 0
    recall_found = 0
    recall_total = 0
    per_product_field_ratios: list[float] = []
    for row in rows:
        expected = row["expected"]
        hypothesis_norm = _normalize_for_metric(_structured_reference(expected))
        f_matched, f_total = _field_match_ratio(_field_units(expected), hypothesis_norm)
        found, total = _ingredient_recall(expected, hypothesis_norm)
        ratio = f_matched / f_total if f_total else 0.0
        per_product_field_ratios.append(ratio)
        field_ratio_sum += ratio
        field_matched_total += f_matched
        field_unit_total += f_total
        recall_found += found
        recall_total += total

    n = len(rows)
    macro = field_ratio_sum / n if n else 0.0
    micro = field_matched_total / field_unit_total if field_unit_total else 0.0
    recall = recall_found / recall_total if recall_total else 0.0

    gates: dict[str, Any] = {}
    for target in GATE_TARGETS:
        pass_rate = sum(1 for r in per_product_field_ratios if r >= target) / n if n else 0.0
        gates[f"{target:.2f}"] = {
            "field_match_macro": _decision_dict(
                metric_decision("field_match_macro", macro, n, target)
            ),
            "ingredient_recall": _decision_dict(
                metric_decision("ingredient_recall", recall, n, target)
            ),
            "per_product_pass_rate": _decision_dict(
                metric_decision("per_product_field_match_pass_rate", pass_rate, n, target)
            ),
        }

    return {
        "schema_version": "oracle-text-ceiling-v1",
        "leg": "perfect_recognition_field_match_ceiling",
        "rows_scored": n,
        "field_match_unit_threshold": FIELD_MATCH_THRESHOLD,
        "field_match_ratio_macro": round(macro, 4),
        "field_match_ratio_micro": round(micro, 4),
        "field_matched_total": [field_matched_total, field_unit_total],
        "ingredient_recall": round(recall, 4),
        "ingredient_found_total": [recall_found, recall_total],
        "gates": gates,
        "interpretation": (
            "Ceiling = field_match with the GT reference text as a perfect hypothesis. "
            "Where a gate's field_match_macro is not certified, even flawless recognition "
            "cannot reach that gate on this holdout, so the binding constraint is metric "
            "normalization / alias coverage / GT field coverage — not the recognizer."
        ),
    }


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = score_ceiling(load_ready_rows(args.bundle_dir))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
