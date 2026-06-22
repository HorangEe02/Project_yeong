"""Export a manual OCR ground-truth template from review-image candidates.

This tool turns PII-cleared review-image OCR candidates into a JSONL template
that an operator can fill with human-reviewed product, ingredient, intake, and
precaution facts. It does not call OCR providers, does not infer label content,
does not write to the database, and does not train PaddleOCR.

Only candidates already marked as safe for teacher OCR are exported. Optional
image materialization copies source images into a private hashed fixture
directory and records only a relative image path.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_supplement_ocr_benchmark_manifest as benchmark  # noqa: E402

SCHEMA_VERSION = "supplement-ocr-ground-truth-template-v1"
ROW_SCHEMA_VERSION = "supplement-ocr-ground-truth-template-row-v1"
ALLOWED_LABEL_SECTIONS = (
    "product_identity",
    "supplement_facts",
    "ingredient_amounts",
    "intake_method",
    "precautions",
    "allergen_warning",
    "other_ingredients",
    "functional_claims",
)
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Optional crawling-image root used only to materialize private hashed fixtures.",
    )
    parser.add_argument(
        "--materialized-image-dir",
        type=Path,
        default=None,
        help="Optional private directory where PII-cleared source images are copied.",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a manual GT template and redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = export_ground_truth_template(
            candidate_manifest=args.candidate_manifest,
            source_run_id=args.source_run_id,
            source_root=args.source_root,
            materialized_image_dir=args.materialized_image_dir,
            output_manifest_path=output_path,
            limit=args.limit,
        )
        benchmark._reject_unsafe_payload({"rows": rows, "summary": summary})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            candidate_manifest=args.candidate_manifest,
            output_path=output_path,
            error=exc,
        )
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def export_ground_truth_template(
    *,
    candidate_manifest: Path,
    source_run_id: str | None = None,
    source_root: Path | None = None,
    materialized_image_dir: Path | None = None,
    output_manifest_path: Path | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Export manual GT template rows from PII-cleared OCR candidates.

    Args:
        candidate_manifest: OCR candidate JSONL path.
        source_run_id: Optional operator run id.
        source_root: Optional crawling-image root for private image copies.
        materialized_image_dir: Optional private image fixture directory.
        output_manifest_path: Optional output manifest path for relative image
            references.
        limit: Optional maximum exported row count.

    Returns:
        Template rows and a redacted summary.

    Raises:
        ValueError: If inputs are unsafe or malformed.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative.")
    candidates = benchmark._read_jsonl(candidate_manifest)
    source_paths = (
        benchmark._source_paths_by_image_ref_hash(source_root)
        if materialized_image_dir is not None
        else {}
    )
    rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()

    for candidate in candidates:
        benchmark._reject_unsafe_payload(candidate)
        if limit is not None and len(rows) >= limit:
            skip_reasons["limit_reached"] += 1
            continue
        if not benchmark._candidate_is_teacher_allowed(candidate):
            skip_reasons["candidate_pii_or_teacher_gate_not_cleared"] += 1
            continue
        image_path = None
        if materialized_image_dir is not None:
            image_path = benchmark._materialize_image_fixture(
                candidate=candidate,
                source_paths=source_paths,
                materialized_image_dir=materialized_image_dir,
                output_manifest_path=output_manifest_path,
            )
            if image_path is None:
                skip_reasons["source_image_not_found_for_materialization"] += 1
                continue
        rows.append(
            _template_row(
                candidate=candidate,
                source_run_id=source_run_id,
                image_path=image_path,
            )
        )

    summary = _summary(
        candidate_manifest=candidate_manifest,
        source_run_id=source_run_id,
        candidate_count=len(candidates),
        rows=rows,
        skip_reasons=skip_reasons,
        image_materialization_requested=materialized_image_dir is not None,
        limit=limit,
    )
    benchmark._reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _template_row(
    *,
    candidate: dict[str, Any],
    source_run_id: str | None,
    image_path: str | None,
) -> dict[str, Any]:
    """Return one manual GT template row.

    Args:
        candidate: PII-cleared OCR candidate row.
        source_run_id: Optional operator run id.
        image_path: Optional relative materialized image path.

    Returns:
        JSON-safe template row.
    """
    row: dict[str, Any] = {
        "schema_version": ROW_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "fixture_id": benchmark._safe_required_token(
            candidate.get("fixture_id"),
            field_name="fixture_id",
        ),
        "source_ref": benchmark._safe_required_token(
            candidate.get("source_ref"),
            field_name="source_ref",
        ),
        "image_ref_hash": benchmark._safe_required_sha256(candidate.get("image_ref_hash")),
        "image_sha256": benchmark._safe_required_sha256(candidate.get("image_sha256")),
        "image_size_bytes": benchmark._safe_nonnegative_int(candidate.get("image_size_bytes")),
        "image_mime_type": benchmark._safe_optional_text(
            candidate.get("image_mime_type"),
            max_length=80,
        ),
        "category_key": benchmark._safe_required_token(
            candidate.get("category_key"),
            field_name="category_key",
        ),
        "source_kind": "review",
        "decision": "pending",
        "ground_truth_status": "pending_manual_review",
        "contains_personal_data": False,
        "pii_screening_status": "operator_cleared_no_personal_data",
        "external_transfer_allowed": True,
        "teacher_ocr_allowed": True,
        "expected": _empty_expected_template(),
        "allowed_label_sections": list(ALLOWED_LABEL_SECTIONS),
        "review_instructions": [
            "fill_product_name_and_manufacturer_if_visible",
            "fill_ingredients_with_display_name_amount_unit",
            "copy_visible_precaution_sentences_without_medical_interpretation",
            "mark_ground_truth_status_human_reviewed_only_after_double_check",
        ],
        "ready_for_benchmark_after_review": False,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    if image_path is not None:
        row["image_path"] = image_path
        row["image_materialization_policy"] = "private_hashed_fixture_copy_materialized"
    else:
        row["image_materialization_policy"] = "not_materialized"
    benchmark._reject_unsafe_payload(row)
    return row


def _empty_expected_template() -> dict[str, Any]:
    """Return an empty expected object for human reviewers.

    Returns:
        Empty benchmark-compatible expected fields.
    """
    return {
        "verification_status": "pending_manual_review",
        "expected_source": "manual_review_template",
        "product_name": "",
        "manufacturer": "",
        "ingredients": [
            {
                "display_name": "",
                "amount": None,
                "unit": "",
                "nutrient_code": "",
            }
        ],
        "intake_method": {
            "text": "",
            "structured": {
                "frequency": "",
                "time_of_day": [],
            },
        },
        "precautions": [{"text": ""}],
        "allergen_warnings": [{"text": ""}],
        "functional_claims": [{"text": ""}],
        "label_sections": [{"section_type": ""}],
    }


def _summary(
    *,
    candidate_manifest: Path,
    source_run_id: str | None,
    candidate_count: int,
    rows: list[dict[str, Any]],
    skip_reasons: Counter[str],
    image_materialization_requested: bool,
    limit: int | None,
) -> dict[str, Any]:
    """Return a redacted export summary.

    Args:
        candidate_manifest: Candidate manifest path.
        source_run_id: Optional operator run id.
        candidate_count: Input candidate count.
        rows: Exported template rows.
        skip_reasons: Skip reason counts.
        image_materialization_requested: Whether image copy was requested.
        limit: Optional export limit.

    Returns:
        JSON-safe summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_manifest_name": candidate_manifest.name,
        "candidate_manifest_hash": benchmark._sha256_text(str(candidate_manifest.expanduser())),
        "candidate_count": candidate_count,
        "template_row_count": len(rows),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "limit": limit,
        "image_materialization_requested": image_materialization_requested,
        "image_materialized_count": sum(1 for row in rows if row.get("image_path")),
        "image_path_style": (
            "relative_private_hashed_fixture_copy" if image_materialization_requested else None
        ),
        "manual_review_required_count": len(rows),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _failure_summary(
    *,
    candidate_manifest: Path,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        candidate_manifest: Candidate manifest path.
        output_path: Planned output path.
        error: Failure exception.

    Returns:
        JSON-safe failure payload.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "candidate_manifest_name": candidate_manifest.name,
        "candidate_manifest_hash": benchmark._sha256_text(str(candidate_manifest.expanduser())),
        "output_name": output_path.name,
        "output_hash": benchmark._sha256_text(str(output_path.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "Ground-truth template export failed.",
        "template_row_count": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


if __name__ == "__main__":
    main()
