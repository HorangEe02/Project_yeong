"""Convert Label Studio rectangle exports into the YOLO section annotation JSONL.

The operator draws section bounding boxes in Label Studio (imported from the
bundle's ``label-studio-tasks.json``), exports the result, and this tool merges
those boxes onto the human-annotation template rows so the existing pipeline
(``extract_supplement_yolo_reviewed_annotations`` -> ``preflight_supplement_yolo_annotation_decisions``
-> ``promote_supplement_yolo_annotation_template``) can consume them.

Label Studio rectangle coordinates are percentages (0-100) of the image with the
origin at the top-left corner; the pipeline stores normalized centre ``xywh`` in
[0, 1] source-image space. This tool performs that conversion and validates that
every label is in the row's ``allowed_labels``.

Rows that receive at least one box are marked ``accepted_for_training``
(``training_export_allowed=true``, ``human_review_required=false``). Template rows
without any exported box are left untouched (still pending) so the strict
preflight keeps blocking until every row is annotated. No raw OCR text, provider
payloads, or local paths are copied — only labels and normalized coordinates.

Dry-run by default; pass ``--apply`` to write. Supports both the Label Studio
full export (tasks with ``annotations[].result[]``) and the JSON-MIN export.

References:
    https://labelstud.io/guide/export.html
    https://docs.ultralytics.com/datasets/detect/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

COORD_EPSILON = 1e-6


def _normalized_box(raw: dict[str, Any], allowed_labels: set[str]) -> dict[str, float | str]:
    """Convert one Label Studio rectangle into a normalized centre-xywh box.

    Args:
        raw: Label Studio rectangle ``value`` (x, y, width, height in percent plus
            a ``rectanglelabels`` list).
        allowed_labels: Labels permitted for this row.

    Returns:
        A box dict with ``label`` and normalized ``x_center``/``y_center``/``width``/
        ``height`` in [0, 1].

    Raises:
        ValueError: If the label is missing/unsupported or coordinates fall outside
            the valid range.
    """
    labels = raw.get("rectanglelabels") or raw.get("labels") or []
    if not labels:
        raise ValueError("Label Studio rectangle has no label.")
    label = str(labels[0])
    if label not in allowed_labels:
        raise ValueError(f"unsupported section label {label!r}; allowed: {sorted(allowed_labels)}")
    try:
        x = float(raw["x"]) / 100.0
        y = float(raw["y"]) / 100.0
        width = float(raw["width"]) / 100.0
        height = float(raw["height"]) / 100.0
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid rectangle geometry: {exc}") from exc
    x_center = x + width / 2.0
    y_center = y + height / 2.0
    for name, value in (
        ("x_center", x_center),
        ("y_center", y_center),
        ("width", width),
        ("height", height),
    ):
        if not (-COORD_EPSILON <= value <= 1.0 + COORD_EPSILON):
            raise ValueError(f"{name}={value} outside the normalized [0, 1] range")
    return {
        "label": label,
        "x_center": round(min(max(x_center, 0.0), 1.0), 6),
        "y_center": round(min(max(y_center, 0.0), 1.0), 6),
        "width": round(min(max(width, 0.0), 1.0), 6),
        "height": round(min(max(height, 0.0), 1.0), 6),
    }


def _iter_export_records(export: Any) -> list[dict[str, Any]]:
    """Return Label Studio task records from a full or JSON-MIN export.

    Args:
        export: Parsed Label Studio export (a list of task objects).

    Returns:
        List of task records.

    Raises:
        ValueError: If the export is not a list of objects.
    """
    if not isinstance(export, list):
        raise ValueError("Label Studio export must be a JSON array of tasks.")
    return [record for record in export if isinstance(record, dict)]


def _fixture_id(record: dict[str, Any]) -> str | None:
    """Return the fixture id from a Label Studio task record (full or JSON-MIN)."""
    data = record.get("data")
    if isinstance(data, dict) and data.get("fixture_id"):
        return str(data["fixture_id"])
    if record.get("fixture_id"):
        return str(record["fixture_id"])
    return None


def _record_rectangles(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the rectangle ``value`` dicts for a task (full or JSON-MIN export).

    Args:
        record: A Label Studio task record.

    Returns:
        Rectangle value dicts (percent coordinates + labels).
    """
    rectangles: list[dict[str, Any]] = []
    annotations = record.get("annotations")
    if isinstance(annotations, list):
        for annotation in annotations:
            for item in annotation.get("result", []) if isinstance(annotation, dict) else []:
                if isinstance(item, dict) and str(item.get("type", "")).startswith("rectangle"):
                    value = item.get("value")
                    if isinstance(value, dict):
                        rectangles.append(value)
    # JSON-MIN export keeps rectangles under a result key (often the from_name).
    for key, value in record.items():
        if key in {"data", "annotations", "id", "fixture_id", "image"}:
            continue
        if isinstance(value, list):
            rectangles.extend(item for item in value if isinstance(item, dict) and "x" in item)
    return rectangles


def convert(
    *, export_path: Path, template_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge Label Studio boxes onto the annotation template rows.

    Args:
        export_path: Label Studio export JSON path.
        template_path: Annotation template JSONL (rows keyed by ``fixture_id``).

    Returns:
        ``(rows, summary)`` where ``rows`` is the merged template and ``summary`` is
        a count-only report.

    Raises:
        ValueError: If a box is invalid or references an unknown fixture id.
    """
    export = json.loads(export_path.read_text(encoding="utf-8"))
    boxes_by_fixture: dict[str, list[dict[str, Any]]] = {}
    for record in _iter_export_records(export):
        fixture_id = _fixture_id(record)
        if fixture_id is None:
            continue
        boxes_by_fixture.setdefault(fixture_id, []).extend(_record_rectangles(record))

    rows: list[dict[str, Any]] = []
    annotated = 0
    box_total = 0
    template_ids: set[str] = set()
    with template_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            text = raw_line.strip()
            if not text:
                continue
            row = json.loads(text)
            fixture_id = str(row.get("fixture_id", ""))
            template_ids.add(fixture_id)
            rectangles = boxes_by_fixture.get(fixture_id, [])
            if rectangles:
                allowed = set(row.get("allowed_labels", []))
                boxes = [_normalized_box(rectangle, allowed) for rectangle in rectangles]
                snapshot = dict(row.get("label_snapshot", {}))
                snapshot.update(
                    boxes=boxes,
                    training_export_allowed=True,
                    human_review_required=False,
                    text_stored=False,
                )
                row["label_snapshot"] = snapshot
                row["annotation_status"] = "accepted_for_training"
                annotated += 1
                box_total += len(boxes)
            rows.append(row)

    unmatched = sorted(set(boxes_by_fixture) - template_ids)
    if unmatched:
        raise ValueError(f"Label Studio export references unknown fixture_id: {unmatched[0]}")
    summary = {
        "template_rows": len(rows),
        "annotated_rows": annotated,
        "pending_rows": len(rows) - annotated,
        "total_boxes": box_total,
        "fixtures_in_export": len(boxes_by_fixture),
    }
    return rows, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label-studio-export", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows, summary = convert(export_path=args.label_studio_export, template_path=args.template)
    summary["apply_requested"] = bool(args.apply)
    if args.apply:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        summary["output"] = str(args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
