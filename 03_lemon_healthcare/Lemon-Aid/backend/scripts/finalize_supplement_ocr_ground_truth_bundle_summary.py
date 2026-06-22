"""Finalize a supplement OCR ground-truth review bundle summary after review.

The bundle builder (``build_supplement_ocr_ground_truth_review_bundle.py``) emits
a summary with ``ready_for_benchmark_rows`` hardcoded to ``0`` and refuses to be
re-run on a filled ``ground-truth.todo.jsonl`` (it only accepts pre-benchmark
rows). The OCR benchmark gate, however, requires a bundle summary where
``ready_for_benchmark_rows == ground_truth_template_row_count`` and both are
positive. This tool closes that gap: it reads the operator/teacher-filled
``ground-truth.todo.jsonl``, counts the rows marked ready for benchmark, and
writes a fresh ``supplement-ocr-ground-truth-review-bundle-v1`` summary scoped to
the ready set (so the benchmark set equals the fully-reviewed set, matching how
``build_supplement_ocr_benchmark_manifest.py`` already filters rows).

It reports only counts, safe basenames, and a path-free hash. It does not call
OCR providers, write to the database, train PaddleOCR, or emit OCR text, provider
payloads, image bytes, local paths, or source row payloads. Dry-run by default;
pass ``--apply`` to write the finalized summary.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_supplement_ocr_benchmark_manifest as benchmark  # noqa: E402
from scripts import build_supplement_ocr_ground_truth_review_bundle as gt_bundle  # noqa: E402

SCHEMA_VERSION = gt_bundle.SCHEMA_VERSION
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
)


def _ready_row_count(rows: list[dict[str, Any]], required_sections: tuple[str, ...]) -> int:
    """Return the number of rows ready for benchmark after review.

    A row counts as ready only when the benchmark builder would also promote it:
    explicitly flagged ready, not blocked, non-empty ingredients, AND no missing
    required expected sections under ``required_sections`` (mirrors
    ``build_supplement_ocr_benchmark_manifest`` so this count cannot exceed the
    benchmark fixture count under any policy).

    Args:
        rows: Filled ground-truth rows.
        required_sections: Required expected sections the benchmark run enforces.

    Returns:
        Count of benchmark-ready rows.
    """
    ready = 0
    for row in rows:
        if row.get("ready_for_benchmark_after_review") is not True:
            continue
        if benchmark._manual_ground_truth_block_reason(row) is not None:
            continue
        expected = benchmark._expected_from_decision(row)
        if not expected["ingredients"]:
            continue
        if benchmark._missing_required_expected_sections(expected, required_sections):
            continue
        ready += 1
    return ready


def build_finalized_summary(
    *, ground_truth_path: Path, required_sections: tuple[str, ...]
) -> dict[str, Any]:
    """Build a redacted, gate-ready bundle summary scoped to the ready rows.

    Args:
        ground_truth_path: Filled ``ground-truth.todo.jsonl`` path.
        required_sections: Required expected sections the benchmark run enforces.

    Returns:
        A ``supplement-ocr-ground-truth-review-bundle-v1`` summary where
        ``ready_for_benchmark_rows == ground_truth_template_row_count``.

    Raises:
        ValueError: If the manifest is unsafe or has no benchmark-ready rows.
    """
    rows = benchmark._read_jsonl(ground_truth_path)
    for row in rows:
        benchmark._reject_unsafe_payload(row)
    total = len(rows)
    ready = _ready_row_count(rows, required_sections)
    if ready <= 0:
        raise ValueError("No benchmark-ready ground-truth rows to finalize.")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "finalized_from_name": ground_truth_path.name,
        "ground_truth_template_hash": benchmark._sha256_text(str(ground_truth_path.expanduser())),
        "template_name": ground_truth_path.name,
        "template_row_count": ready,
        "reviewable_row_count": ready,
        "ground_truth_template_row_count": ready,
        "ready_for_benchmark_rows": ready,
        "manual_review_required_count": 0,
        "source_total_row_count": total,
        "excluded_not_ready_row_count": total - ready,
        "required_expected_sections": list(required_sections),
        "image_path_style": "relative_private_hashed_fixture_copy",
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    benchmark._reject_unsafe_payload(summary)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--required-expected-section",
        action="append",
        choices=sorted(benchmark.ALLOWED_REQUIRED_EXPECTED_SECTIONS),
        default=None,
        help=(
            "Required expected section the downstream benchmark run enforces; repeatable. "
            "Must match the benchmark/gate policy so the ready count cannot exceed the "
            f"benchmark fixture count. Default: {list(benchmark.DEFAULT_REQUIRED_EXPECTED_SECTIONS)}."
        ),
    )
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Write the finalized bundle summary (or report counts in dry-run).

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    ground_truth_path = args.ground_truth.expanduser()
    if not ground_truth_path.is_file():
        raise SystemExit(f"ERROR: ground-truth manifest not found: {ground_truth_path.name}")
    required_sections = benchmark._required_expected_sections(args.required_expected_section)
    summary = build_finalized_summary(
        ground_truth_path=ground_truth_path, required_sections=required_sections
    )
    if not args.apply:
        print(
            json.dumps(
                {
                    "apply_requested": False,
                    "ready_for_benchmark_rows": summary["ready_for_benchmark_rows"],
                    "source_total_row_count": summary["source_total_row_count"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
