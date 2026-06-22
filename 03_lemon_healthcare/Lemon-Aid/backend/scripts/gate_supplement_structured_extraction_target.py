"""Gate held-out STRUCTURED extraction quality (field-level) against a target.

Separated from the char-level text gate (``gate_paddleocr_text_extraction_target``)
on purpose: the text gate measures concatenated normalized-text precision/recall,
which is precision-capped when OCR output scope exceeds the section-scoped ground
truth. This gate answers the product question — "are the required fields extracted
correctly?" — using ``field_match_ratio`` (per-field match) on the held-out split.

Consumes only a redacted structured-extraction summary
(``supplement-structured-extraction-eval-summary-v1``). No images, OCR text,
payloads, DB, or source manifests are read.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:  # importable both as a script (backend/scripts on path) and as scripts.<mod>
    from eval_statistics import metric_decision
except ImportError:  # pragma: no cover - import-path shim for package context
    from scripts.eval_statistics import metric_decision

SCHEMA_VERSION = "supplement-structured-extraction-target-gate-v1"
SUPPORTED_EVAL_SCHEMA_VERSIONS = frozenset({"supplement-structured-extraction-eval-summary-v1"})
TARGET_PROVIDER = "paddleocr_local"
ALLOWED_STOP_SPLITS = frozenset({"holdout", "test"})
STATUS_TARGET_REACHED = "structured_target_reached"
STATUS_CONTINUE = "continue_extraction_improvement"
DEFAULT_TARGET_THRESHOLD = Decimal("0.90")
DEFAULT_MIN_INGREDIENT_RECALL = Decimal("0.85")
DEFAULT_MIN_FIXTURE_COUNT = 30


class StructuredGateError(RuntimeError):
    """Raised when the structured gate input cannot be trusted."""


def build_structured_extraction_gate(
    summary: dict[str, Any],
    *,
    target_threshold: Decimal = DEFAULT_TARGET_THRESHOLD,
    min_ingredient_recall: Decimal = DEFAULT_MIN_INGREDIENT_RECALL,
    min_fixture_count: int = DEFAULT_MIN_FIXTURE_COUNT,
) -> dict[str, Any]:
    """Build the redacted structured-extraction target gate artifact.

    Args:
        summary: Structured-extraction eval summary.
        target_threshold: Required ``field_match_ratio`` (macro and micro).
        min_ingredient_recall: Required ingredient recall.
        min_fixture_count: Minimum held-out fixtures for a trustworthy stop.

    Returns:
        Redacted gate artifact with a boolean ``structured_target_reached``.
    """
    if summary.get("schema_version") not in SUPPORTED_EVAL_SCHEMA_VERSIONS:
        raise StructuredGateError("Unsupported or missing structured-eval schema_version.")
    metrics = summary.get("metrics") or {}
    eval_split = summary.get("eval_split")
    fixture_count = int(summary.get("fixture_count", 0))

    def _dec(key: str) -> Decimal:
        try:
            return Decimal(str(metrics.get(key)))
        except (InvalidOperation, TypeError) as exc:
            raise StructuredGateError(f"Metric {key} is not a number.") from exc

    macro = _dec("field_match_ratio_macro")
    micro = _dec("field_match_ratio_micro")
    ing_recall = _dec("ingredient_recall")

    checks = {
        "schema_supported": True,
        "provider_is_local": summary.get("provider") == TARGET_PROVIDER,
        "eval_split_allowed": eval_split in ALLOWED_STOP_SPLITS,
        "minimum_fixture_count_met": fixture_count >= min_fixture_count,
        "leakage_check_passed": summary.get("leakage_check_passed") is True,
        "privacy_review_cleared": summary.get("privacy_review_cleared") is True,
        "field_match_macro_met": macro >= target_threshold,
        "field_match_micro_met": micro >= target_threshold,
        "ingredient_recall_met": ing_recall >= min_ingredient_recall,
    }
    reached = all(checks.values())
    blockers = [name for name, ok in checks.items() if not ok]

    # Step-0 statistical discipline: a metric is only CERTIFIED at its threshold
    # when the 95% Wilson lower bound clears it. At small fixture counts a point
    # estimate above threshold can still have a lower bound well below it, so
    # ``structured_target_reached`` (point-based) is kept for backward compatibility
    # while ``certified_target_reached`` is the honest gate.
    decisions = {
        "field_match_ratio_macro": metric_decision(
            "field_match_ratio_macro", float(macro), fixture_count, float(target_threshold)
        ),
        "field_match_ratio_micro": metric_decision(
            "field_match_ratio_micro", float(micro), fixture_count, float(target_threshold)
        ),
        "ingredient_recall": metric_decision(
            "ingredient_recall", float(ing_recall), fixture_count, float(min_ingredient_recall)
        ),
    }
    certified_checks = {
        "field_match_macro_certified": decisions["field_match_ratio_macro"].certified,
        "field_match_micro_certified": decisions["field_match_ratio_micro"].certified,
        "ingredient_recall_certified": decisions["ingredient_recall"].certified,
    }
    certified = reached and all(certified_checks.values())

    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_TARGET_REACHED if reached else STATUS_CONTINUE,
        "structured_target_reached": reached,
        "certified_target_reached": certified,
        "continue_extraction_improvement": not reached,
        "provider": summary.get("provider"),
        "eval_split": eval_split,
        "fixture_count": fixture_count,
        "target_threshold": str(target_threshold),
        "min_ingredient_recall": str(min_ingredient_recall),
        "observed": {
            "field_match_ratio_macro": str(macro),
            "field_match_ratio_micro": str(micro),
            "ingredient_recall": str(ing_recall),
        },
        "metric_lower_bounds_95": {
            name: round(decision.lower_bound, 4) for name, decision in decisions.items()
        },
        "checks": checks,
        "certified_checks": certified_checks,
        "blocker_codes": blockers,
        "statistical_note": (
            "certified_target_reached requires the 95% Wilson LOWER bound to clear the "
            "threshold (Step-0 rule); field_match_ratio_macro is a mean of per-product "
            "ratios so its Wilson interval is a conservative binomial approximation. "
            "Compare two strategies with eval_statistics.paired_mcnemar on the same fixtures."
        ),
    }


def main() -> int:
    """Run the structured-extraction gate and print a redacted status."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eval-summary", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--target-threshold", default=str(DEFAULT_TARGET_THRESHOLD))
    ap.add_argument("--min-ingredient-recall", default=str(DEFAULT_MIN_INGREDIENT_RECALL))
    ap.add_argument("--min-fixtures", type=int, default=DEFAULT_MIN_FIXTURE_COUNT)
    a = ap.parse_args()
    try:
        gate = build_structured_extraction_gate(
            json.loads(a.eval_summary.read_text(encoding="utf-8")),
            target_threshold=Decimal(str(a.target_threshold)),
            min_ingredient_recall=Decimal(str(a.min_ingredient_recall)),
            min_fixture_count=a.min_fixtures,
        )
    except StructuredGateError as exc:
        print(
            json.dumps(
                {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if gate["structured_target_reached"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
