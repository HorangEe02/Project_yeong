"""Build a redacted triage report for one supplement brand review CSV batch.

Brand/product review remains a human decision. This helper only ranks
operator-local CSV rows by review urgency so the next batch can be completed
without copying product names, OCR text, provider payloads, image paths, or
source folder literals into public artifacts.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/csv.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
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

from scripts import apply_supplement_brand_batch_review_csv_decisions as batch_csv  # noqa: E402

SCHEMA_VERSION = "supplement-brand-review-batch-triage-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-brand-review-batch-triage-markdown-v1"
REQUIRED_CSV_COLUMNS = frozenset(
    {
        "fixture_id",
        "decision",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "reason_codes",
    }
)
OPTIONAL_NUMERIC_COLUMNS = ("image_count", "detail_page_count", "review_count")
OPTIONAL_CLUSTER_COLUMNS = ("category_key", "brand_candidate_key")
DESCRIPTOR_LIKE_BRAND_TERMS = frozenset(
    {
        "100",
        "고함량",
        "기능성",
        "마시는",
        "분말",
        "수용성",
        "식물성",
        "액상",
        "저분자",
        "초임계",
        "캡슐",
        "프리미엄",
    }
)
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/csv.html",
    "https://docs.python.org/3/library/json.html",
)


class BrandReviewBatchTriageError(ValueError):
    """Raised when a brand review batch cannot be triaged safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-review-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--max-row-hints", type=int, default=25)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted triage summary for one batch review CSV.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {"batch_review_csv": args.batch_review_csv.expanduser().resolve()}
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_brand_review_batch_triage(
            input_paths=input_paths,
            max_row_hints=args.max_row_hints,
        )
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, csv.Error, BrandReviewBatchTriageError, ValueError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_brand_review_batch_triage(
    *,
    input_paths: Mapping[str, Path],
    max_row_hints: int = 25,
) -> dict[str, Any]:
    """Return a redacted review-priority summary for one batch CSV.

    Args:
        input_paths: Mapping containing ``batch_review_csv``.
        max_row_hints: Maximum redacted row-index hints to include.

    Returns:
        Aggregate triage summary.

    Raises:
        BrandReviewBatchTriageError: If the CSV is malformed or unsafe.
    """
    if max_row_hints < 0:
        raise BrandReviewBatchTriageError("max_row_hints must be nonnegative.")
    review_csv = _required_input(input_paths, "batch_review_csv")
    rows = _read_csv_rows(review_csv)
    cluster_sizes = _cluster_sizes(rows)
    row_summaries = [
        _row_triage(row=row, row_index=index, cluster_sizes=cluster_sizes)
        for index, row in enumerate(rows, start=1)
    ]
    decision_counts = Counter(item["decision_state"] for item in row_summaries)
    priority_counts = Counter(item["priority"] for item in row_summaries)
    reason_counts: Counter[str] = Counter()
    for item in row_summaries:
        reason_counts.update(item["reason_codes"])
    row_hints = [
        {
            "row_index": item["row_index"],
            "contact_sheet_anchor": _row_anchor(item["row_index"]),
            "priority": item["priority"],
            "reason_codes": item["reason_codes"],
        }
        for item in sorted(row_summaries, key=_row_hint_sort_key)
        if item["priority"] != "p4_reviewed"
    ][:max_row_hints]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _fingerprint_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "batch_review_csv_name": _safe_filename(review_csv.name),
        "row_count": len(rows),
        "blank_decision_row_count": decision_counts.get("blank", 0),
        "partial_review_without_decision_count": reason_counts.get(
            "partial_review_fields_without_decision",
            0,
        ),
        "reviewed_row_count": len(rows) - decision_counts.get("blank", 0),
        "decision_counts": dict(sorted(decision_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "duplicate_candidate_cluster_count": sum(1 for size in cluster_sizes.values() if size > 1),
        "duplicate_candidate_row_count": sum(size for size in cluster_sizes.values() if size > 1),
        "row_hints_truncated": len(row_hints)
        < sum(1 for item in row_summaries if item["priority"] != "p4_reviewed"),
        "row_hints": row_hints,
        "operator_next_steps": _operator_next_steps(reason_counts=reason_counts),
        "automatic_decision_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_public_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown triage report.

    Args:
        summary: Triage summary.

    Returns:
        Markdown report.
    """
    _reject_public_payload(summary)
    markdown = "\n".join(
        [
            "# Supplement Brand Review Batch Triage",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 brand/product review CSV의 검토 우선순위만 표시합니다.",
            "제품명, 브랜드명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로는 포함하지 않습니다.",
            "",
            "## Batch",
            "",
            f"- CSV: `{_safe_filename(str(summary.get('batch_review_csv_name') or ''))}`",
            f"- Rows: `{_non_negative_int(summary.get('row_count'))}`",
            f"- Blank decision rows: `{_non_negative_int(summary.get('blank_decision_row_count'))}`",
            f"- Partial review rows without decision: `{_non_negative_int(summary.get('partial_review_without_decision_count'))}`",
            f"- Reviewed rows: `{_non_negative_int(summary.get('reviewed_row_count'))}`",
            "",
            "## Priority Counts",
            "",
            _markdown_mapping(summary.get("priority_counts")),
            "",
            "## Reason Counts",
            "",
            _markdown_mapping(summary.get("reason_counts")),
            "",
            "## Row Hints",
            "",
            _markdown_row_hints(summary.get("row_hints")),
            "",
            "## Next Steps",
            "",
            _markdown_list(summary.get("operator_next_steps")),
            "",
            "## Rule",
            "",
            "이 triage는 수동 검토 순서만 제안합니다. approve/reject 결정, DB import, OCR ground-truth 전환은 별도 gate를 통과해야 합니다.",
            "",
        ]
    )
    _reject_public_payload(markdown)
    return markdown


def _row_triage(
    *,
    row: Mapping[str, str],
    row_index: int,
    cluster_sizes: Mapping[tuple[str, str], int],
) -> dict[str, Any]:
    """Return redacted triage facts for one CSV row.

    Args:
        row: CSV row.
        row_index: One-based CSV row index.
        cluster_sizes: Candidate duplicate counts keyed by category and brand.

    Returns:
        Row triage dictionary with no product text.
    """
    decision = _cell(row, "decision").casefold()
    reviewed_fields_filled = any(
        _cell(row, key)
        for key in ("reviewed_manufacturer", "reviewed_product_name", "reason_codes")
    )
    reason_codes: list[str] = []
    if not decision:
        reason_codes.append("blank_decision")
        if reviewed_fields_filled:
            reason_codes.append("partial_review_fields_without_decision")
    else:
        reason_codes.append(f"decision_{_safe_token(decision)}")
    review_count = _optional_count(row, "review_count")
    detail_page_count = _optional_count(row, "detail_page_count")
    image_count = _optional_count(row, "image_count")
    if review_count == 0:
        reason_codes.append("no_review_images")
    if detail_page_count == 0:
        reason_codes.append("no_detail_page_images")
    if image_count == 0:
        reason_codes.append("no_image_evidence")
    cluster_key = (
        _safe_optional_token(_cell(row, "category_key")),
        _safe_optional_token(_cell(row, "brand_candidate_key")),
    )
    if all(cluster_key) and cluster_sizes.get(cluster_key, 0) > 1:
        reason_codes.append("duplicate_candidate_in_batch")
    reason_codes.extend(_candidate_quality_reason_codes(row))
    priority = _priority(decision=decision, reason_codes=reason_codes)
    return {
        "row_index": row_index,
        "decision_state": decision or "blank",
        "priority": priority,
        "reason_codes": sorted(set(reason_codes)),
    }


def _priority(*, decision: str, reason_codes: list[str]) -> str:
    """Return a review priority token.

    Args:
        decision: Lowercase decision value.
        reason_codes: Row reason codes.

    Returns:
        Priority token.
    """
    reasons = set(reason_codes)
    if decision:
        return "p4_reviewed"
    if "partial_review_fields_without_decision" in reasons:
        return "p0_partial_review_fix"
    if {"no_review_images", "no_detail_page_images", "no_image_evidence"} & reasons:
        return "p1_evidence_check"
    if "descriptor_like_brand_candidate" in reasons:
        return "p1_candidate_quality_check"
    if "duplicate_candidate_in_batch" in reasons:
        return "p2_duplicate_candidate_review"
    return "p3_standard_review"


def _row_hint_sort_key(item: Mapping[str, Any]) -> tuple[int, int]:
    """Sort row hints by priority then row index.

    Args:
        item: Row triage item.

    Returns:
        Sort key.
    """
    rank = {
        "p0_partial_review_fix": 0,
        "p1_evidence_check": 1,
        "p1_candidate_quality_check": 2,
        "p2_duplicate_candidate_review": 3,
        "p3_standard_review": 4,
        "p4_reviewed": 5,
    }
    return (rank.get(str(item.get("priority")), 9), _non_negative_int(item.get("row_index")))


def _cluster_sizes(rows: list[Mapping[str, str]]) -> Mapping[tuple[str, str], int]:
    """Return duplicate candidate cluster sizes.

    Args:
        rows: CSV rows.

    Returns:
        Mapping keyed by category and brand candidate tokens.
    """
    counts: defaultdict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        category_key = _safe_optional_token(_cell(row, "category_key"))
        brand_key = _safe_optional_token(_cell(row, "brand_candidate_key"))
        if category_key and brand_key:
            counts[(category_key, brand_key)] += 1
    return dict(counts)


def _candidate_quality_reason_codes(row: Mapping[str, str]) -> list[str]:
    """Return safe quality reason codes for suspicious brand candidates.

    Args:
        row: CSV row.

    Returns:
        Redacted reason codes. The candidate literal is never returned.
    """
    candidate = _normalized_candidate_token(_cell(row, "brand_candidate_key"))
    if not candidate:
        return []
    if candidate in DESCRIPTOR_LIKE_BRAND_TERMS:
        return ["descriptor_like_brand_candidate"]
    return []


def _normalized_candidate_token(value: str) -> str:
    """Normalize a brand candidate token for internal quality checks.

    Args:
        value: Raw CSV token.

    Returns:
        Normalized token used only for redacted reason classification.
    """
    return "".join(ch for ch in value.casefold().strip() if ch not in {" ", "_", "-"})


def _operator_next_steps(*, reason_counts: Mapping[str, int]) -> list[str]:
    """Return aggregate operator next-step tokens.

    Args:
        reason_counts: Reason counts.

    Returns:
        Safe next-step tokens.
    """
    steps = []
    if reason_counts.get("partial_review_fields_without_decision", 0):
        steps.append("fix_partial_review_rows_before_apply")
    if reason_counts.get("no_review_images", 0) or reason_counts.get("no_detail_page_images", 0):
        steps.append("verify_low_evidence_rows_in_contact_sheet")
    if reason_counts.get("descriptor_like_brand_candidate", 0):
        steps.append("review_descriptor_like_brand_candidates_as_not_a_brand_or_needs_review")
    if reason_counts.get("duplicate_candidate_in_batch", 0):
        steps.append("review_duplicate_candidate_rows_together")
    steps.extend(
        [
            "complete_blank_decisions_in_review_csv",
            "run_apply_brand_batch_review_csv_decisions",
            "run_batch_file_preflight_before_reconcile",
        ]
    )
    return steps


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read review CSV rows as safe strings.

    Args:
        path: CSV path.

    Returns:
        CSV rows.
    """
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                raise BrandReviewBatchTriageError("Batch review CSV is missing a header.")
            _validate_csv_columns(fieldnames)
            rows = []
            for row in reader:
                _reject_unsafe_csv_row(row)
                rows.append({key: value or "" for key, value in row.items()})
    except OSError as exc:
        raise BrandReviewBatchTriageError("Batch review CSV is missing or unreadable.") from exc
    if not rows:
        raise BrandReviewBatchTriageError("Batch review CSV is empty.")
    return rows


def _validate_csv_columns(fieldnames: list[str]) -> None:
    """Validate CSV headers.

    Args:
        fieldnames: CSV header names.
    """
    normalized = {field.strip() for field in fieldnames}
    missing = sorted(REQUIRED_CSV_COLUMNS - normalized)
    if missing:
        raise BrandReviewBatchTriageError("Batch review CSV is missing a required column.")
    for fieldname in fieldnames:
        if fieldname.lower() in batch_csv.RAW_FORBIDDEN_CSV_COLUMNS:
            raise BrandReviewBatchTriageError("Unsafe raw/provider key found in review CSV.")


def _reject_unsafe_csv_row(row: Mapping[str, str | None]) -> None:
    """Reject local paths and URLs in CSV cells.

    Args:
        row: CSV row.
    """
    for value in row.values():
        if value and any(marker in value for marker in batch_csv.applier.LOCAL_PATH_OR_URL_MARKERS):
            raise BrandReviewBatchTriageError(
                "Unsafe local path or URL marker found in review CSV."
            )


def _reject_public_payload(value: Any) -> None:
    """Reject unsafe public output payloads.

    Args:
        value: JSON-like value or Markdown text.
    """
    try:
        batch_csv._reject_unsafe_payload(value)
    except ValueError as exc:
        raise BrandReviewBatchTriageError(str(exc)) from exc
    dumped = (
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        if not isinstance(value, str)
        else value
    )
    forbidden_markers = (
        "brand_candidate_display_name",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "source_product_id",
    )
    if any(marker in dumped for marker in forbidden_markers):
        raise BrandReviewBatchTriageError(
            "Public triage payload contains operator review text fields."
        )


def _cell(row: Mapping[str, str], key: str) -> str:
    """Return a stripped CSV cell.

    Args:
        row: CSV row.
        key: Column key.

    Returns:
        Stripped cell.
    """
    return str(row.get(key) or "").strip()


def _optional_count(row: Mapping[str, str], key: str) -> int | None:
    """Return an optional non-negative count.

    Args:
        row: CSV row.
        key: Count column.

    Returns:
        Count or ``None`` if the column is absent/blank.
    """
    value = _cell(row, key)
    if not value:
        return None
    try:
        count = int(value)
    except ValueError as exc:
        raise BrandReviewBatchTriageError("Batch review CSV count column is invalid.") from exc
    if count < 0:
        raise BrandReviewBatchTriageError("Batch review CSV count column is invalid.")
    return count


def _safe_optional_token(value: str) -> str:
    """Return a safe optional token.

    Args:
        value: Candidate token.

    Returns:
        Safe token or empty string.
    """
    if not value:
        return ""
    return _safe_token(value)


def _safe_token(value: str) -> str:
    """Return a safe token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    return batch_csv.applier._required_safe_token(value, field_name="token")


def _safe_filename(value: str) -> str:
    """Return a safe file name.

    Args:
        value: Candidate filename.

    Returns:
        Safe filename.
    """
    return batch_csv._safe_filename(value)


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate value.

    Returns:
        Integer or zero.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _markdown_mapping(value: Any) -> str:
    """Return a Markdown mapping list.

    Args:
        value: Candidate mapping.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, Mapping) or not value:
        return "- none"
    return "\n".join(
        f"- `{_safe_token(str(key))}`: `{_non_negative_int(item)}`"
        for key, item in sorted(value.items())
    )


def _markdown_row_hints(value: Any) -> str:
    """Return redacted row-index hints as Markdown.

    Args:
        value: Candidate row hint list.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, list) or not value:
        return "- none"
    lines = []
    for item in value:
        if not isinstance(item, Mapping):
            raise BrandReviewBatchTriageError("Expected row hint mapping.")
        reasons = ", ".join(_safe_token(str(reason)) for reason in item.get("reason_codes", []))
        anchor = _safe_token(str(item.get("contact_sheet_anchor") or ""))
        anchor_note = f", anchor `#{anchor}`" if anchor else ""
        lines.append(
            f"- row `{_non_negative_int(item.get('row_index'))}`: "
            f"`{_safe_token(str(item.get('priority') or 'unknown'))}` "
            f"({reasons}{anchor_note})"
        )
    return "\n".join(lines)


def _markdown_list(value: Any) -> str:
    """Return a Markdown token list.

    Args:
        value: Candidate token list.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, list) or not value:
        return "- none"
    return "\n".join(f"- `{_safe_token(str(item))}`" for item in value)


def _row_anchor(value: Any) -> str:
    """Return a deterministic redacted contact-sheet row anchor.

    Args:
        value: One-based CSV row index.

    Returns:
        Safe HTML fragment identifier for the matching contact-sheet card.

    Raises:
        BrandReviewBatchTriageError: If the row index is invalid.
    """
    row_index = _non_negative_int(value)
    if row_index <= 0:
        raise BrandReviewBatchTriageError("row index must be positive.")
    return f"row-{row_index:03d}"


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return one required input path.

    Args:
        input_paths: Input path mapping.
        key: Required key.

    Returns:
        Existing path.
    """
    path = input_paths.get(key)
    if path is None or not path.is_file():
        raise BrandReviewBatchTriageError("Required batch triage input is missing.")
    return path


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for local artifact identity.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint_text(value: str) -> str:
    """Return a short public fingerprint for local artifact identity.

    Args:
        value: Text value.

    Returns:
        Short fingerprint safe for public reports.
    """
    return f"fp-{_sha256_text(value)[:12]}"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    _reject_public_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact CLI-safe summary.

    Args:
        summary: Full summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "row_count": _non_negative_int(summary.get("row_count")),
        "blank_decision_row_count": _non_negative_int(summary.get("blank_decision_row_count")),
        "partial_review_without_decision_count": _non_negative_int(
            summary.get("partial_review_without_decision_count")
        ),
        "priority_counts": summary.get("priority_counts"),
        "db_write_performed": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        input_paths: Input path mapping.
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
        "input_path_hashes": {
            key: _fingerprint_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "output_name": output_path.name,
        "output_hash": _fingerprint_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_public_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    text = str(error).casefold()
    if "unsafe" in text:
        return "unsafe_input"
    if "missing" in text:
        return "missing_input"
    if "count" in text:
        return "invalid_count"
    return "validation_error"


if __name__ == "__main__":
    main()
