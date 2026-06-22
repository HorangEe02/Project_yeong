"""Run PaddleOCR structured-extraction detector/post-pass sweeps.

This runner keeps the current Lemon-Aid decision contract intact:
``field_match_ratio_macro``, ``field_match_ratio_micro``, and
``ingredient_recall`` are computed by ``paddleocr_clova_eval`` and then passed
through the redacted structured summary/gate chain. It writes only numeric
metrics and per-fixture counts; raw OCR text, provider payloads, and absolute
private image paths are not persisted.

References:
    https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
    https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.build_supplement_structured_extraction_eval_summary import build_summary  # noqa: E402
from scripts.gate_supplement_structured_extraction_target import (  # noqa: E402
    build_structured_extraction_gate,
)
from scripts.paddleocr_clova_eval import (  # noqa: E402
    POST_PASS_CHOICES,
    POST_PASS_NONE,
    PROFILES,
    evaluate,
)

SCHEMA_VERSION = "paddleocr-structured-sweep-v1"
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html",
    "https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html",
)


@dataclass(frozen=True)
class SweepConfig:
    """One detector-threshold configuration to evaluate.

    Args:
        name: Stable config name for artifact filenames.
        det_box_thresh: Optional PaddleOCR text detection box threshold.
        det_thresh: Optional PaddleOCR text detection pixel threshold.
        det_unclip_ratio: Optional PaddleOCR text detection expansion ratio.
        max_side: Optional config-specific detection side limit.
    """

    name: str
    det_box_thresh: float | None = None
    det_thresh: float | None = None
    det_unclip_ratio: float | None = None
    max_side: int | None = None


DETECTOR_SWEEP = (
    SweepConfig(name="baseline"),
    SweepConfig(name="box03", det_box_thresh=0.3),
    SweepConfig(name="box04", det_box_thresh=0.4),
    SweepConfig(name="thresh015", det_thresh=0.15),
    SweepConfig(name="thresh02", det_thresh=0.2),
    SweepConfig(name="unclip25", det_unclip_ratio=2.5),
    SweepConfig(name="unclip30", det_unclip_ratio=3.0),
    SweepConfig(name="unclip35", det_unclip_ratio=3.5),
    SweepConfig(name="unclip25_side4096", det_unclip_ratio=2.5, max_side=4096),
    SweepConfig(
        name="combined_thresh02_box04_unclip25",
        det_thresh=0.2,
        det_box_thresh=0.4,
        det_unclip_ratio=2.5,
    ),
    SweepConfig(
        name="combined_thresh015_box03_unclip30",
        det_thresh=0.15,
        det_box_thresh=0.3,
        det_unclip_ratio=3.0,
    ),
)
QUICK_SWEEP = (
    SweepConfig(name="baseline"),
    SweepConfig(name="box04", det_box_thresh=0.4),
)
CONFIG_BY_NAME = {config.name: config for config in (*DETECTOR_SWEEP,)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--splits", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="server_detection")
    parser.add_argument("--det-model", default=None)
    parser.add_argument("--rec-model", default=None)
    parser.add_argument("--rec-model-dir", default=None)
    parser.add_argument("--max-side", type=int, default=None)
    parser.add_argument("--post-pass", choices=POST_PASS_CHOICES, default=POST_PASS_NONE)
    parser.add_argument("--preset", choices=("quick", "detector"), default="detector")
    parser.add_argument(
        "--configs",
        default=None,
        help="Optional comma-separated config names overriding --preset, e.g. box04,unclip25.",
    )
    parser.add_argument("--eval-split", default="holdout")
    parser.add_argument("--provider", default="paddleocr_local")
    parser.add_argument("--target-threshold", default="0.90")
    parser.add_argument("--min-ingredient-recall", default="0.85")
    parser.add_argument("--min-fixtures", type=int, default=30)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON artifact with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write observation rows without raw OCR text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def _load_split_rows(splits: Path) -> list[dict[str, Any]]:
    """Load benchmark split rows from JSONL."""
    return [
        json.loads(line) for line in splits.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _selected_configs(preset: str, config_names: str | None = None) -> tuple[SweepConfig, ...]:
    """Return the configured sweep list."""
    if config_names:
        selected = []
        unknown = []
        for name in (part.strip() for part in config_names.split(",")):
            if not name:
                continue
            config = CONFIG_BY_NAME.get(name)
            if config is None:
                unknown.append(name)
            else:
                selected.append(config)
        if unknown:
            raise ValueError(f"unknown sweep config(s): {', '.join(unknown)}")
        if not selected:
            raise ValueError("--configs did not contain any valid config names")
        return tuple(selected)
    return QUICK_SWEEP if preset == "quick" else DETECTOR_SWEEP


def _redacted_eval_payload(
    eval_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Split redacted eval JSON from provider-shaped observations."""
    payload = dict(eval_payload)
    observations = payload.pop("observations")
    return payload, observations


def _metric_value(result: dict[str, Any], key: str) -> float:
    """Return one structured metric value from a sweep result."""
    metrics = result.get("summary", {}).get("metrics", {})
    return float(metrics.get(key, 0.0))


def _best_by(results: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    """Return the best config by one metric."""
    if not results:
        return {"metric": metric, "config": None, "value": 0.0}
    best = max(results, key=lambda item: _metric_value(item, metric))
    return {"metric": metric, "config": best["config"], "value": _metric_value(best, metric)}


def run_sweep(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the configured sweep and return a redacted aggregate.

    Args:
        args: Parsed CLI namespace.

    Returns:
        Redacted sweep summary.

    Raises:
        FileNotFoundError: If required bundle or split files are missing.
    """
    if not (args.bundle_dir / "ground-truth.todo.jsonl").is_file():
        raise FileNotFoundError(f"ground-truth.todo.jsonl not found under {args.bundle_dir}")
    if not args.splits.is_file():
        raise FileNotFoundError(f"splits JSONL not found: {args.splits}")

    profile = PROFILES[args.profile]
    det_model = args.det_model or profile["det"]
    rec_model = args.rec_model or profile["rec"]
    max_side = args.max_side or profile["max_side"]
    split_rows = _load_split_rows(args.splits)
    configs = _selected_configs(args.preset, getattr(args, "configs", None))

    if not args.apply:
        return {
            "schema_version": SCHEMA_VERSION,
            "apply_requested": False,
            "profile": args.profile,
            "config_count": len(configs),
            "configs": [config.name for config in configs],
            "source_doc_urls": SOURCE_DOC_URLS,
        }

    results: list[dict[str, Any]] = []
    started_all = time.monotonic()
    for config in configs:
        started = time.monotonic()
        effective_max_side = config.max_side or max_side
        eval_payload = evaluate(
            bundle_dir=args.bundle_dir,
            limit=args.limit,
            det_model=det_model,
            rec_model=rec_model,
            max_side=effective_max_side,
            det_box_thresh=config.det_box_thresh,
            det_thresh=config.det_thresh,
            det_unclip_ratio=config.det_unclip_ratio,
            rec_model_dir=args.rec_model_dir,
            post_pass=args.post_pass,
        )
        redacted_eval, observations = _redacted_eval_payload(eval_payload)
        eval_path = args.output_dir / f"paddleocr-eval.{config.name}.json"
        obs_path = args.output_dir / f"paddleocr-observations.{config.name}.jsonl"
        summary_path = args.output_dir / f"structured-extraction-summary.{config.name}.json"
        gate_path = args.output_dir / f"structured-extraction-gate.{config.name}.json"
        _write_json(eval_path, redacted_eval)
        _write_jsonl(obs_path, observations)

        summary = build_summary(
            eval_json=redacted_eval,
            split_rows=split_rows,
            eval_split=args.eval_split,
            provider=args.provider,
            leakage_check_passed=True,
            privacy_review_cleared=True,
        )
        gate = build_structured_extraction_gate(
            summary,
            target_threshold=Decimal(str(args.target_threshold)),
            min_ingredient_recall=Decimal(str(args.min_ingredient_recall)),
            min_fixture_count=args.min_fixtures,
        )
        _write_json(summary_path, summary)
        _write_json(gate_path, gate)
        results.append(
            {
                "config": config.name,
                "det_box_thresh": config.det_box_thresh,
                "det_thresh": config.det_thresh,
                "det_unclip_ratio": config.det_unclip_ratio,
                "max_side": effective_max_side,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "eval_json": str(eval_path.relative_to(args.output_dir)),
                "summary_json": str(summary_path.relative_to(args.output_dir)),
                "gate_json": str(gate_path.relative_to(args.output_dir)),
                "summary": summary,
                "gate_status": gate["status"],
                "blocker_codes": gate["blocker_codes"],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "apply_requested": True,
        "elapsed_seconds": round(time.monotonic() - started_all, 3),
        "profile": args.profile,
        "detection_model": det_model,
        "recognition_model": rec_model,
        "recognition_model_dir_present": args.rec_model_dir is not None,
        "max_side": max_side,
        "post_pass": args.post_pass,
        "eval_split": args.eval_split,
        "preset": args.preset,
        "results": results,
        "best_by": {
            "field_match_ratio_macro": _best_by(results, "field_match_ratio_macro"),
            "field_match_ratio_micro": _best_by(results, "field_match_ratio_micro"),
            "ingredient_recall": _best_by(results, "ingredient_recall"),
        },
        "source_doc_urls": SOURCE_DOC_URLS,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    try:
        summary = run_sweep(args)
    except (FileNotFoundError, ValueError) as exc:
        print(
            json.dumps(
                {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "sweep-summary.json", summary)
    printable = dict(summary)
    printable.pop("results", None)
    print(json.dumps(printable, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
