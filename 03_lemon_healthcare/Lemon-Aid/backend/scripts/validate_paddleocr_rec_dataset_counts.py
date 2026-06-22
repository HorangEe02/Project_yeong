"""Validate PaddleOCR recognition dataset counts without printing labels.

This script is a count-only hard gate for private teacher-labeled PaddleOCR
recognition datasets. It never emits label text, crop paths, or provider payloads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_EXPECTED_TRAIN_ROWS = 70_778
DEFAULT_EXPECTED_VAL_ROWS = 6_828
DEFAULT_EXPECTED_DICT_ROWS = 1_066

COUNT_TARGETS = {
    "train": Path("rec/rec_gt_train.txt"),
    "val": Path("rec/rec_gt_val.txt"),
    "dict": Path("dict.txt"),
}


class DatasetCountValidationError(RuntimeError):
    """Raised when the dataset count gate fails."""


def _line_count(path: Path) -> int:
    """Return the number of text lines in a UTF-8 file.

    Args:
        path: Text file path.

    Returns:
        Number of lines in the file.
    """
    count = 0
    with path.open(encoding="utf-8") as handle:
        for _line in handle:
            count += 1
    return count


def validate_paddleocr_rec_dataset_counts(
    *,
    dataset_dir: Path,
    expected_train_rows: int = DEFAULT_EXPECTED_TRAIN_ROWS,
    expected_val_rows: int = DEFAULT_EXPECTED_VAL_ROWS,
    expected_dict_rows: int = DEFAULT_EXPECTED_DICT_ROWS,
) -> dict[str, Any]:
    """Return a count-only PaddleOCR rec dataset validation summary.

    Args:
        dataset_dir: PaddleOCR recognition dataset root.
        expected_train_rows: Expected ``rec/rec_gt_train.txt`` line count.
        expected_val_rows: Expected ``rec/rec_gt_val.txt`` line count.
        expected_dict_rows: Expected ``dict.txt`` line count.

    Returns:
        Count-only summary that omits label text, crop paths, and absolute paths.

    Raises:
        DatasetCountValidationError: If any required file is missing or a count
            differs from the expected value.
    """
    expected = {
        "train": expected_train_rows,
        "val": expected_val_rows,
        "dict": expected_dict_rows,
    }
    actual: dict[str, int | None] = {}
    missing: list[str] = []
    for name, relative_path in COUNT_TARGETS.items():
        path = dataset_dir / relative_path
        if not path.is_file():
            actual[name] = None
            missing.append(name)
            continue
        actual[name] = _line_count(path)

    mismatches = {
        name: {"expected": expected[name], "actual": actual[name]}
        for name in expected
        if actual[name] != expected[name]
    }
    passed = not missing and not mismatches
    summary: dict[str, Any] = {
        "schema_version": "paddleocr-rec-dataset-count-gate-v1",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "missing_files": missing,
        "mismatches": mismatches,
        "dataset_path_printed": False,
        "label_text_printed": False,
        "crop_paths_printed": False,
        "raw_provider_payload_printed": False,
    }
    if not passed:
        raise DatasetCountValidationError(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument vector.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--expected-train-rows", default=DEFAULT_EXPECTED_TRAIN_ROWS, type=int)
    parser.add_argument("--expected-val-rows", default=DEFAULT_EXPECTED_VAL_ROWS, type=int)
    parser.add_argument("--expected-dict-rows", default=DEFAULT_EXPECTED_DICT_ROWS, type=int)
    parser.add_argument("--summary-output", default=None, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the count-only dataset gate.

    Args:
        argv: Optional argument vector.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = validate_paddleocr_rec_dataset_counts(
            dataset_dir=args.dataset_dir,
            expected_train_rows=args.expected_train_rows,
            expected_val_rows=args.expected_val_rows,
            expected_dict_rows=args.expected_dict_rows,
        )
    except DatasetCountValidationError as exc:
        summary = json.loads(str(exc))
        if args.summary_output is not None:
            args.summary_output.parent.mkdir(parents=True, exist_ok=True)
            args.summary_output.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    if args.summary_output is not None:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
