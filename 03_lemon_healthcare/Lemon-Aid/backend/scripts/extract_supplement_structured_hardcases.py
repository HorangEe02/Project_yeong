"""Extract structured OCR hard-case fixture ids from a redacted eval artifact.

The input is the redacted ``paddleocr_clova_eval`` JSON that contains
``per_image`` numeric counts only. This tool does not read images, provider
payloads, raw OCR text, or private absolute paths.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-structured-hardcase-fixtures-v1"
FIELD_HALF_THRESHOLD = 0.5


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object, accepting UTF-8 BOM artifacts from Windows.

    Args:
        path: JSON path.

    Returns:
        Parsed JSON object.
    """
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_split_rows(path: Path | None) -> dict[str, str]:
    """Read optional fixture split assignments.

    Args:
        path: Optional JSONL split file.

    Returns:
        Mapping of fixture id to split name.
    """
    if path is None:
        return {}
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        fixture_id = row.get("fixture_id")
        split = row.get("split")
        if isinstance(fixture_id, str) and isinstance(split, str):
            rows[fixture_id] = split
    return rows


def _fixture_id(row: dict[str, Any]) -> str:
    """Return a bounded fixture id from one per-image row.

    Args:
        row: One ``per_image`` row.

    Returns:
        Fixture id string.

    Raises:
        ValueError: If the row does not contain a fixture id.
    """
    value = row.get("fixture_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("per_image row missing fixture_id")
    return value.strip()


def extract_hardcases(
    *,
    eval_json: dict[str, Any],
    split_by_fixture: dict[str, str] | None = None,
    eval_split: str | None = None,
) -> dict[str, Any]:
    """Extract hard-case fixture id lists from redacted per-image metrics.

    Args:
        eval_json: Redacted PaddleOCR eval JSON.
        split_by_fixture: Optional fixture id to split mapping.
        eval_split: Optional split filter.

    Returns:
        Redacted hard-case manifest.
    """
    split_by_fixture = split_by_fixture or {}
    rows = []
    for row in eval_json.get("per_image") or []:
        fixture_id = _fixture_id(row)
        if eval_split is not None and split_by_fixture.get(fixture_id) != eval_split:
            continue
        rows.append(row)

    field_zero: list[str] = []
    field_lt50: list[str] = []
    ingredient_all_missed: list[str] = []
    for row in rows:
        fixture_id = _fixture_id(row)
        field_ratio = float(row.get("field_match_ratio", 0.0))
        ingredient_total = int(row.get("ingredient_total", 0))
        ingredient_found = int(row.get("ingredient_found", 0))
        if field_ratio == 0.0:
            field_zero.append(fixture_id)
        if field_ratio < FIELD_HALF_THRESHOLD:
            field_lt50.append(fixture_id)
        if ingredient_total > 0 and ingredient_found == 0:
            ingredient_all_missed.append(fixture_id)

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": eval_json.get("schema_version"),
        "eval_split": eval_split,
        "fixture_count": len(rows),
        "counts": {
            "field_zero": len(field_zero),
            "field_lt50": len(field_lt50),
            "ingredient_all_missed": len(ingredient_all_missed),
        },
        "fixture_ids": {
            "field_zero": field_zero,
            "field_lt50": field_lt50,
            "ingredient_all_missed": ingredient_all_missed,
            "union_field_zero_or_ingredient_all_missed": sorted(
                set(field_zero) | set(ingredient_all_missed)
            ),
        },
        "raw_ocr_text_stored": False,
        "provider_payload_stored": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-json", required=True, type=Path)
    parser.add_argument("--splits", type=Path, default=None)
    parser.add_argument("--eval-split", default=None)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    summary = extract_hardcases(
        eval_json=_read_json(args.eval_json),
        split_by_fixture=_read_split_rows(args.splits),
        eval_split=args.eval_split,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
