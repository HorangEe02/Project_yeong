"""Build a local-only bundle for supplement section YOLO bbox annotation.

The bundle wraps rows from ``export_supplement_yolo_annotation_template.py`` so
an operator can inspect materialized detail-page images and edit a copied JSONL
template with normalized section boxes. It also writes a lightweight Label
Studio-compatible task list for teams that prefer importing tasks into a local
annotation tool.

This script does not infer boxes, does not write final YOLO labels, does not
call OCR providers or LLMs, does not write to the database, and does not emit
local absolute paths, raw OCR text, provider payloads, product directory
literals, or image bytes.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import export_supplement_yolo_annotation_template as template_export  # noqa: E402

SCHEMA_VERSION = "supplement-yolo-annotation-review-bundle-v1"
EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION = template_export.ROW_SCHEMA_VERSION
HTML_INDEX_NAME = "annotation-index.html"
ANNOTATION_TEMPLATE_NAME = "annotation.todo.jsonl"
LABEL_STUDIO_TASKS_NAME = "label-studio-tasks.json"
README_NAME = "README.md"
SUMMARY_NAME = "summary.json"
SOURCE_DOC_URLS = template_export.SOURCE_DOC_URLS
SECTION_LABEL_GUIDE = {
    "product_identity": "Product name, brand, front label, or title block.",
    "supplement_facts": "The full Supplement Facts or Nutrition Facts panel.",
    "ingredient_amounts": "Ingredient rows, amounts, units, and daily-value table cells.",
    "intake_method": "Suggested use, directions, dosage schedule, or serving instructions.",
    "precautions": "Warnings, cautions, contraindications, or consult-doctor text.",
    "allergen_warning": "Allergy, allergen, intolerance, contains, or cross-contact warning text.",
    "other_ingredients": "Other ingredients, inactive ingredients, capsule shell, or additives.",
    "functional_claims": "Structure/function claims, benefits, marketing claim text, or certifications.",
}
BOX_SCHEMA_EXAMPLE = {
    "label": "supplement_facts",
    "x_center": 0.5,
    "y_center": 0.5,
    "width": 0.4,
    "height": 0.3,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a local-only annotation bundle and print a redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()
    try:
        summary = build_review_bundle(
            template_path=args.template,
            output_dir=output_dir,
            source_run_id=args.source_run_id,
            limit=args.limit,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            template_path=args.template,
            output_dir=output_dir,
            error=exc,
        )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / SUMMARY_NAME).write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def build_review_bundle(
    *,
    template_path: Path,
    output_dir: Path,
    source_run_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Build a local annotation bundle from materialized template rows.

    Args:
        template_path: YOLO annotation template JSONL.
        output_dir: Directory where bundle files are written.
        source_run_id: Optional operator run id.
        limit: Optional maximum number of reviewable rows.

    Returns:
        Redacted bundle summary.

    Raises:
        ValueError: If rows are malformed, unsafe, duplicated, or not
            materialized with safe relative image paths.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative.")
    template_path = template_path.expanduser().resolve()
    rows = _read_template_rows(template_path)
    review_rows, skip_reasons = _reviewable_rows(
        rows, source_base=template_path.parent, limit=limit
    )
    annotation_rows = [_annotation_template_row(row) for row in review_rows]
    label_studio_tasks = [
        _label_studio_task(row, index=index + 1) for index, row in enumerate(review_rows)
    ]
    html_text = _html_index(review_rows)
    readme_text = _readme_text()
    summary = _summary(
        template_path=template_path,
        source_run_id=source_run_id,
        template_row_count=len(rows),
        review_rows=review_rows,
        annotation_rows=annotation_rows,
        label_studio_tasks=label_studio_tasks,
        skip_reasons=skip_reasons,
        limit=limit,
    )
    payload = {
        "html": html_text,
        "readme": readme_text,
        "annotation_rows": annotation_rows,
        "label_studio_tasks": label_studio_tasks,
        "summary": summary,
    }
    template_export._reject_unsafe_payload(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    image_copied_count = _copy_annotation_images(
        review_rows,
        source_base=template_path.parent,
        output_dir=output_dir,
    )
    summary["image_copied_count"] = image_copied_count
    template_export._reject_unsafe_payload(summary)
    (output_dir / HTML_INDEX_NAME).write_text(html_text, encoding="utf-8")
    (output_dir / ANNOTATION_TEMPLATE_NAME).write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in annotation_rows
        ),
        encoding="utf-8",
    )
    (output_dir / LABEL_STUDIO_TASKS_NAME).write_text(
        json.dumps(label_studio_tasks, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / README_NAME).write_text(readme_text, encoding="utf-8")
    (output_dir / SUMMARY_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _read_template_rows(path: Path) -> list[dict[str, Any]]:
    """Read and validate annotation template JSONL rows.

    Args:
        path: Template JSONL path.

    Returns:
        Validated template rows.

    Raises:
        ValueError: If a row is unsafe, duplicated, or not an annotation row.
    """
    rows = template_export._read_jsonl(path)
    seen: set[str] = set()
    for row in rows:
        template_export._reject_unsafe_payload(row)
        if row.get("schema_version") != EXPECTED_TEMPLATE_ROW_SCHEMA_VERSION:
            raise ValueError("Supplement YOLO bundle requires annotation template rows.")
        fixture_id = template_export._safe_required_token(
            row.get("fixture_id"), field_name="fixture_id"
        )
        if fixture_id in seen:
            raise ValueError(f"Duplicate supplement YOLO template fixture_id: {fixture_id}")
        seen.add(fixture_id)
        if row.get("annotation_task_type") != "supplement_roi_box":
            raise ValueError("Supplement YOLO bundle only supports supplement_roi_box rows.")
        if row.get("annotation_status") != "pending_human_bbox_review":
            raise ValueError("Supplement YOLO bundle only accepts pending human bbox rows.")
        if row.get("training_export_performed") is not False:
            raise ValueError("Supplement YOLO review bundle cannot include exported training rows.")
    return rows


def _reviewable_rows(
    rows: list[dict[str, Any]],
    *,
    source_base: Path,
    limit: int | None,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Return rows that have materialized images ready for local annotation.

    Args:
        rows: Annotation template rows.
        source_base: Directory containing relative template image paths.
        limit: Optional maximum row count.

    Returns:
        Reviewable rows and skip reason counts.
    """
    review_rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    for row in rows:
        if limit is not None and len(review_rows) >= limit:
            skip_reasons["limit_reached"] += 1
            continue
        image_path = row.get("image_path")
        if not isinstance(image_path, str) or not image_path:
            skip_reasons["missing_materialized_image_path"] += 1
            continue
        _safe_relative_image_path(image_path)
        if not (source_base / image_path).is_file():
            skip_reasons["materialized_image_file_not_found"] += 1
            continue
        review_rows.append(row)
    return review_rows, skip_reasons


def _copy_annotation_images(
    rows: list[dict[str, Any]],
    *,
    source_base: Path,
    output_dir: Path,
) -> int:
    """Copy materialized annotation images into the bundle.

    Args:
        rows: Reviewable rows.
        source_base: Template base directory.
        output_dir: Bundle output directory.

    Returns:
        Number of copied or already-present images.
    """
    copied_count = 0
    for row in rows:
        image_path = _safe_relative_image_path(str(row.get("image_path")))
        source = (source_base / image_path).resolve()
        destination = (output_dir / image_path).resolve()
        if source == destination:
            copied_count += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied_count += 1
    return copied_count


def _annotation_template_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return an editable annotation row copied into the bundle.

    Args:
        row: Original annotation template row.

    Returns:
        JSON-safe row for operator edits.
    """
    copied = dict(row)
    copied["bundle_editing_instructions"] = [
        "fill label_snapshot.boxes with normalized xywh boxes using allowed_labels only",
        "box fields are label, x_center, y_center, width, height; every coordinate must be between 0 and 1",
        "draw multiple boxes when section blocks are visually separated",
        "set annotation_status=accepted_for_training only after human review",
        "set label_snapshot.training_export_allowed=true and label_snapshot.human_review_required=false only after review",
        "do not add raw OCR text, provider payloads, local paths, or product directory literals",
    ]
    copied["box_schema_example"] = dict(BOX_SCHEMA_EXAMPLE)
    copied["section_label_guide"] = {
        label: SECTION_LABEL_GUIDE[label] for label in _allowed_labels(row)
    }
    template_export._reject_unsafe_payload(copied)
    return copied


def _label_studio_task(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    """Return a lightweight local Label Studio task.

    Args:
        row: Reviewable annotation row.
        index: One-based task index.

    Returns:
        Label Studio-style task object.
    """
    image_path = _safe_relative_image_path(str(row.get("image_path")))
    fixture_id = template_export._safe_required_token(
        row.get("fixture_id"), field_name="fixture_id"
    )
    labels = _allowed_labels(row)
    task = {
        "id": index,
        "data": {
            "image": image_path,
            "fixture_id": fixture_id,
            "category_key": template_export._safe_required_token(
                row.get("category_key"),
                field_name="category_key",
            ),
        },
        "meta": {
            "annotation_task_type": "supplement_roi_box",
            "coordinate_space": "source_image",
            "allowed_labels": labels,
            "section_label_guide": {label: SECTION_LABEL_GUIDE[label] for label in labels},
            "export_contract": "normalized_xywh_after_operator_review",
            "box_schema_example": dict(BOX_SCHEMA_EXAMPLE),
        },
    }
    template_export._reject_unsafe_payload(task)
    return task


def _html_index(rows: list[dict[str, Any]]) -> str:
    """Return static local-only HTML for bbox annotation review.

    Args:
        rows: Reviewable annotation rows.

    Returns:
        HTML string.
    """
    cards = "\n".join(_html_card(row, index=index + 1) for index, row in enumerate(rows))
    labels = sorted({label for row in rows for label in _allowed_labels(row)})
    label_text = ", ".join(html.escape(label) for label in labels)
    label_guide = "\n".join(
        f"      <li><code>{html.escape(label)}</code>: {html.escape(SECTION_LABEL_GUIDE[label])}</li>"
        for label in labels
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Supplement YOLO Section Annotation</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f6f7f9; color: #17202a; }}
    header {{ max-width: 1080px; margin: 0 auto 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; max-width: 1280px; margin: 0 auto; }}
    article {{ background: white; border: 1px solid #dde2e8; border-radius: 8px; padding: 14px; }}
    img {{ width: 100%; max-height: 520px; object-fit: contain; background: #111; border-radius: 6px; }}
    code {{ word-break: break-all; }}
    .meta {{ color: #52606d; font-size: 13px; line-height: 1.5; }}
    .labels {{ color: #233; font-size: 13px; }}
    .guide {{ max-width: 1080px; margin: 12px auto 24px; padding: 16px; background: #fff; border: 1px solid #dde2e8; border-radius: 8px; }}
    .guide li {{ margin: 4px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>Supplement Section YOLO Annotation Bundle</h1>
    <p>Edit <code>{html.escape(ANNOTATION_TEMPLATE_NAME)}</code> after drawing boxes. Final YOLO labels are generated only after accepted rows pass the promotion/materialization scripts.</p>
    <p class="labels">Allowed labels: {label_text}</p>
  </header>
  <section class="guide">
    <h2>Box Format</h2>
    <p>Use normalized source-image <code>xywh</code>: <code>{{"label":"supplement_facts","x_center":0.5,"y_center":0.5,"width":0.4,"height":0.3}}</code>. Draw multiple boxes when one section is split across separated regions.</p>
    <h2>Section Guide</h2>
    <ul>
{label_guide}
    </ul>
  </section>
  <main class="grid">
{cards}
  </main>
</body>
</html>
"""


def _html_card(row: dict[str, Any], *, index: int) -> str:
    """Return one HTML annotation card.

    Args:
        row: Reviewable annotation row.
        index: One-based display index.

    Returns:
        HTML card.
    """
    image_path = _safe_relative_image_path(str(row.get("image_path")))
    fixture_id = template_export._safe_required_token(
        row.get("fixture_id"), field_name="fixture_id"
    )
    category_key = template_export._safe_required_token(
        row.get("category_key"), field_name="category_key"
    )
    labels = ", ".join(html.escape(label) for label in _allowed_labels(row))
    return f"""    <article>
      <h2>{index}. <code>{html.escape(fixture_id)}</code></h2>
      <img src="{html.escape(image_path)}" alt="detail page image for {html.escape(fixture_id)}">
      <p class="meta">category: <code>{html.escape(category_key)}</code><br>coordinate space: source_image<br>box format: normalized xywh</p>
      <p class="labels">{labels}</p>
    </article>"""


def _readme_text() -> str:
    """Return annotation bundle instructions.

    Returns:
        Markdown instructions.
    """
    return """# Supplement YOLO Section Annotation Bundle

Open `annotation-index.html` locally to inspect materialized detail-page images.

Annotate section boxes for supplement label regions only:
`product_identity`, `supplement_facts`, `ingredient_amounts`, `intake_method`,
`precautions`, `allergen_warning`, `other_ingredients`, `functional_claims`.

Use normalized `xywh` values in source-image coordinate space:

```json
{"label":"supplement_facts","x_center":0.5,"y_center":0.5,"width":0.4,"height":0.3}
```

All coordinate values must be between 0 and 1. Draw multiple boxes when a
section is visually split across separated regions.

## Section Guide

- `product_identity`: Product name, brand, front label, or title block.
- `supplement_facts`: The full Supplement Facts or Nutrition Facts panel.
- `ingredient_amounts`: Ingredient rows, amounts, units, and daily-value table cells.
- `intake_method`: Suggested use, directions, dosage schedule, or serving instructions.
- `precautions`: Warnings, cautions, contraindications, or consult-doctor text.
- `allergen_warning`: Allergy, allergen, intolerance, contains, or cross-contact warning text.
- `other_ingredients`: Other ingredients, inactive ingredients, capsule shell, or additives.
- `functional_claims`: Structure/function claims, benefits, marketing claim text, or certifications.

Do not copy raw OCR text, provider payloads, local paths, product folder names,
or image bytes into `annotation.todo.jsonl`.

After human review, accepted rows can be passed to
`promote_supplement_yolo_annotation_template.py`, then
`materialize_supplement_section_yolo_dataset.py`.
"""


def _summary(
    *,
    template_path: Path,
    source_run_id: str | None,
    template_row_count: int,
    review_rows: list[dict[str, Any]],
    annotation_rows: list[dict[str, Any]],
    label_studio_tasks: list[dict[str, Any]],
    skip_reasons: Counter[str],
    limit: int | None,
) -> dict[str, Any]:
    """Return a redacted bundle summary.

    Args:
        template_path: Source annotation template.
        source_run_id: Optional operator run id.
        template_row_count: Input row count.
        review_rows: Rows included in the bundle.
        annotation_rows: Editable annotation rows.
        label_studio_tasks: Local task objects.
        skip_reasons: Skip reason counts.
        limit: Optional row limit.

    Returns:
        Summary dictionary.
    """
    category_counts = Counter(str(row["category_key"]) for row in review_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "template_name": template_path.name,
        "template_hash": _sha256_text(str(template_path.expanduser())),
        "template_row_count": template_row_count,
        "reviewable_row_count": len(review_rows),
        "annotation_template_row_count": len(annotation_rows),
        "label_studio_task_count": len(label_studio_tasks),
        "category_counts": dict(sorted(category_counts.items())),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "limit": limit,
        "html_index_name": HTML_INDEX_NAME,
        "annotation_template_name": ANNOTATION_TEMPLATE_NAME,
        "label_studio_tasks_name": LABEL_STUDIO_TASKS_NAME,
        "readme_name": README_NAME,
        "image_path_style": "relative_private_hashed_fixture_copy",
        "required_human_review_count": len(review_rows),
        "training_export_allowed_rows": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _allowed_labels(row: dict[str, Any]) -> list[str]:
    """Return validated allowed label names.

    Args:
        row: Annotation template row.

    Returns:
        Allowed labels.

    Raises:
        ValueError: If labels are missing or unsafe.
    """
    labels = row.get("allowed_labels")
    if not isinstance(labels, list) or not labels:
        raise ValueError("Supplement YOLO template rows require allowed_labels.")
    safe_labels = [
        template_export._safe_required_token(label, field_name="allowed_label") for label in labels
    ]
    expected = set(template_export.SUPPLEMENT_SECTION_CLASS_NAMES)
    if set(safe_labels) - expected:
        raise ValueError("Supplement YOLO template row contains unknown allowed label.")
    return safe_labels


def _safe_relative_image_path(value: str) -> str:
    """Validate and return a safe relative image path.

    Args:
        value: Candidate image path.

    Returns:
        Validated relative path.

    Raises:
        ValueError: If the path is absolute or traversing.
    """
    if value.startswith("/") or value.startswith("\\") or "://" in value:
        raise ValueError("Supplement YOLO review bundle requires relative image paths.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Supplement YOLO review bundle image paths must be safe relative paths.")
    return value


def _failure_summary(
    *,
    template_path: Path,
    output_dir: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        template_path: Source template path.
        output_dir: Planned bundle directory.
        error: Raised exception.

    Returns:
        JSON-safe failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "template_name": template_path.name,
        "template_hash": _sha256_text(str(template_path.expanduser())),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "Supplement YOLO annotation review bundle build failed.",
        "reviewable_row_count": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for text.

    Args:
        value: Text to hash.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
