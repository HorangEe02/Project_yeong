"""Apply operator-edited brand review CSV values to one batch JSONL file.

The batch ``*.review.csv`` file is easier for operators to review than raw
JSONL, but downstream gates expect the original decision JSONL schema. This
tool converts reviewed CSV fields into a new operator-local batch JSONL copy.

It does not modify source files, write to the database, read images, run OCR,
call LLMs, or emit product text in summaries. Approved rows still require the
same explicit attestations enforced by the brand review apply gate.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/csv.html
    https://docs.python.org/3/library/json.html
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from scripts import apply_supplement_brand_review_decisions as applier  # noqa: E402
from scripts import preflight_supplement_operator_review_batch_file as batch_preflight  # noqa: E402

SCHEMA_VERSION = "supplement-brand-batch-review-csv-apply-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-brand-batch-review-csv-apply-markdown-v1"
REQUIRED_CSV_COLUMNS = frozenset(
    {
        "fixture_id",
        "decision",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "reason_codes",
    }
)
RAW_FORBIDDEN_CSV_COLUMNS = frozenset(
    {
        "api_key",
        "authorization",
        "credential",
        "credentials",
        "image_base64",
        "image_bytes",
        "local_path",
        "object_uri",
        "ocr_text",
        "owner_subject",
        "owner_subject_hash",
        "provider_payload",
        "raw_ocr_text",
        "raw_payload",
        "raw_provider_payload",
        "secret",
        "signed_url",
        "url",
    }
)
APPROVAL_ATTESTATION_FLAGS = {
    "attest_brand_product_review_completed": "attest_brand_product_review_completed",
    "attest_not_using_product_folder_literal_as_manufacturer": (
        "attest_not_using_product_folder_literal_as_manufacturer"
    ),
    "attest_product_name_reviewed_from_label_or_safe_catalog": (
        "attest_product_name_reviewed_from_label_or_safe_catalog"
    ),
    "attest_no_raw_ocr_or_provider_payload_copied": (
        "attest_no_raw_ocr_or_provider_payload_copied"
    ),
    "attest_db_import_allowed": "attest_db_import_allowed",
}
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/csv.html",
    "https://docs.python.org/3/library/json.html",
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
)


class BrandBatchCsvApplyError(ValueError):
    """Raised when brand batch CSV decisions cannot be safely applied."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-file", type=Path, required=True)
    parser.add_argument("--batch-review-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--reviewed-at-safe-token", required=True)
    parser.add_argument("--attest-brand-product-review-completed", action="store_true")
    parser.add_argument(
        "--attest-not-using-product-folder-literal-as-manufacturer",
        action="store_true",
    )
    parser.add_argument(
        "--attest-product-name-reviewed-from-label-or-safe-catalog",
        action="store_true",
    )
    parser.add_argument("--attest-no-raw-ocr-or-provider-payload-copied", action="store_true")
    parser.add_argument("--attest-db-import-allowed", action="store_true")
    parser.add_argument(
        "--require-all-reviewed",
        action="store_true",
        help="Fail if any CSV row still has a blank decision.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write an updated batch JSONL and redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "batch_file": args.batch_file.expanduser().resolve(),
        "batch_review_csv": args.batch_review_csv.expanduser().resolve(),
    }
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary_output.expanduser().resolve()
        if args.summary_output is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        rows, summary = apply_brand_batch_review_csv_decisions(
            input_paths=input_paths,
            reviewer_id=args.reviewer_id,
            reviewed_at_safe_token=args.reviewed_at_safe_token,
            approval_attestations=_approval_attestations_from_args(args),
            require_all_reviewed=args.require_all_reviewed,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        summary["output_batch_file_written"] = True
        _write_json(summary_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, BrandBatchCsvApplyError, ValueError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(summary_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def apply_brand_batch_review_csv_decisions(
    *,
    input_paths: Mapping[str, Path],
    reviewer_id: str,
    reviewed_at_safe_token: str,
    approval_attestations: Mapping[str, bool],
    require_all_reviewed: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply reviewed CSV decisions to a brand batch JSONL copy.

    Args:
        input_paths: ``batch_file`` and ``batch_review_csv`` paths.
        reviewer_id: Operator-scoped reviewer id.
        reviewed_at_safe_token: Safe reviewed-at token.
        approval_attestations: Explicit approval attestation flags.
        require_all_reviewed: Fail closed when blank decisions remain.

    Returns:
        Updated batch rows and redacted summary.

    Raises:
        BrandBatchCsvApplyError: If CSV and JSONL rows diverge or contain unsafe values.
    """
    batch_file = _required_input(input_paths, "batch_file")
    review_csv = _required_input(input_paths, "batch_review_csv")
    batch_rows = batch_preflight.progress._read_jsonl(path=batch_file)
    csv_rows = _read_csv_rows(review_csv)
    if len(batch_rows) != len(csv_rows):
        raise BrandBatchCsvApplyError("Batch CSV row count does not match batch JSONL.")
    safe_reviewer_id = _safe_reviewer_id(reviewer_id)
    safe_reviewed_at = applier._required_safe_token(
        reviewed_at_safe_token,
        field_name="reviewed_at",
    )
    updated_rows: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()
    changed_count = 0
    for index, (batch_row, csv_row) in enumerate(zip(batch_rows, csv_rows, strict=True), start=1):
        updated_row, decision_value, changed = _updated_row_from_csv(
            batch_row=batch_row,
            csv_row=csv_row,
            row_index=index,
            reviewer_id=safe_reviewer_id,
            reviewed_at=safe_reviewed_at,
            approval_attestations=approval_attestations,
        )
        updated_rows.append(updated_row)
        decision_counts[decision_value] += 1
        if changed:
            changed_count += 1
    blank_count = decision_counts.get("blank", 0)
    if require_all_reviewed and blank_count:
        raise BrandBatchCsvApplyError("Batch review CSV still contains blank decisions.")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_fingerprints": {
            key: _path_fingerprint(path) for key, path in sorted(input_paths.items())
        },
        "batch_file_name": batch_file.name,
        "batch_review_csv_name": review_csv.name,
        "output_row_count": len(updated_rows),
        "changed_row_count": changed_count,
        "unchanged_row_count": len(updated_rows) - changed_count,
        "decision_counts": dict(sorted(decision_counts.items())),
        "require_all_reviewed": require_all_reviewed,
        "ready_for_batch_file_preflight": True,
        "original_batch_file_modified": False,
        "output_batch_file_written": False,
        "db_write_performed": False,
        "approved_for_db_write_rows": decision_counts.get("approve", 0),
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload({"summary": summary})
    return updated_rows, summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown summary.

    Args:
        summary: Apply summary.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload({"summary": summary})
    decision_counts = _markdown_mapping(summary.get("decision_counts"))
    markdown = "\n".join(
        [
            "# Supplement Brand Batch Review CSV Apply",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 CSV decision을 batch JSONL schema로 변환한 aggregate 결과만 표시합니다.",
            "",
            f"- Batch file: `{_safe_filename(str(summary.get('batch_file_name') or ''))}`",
            f"- Batch review CSV: `{_safe_filename(str(summary.get('batch_review_csv_name') or ''))}`",
            f"- Output rows: `{_non_negative_int(summary.get('output_row_count'))}`",
            f"- Changed rows: `{_non_negative_int(summary.get('changed_row_count'))}`",
            f"- Unchanged rows: `{_non_negative_int(summary.get('unchanged_row_count'))}`",
            "",
            "## Decision Counts",
            "",
            decision_counts,
            "",
            "## Next Gate",
            "",
            "1. Output batch JSONL에 대해 single-batch preflight를 다시 실행합니다.",
            "2. complete 상태가 된 batch만 reconcile로 넘깁니다.",
            "3. queue-level preflight 통과 전에는 DB import manifest를 만들지 않습니다.",
            "",
        ]
    )
    _reject_unsafe_payload({"markdown": markdown})
    return markdown


def _updated_row_from_csv(
    *,
    batch_row: Mapping[str, Any],
    csv_row: Mapping[str, str],
    row_index: int,
    reviewer_id: str,
    reviewed_at: str,
    approval_attestations: Mapping[str, bool],
) -> tuple[dict[str, Any], str, bool]:
    """Return one updated batch row from matching CSV fields.

    Args:
        batch_row: Original batch JSONL row.
        csv_row: Matching CSV row.
        row_index: One-based row index for redacted validation errors.
        reviewer_id: Safe reviewer id.
        reviewed_at: Safe reviewed-at token.
        approval_attestations: Approval attestation flags.

    Returns:
        Updated row, decision value, and whether it changed.
    """
    fixture_id = _safe_fixture_id(batch_row.get("fixture_id"))
    csv_fixture_id = _safe_fixture_id(csv_row.get("fixture_id"))
    if fixture_id != csv_fixture_id:
        raise BrandBatchCsvApplyError("Batch CSV fixture order does not match batch JSONL.")
    original_row = dict(batch_row)
    decision_value = _safe_optional_token(csv_row.get("decision"))
    if decision_value is None:
        _reject_partial_blank_csv_row(csv_row, row_index=row_index)
        return original_row, "blank", False
    decision = _decision_from_csv_row(
        csv_row=csv_row,
        decision_value=decision_value,
        reviewer_id=reviewer_id,
        reviewed_at=reviewed_at,
        approval_attestations=approval_attestations,
    )
    updated_row = dict(batch_row)
    updated_row["brand_review_decision"] = decision
    _reject_unsafe_payload({"row": updated_row})
    changed = _stable_json(updated_row) != _stable_json(original_row)
    return updated_row, decision_value, changed


def _decision_from_csv_row(
    *,
    csv_row: Mapping[str, str],
    decision_value: str,
    reviewer_id: str,
    reviewed_at: str,
    approval_attestations: Mapping[str, bool],
) -> dict[str, Any]:
    """Build and validate a brand review decision object from CSV values.

    Args:
        csv_row: CSV row.
        decision_value: Safe decision token.
        reviewer_id: Safe reviewer id.
        reviewed_at: Safe reviewed-at token.
        approval_attestations: Approval attestation flags.

    Returns:
        Validated decision object.
    """
    decision = {
        "decision": decision_value,
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "reviewed_manufacturer": _csv_text(csv_row.get("reviewed_manufacturer")),
        "reviewed_product_name": _csv_text(csv_row.get("reviewed_product_name")),
        "reason_codes": _reason_codes_from_csv(csv_row.get("reason_codes")),
    }
    for decision_key, flag_key in APPROVAL_ATTESTATION_FLAGS.items():
        decision[decision_key] = bool(approval_attestations.get(flag_key))
    try:
        applier._validate_decision(decision)
    except ValueError as exc:
        raise BrandBatchCsvApplyError(str(exc)) from exc
    return decision


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read batch review CSV rows.

    Args:
        path: CSV path.

    Returns:
        CSV rows as strings.
    """
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                raise BrandBatchCsvApplyError("Batch review CSV is missing a header.")
            missing = sorted(REQUIRED_CSV_COLUMNS - {field.strip() for field in fieldnames})
            if missing:
                raise BrandBatchCsvApplyError("Batch review CSV is missing a required column.")
            _reject_unsafe_csv_columns(fieldnames)
            rows = []
            for row in reader:
                _reject_unsafe_csv_row(row)
                rows.append({key: value or "" for key, value in row.items()})
    except OSError as exc:
        raise BrandBatchCsvApplyError("Batch review CSV is missing or unreadable.") from exc
    if not rows:
        raise BrandBatchCsvApplyError("Batch review CSV is empty.")
    return rows


def _approval_attestations_from_args(args: argparse.Namespace) -> dict[str, bool]:
    """Return approval attestation flags from parsed CLI args.

    Args:
        args: Parsed CLI namespace.

    Returns:
        Attestation mapping.
    """
    return {
        "attest_brand_product_review_completed": bool(args.attest_brand_product_review_completed),
        "attest_not_using_product_folder_literal_as_manufacturer": bool(
            args.attest_not_using_product_folder_literal_as_manufacturer
        ),
        "attest_product_name_reviewed_from_label_or_safe_catalog": bool(
            args.attest_product_name_reviewed_from_label_or_safe_catalog
        ),
        "attest_no_raw_ocr_or_provider_payload_copied": bool(
            args.attest_no_raw_ocr_or_provider_payload_copied
        ),
        "attest_db_import_allowed": bool(args.attest_db_import_allowed),
    }


def _reject_partial_blank_csv_row(row: Mapping[str, str], *, row_index: int) -> None:
    """Reject CSV rows with fields filled but no decision.

    Args:
        row: CSV row.
        row_index: One-based row index.
    """
    keys = ("reviewed_manufacturer", "reviewed_product_name", "reason_codes")
    if any((row.get(key) or "").strip() for key in keys):
        raise BrandBatchCsvApplyError(f"CSV row {row_index} has review fields but no decision.")


def _reason_codes_from_csv(value: str | None) -> list[str]:
    """Return reason codes from a CSV cell.

    Args:
        value: CSV reason code cell.

    Returns:
        Reason code list.
    """
    if value is None or not value.strip():
        return []
    return [
        applier._required_safe_token(token, field_name="reason_codes")
        for token in re.split(r"[,;]", value)
        if token.strip()
    ]


def _csv_text(value: str | None) -> str:
    """Return a stripped CSV text value.

    Args:
        value: CSV cell value.

    Returns:
        Stripped text.
    """
    return "" if value is None else value.strip()


def _safe_fixture_id(value: object) -> str:
    """Return a safe fixture id.

    Args:
        value: Candidate fixture id.

    Returns:
        Safe fixture id.
    """
    return applier._required_safe_token(value, field_name="fixture_id")


def _safe_reviewer_id(value: str) -> str:
    """Return a safe operator reviewer id.

    Args:
        value: Candidate reviewer id.

    Returns:
        Valid reviewer id.
    """
    decision = {
        "reviewer_id": value,
        "decision": "needs_review",
        "reviewed_at": "review_token",
        "reason_codes": ["needs_catalog_lookup"],
    }
    return applier._required_operator_reviewer_id(decision)


def _safe_optional_token(value: str | None) -> str | None:
    """Return a safe token or None for blank CSV cells.

    Args:
        value: Candidate token.

    Returns:
        Safe token or None.
    """
    if value is None or not value.strip():
        return None
    return applier._required_safe_token(value, field_name="decision")


def _reject_unsafe_csv_columns(fieldnames: list[str]) -> None:
    """Reject unsafe CSV column names.

    Args:
        fieldnames: CSV header names.
    """
    for fieldname in fieldnames:
        if fieldname.lower() in RAW_FORBIDDEN_CSV_COLUMNS:
            raise BrandBatchCsvApplyError("Unsafe raw/provider key found in review CSV.")


def _reject_unsafe_csv_row(row: Mapping[str, str | None]) -> None:
    """Reject local path markers in CSV values.

    Args:
        row: CSV row.
    """
    for value in row.values():
        if value and any(marker in value for marker in applier.LOCAL_PATH_OR_URL_MARKERS):
            raise BrandBatchCsvApplyError("Unsafe local path or URL marker found in review CSV.")


def _reject_unsafe_payload(value: Any) -> None:
    """Reject unsafe public payloads.

    Args:
        value: JSON-like payload.
    """
    try:
        applier._reject_unsafe_payload(value)
    except ValueError as exc:
        raise BrandBatchCsvApplyError(str(exc)) from exc


def _markdown_mapping(value: Any) -> str:
    """Return a Markdown mapping list.

    Args:
        value: Candidate mapping.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, Mapping) or not value:
        return "- none"
    lines = []
    for key, item in sorted(value.items()):
        lines.append(
            f"- `{applier._required_safe_token(str(key), field_name='decision_count_key')}`: `{_non_negative_int(item)}`"
        )
    return "\n".join(lines)


def _safe_filename(value: str) -> str:
    """Return a safe file name.

    Args:
        value: Candidate filename.

    Returns:
        Safe file name.
    """
    return batch_preflight._safe_filename(value)


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate value.

    Returns:
        Non-negative integer.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Path mapping.
        key: Required key.

    Returns:
        Input path.
    """
    path = input_paths.get(key)
    if path is None:
        raise BrandBatchCsvApplyError("Required input is missing.")
    return path


def _stable_json(value: Mapping[str, Any]) -> str:
    """Return stable JSON for equality checks.

    Args:
        value: JSON-like row.

    Returns:
        Stable JSON string.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for text.

    Args:
        value: Text.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _path_fingerprint(path: Path) -> str:
    """Return a short non-secret path fingerprint for public artifacts.

    Args:
        path: Path to identify without exposing it.

    Returns:
        Short hexadecimal fingerprint with a non-hex prefix.
    """
    return f"fp-{_sha256_text(str(path.expanduser()))[:8]}"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON object.

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
        summary: Full summary.

    Returns:
        CLI-safe summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "output_row_count": _non_negative_int(summary.get("output_row_count")),
        "changed_row_count": _non_negative_int(summary.get("changed_row_count")),
        "unchanged_row_count": _non_negative_int(summary.get("unchanged_row_count")),
        "ready_for_batch_file_preflight": summary.get("ready_for_batch_file_preflight") is True,
        "original_batch_file_modified": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return redacted failure summary.

    Args:
        input_paths: Input paths.
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_fingerprints": {
            key: _path_fingerprint(path) for key, path in sorted(input_paths.items())
        },
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "output_row_count": 0,
        "changed_row_count": 0,
        "original_batch_file_modified": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload({"summary": summary})
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return bounded public error code.

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
    keyword_codes = (
        ("fixture", "fixture_mismatch"),
        ("attestation", "missing_attestation"),
        ("unsafe", "unsafe_input"),
        ("column", "invalid_csv_columns"),
        ("count", "row_count_mismatch"),
    )
    for keyword, code in keyword_codes:
        if keyword in text:
            return code
    return "validation_error"


if __name__ == "__main__":
    main()
