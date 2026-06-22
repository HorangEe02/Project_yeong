"""Export a local-only PII screening template for supplement review images.

The generated JSONL is for human/operator review before review images can be
used with teacher OCR providers. Pending review OCR candidates remain
``external_transfer_allowed=false`` and ``teacher_ocr_allowed=false``. Optional
image materialization copies source images to a private hashed fixture
directory and records only a relative path.

This script does not run OCR, does not call external providers, does not write
to the database, and does not emit local absolute paths, product directory
literals, raw OCR text, provider payloads, or image bytes.
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

from scripts import apply_supplement_review_pii_screening_decisions as decision_apply  # noqa: E402
from scripts import build_supplement_learning_candidate_manifests as candidate_builder  # noqa: E402
from scripts import build_supplement_ocr_benchmark_manifest as benchmark  # noqa: E402

SCHEMA_VERSION = "supplement-review-pii-screening-template-v1"
ROW_SCHEMA_VERSION = "supplement-review-pii-screening-template-row-v1"
EXPECTED_CANDIDATE_SCHEMA_VERSION = candidate_builder.OCR_ROW_SCHEMA_VERSION
SOURCE_DOC_URLS = (
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
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
        help="Optional private directory for local-only PII screening image copies.",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a PII screening template and redacted summary.

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
        rows, summary = export_pii_screening_template(
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


def export_pii_screening_template(
    *,
    candidate_manifest: Path,
    source_run_id: str | None = None,
    source_root: Path | None = None,
    materialized_image_dir: Path | None = None,
    output_manifest_path: Path | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Export local-only PII screening template rows.

    Args:
        candidate_manifest: Review OCR candidate JSONL.
        source_run_id: Optional operator run id.
        source_root: Optional crawling-image root for private image copies.
        materialized_image_dir: Optional local-only fixture directory.
        output_manifest_path: Optional output path used for relative image refs.
        limit: Optional maximum number of exported rows.

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
        if not _candidate_needs_pii_screening(candidate):
            skip_reasons["candidate_not_pending_pii_screening"] += 1
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


def _candidate_needs_pii_screening(candidate: dict[str, Any]) -> bool:
    """Return whether a candidate should be exported for PII screening.

    Args:
        candidate: Review OCR candidate row.

    Returns:
        True for pending local-only review OCR candidates.
    """
    return (
        candidate.get("schema_version") == EXPECTED_CANDIDATE_SCHEMA_VERSION
        and candidate.get("candidate_purpose") == "ocr_ground_truth_review"
        and candidate.get("source_kind") == "review"
        and candidate.get("contains_personal_data") is None
        and candidate.get("pii_screening_status") == "pending_local_screening"
        and candidate.get("external_transfer_allowed") is False
        and candidate.get("teacher_ocr_allowed") is False
        and candidate.get("local_processing_allowed") is True
    )


def _template_row(
    *,
    candidate: dict[str, Any],
    source_run_id: str | None,
    image_path: str | None,
) -> dict[str, Any]:
    """Return one operator-facing PII screening template row.

    Args:
        candidate: Pending review OCR candidate.
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
        "contains_personal_data": None,
        "pii_screening_status": "pending_local_screening",
        "external_transfer_allowed": False,
        "teacher_ocr_allowed": False,
        "local_processing_allowed": True,
        "operator_decision_required": True,
        "decision_stub": _decision_stub(candidate),
        "screening_instructions": [
            "inspect_local_image_only",
            "mark_cleared_only_when_no_face_name_contact_address_order_or_other_personal_data_is_visible",
            "do_not_copy_raw_label_text_or_review_text_into_decision",
            "use_apply_supplement_review_pii_screening_decisions_after_operator_review",
        ],
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


def _decision_stub(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a fill-in-place decision object skeleton.

    Args:
        candidate: Pending review OCR candidate.

    Returns:
        Decision JSON skeleton accepted by the apply script after completion.
    """
    return {
        "schema_version": decision_apply.DECISION_SCHEMA_VERSION,
        "fixture_id": benchmark._safe_required_token(
            candidate.get("fixture_id"),
            field_name="fixture_id",
        ),
        "pii_screening_decision": {
            "decision": "",
            "reviewer_id": "",
            "reviewed_at": "",
            "reason_codes": [],
            "attest_local_screening_completed": False,
            "attest_no_personal_data_visible": False,
            "attest_no_raw_text_copied": False,
            "attest_teacher_ocr_transfer_allowed": False,
        },
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
    """Return a redacted template export summary.

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
        "operator_decision_required_count": len(rows),
        "external_transfer_allowed_rows": 0,
        "teacher_ocr_allowed_rows": 0,
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
        error: Raised exception.

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
        "error_message": "Supplement review PII screening template export failed.",
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
