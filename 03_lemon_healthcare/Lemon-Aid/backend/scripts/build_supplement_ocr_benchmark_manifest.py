"""Build a redacted OCR provider benchmark fixture manifest.

This tool joins review-image OCR candidate rows with operator-authored manual
ground truth. It only emits benchmark fixtures when both gates pass:

* review image PII screening was cleared for teacher OCR transfer
* manual ground truth is marked human-reviewed

It does not call OCR providers, does not write to the database, does not train
PaddleOCR, and does not emit local paths, product directory literals, raw OCR
text, raw provider payloads, image bytes, credentials, or request headers.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-ocr-provider-benchmark-manifest-v1"
ROW_SCHEMA_VERSION = "supplement-ocr-provider-benchmark-fixture-v1"
DEFAULT_PROVIDERS = ("clova_ocr", "google_vision_document", "paddleocr_local")
TEACHER_PROVIDERS = ("clova_ocr", "google_vision_document")
TARGET_PROVIDER = "paddleocr_local"
MAX_INGREDIENTS = 80
MAX_PRECAUTIONS = 40
MAX_ALLERGEN_WARNINGS = 40
MAX_FUNCTIONAL_CLAIMS = 30
MAX_TEXT_LENGTH = 512
MAX_SHORT_TEXT_LENGTH = 160
SAFE_TOKEN_PATTERN = re.compile(r"^[0-9A-Za-z가-힣_.:-]{1,160}$")
ALLOWED_LABEL_SECTIONS = frozenset(
    {
        "product_identity",
        "supplement_facts",
        "ingredient_amounts",
        "intake_method",
        "precautions",
        "allergen_warning",
        "other_ingredients",
        "functional_claims",
    }
)
ALLOWED_REQUIRED_EXPECTED_SECTIONS = frozenset(
    {
        "product_identity",
        "ingredient_amounts",
        "intake_method",
        "precautions",
        "allergen_warnings",
        "functional_claims",
    }
)
DEFAULT_REQUIRED_EXPECTED_SECTIONS = ("ingredient_amounts",)
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "local_path",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "service_key",
    }
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
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
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument(
        "--required-expected-section",
        action="append",
        choices=sorted(ALLOWED_REQUIRED_EXPECTED_SECTIONS),
        default=None,
        help=(
            "Expected section that must be present before a fixture is scoreable. "
            "Can be passed multiple times. Defaults to ingredient_amounts."
        ),
    )
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write the benchmark fixture manifest and summary.

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
        rows, summary = build_ocr_benchmark_manifest(
            candidate_manifest=args.candidate_manifest,
            ground_truth_manifest=args.ground_truth,
            source_run_id=args.source_run_id,
            source_root=args.source_root,
            materialized_image_dir=args.materialized_image_dir,
            output_manifest_path=output_path,
            required_expected_sections=args.required_expected_section,
        )
        _reject_unsafe_payload({"rows": rows, "summary": summary})
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
            ground_truth_manifest=args.ground_truth,
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


def build_ocr_benchmark_manifest(
    *,
    candidate_manifest: Path,
    ground_truth_manifest: Path,
    source_run_id: str | None = None,
    source_root: Path | None = None,
    materialized_image_dir: Path | None = None,
    output_manifest_path: Path | None = None,
    required_expected_sections: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build benchmark fixture rows from candidates and manual ground truth.

    Args:
        candidate_manifest: OCR candidate JSONL generated after PII screening.
        ground_truth_manifest: Operator-authored JSONL containing reviewed
            expected supplement fields.
        source_run_id: Optional operator run id for traceability.
        source_root: Optional crawling-image root used to find source images
            by private hash.
        materialized_image_dir: Optional private output directory for hashed
            image fixture copies.
        output_manifest_path: Optional benchmark manifest path used to write
            relative ``image_path`` references.
        required_expected_sections: Expected sections that must be present
            before a human-reviewed row can become a benchmark fixture.

    Returns:
        Benchmark fixture rows and a redacted summary.

    Raises:
        ValueError: If input rows are unsafe or malformed.
    """
    candidates = _read_jsonl(candidate_manifest)
    decisions = _manual_ground_truth_by_key(_read_jsonl(ground_truth_manifest))
    source_paths = _source_paths_by_image_ref_hash(source_root) if materialized_image_dir else {}
    required_sections = _required_expected_sections(required_expected_sections)
    rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    missing_required_section_counts: Counter[str] = Counter()

    for candidate in candidates:
        _reject_unsafe_payload(candidate)
        fixture_id = _safe_required_token(candidate.get("fixture_id"), field_name="fixture_id")
        if not _candidate_is_teacher_allowed(candidate):
            skip_reasons["candidate_pii_or_teacher_gate_not_cleared"] += 1
            continue
        decision = decisions.get(fixture_id) or decisions.get(str(candidate.get("image_ref_hash")))
        if decision is None:
            skip_reasons["missing_manual_ground_truth"] += 1
            continue
        _reject_unsafe_payload(decision)
        block_reason = _manual_ground_truth_block_reason(decision)
        if block_reason is not None:
            skip_reasons[block_reason] += 1
            continue
        expected = _expected_from_decision(decision)
        if not expected["ingredients"]:
            skip_reasons["manual_ground_truth_missing_ingredients"] += 1
            continue
        missing_sections = _missing_required_expected_sections(expected, required_sections)
        if missing_sections:
            skip_reasons["manual_ground_truth_missing_required_sections"] += 1
            missing_required_section_counts.update(missing_sections)
            continue
        image_path = None
        if materialized_image_dir is not None:
            image_path = _materialize_image_fixture(
                candidate=candidate,
                source_paths=source_paths,
                materialized_image_dir=materialized_image_dir,
                output_manifest_path=output_manifest_path,
            )
            if image_path is None:
                skip_reasons["source_image_not_found_for_materialization"] += 1
                continue
        rows.append(
            _benchmark_row(
                candidate=candidate,
                expected=expected,
                source_run_id=source_run_id,
                image_path=image_path,
                required_expected_sections=required_sections,
            )
        )

    summary = _summary(
        candidate_manifest=candidate_manifest,
        ground_truth_manifest=ground_truth_manifest,
        source_run_id=source_run_id,
        candidate_count=len(candidates),
        decision_count=len(decisions),
        rows=rows,
        skip_reasons=skip_reasons,
        missing_required_section_counts=missing_required_section_counts,
        image_materialization_requested=materialized_image_dir is not None,
        required_expected_sections=required_sections,
    )
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _benchmark_row(
    *,
    candidate: dict[str, Any],
    expected: dict[str, Any],
    source_run_id: str | None,
    image_path: str | None,
    required_expected_sections: tuple[str, ...],
) -> dict[str, Any]:
    """Return one redacted provider benchmark fixture row.

    Args:
        candidate: OCR candidate row.
        expected: Sanitized human-reviewed expected fields.
        source_run_id: Optional operator run id.
        image_path: Optional relative hashed fixture image path.
        required_expected_sections: Expected sections required for this run.

    Returns:
        JSON-safe benchmark row.
    """
    row = {
        "schema_version": ROW_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "fixture_id": _safe_required_token(candidate.get("fixture_id"), field_name="fixture_id"),
        "source_ref": _safe_required_token(candidate.get("source_ref"), field_name="source_ref"),
        "image_ref_hash": _safe_required_sha256(candidate.get("image_ref_hash")),
        "image_sha256": _safe_required_sha256(candidate.get("image_sha256")),
        "product_dir_hash": _safe_required_sha256(candidate.get("product_dir_hash")),
        "image_size_bytes": _safe_nonnegative_int(candidate.get("image_size_bytes")),
        "image_mime_type": _safe_optional_text(candidate.get("image_mime_type"), max_length=80),
        "category_key": _safe_required_token(
            candidate.get("category_key"), field_name="category_key"
        ),
        "source_kind": "review",
        "expected": expected,
        "required_expected_sections": list(required_expected_sections),
        "benchmark_providers": list(DEFAULT_PROVIDERS),
        "teacher_providers": list(TEACHER_PROVIDERS),
        "target_provider": TARGET_PROVIDER,
        "metric_plan": {
            "text_metrics": ["cer", "wer"],
            "field_metrics": [
                "ingredient_name_exact_rate",
                "ingredient_amount_unit_exact_rate",
                "intake_method_extraction_rate",
                "precaution_extraction_rate",
            ],
            "paddleocr_improvement_target": "raise_accuracy_and_precision_after_human_reviewed_gt",
        },
        "image_materialization_required": True,
        "image_materialization_policy": "copy_pii_cleared_source_to_private_hashed_fixture_dir",
        "paddleocr_training_candidate": True,
        "requires_human_review": False,
        "contains_personal_data": False,
        "pii_screening_status": "operator_cleared_no_personal_data",
        "external_transfer_allowed": True,
        "teacher_ocr_allowed": True,
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
        row["image_materialization_required"] = False
        row["image_materialization_policy"] = "private_hashed_fixture_copy_materialized"
    return row


def _candidate_is_teacher_allowed(candidate: dict[str, Any]) -> bool:
    """Return whether an OCR candidate is safe for teacher comparison.

    Args:
        candidate: Candidate row.

    Returns:
        True when PII and transfer gates are cleared.
    """
    return (
        candidate.get("candidate_purpose") == "ocr_ground_truth_review"
        and candidate.get("source_kind") == "review"
        and candidate.get("contains_personal_data") is False
        and candidate.get("pii_screening_status") == "operator_cleared_no_personal_data"
        and candidate.get("external_transfer_allowed") is True
        and candidate.get("teacher_ocr_allowed") is True
    )


def _manual_ground_truth_by_key(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index manual ground-truth rows by fixture id and image hash.

    Args:
        rows: Manual ground-truth rows.

    Returns:
        Mapping keyed by fixture id and image hash.

    Raises:
        ValueError: If a row has no usable key.
    """
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        _reject_unsafe_payload(row)
        fixture_id = row.get("fixture_id")
        image_ref_hash = row.get("image_ref_hash")
        if isinstance(fixture_id, str) and fixture_id:
            indexed[_safe_required_token(fixture_id, field_name="fixture_id")] = row
        elif isinstance(image_ref_hash, str) and image_ref_hash:
            indexed[_safe_required_sha256(image_ref_hash)] = row
        else:
            raise ValueError("Manual ground-truth row must include fixture_id or image_ref_hash.")
    return indexed


def _ground_truth_is_approved(row: dict[str, Any]) -> bool:
    """Return whether a manual ground-truth row is human-reviewed and PII-cleared.

    Args:
        row: Manual ground-truth row.

    Returns:
        True when the row can be used as a benchmark fixture.
    """
    return _manual_ground_truth_block_reason(row) is None


def _manual_ground_truth_block_reason(row: dict[str, Any]) -> str | None:
    """Return the benchmark blocker for one manual ground-truth row.

    Args:
        row: Manual ground-truth row.

    Returns:
        Stable skip reason when the row cannot be promoted, otherwise None.
    """
    decision = row.get("decision")
    status = row.get("ground_truth_status") or row.get("verification_status")
    expected = row.get("expected") if isinstance(row.get("expected"), dict) else {}
    expected_status = expected.get("verification_status") if isinstance(expected, dict) else None
    if row.get("contains_personal_data") is not False:
        return "manual_ground_truth_personal_data_not_cleared"
    if row.get("ready_for_benchmark_after_review") is False:
        return "manual_ground_truth_not_marked_ready_for_benchmark"
    if decision not in {None, "approve", "approved"}:
        return "manual_ground_truth_not_human_reviewed"
    if status not in {"human_reviewed", "verified", "approved"}:
        return "manual_ground_truth_not_human_reviewed"
    if expected_status not in {None, "human_reviewed", "verified", "approved"}:
        return "manual_ground_truth_not_human_reviewed"
    return None


def _expected_from_decision(row: dict[str, Any]) -> dict[str, Any]:
    """Return sanitized expected fields from a manual ground-truth row.

    Args:
        row: Manual ground-truth row.

    Returns:
        Sanitized expected object compatible with OCR evaluation scripts.
    """
    raw_expected = row.get("expected")
    expected = raw_expected if isinstance(raw_expected, dict) else row
    sanitized = {
        "expected_source": "manual_review",
        "verification_status": "human_reviewed",
        "product_name": _safe_optional_text(expected.get("product_name")),
        "manufacturer": _safe_optional_text(expected.get("manufacturer")),
        "ingredients": _ingredient_rows(expected.get("ingredients")),
        "intake_method": _intake_method(expected.get("intake_method")),
        "precautions": _text_rows(expected.get("precautions"), limit=MAX_PRECAUTIONS),
        "allergen_warnings": _text_rows(
            expected.get("allergen_warnings") or expected.get("allergen_warning"),
            limit=MAX_ALLERGEN_WARNINGS,
        ),
        "functional_claims": _text_rows(
            expected.get("functional_claims"),
            limit=MAX_FUNCTIONAL_CLAIMS,
        ),
        "label_sections": _label_sections(expected.get("label_sections")),
        "warnings": _safe_token_list(expected.get("warnings")),
    }
    if not sanitized["warnings"]:
        sanitized.pop("warnings")
    return sanitized


def _required_expected_sections(
    value: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    """Return a validated required expected-section tuple.

    Args:
        value: Optional section list from CLI or caller.

    Returns:
        Deduplicated expected-section tuple.

    Raises:
        ValueError: If a section is unsupported.
    """
    raw_sections = value or DEFAULT_REQUIRED_EXPECTED_SECTIONS
    sections: list[str] = []
    for section in raw_sections:
        if section not in ALLOWED_REQUIRED_EXPECTED_SECTIONS:
            raise ValueError(f"Unsupported required expected section: {section}")
        if section not in sections:
            sections.append(section)
    if not sections:
        return DEFAULT_REQUIRED_EXPECTED_SECTIONS
    return tuple(sections)


def _missing_required_expected_sections(
    expected: dict[str, Any],
    required_sections: tuple[str, ...],
) -> list[str]:
    """Return required expected sections that are not present.

    Args:
        expected: Sanitized human-reviewed expected fields.
        required_sections: Expected section keys required by this run.

    Returns:
        Missing section keys.
    """
    missing: list[str] = []
    for section in required_sections:
        if section == "product_identity":
            if not (expected.get("product_name") or expected.get("manufacturer")):
                missing.append(section)
        elif section == "ingredient_amounts":
            if not expected.get("ingredients"):
                missing.append(section)
        elif section == "intake_method":
            intake = expected.get("intake_method")
            if not isinstance(intake, dict) or not intake:
                missing.append(section)
        elif section == "precautions":
            if not expected.get("precautions"):
                missing.append(section)
        elif section == "allergen_warnings":
            if not expected.get("allergen_warnings"):
                missing.append(section)
        elif section == "functional_claims" and not expected.get("functional_claims"):
            missing.append(section)
    return missing


def _ingredient_rows(value: Any) -> list[dict[str, Any]]:
    """Return bounded sanitized ingredient rows.

    Args:
        value: Raw ingredient list.

    Returns:
        Sanitized ingredient rows.
    """
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:MAX_INGREDIENTS]:
        if not isinstance(item, dict):
            continue
        name = _safe_optional_text(
            item.get("display_name") or item.get("name") or item.get("normalized_name"),
            max_length=MAX_SHORT_TEXT_LENGTH,
        )
        if not name:
            continue
        row: dict[str, Any] = {
            "display_name": name,
            "amount": _safe_optional_number(item.get("amount")),
            "unit": _safe_optional_text(item.get("unit"), max_length=24),
        }
        nutrient_code = _safe_optional_token(item.get("nutrient_code"))
        if nutrient_code is not None:
            row["nutrient_code"] = nutrient_code
        rows.append(row)
    return rows


def _intake_method(value: Any) -> dict[str, Any]:
    """Return a sanitized intake method object.

    Args:
        value: Raw intake method value.

    Returns:
        Sanitized object compatible with ``evaluate_ocr_three_tier``.
    """
    if isinstance(value, str):
        return {"text": _truncate(value, max_length=MAX_TEXT_LENGTH)}
    if not isinstance(value, dict):
        return {}
    sanitized: dict[str, Any] = {}
    text = _safe_optional_text(value.get("text"), max_length=MAX_TEXT_LENGTH)
    if text:
        sanitized["text"] = text
    structured = value.get("structured")
    if isinstance(structured, dict):
        structured_row: dict[str, Any] = {}
        frequency = _safe_optional_text(structured.get("frequency"), max_length=80)
        if frequency:
            structured_row["frequency"] = frequency
        time_of_day = _safe_token_list(structured.get("time_of_day"))
        if time_of_day:
            structured_row["time_of_day"] = time_of_day
        if structured_row:
            sanitized["structured"] = structured_row
    return sanitized


def _text_rows(value: Any, *, limit: int) -> list[dict[str, str]]:
    """Return sanitized text rows from strings or dictionaries.

    Args:
        value: Raw list of strings/dictionaries.
        limit: Maximum row count.

    Returns:
        Rows with bounded ``text`` values.
    """
    if isinstance(value, str):
        return [{"text": _truncate(value, max_length=MAX_TEXT_LENGTH)}] if value.strip() else []
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value[:limit]:
        text = item.get("text") if isinstance(item, dict) else item
        sanitized = _safe_optional_text(text, max_length=MAX_TEXT_LENGTH)
        if sanitized:
            rows.append({"text": sanitized})
    return rows


def _label_sections(value: Any) -> list[dict[str, str]]:
    """Return sanitized label section rows.

    Args:
        value: Raw label section list.

    Returns:
        Rows with whitelisted section types.
    """
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        raw_section = item.get("section_type") if isinstance(item, dict) else item
        if not isinstance(raw_section, str):
            continue
        normalized = raw_section.strip()
        if normalized in ALLOWED_LABEL_SECTIONS:
            rows.append({"section_type": normalized})
    return rows


def _summary(
    *,
    candidate_manifest: Path,
    ground_truth_manifest: Path,
    source_run_id: str | None,
    candidate_count: int,
    decision_count: int,
    rows: list[dict[str, Any]],
    skip_reasons: Counter[str],
    missing_required_section_counts: Counter[str],
    image_materialization_requested: bool,
    required_expected_sections: tuple[str, ...],
) -> dict[str, Any]:
    """Return a redacted benchmark build summary.

    Args:
        candidate_manifest: Candidate manifest path.
        ground_truth_manifest: Manual GT manifest path.
        source_run_id: Optional operator run id.
        candidate_count: Candidate input row count.
        decision_count: Manual decision input row count.
        rows: Benchmark output rows.
        skip_reasons: Skip reason counts.
        missing_required_section_counts: Missing required expected-section counts.
        image_materialization_requested: Whether private hashed image copies
            were requested.
        required_expected_sections: Expected sections required for this run.

    Returns:
        JSON-safe summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_manifest_name": candidate_manifest.name,
        "candidate_manifest_hash": _sha256_text(str(candidate_manifest.expanduser())),
        "ground_truth_manifest_name": ground_truth_manifest.name,
        "ground_truth_manifest_hash": _sha256_text(str(ground_truth_manifest.expanduser())),
        "candidate_count": candidate_count,
        "ground_truth_decision_count": decision_count,
        "benchmark_fixture_count": len(rows),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "required_expected_sections": list(required_expected_sections),
        "missing_required_section_counts": dict(sorted(missing_required_section_counts.items())),
        "provider_plan": {
            "teacher_providers": list(TEACHER_PROVIDERS),
            "target_provider": TARGET_PROVIDER,
            "default_providers": list(DEFAULT_PROVIDERS),
        },
        "scoreable_fixture_count": sum(1 for row in rows if row["expected"]["ingredients"]),
        "image_materialization_requested": image_materialization_requested,
        "image_materialized_count": sum(1 for row in rows if row.get("image_path")),
        "image_path_style": (
            "relative_private_hashed_fixture_copy" if image_materialization_requested else None
        ),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _source_paths_by_image_ref_hash(source_root: Path | None) -> dict[str, Path]:
    """Build a private source-image lookup by candidate image reference hash.

    Args:
        source_root: crawling-image root.

    Returns:
        Mapping from image ref hash to local source path. The mapping is kept in
        process memory only and is never emitted.

    Raises:
        ValueError: If materialization was requested without a valid root.
    """
    if source_root is None:
        raise ValueError("source_root is required when materializing image fixtures.")
    resolved_root = source_root.expanduser().resolve()
    if not resolved_root.is_dir():
        raise ValueError("source_root is not a directory.")
    paths: dict[str, Path] = {}
    for path in sorted(resolved_root.rglob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
            continue
        if not path.is_file():
            continue
        try:
            relative_ref = path.relative_to(resolved_root).as_posix()
        except ValueError:
            continue
        paths[_sha256_text(relative_ref)] = path
    return paths


def _materialize_image_fixture(
    *,
    candidate: dict[str, Any],
    source_paths: dict[str, Path],
    materialized_image_dir: Path,
    output_manifest_path: Path | None,
) -> str | None:
    """Copy one PII-cleared source image to a private hashed fixture path.

    Args:
        candidate: Benchmark candidate row.
        source_paths: Private source lookup keyed by image ref hash.
        materialized_image_dir: Destination directory.
        output_manifest_path: Manifest path used for relative image reference.

    Returns:
        Relative image path for the manifest, or None when the source image is
        not found.
    """
    image_ref_hash = candidate.get("image_ref_hash")
    if not isinstance(image_ref_hash, str):
        return None
    source_path = source_paths.get(image_ref_hash)
    if source_path is None:
        return None
    destination_dir = materialized_image_dir.expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()
    fixture_id = _safe_required_token(candidate.get("fixture_id"), field_name="fixture_id")
    destination_path = (destination_dir / f"{fixture_id}{suffix}").resolve()
    try:
        destination_path.relative_to(destination_dir)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Materialized image destination escaped output directory.") from exc
    shutil.copyfile(source_path, destination_path)
    if output_manifest_path is None:
        return destination_path.name
    manifest_dir = output_manifest_path.expanduser().resolve().parent
    try:
        return destination_path.relative_to(manifest_dir).as_posix()
    except ValueError:
        return destination_path.name


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: JSONL path.

    Returns:
        Parsed object rows.

    Raises:
        ValueError: If any line is not an object.
    """
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError(f"JSONL line {line_number} must be an object.")
        rows.append(parsed)
    return rows


def _safe_required_token(value: Any, *, field_name: str) -> str:
    """Return a safe required token.

    Args:
        value: Raw value.
        field_name: Field name for diagnostics.

    Returns:
        Safe token.

    Raises:
        ValueError: If value is missing or unsafe.
    """
    token = _safe_optional_token(value)
    if token is None:
        raise ValueError(f"Missing or unsafe token: {field_name}")
    return token


def _safe_optional_token(value: Any) -> str | None:
    """Return a bounded token or None.

    Args:
        value: Raw value.

    Returns:
        Safe token or None.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        return None
    return stripped


def _safe_required_sha256(value: Any) -> str:
    """Return a SHA-256 hex string.

    Args:
        value: Raw value.

    Returns:
        Lowercase SHA-256 hex digest.

    Raises:
        ValueError: If value is not a SHA-256 digest.
    """
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ValueError("Expected SHA-256 hex digest.")
    return value.lower()


def _safe_nonnegative_int(value: Any) -> int | None:
    """Return a non-negative int or None.

    Args:
        value: Raw value.

    Returns:
        Non-negative int or None.
    """
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _safe_optional_number(value: Any) -> float | None:
    """Return a non-negative finite number or None.

    Args:
        value: Raw value.

    Returns:
        Number rounded for stable JSON.
    """
    if isinstance(value, int | float) and value >= 0:
        return round(float(value), 6)
    return None


def _safe_optional_text(value: Any, *, max_length: int = MAX_SHORT_TEXT_LENGTH) -> str | None:
    """Return bounded text or None.

    Args:
        value: Raw value.
        max_length: Maximum character length.

    Returns:
        Sanitized text or None.
    """
    if not isinstance(value, str):
        return None
    sanitized = _truncate(value, max_length=max_length)
    return sanitized or None


def _truncate(value: str, *, max_length: int) -> str:
    """Normalize and bound a text field.

    Args:
        value: Raw text.
        max_length: Maximum character length.

    Returns:
        Bounded text with control characters collapsed.
    """
    collapsed = re.sub(r"\s+", " ", value).strip()
    return collapsed[:max_length]


def _safe_token_list(value: Any) -> list[str]:
    """Return safe token list.

    Args:
        value: Raw list-like value.

    Returns:
        Safe tokens.
    """
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value[:20]:
        token = _safe_optional_token(item)
        if token is not None:
            tokens.append(token)
    return tokens


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest of text.

    Args:
        value: Text to hash.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw keys and local path markers.

    Args:
        value: Payload candidate.

    Raises:
        ValueError: If unsafe content is detected.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("OCR benchmark manifest contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw OCR/provider key names.

    Args:
        value: Payload candidate.

    Raises:
        ValueError: If an unsafe raw key appears.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"OCR benchmark manifest contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


def _failure_summary(
    *,
    candidate_manifest: Path,
    ground_truth_manifest: Path,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        candidate_manifest: Candidate manifest path.
        ground_truth_manifest: Manual GT manifest path.
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
        "candidate_manifest_hash": _sha256_text(str(candidate_manifest.expanduser())),
        "ground_truth_manifest_name": ground_truth_manifest.name,
        "ground_truth_manifest_hash": _sha256_text(str(ground_truth_manifest.expanduser())),
        "output_name": output_path.name,
        "output_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "OCR benchmark manifest build failed.",
        "benchmark_fixture_count": 0,
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
