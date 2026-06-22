"""Build redacted operator workpack files for supplement review batches.

The workpack connects three already-safe artifacts:

1. the redacted batch plan,
2. the redacted batch-file export summary,
3. each redacted source review-bundle summary,
4. optional redacted contact-sheet summaries for visual review context.

It writes one Markdown guide per batch plus a global index. It does not inspect
image files, OCR text, provider payloads, source rows, or database records.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from scripts import (  # noqa: E402
    export_supplement_operator_review_batch_files as batch_exporter,
)

SCHEMA_VERSION = "supplement-operator-review-workpack-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-operator-review-workpack-markdown-v1"
BATCH_PLAN_SCHEMA = "supplement-operator-review-batch-plan-v1"
BATCH_EXPORT_SCHEMA = "supplement-operator-review-batch-file-export-v1"
BRAND_BUNDLE_SCHEMA = "supplement-brand-review-bundle-v1"
PII_BUNDLE_SCHEMA = "supplement-review-pii-screening-review-bundle-v1"
YOLO_BUNDLE_SCHEMA = "supplement-yolo-annotation-review-bundle-v1"
BRAND_CONTACT_SHEET_SCHEMA = "supplement-brand-detail-contact-sheet-v1"
WORKPACK_INDEX_NAME = "index.md"
BRAND_CONTACT_SHEET_HTML_NAME = "brand-detail-contact-sheet.html"
BRAND_CONTACT_SHEET_README_NAME = "README.md"
BRAND_CONTACT_SHEET_SUMMARY_NAME = "brand-detail-contact-sheet.summary.json"
BRAND_CONTACT_SHEET_FILE_NAMES = (
    BRAND_CONTACT_SHEET_HTML_NAME,
    BRAND_CONTACT_SHEET_README_NAME,
    BRAND_CONTACT_SHEET_SUMMARY_NAME,
)
BUNDLE_INPUTS = {
    "brand_product_review": {
        "input_key": "brand_bundle_summary",
        "schema": BRAND_BUNDLE_SCHEMA,
        "optional_files": ("html_index_name", "readme_name", "csv_name"),
        "primary_editable_field": "decision_template_name",
    },
    "review_pii_screening": {
        "input_key": "pii_bundle_summary",
        "schema": PII_BUNDLE_SCHEMA,
        "optional_files": ("html_index_name", "readme_name"),
        "primary_editable_field": "decision_template_name",
    },
    "yolo_section_annotation": {
        "input_key": "yolo_bundle_summary",
        "schema": YOLO_BUNDLE_SCHEMA,
        "optional_files": ("html_index_name", "readme_name", "label_studio_tasks_name"),
        "primary_editable_field": "annotation_template_name",
    },
}
QUEUE_GUIDES = {
    "brand_product_review": (
        "브랜드 및 제품명 검수 batch입니다.",
        "review index 또는 CSV를 보고 manufacturer와 product가 라벨 또는 안전한 catalog 근거로 확인되는지 판단합니다.",
        "제품 폴더 literal을 manufacturer로 그대로 쓰지 않습니다.",
    ),
    "review_pii_screening": (
        "review 이미지 PII screening batch입니다.",
        "검수용 이미지만 보고 개인 정보 노출 여부를 판정합니다.",
        "텍스트 원문이나 보이는 개인 정보를 notes에 복사하지 않습니다.",
    ),
    "yolo_section_annotation": (
        "상세 페이지 section bbox annotation batch입니다.",
        "allowed label만 사용해 원본 이미지 기준 normalized xywh bbox를 채웁니다.",
        "OCR 원문, provider payload, 로컬 경로는 label snapshot에 저장하지 않습니다.",
    ),
}
QUEUE_DECISION_GUIDES = {
    "brand_product_review": {
        "decision_object": "brand_review_decision",
        "allowed_decisions": (
            "approve",
            "reject",
            "needs_review",
            "not_a_brand",
        ),
        "required_approval_fields": (
            "reviewer_id_operator_prefix",
            "reviewed_at_safe_token",
            "reviewed_manufacturer",
            "reviewed_product_name",
            "reason_codes",
        ),
        "required_approval_attestations": (
            "attest_brand_product_review_completed",
            "attest_not_using_product_folder_literal_as_manufacturer",
            "attest_product_name_reviewed_from_label_or_safe_catalog",
            "attest_no_raw_ocr_or_provider_payload_copied",
            "attest_db_import_allowed",
        ),
        "allowed_reason_codes": (
            "reviewed_label_or_catalog",
            "not_brand",
            "unclear_brand",
            "duplicate_product",
            "needs_catalog_lookup",
            "unsafe_text",
            "category_mismatch",
            "low_confidence_folder_name",
        ),
        "invalid_if": (
            "free_text_notes_present",
            "local_path_or_url_literal_present",
            "raw_ocr_or_provider_payload_copied",
            "folder_literal_used_without_review",
        ),
    },
    "review_pii_screening": {
        "decision_object": "pii_screening_decision",
        "allowed_decisions": (
            "cleared_no_personal_data",
            "contains_personal_data",
            "needs_review",
        ),
        "required_approval_fields": (
            "reviewer_id_operator_prefix",
            "reviewed_at_safe_token",
            "reason_codes",
        ),
        "required_approval_attestations": (
            "attest_local_screening_completed",
            "attest_no_personal_data_visible",
            "attest_no_raw_text_copied",
            "attest_teacher_ocr_transfer_allowed",
        ),
        "allowed_reason_codes": (
            "no_personal_data_visible",
            "face_or_person_visible",
            "contact_or_address_visible",
            "account_or_identifier_visible",
            "unclear_image",
        ),
        "invalid_if": (
            "visible_text_copied_into_notes",
            "local_path_or_url_literal_present",
            "raw_ocr_or_provider_payload_copied",
        ),
    },
    "yolo_section_annotation": {
        "decision_object": "label_snapshot",
        "allowed_decisions": (
            "accepted_annotation",
            "needs_annotation",
            "skip_unusable_image",
        ),
        "required_approval_fields": (
            "supported_section_labels_only",
            "normalized_xywh_boxes",
            "training_export_allowed_after_review",
        ),
        "required_approval_attestations": (
            "boxes_checked_against_image",
            "labels_checked_against_allowed_taxonomy",
            "no_raw_ocr_or_provider_payload_copied",
        ),
        "allowed_reason_codes": (
            "supplement_facts",
            "ingredient_amounts",
            "intake_method",
            "precautions",
            "allergen_warning",
            "other_ingredients",
            "product_identity",
        ),
        "invalid_if": (
            "unsupported_label_present",
            "box_coordinates_outside_normalized_range",
            "relative_or_absolute_local_path_leaked",
        ),
    },
}
QUEUE_COMPLETION_RULES = {
    "brand_product_review": (
        "Batch JSONL을 검수합니다.",
        "Reconcile 도구로 queue-level copy를 생성합니다.",
        "reviewed-only extract를 실행해 blank stub이 섞인 전체 queue와 부분 manifest preview 입력을 분리합니다.",
        "Batch progress preflight와 brand decision preflight를 다시 실행합니다.",
        "strict preflight 통과 전에는 product DB import manifest나 DB apply를 진행하지 않습니다.",
    ),
    "review_pii_screening": (
        "Batch JSONL을 검수합니다.",
        "Reconcile 도구로 queue-level copy를 생성합니다.",
        "reviewed-only extract를 실행해 blank stub이 섞인 전체 queue와 부분 teacher OCR preview 입력을 분리합니다.",
        "Batch progress preflight와 PII decision preflight를 다시 실행합니다.",
        "PII strict preflight 통과 전에는 teacher OCR transfer나 benchmark manifest 생성을 진행하지 않습니다.",
    ),
    "yolo_section_annotation": (
        "Batch JSONL을 검수합니다.",
        "Reconcile 도구로 queue-level copy를 생성합니다.",
        "reviewed-only extract를 실행해 blank stub이 섞인 전체 queue와 부분 YOLO dataset preview 입력을 분리합니다.",
        "Batch progress preflight와 YOLO annotation preflight를 다시 실행합니다.",
        "YOLO annotation preflight 통과 전에는 dataset promotion이나 training export를 진행하지 않습니다.",
    ),
}


class WorkpackError(ValueError):
    """Raised when workpack input or output cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-plan", type=Path, required=True)
    parser.add_argument("--batch-export-summary", type=Path, required=True)
    parser.add_argument("--brand-bundle-summary", type=Path, default=None)
    parser.add_argument("--pii-bundle-summary", type=Path, default=None)
    parser.add_argument("--yolo-bundle-summary", type=Path, default=None)
    parser.add_argument(
        "--brand-contact-sheet-summary",
        type=Path,
        action="append",
        default=[],
        help=(
            "Optional redacted brand detail contact-sheet summary. Repeat for "
            "multiple brand review batches."
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write operator workpack Markdown files and redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "batch_plan": args.batch_plan.expanduser().resolve(),
        "batch_export_summary": args.batch_export_summary.expanduser().resolve(),
    }
    optional_inputs = {
        "brand_bundle_summary": args.brand_bundle_summary,
        "pii_bundle_summary": args.pii_bundle_summary,
        "yolo_bundle_summary": args.yolo_bundle_summary,
    }
    for key, value in optional_inputs.items():
        if value is not None:
            input_paths[key] = value.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    summary_output = (
        args.summary_output.expanduser().resolve()
        if args.summary_output is not None
        else output_dir / "summary.json"
    )
    contact_sheet_summary_paths = [
        path.expanduser().resolve() for path in args.brand_contact_sheet_summary
    ]
    try:
        summary = build_operator_review_workpack(
            input_paths=input_paths,
            output_dir=output_dir,
            brand_contact_sheet_summary_paths=contact_sheet_summary_paths,
        )
        _write_json(summary_output, summary)
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, WorkpackError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_dir=output_dir, error=exc)
        _write_json(summary_output, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_operator_review_workpack(
    *,
    input_paths: Mapping[str, Path],
    output_dir: Path,
    brand_contact_sheet_summary_paths: Sequence[Path] = (),
) -> dict[str, Any]:
    """Build batch-level operator Markdown guides.

    Args:
        input_paths: Redacted input artifact paths.
        output_dir: Destination directory.
        brand_contact_sheet_summary_paths: Optional redacted contact-sheet
            summaries keyed by their batch review CSV.

    Returns:
        Redacted workpack summary.
    """
    plan = _load_json_object(_required_input(input_paths, "batch_plan"))
    _require_schema(plan, BATCH_PLAN_SCHEMA)
    export_summary = _load_json_object(_required_input(input_paths, "batch_export_summary"))
    _require_schema(export_summary, BATCH_EXPORT_SCHEMA)
    bundle_summaries = _load_bundle_summaries(input_paths)
    brand_contact_sheets_by_review_csv = _load_brand_contact_sheet_summaries(
        brand_contact_sheet_summary_paths
    )
    plan_batches = _batch_rows(plan)
    export_rows = _export_rows(export_summary)
    export_by_batch = _export_rows_by_batch(export_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    workpack_rows = []
    for batch in plan_batches:
        row = _write_batch_workpack(
            batch=batch,
            export_by_batch=export_by_batch,
            bundle_summaries=bundle_summaries,
            brand_contact_sheets_by_review_csv=brand_contact_sheets_by_review_csv,
            output_dir=output_dir,
        )
        workpack_rows.append(row)
    index_markdown = _build_index_markdown(workpack_rows=workpack_rows, plan=plan)
    (output_dir / WORKPACK_INDEX_NAME).write_text(index_markdown, encoding="utf-8")
    queue_workpack_counts: dict[str, int] = {}
    for row in workpack_rows:
        queue_key = str(row["queue_key"])
        queue_workpack_counts[queue_key] = queue_workpack_counts.get(queue_key, 0) + 1
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: batch_exporter._sha256_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "output_dir_name": output_dir.name,
        "output_dir_hash": batch_exporter._sha256_text(str(output_dir.expanduser())),
        "index_file_name": WORKPACK_INDEX_NAME,
        "batch_count": len(workpack_rows),
        "workpack_file_count": len(workpack_rows) + 1,
        "queue_workpack_counts": dict(sorted(queue_workpack_counts.items())),
        "next_batch_key": workpack_rows[0]["batch_key"] if workpack_rows else None,
        "batch_workpacks": workpack_rows,
        "brand_contact_sheet_summary_count": len(brand_contact_sheets_by_review_csv),
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(batch_exporter.SOURCE_DOC_URLS),
    }
    summary_without_doc_urls = dict(summary)
    summary_without_doc_urls.pop("source_doc_urls", None)
    _reject_unsafe_payload(summary_without_doc_urls)
    return summary


def _write_batch_workpack(
    *,
    batch: Mapping[str, Any],
    export_by_batch: Mapping[str, Mapping[str, Any]],
    bundle_summaries: Mapping[str, Mapping[str, Any]],
    brand_contact_sheets_by_review_csv: Mapping[str, Mapping[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    """Write one batch Markdown guide.

    Args:
        batch: Batch plan row.
        export_by_batch: Batch export rows by batch key.
        bundle_summaries: Bundle summaries by queue key.
        brand_contact_sheets_by_review_csv: Redacted brand contact-sheet
            summaries keyed by batch review CSV filename.
        output_dir: Workpack directory.

    Returns:
        Redacted workpack row.
    """
    queue_key = batch_exporter._queue_key(batch.get("queue_key"))
    batch_key = batch_exporter._safe_token(str(batch.get("batch_key") or "unknown"))
    export_row = export_by_batch.get(batch_key)
    if export_row is None:
        raise WorkpackError("Batch export summary is missing a planned batch.")
    bundle_summary = bundle_summaries.get(queue_key)
    if bundle_summary is None:
        raise WorkpackError("Source bundle summary is missing for a queued batch.")
    workpack_file_name = _workpack_file_name(batch_key=batch_key)
    bundle_files = _bundle_file_names(queue_key=queue_key, bundle_summary=bundle_summary)
    contact_sheet = _matched_brand_contact_sheet(
        queue_key=queue_key,
        export_row=export_row,
        brand_contact_sheets_by_review_csv=brand_contact_sheets_by_review_csv,
    )
    row = {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "workpack_file_name": workpack_file_name,
        "batch_file_name": batch_exporter._safe_filename(str(export_row["batch_file_name"])),
        "batch_review_file_name": _optional_safe_filename(export_row.get("batch_review_file_name")),
        "source_editable_file_name": batch_exporter._safe_filename(
            str(batch.get("editable_file_name") or "")
        ),
        "row_index_start": batch_exporter._positive_int(batch.get("row_index_start")),
        "row_index_end": batch_exporter._positive_int(batch.get("row_index_end")),
        "pending_row_count": batch_exporter._non_negative_int(batch.get("pending_row_count")),
        "bundle_file_names": bundle_files,
        "visual_index_available": _visual_index_available(bundle_summary),
        "visual_index_file_name": _visual_index_file_name(bundle_summary),
        "visual_index_reviewable_row_count": _bundle_non_negative_int(
            bundle_summary,
            "reviewable_row_count",
        ),
        "visual_index_image_count": _bundle_non_negative_int(
            bundle_summary,
            "image_copied_count",
        ),
        "operator_checklist": _safe_string_list(batch.get("operator_checklist")),
        "contact_sheet_available": contact_sheet is not None,
        "contact_sheet_dir_name": _contact_sheet_dir_name(contact_sheet),
        "contact_sheet_file_names": _contact_sheet_file_names(contact_sheet),
        "contact_sheet_reviewable_row_count": _contact_sheet_non_negative_int(
            contact_sheet,
            "reviewable_row_count",
        ),
        "contact_sheet_rows_with_thumbnails": _contact_sheet_non_negative_int(
            contact_sheet,
            "rows_with_thumbnails",
        ),
        "contact_sheet_rows_without_thumbnails": _contact_sheet_non_negative_int(
            contact_sheet,
            "rows_without_thumbnails",
        ),
        "contact_sheet_thumbnail_count": _contact_sheet_non_negative_int(
            contact_sheet,
            "thumbnail_count",
        ),
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(row)
    markdown = _build_batch_markdown(row)
    (output_dir / workpack_file_name).write_text(markdown, encoding="utf-8")
    return row


def _build_batch_markdown(row: Mapping[str, Any]) -> str:
    """Build one batch Markdown guide.

    Args:
        row: Redacted batch workpack row.

    Returns:
        Markdown guide.
    """
    queue_key = batch_exporter._safe_token(str(row["queue_key"]))
    checklist = _markdown_bullets(row.get("operator_checklist"))
    bundle_files = _markdown_bullets(row.get("bundle_file_names"))
    visual_index = _visual_index_markdown(row)
    contact_sheet = _contact_sheet_markdown(row)
    guide_lines = _markdown_bullets(QUEUE_GUIDES.get(queue_key, ()))
    decision_guide = _build_decision_guide_markdown(queue_key)
    completion_rule = _completion_rule_markdown(queue_key)
    batch_review_line = _optional_batch_review_markdown_line(row.get("batch_review_file_name"))
    markdown = "\n".join(
        [
            f"# {batch_exporter._safe_token(str(row['batch_key']))}",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 파일은 redacted operator workpack입니다. row id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로를 포함하지 않습니다.",
            "",
            "## Batch",
            "",
            f"- Queue: `{queue_key}`",
            f"- Batch file: `{batch_exporter._safe_filename(str(row['batch_file_name']))}`",
            batch_review_line,
            f"- Source editable file: `{batch_exporter._safe_filename(str(row['source_editable_file_name']))}`",
            f"- Row range: `{batch_exporter._positive_int(row.get('row_index_start'))}-{batch_exporter._positive_int(row.get('row_index_end'))}`",
            f"- Pending rows: `{batch_exporter._non_negative_int(row.get('pending_row_count'))}`",
            "",
            "## Source Bundle Files",
            "",
            bundle_files,
            "",
            "## Visual Review Index",
            "",
            visual_index,
            "",
            "## Visual Review Contact Sheet",
            "",
            contact_sheet,
            "",
            "## Queue Guide",
            "",
            guide_lines,
            "",
            "## Decision Schema Guide",
            "",
            decision_guide,
            "",
            "## Checklist",
            "",
            checklist,
            "",
            "## Completion Rule",
            "",
            completion_rule,
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _optional_batch_review_markdown_line(value: object) -> str:
    """Return a Markdown line for an optional batch review CSV.

    Args:
        value: Candidate file name.

    Returns:
        Markdown line.
    """
    if not isinstance(value, str) or not value.strip():
        return "- Batch review CSV: `none`"
    return f"- Batch review CSV: `{batch_exporter._safe_filename(value)}`"


def _build_decision_guide_markdown(queue_key: str) -> str:
    """Build a redacted decision schema guide for one queue.

    Args:
        queue_key: Supported queue key.

    Returns:
        Markdown decision guide.
    """
    guide = QUEUE_DECISION_GUIDES.get(queue_key)
    if guide is None:
        return "- none"
    sections = [
        ("Decision object", (str(guide["decision_object"]),)),
        ("Allowed decisions", _safe_string_list(guide["allowed_decisions"])),
        ("Required fields", _safe_string_list(guide["required_approval_fields"])),
        (
            "Required approval attestations",
            _safe_string_list(guide["required_approval_attestations"]),
        ),
        ("Allowed reason codes", _safe_string_list(guide["allowed_reason_codes"])),
        ("Invalid if", _safe_string_list(guide["invalid_if"])),
    ]
    lines: list[str] = []
    for title, values in sections:
        lines.append(f"- {batch_exporter._safe_token(title)}:")
        for value in values:
            lines.append(f"  - `{batch_exporter._safe_token(str(value))}`")
    return "\n".join(lines)


def _completion_rule_markdown(queue_key: str) -> str:
    """Build queue-specific completion rules.

    Args:
        queue_key: Supported queue key.

    Returns:
        Numbered Markdown rules.
    """
    rules = QUEUE_COMPLETION_RULES.get(queue_key)
    if not rules:
        rules = (
            "Batch JSONL을 검수합니다.",
            "Reconcile 도구로 queue-level copy를 생성합니다.",
            "Batch progress preflight와 큐별 정식 preflight를 다시 실행합니다.",
            "preflight 통과 전에는 DB apply, teacher OCR transfer, YOLO dataset promotion을 진행하지 않습니다.",
        )
    return "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, start=1))


def _build_index_markdown(
    *,
    workpack_rows: Sequence[Mapping[str, Any]],
    plan: Mapping[str, Any],
) -> str:
    """Build the global workpack index.

    Args:
        workpack_rows: Redacted batch workpack rows.
        plan: Batch plan.

    Returns:
        Markdown index.
    """
    table_rows = []
    for row in workpack_rows:
        table_rows.append(
            "| {batch} | {queue} | {file} | {batch_file} | {review_csv} | {start} | {end} | {count} |".format(
                batch=batch_exporter._safe_token(str(row["batch_key"])),
                queue=batch_exporter._safe_token(str(row["queue_key"])),
                file=batch_exporter._safe_filename(str(row["workpack_file_name"])),
                batch_file=batch_exporter._safe_filename(str(row["batch_file_name"])),
                review_csv=_optional_safe_filename(row.get("batch_review_file_name")) or "none",
                start=batch_exporter._positive_int(row.get("row_index_start")),
                end=batch_exporter._positive_int(row.get("row_index_end")),
                count=batch_exporter._non_negative_int(row.get("pending_row_count")),
            )
        )
    markdown = "\n".join(
        [
            "# Supplement Operator Review Workpack Index",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 index는 batch별 Markdown guide와 batch JSONL 파일명을 연결합니다. 원본 이미지, OCR 원문, provider payload, 로컬 경로, 제품 폴더 literal은 포함하지 않습니다.",
            "",
            f"- Batch count: `{len(workpack_rows)}`",
            f"- Next queue: `{batch_exporter._safe_token(str(plan.get('next_queue_key') or 'none'))}`",
            "",
            "| Batch | Queue | Workpack | Batch JSONL | Batch review CSV | Start row | End row | Rows |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
            *table_rows,
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _load_bundle_summaries(input_paths: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    """Load required bundle summaries by queue key.

    Args:
        input_paths: Input path mapping.

    Returns:
        Bundle summaries by queue key.
    """
    summaries: dict[str, dict[str, Any]] = {}
    for queue_key, spec in BUNDLE_INPUTS.items():
        input_key = str(spec["input_key"])
        path = _required_input(input_paths, input_key)
        summary = _load_json_object(path)
        _require_schema(summary, str(spec["schema"]))
        summaries[queue_key] = summary
    return summaries


def _load_brand_contact_sheet_summaries(paths: Sequence[Path]) -> dict[str, dict[str, Any]]:
    """Load optional brand contact-sheet summaries by review CSV filename.

    Args:
        paths: Optional contact-sheet summary paths.

    Returns:
        Mapping keyed by the contact sheet's batch review CSV name.
    """
    summaries: dict[str, dict[str, Any]] = {}
    for path in paths:
        summary = _load_contact_sheet_summary(path)
        review_csv_name = batch_exporter._safe_filename(str(summary["review_csv_name"]))
        if review_csv_name in summaries:
            raise WorkpackError("Duplicate brand contact-sheet review CSV summary.")
        summaries[review_csv_name] = summary
    return summaries


def _load_contact_sheet_summary(path: Path) -> dict[str, Any]:
    """Load a redacted contact-sheet summary without copying row payloads.

    Args:
        path: Contact-sheet summary JSON path.

    Returns:
        Parsed contact-sheet summary.
    """
    if not path.is_file():
        raise WorkpackError("Brand contact-sheet summary is missing.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkpackError("Brand contact-sheet summary must be a JSON object.")
    _require_schema(payload, BRAND_CONTACT_SHEET_SCHEMA)
    _validate_contact_sheet_summary(payload)
    payload["_contact_sheet_dir_name"] = batch_exporter._safe_filename(path.parent.name)
    return payload


def _validate_contact_sheet_summary(summary: Mapping[str, Any]) -> None:
    """Validate contact-sheet summary fields allowed into workpack metadata.

    Args:
        summary: Parsed contact-sheet summary.

    Raises:
        WorkpackError: If the summary includes unsafe storage flags or is missing
            required review CSV metadata.
    """
    summary_without_doc_urls = dict(summary)
    summary_without_doc_urls.pop("source_doc_urls", None)
    _reject_unsafe_payload(summary_without_doc_urls)
    review_csv_name = summary.get("review_csv_name")
    if not isinstance(review_csv_name, str) or not review_csv_name.strip():
        raise WorkpackError("Brand contact-sheet summary is missing review CSV name.")
    batch_exporter._safe_filename(review_csv_name)
    for key in (
        "db_write_performed",
        "external_provider_call_performed",
        "llm_call_performed",
        "paddleocr_training_performed",
        "raw_ocr_text_stored",
        "raw_provider_payload_stored",
        "absolute_paths_stored",
        "local_path_literals_stored",
        "product_dir_literals_stored",
        "full_size_source_images_copied",
    ):
        if summary.get(key) is True:
            raise WorkpackError("Brand contact-sheet summary contains unsafe true flags.")
    for key in (
        "reviewable_row_count",
        "rows_with_thumbnails",
        "rows_without_thumbnails",
        "thumbnail_count",
    ):
        batch_exporter._non_negative_int(summary.get(key))


def _matched_brand_contact_sheet(
    *,
    queue_key: str,
    export_row: Mapping[str, Any],
    brand_contact_sheets_by_review_csv: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Return the contact sheet matching one brand review batch.

    Args:
        queue_key: Current queue key.
        export_row: Export row for the current batch.
        brand_contact_sheets_by_review_csv: Contact sheets keyed by review CSV.

    Returns:
        Matching contact-sheet summary, if any.
    """
    if queue_key != "brand_product_review":
        return None
    review_csv_name = _optional_safe_filename(export_row.get("batch_review_file_name"))
    if review_csv_name is None:
        return None
    return brand_contact_sheets_by_review_csv.get(review_csv_name)


def _contact_sheet_dir_name(contact_sheet: Mapping[str, Any] | None) -> str | None:
    """Return the safe contact-sheet directory name for a row."""
    if contact_sheet is None:
        return None
    return batch_exporter._safe_filename(str(contact_sheet["_contact_sheet_dir_name"]))


def _contact_sheet_file_names(contact_sheet: Mapping[str, Any] | None) -> list[str]:
    """Return contact-sheet files a reviewer can open.

    Args:
        contact_sheet: Optional contact-sheet summary.

    Returns:
        Safe filenames only, without directory or local path fragments.
    """
    if contact_sheet is None:
        return []
    return [batch_exporter._safe_filename(name) for name in BRAND_CONTACT_SHEET_FILE_NAMES]


def _contact_sheet_non_negative_int(
    contact_sheet: Mapping[str, Any] | None,
    key: str,
) -> int | None:
    """Return a non-negative contact-sheet count if a contact sheet exists."""
    if contact_sheet is None:
        return None
    return batch_exporter._non_negative_int(contact_sheet.get(key))


def _contact_sheet_markdown(row: Mapping[str, Any]) -> str:
    """Build safe contact-sheet guidance for a batch.

    Args:
        row: Redacted workpack row.

    Returns:
        Markdown text with safe filenames and coverage counts only.
    """
    if row.get("contact_sheet_available") is not True:
        if row.get("visual_index_available") is True:
            return "- none; use the Visual Review Index above for this queue."
        return "- none"
    file_names = _markdown_bullets(row.get("contact_sheet_file_names"))
    return "\n".join(
        [
            f"- Directory: `{batch_exporter._safe_filename(str(row.get('contact_sheet_dir_name') or ''))}`",
            "- Files:",
            file_names,
            f"- Reviewable rows: `{batch_exporter._non_negative_int(row.get('contact_sheet_reviewable_row_count'))}`",
            f"- Rows with thumbnails: `{batch_exporter._non_negative_int(row.get('contact_sheet_rows_with_thumbnails'))}`",
            f"- Rows without thumbnails: `{batch_exporter._non_negative_int(row.get('contact_sheet_rows_without_thumbnails'))}`",
            f"- Thumbnail count: `{batch_exporter._non_negative_int(row.get('contact_sheet_thumbnail_count'))}`",
            "- Row anchors: append `#row-001`, `#row-002`, ... to the HTML file for triage row hints.",
            "- Use this only as visual context for brand/product review; do not copy visible text into notes.",
        ]
    )


def _bundle_file_names(
    *,
    queue_key: str,
    bundle_summary: Mapping[str, Any],
) -> list[str]:
    """Return safe file names from a bundle summary.

    Args:
        queue_key: Queue key.
        bundle_summary: Bundle summary.

    Returns:
        Safe file names.
    """
    spec = BUNDLE_INPUTS[queue_key]
    names: list[str] = []
    primary = bundle_summary.get(str(spec["primary_editable_field"]))
    if isinstance(primary, str) and primary.strip():
        names.append(batch_exporter._safe_filename(primary))
    for field in spec["optional_files"]:
        value = bundle_summary.get(str(field))
        if isinstance(value, str) and value.strip():
            safe = batch_exporter._safe_filename(value)
            if safe not in names:
                names.append(safe)
    return names


def _visual_index_available(bundle_summary: Mapping[str, Any]) -> bool:
    """Return whether a bundle has a safe visual review index.

    Args:
        bundle_summary: Source bundle summary.

    Returns:
        True when a safe HTML index filename is available.
    """
    return _visual_index_file_name(bundle_summary) is not None


def _visual_index_file_name(bundle_summary: Mapping[str, Any]) -> str | None:
    """Return the safe visual review index filename from a bundle summary.

    Args:
        bundle_summary: Source bundle summary.

    Returns:
        Safe HTML index filename, if present.
    """
    value = bundle_summary.get("html_index_name")
    if not isinstance(value, str) or not value.strip():
        return None
    return batch_exporter._safe_filename(value)


def _bundle_non_negative_int(
    bundle_summary: Mapping[str, Any],
    key: str,
) -> int | None:
    """Return a safe optional count from a bundle summary.

    Args:
        bundle_summary: Source bundle summary.
        key: Count field name.

    Returns:
        Non-negative integer, or None when absent.
    """
    if key not in bundle_summary:
        return None
    return batch_exporter._non_negative_int(bundle_summary.get(key))


def _visual_index_markdown(row: Mapping[str, Any]) -> str:
    """Build safe visual-index guidance for a batch.

    Args:
        row: Redacted workpack row.

    Returns:
        Markdown text with safe filenames and counts only.
    """
    if row.get("visual_index_available") is not True:
        return "- none"
    file_name = batch_exporter._safe_filename(str(row.get("visual_index_file_name") or ""))
    lines = [
        f"- HTML index: `{file_name}`",
        f"- Reviewable rows: `{batch_exporter._non_negative_int(row.get('visual_index_reviewable_row_count'))}`",
        f"- Copied review images: `{batch_exporter._non_negative_int(row.get('visual_index_image_count'))}`",
        "- Use the HTML index for visual-only review; do not copy visible text, source refs, or image paths into decisions.",
    ]
    return "\n".join(lines)


def _export_rows_by_batch(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """Return batch export rows keyed by batch key.

    Args:
        rows: Batch export rows.

    Returns:
        Mapping keyed by batch key.
    """
    output: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        batch_key = batch_exporter._safe_token(str(row.get("batch_key") or "unknown"))
        if batch_key in output:
            raise WorkpackError("Duplicate batch key in export summary.")
        output[batch_key] = row
    return output


def _batch_rows(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return batch plan rows.

    Args:
        plan: Batch plan.

    Returns:
        Batch row mappings.
    """
    try:
        return batch_exporter._batch_rows(plan)
    except batch_exporter.BatchFileExportError as exc:
        raise WorkpackError(str(exc)) from exc


def _export_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return batch export rows.

    Args:
        summary: Batch export summary.

    Returns:
        Batch export rows.
    """
    try:
        return batch_exporter._export_rows(summary)
    except batch_exporter.BatchFileExportError as exc:
        raise WorkpackError(str(exc)) from exc


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object and reject unsafe public payloads.

    Args:
        path: JSON path.

    Returns:
        Parsed object.
    """
    try:
        payload = batch_exporter._load_json_object(path)
    except batch_exporter.BatchFileExportError as exc:
        raise WorkpackError(str(exc)) from exc
    return payload


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Input path mapping.
        key: Required input key.

    Returns:
        Input path.
    """
    path = input_paths.get(key)
    if path is None:
        raise WorkpackError("Required workpack input is missing.")
    return path


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate a schema version.

    Args:
        payload: Parsed payload.
        expected_schema: Required schema version.
    """
    if payload.get("schema_version") != expected_schema:
        raise WorkpackError("Workpack input schema does not match.")


def _workpack_file_name(*, batch_key: str) -> str:
    """Return a safe Markdown file name for a batch.

    Args:
        batch_key: Batch key.

    Returns:
        Workpack file name.
    """
    return batch_exporter._safe_filename(f"{batch_key.replace(':', '-')}.md")


def _safe_string_list(value: object) -> list[str]:
    """Return safe bounded strings from a list-like value.

    Args:
        value: Candidate list.

    Returns:
        Safe strings.
    """
    if not isinstance(value, list | tuple):
        return []
    output = []
    for item in value:
        output.append(batch_exporter._safe_token(str(item)))
    return output


def _optional_safe_filename(value: object) -> str | None:
    """Return a safe optional file name.

    Args:
        value: Candidate file name.

    Returns:
        Safe file name or None.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return batch_exporter._safe_filename(value)


def _markdown_bullets(value: object) -> str:
    """Format a safe list as Markdown bullets.

    Args:
        value: Candidate list.

    Returns:
        Markdown bullet text.
    """
    items = _safe_string_list(value)
    if not items:
        return "- none"
    return "\n".join(f"- `{item}`" for item in items)


def _reject_unsafe_payload(value: Any) -> None:
    """Reject unsafe public output fields.

    Args:
        value: JSON-like output payload.
    """
    try:
        batch_exporter._reject_unsafe_payload(value)
    except batch_exporter.BatchFileExportError as exc:
        raise WorkpackError(str(exc)) from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        summary: Full workpack summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "batch_count": batch_exporter._non_negative_int(summary.get("batch_count")),
        "workpack_file_count": batch_exporter._non_negative_int(summary.get("workpack_file_count")),
        "next_batch_key": summary.get("next_batch_key"),
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    output_dir: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        input_paths: Input path mapping.
        output_dir: Planned output directory.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: batch_exporter._sha256_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "output_dir_name": output_dir.name,
        "output_dir_hash": batch_exporter._sha256_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    if isinstance(error, OSError):
        return "local_file_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    text = str(error).casefold()
    markers = (
        ("missing", "missing_input"),
        ("unsafe", "unsafe_input"),
        ("schema", "schema_mismatch"),
        ("duplicate", "duplicate_batch"),
    )
    for marker, code in markers:
        if marker in text:
            return code
    return "validation_error"


if __name__ == "__main__":
    main()
