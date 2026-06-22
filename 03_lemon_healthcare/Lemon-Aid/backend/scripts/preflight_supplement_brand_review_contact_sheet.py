"""Preflight a supplement brand review CSV against its contact sheet summary.

The contact sheet is a human-review aid for brand/product decisions. This
preflight makes sure the editable CSV and the visual contact sheet are still
aligned before an operator applies review decisions. It never emits fixture ids,
brand text, product text, OCR text, provider payloads, image paths, or source
folder literals.

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

from scripts import apply_supplement_brand_batch_review_csv_decisions as csv_applier  # noqa: E402

SCHEMA_VERSION = "supplement-brand-review-contact-sheet-preflight-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-brand-review-contact-sheet-preflight-markdown-v1"
CONTACT_SHEET_SCHEMA = "supplement-brand-detail-contact-sheet-v1"
REQUIRED_CSV_COLUMNS = frozenset(
    {
        "fixture_id",
        "decision",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "reason_codes",
    }
)
UNSAFE_INPUT_KEYS = frozenset(
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
        "request_headers",
        "secret",
        "service_key",
        "signed_url",
        "url",
    }
)
UNSAFE_PUBLIC_MARKERS = (
    "brand_candidate_display_name",
    "category_display_name",
    "fixture_id",
    "reviewed_manufacturer",
    "reviewed_product_name",
    "source_product_id",
    "thumbnail_filenames",
)
UNSAFE_TRUE_FLAGS = (
    "auto_decision_performed",
    "db_import_allowed",
    "db_write_allowed",
    "db_write_performed",
    "external_provider_call_performed",
    "llm_call_performed",
    "ocr_provider_call_performed",
    "paddleocr_training_performed",
)
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/csv.html",
    "https://docs.python.org/3/library/json.html",
    "https://docs.python.org/3/library/pathlib.html",
    "https://pillow.readthedocs.io/en/stable/reference/Image.html",
)


class BrandReviewContactSheetPreflightError(ValueError):
    """Raised when brand review contact sheet inputs cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional test argument list.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-review-csv", type=Path, required=True)
    parser.add_argument("--contact-sheet-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--require-all-rows-with-thumbnails", action="store_true")
    parser.add_argument("--max-row-hints", type=int, default=50)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write contact sheet preflight JSON and optional Markdown.

    Args:
        argv: Optional test argument list.
    """
    args = parse_args(argv)
    input_paths = {
        "batch_review_csv": args.batch_review_csv.expanduser().resolve(),
        "contact_sheet_summary": args.contact_sheet_summary.expanduser().resolve(),
    }
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = preflight_brand_review_contact_sheet(
            input_paths=input_paths,
            require_all_rows_with_thumbnails=args.require_all_rows_with_thumbnails,
            max_row_hints=args.max_row_hints,
        )
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
        if summary["status"] != "passed":
            raise SystemExit(1)
    except (
        OSError,
        csv.Error,
        json.JSONDecodeError,
        BrandReviewContactSheetPreflightError,
        ValueError,
    ) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def preflight_brand_review_contact_sheet(
    *,
    input_paths: Mapping[str, Path],
    require_all_rows_with_thumbnails: bool = False,
    max_row_hints: int = 50,
) -> dict[str, Any]:
    """Return a redacted CSV/contact-sheet alignment summary.

    Args:
        input_paths: Mapping containing ``batch_review_csv`` and
            ``contact_sheet_summary`` paths.
        require_all_rows_with_thumbnails: Whether zero-thumbnail rows should
            fail preflight.
        max_row_hints: Maximum redacted row-index hints to include.

    Returns:
        Redacted preflight summary.

    Raises:
        BrandReviewContactSheetPreflightError: If inputs are malformed or
            contain unsafe values.
    """
    if max_row_hints < 0:
        raise BrandReviewContactSheetPreflightError("max_row_hints must be nonnegative.")
    review_csv = _required_input(input_paths, "batch_review_csv")
    contact_summary_path = _required_input(input_paths, "contact_sheet_summary")
    csv_rows = _read_csv_rows(review_csv)
    contact_summary = _load_contact_summary(contact_summary_path)
    contact_rows = _contact_rows(contact_summary)

    issue_counts: Counter[str] = Counter()
    row_issues: defaultdict[int, set[str]] = defaultdict(set)
    _check_summary_contract(
        summary=contact_summary,
        review_csv_name=review_csv.name,
        csv_row_count=len(csv_rows),
        contact_row_count=len(contact_rows),
        issue_counts=issue_counts,
    )
    _check_execution_flags(
        summary=contact_summary,
        contact_rows=contact_rows,
        issue_counts=issue_counts,
        row_issues=row_issues,
    )
    _check_row_alignment(
        csv_rows=csv_rows,
        contact_rows=contact_rows,
        issue_counts=issue_counts,
        row_issues=row_issues,
    )
    _check_thumbnail_coverage(
        summary=contact_summary,
        contact_rows=contact_rows,
        require_all_rows_with_thumbnails=require_all_rows_with_thumbnails,
        issue_counts=issue_counts,
        row_issues=row_issues,
    )
    row_hints = _row_hints(row_issues=row_issues, max_row_hints=max_row_hints)
    status = "passed" if not issue_counts else "failed"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_fingerprints": {
            key: _path_fingerprint(path) for key, path in sorted(input_paths.items())
        },
        "batch_review_csv_name": _safe_filename(review_csv.name),
        "contact_sheet_summary_name": _safe_filename(contact_summary_path.name),
        "contact_sheet_schema_version": CONTACT_SHEET_SCHEMA,
        "row_count": len(csv_rows),
        "contact_row_count": len(contact_rows),
        "reviewable_row_count": _non_negative_int(contact_summary.get("reviewable_row_count")),
        "rows_with_thumbnails": _non_negative_int(contact_summary.get("rows_with_thumbnails")),
        "rows_without_thumbnails": _non_negative_int(
            contact_summary.get("rows_without_thumbnails")
        ),
        "thumbnail_count": _non_negative_int(contact_summary.get("thumbnail_count")),
        "require_all_rows_with_thumbnails": bool(require_all_rows_with_thumbnails),
        "issue_counts": dict(sorted(issue_counts.items())),
        "row_hints_truncated": len(row_hints) < len(row_issues),
        "row_hints": row_hints,
        "operator_next_steps": _operator_next_steps(status=status, issue_counts=issue_counts),
        "automatic_decision_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed_by_preflight": False,
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
    """Build a redacted Markdown preflight report.

    Args:
        summary: Preflight summary.

    Returns:
        Markdown text.
    """
    _reject_public_payload(summary)
    markdown = "\n".join(
        [
            "# Supplement Brand Review Contact Sheet Preflight",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 brand review CSV와 contact sheet summary의 정합성만 검증합니다.",
            "제품명, 브랜드명, fixture id, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로는 포함하지 않습니다.",
            "",
            "## Status",
            "",
            f"- Status: `{_safe_token(str(summary.get('status') or 'failed'))}`",
            f"- CSV rows: `{_non_negative_int(summary.get('row_count'))}`",
            f"- Contact rows: `{_non_negative_int(summary.get('contact_row_count'))}`",
            f"- Rows with thumbnails: `{_non_negative_int(summary.get('rows_with_thumbnails'))}`",
            f"- Rows without thumbnails: `{_non_negative_int(summary.get('rows_without_thumbnails'))}`",
            f"- Thumbnail count: `{_non_negative_int(summary.get('thumbnail_count'))}`",
            "",
            "## Issue Counts",
            "",
            _markdown_mapping(summary.get("issue_counts")),
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
            "이 preflight가 통과해도 brand/product 결정은 자동 완료되지 않습니다. operator가 CSV decision을 채운 뒤 strict brand review preflight를 다시 통과해야 DB import manifest를 만들 수 있습니다.",
            "",
        ]
    )
    _reject_public_payload(markdown)
    return markdown


def _check_summary_contract(
    *,
    summary: Mapping[str, Any],
    review_csv_name: str,
    csv_row_count: int,
    contact_row_count: int,
    issue_counts: Counter[str],
) -> None:
    """Check top-level contact sheet metadata.

    Args:
        summary: Contact sheet summary.
        review_csv_name: Actual review CSV file name.
        csv_row_count: CSV row count.
        contact_row_count: Contact row count.
        issue_counts: Mutable issue counter.
    """
    if _safe_filename(str(summary.get("review_csv_name") or "")) != _safe_filename(review_csv_name):
        issue_counts["review_csv_name_mismatch"] += 1
    reviewable_count = _non_negative_int(summary.get("reviewable_row_count"))
    if reviewable_count != contact_row_count:
        issue_counts["contact_reviewable_count_mismatch"] += 1
    if csv_row_count != contact_row_count:
        issue_counts["csv_contact_row_count_mismatch"] += 1
    if csv_row_count != reviewable_count:
        issue_counts["csv_reviewable_count_mismatch"] += 1


def _check_execution_flags(
    *,
    summary: Mapping[str, Any],
    contact_rows: Sequence[Mapping[str, Any]],
    issue_counts: Counter[str],
    row_issues: defaultdict[int, set[str]],
) -> None:
    """Check no unsafe automatic execution was performed.

    Args:
        summary: Contact sheet summary.
        contact_rows: Contact sheet rows.
        issue_counts: Mutable issue counter.
        row_issues: Mutable row-index issue mapping.
    """
    for flag in UNSAFE_TRUE_FLAGS:
        if summary.get(flag) is True:
            issue_counts[f"{flag}_true"] += 1
    if summary.get("full_size_source_images_copied") is True:
        issue_counts["full_size_source_images_copied_true"] += 1
    for expected_index, row in enumerate(contact_rows, start=1):
        row_index = _contact_row_index(row, fallback=expected_index)
        if row.get("auto_decision_performed") is True:
            issue_counts["row_auto_decision_true"] += 1
            row_issues[row_index].add("row_auto_decision_true")
        if row.get("db_write_allowed") is True:
            issue_counts["row_db_write_allowed_true"] += 1
            row_issues[row_index].add("row_db_write_allowed_true")


def _check_row_alignment(
    *,
    csv_rows: Sequence[Mapping[str, str]],
    contact_rows: Sequence[Mapping[str, Any]],
    issue_counts: Counter[str],
    row_issues: defaultdict[int, set[str]],
) -> None:
    """Check fixture set and order alignment without emitting fixture ids.

    Args:
        csv_rows: Review CSV rows.
        contact_rows: Contact sheet rows.
        issue_counts: Mutable issue counter.
        row_issues: Mutable row-index issue mapping.
    """
    csv_ids = [_safe_fixture_id(row.get("fixture_id")) for row in csv_rows]
    contact_ids = [_safe_fixture_id(row.get("fixture_id")) for row in contact_rows]
    for row_index, issue in _duplicate_row_issues(csv_ids).items():
        issue_counts["duplicate_csv_fixture_id"] += 1
        row_issues[row_index].add(issue)
    for row_index, issue in _duplicate_row_issues(contact_ids).items():
        issue_counts["duplicate_contact_fixture_id"] += 1
        row_issues[row_index].add(issue)
    csv_id_set = set(csv_ids)
    contact_id_set = set(contact_ids)
    missing_from_contact = csv_id_set - contact_id_set
    extra_in_contact = contact_id_set - csv_id_set
    if missing_from_contact:
        issue_counts["missing_contact_fixture"] += len(missing_from_contact)
        for row_index, fixture_id in enumerate(csv_ids, start=1):
            if fixture_id in missing_from_contact:
                row_issues[row_index].add("missing_contact_fixture")
    if extra_in_contact:
        issue_counts["extra_contact_fixture"] += len(extra_in_contact)
        for row_index, fixture_id in enumerate(contact_ids, start=1):
            if fixture_id in extra_in_contact:
                row_issues[row_index].add("extra_contact_fixture")
    for expected_index, row in enumerate(contact_rows, start=1):
        if _contact_row_index(row, fallback=0) != expected_index:
            issue_counts["contact_row_index_mismatch"] += 1
            row_issues[expected_index].add("contact_row_index_mismatch")
    for row_index, (csv_id, contact_id) in enumerate(
        zip(csv_ids, contact_ids, strict=False), start=1
    ):
        if csv_id != contact_id:
            issue_counts["fixture_order_mismatch"] += 1
            row_issues[row_index].add("fixture_order_mismatch")


def _check_thumbnail_coverage(
    *,
    summary: Mapping[str, Any],
    contact_rows: Sequence[Mapping[str, Any]],
    require_all_rows_with_thumbnails: bool,
    issue_counts: Counter[str],
    row_issues: defaultdict[int, set[str]],
) -> None:
    """Check contact sheet thumbnail coverage.

    Args:
        summary: Contact sheet summary.
        contact_rows: Contact sheet rows.
        require_all_rows_with_thumbnails: Whether missing thumbnails fail.
        issue_counts: Mutable issue counter.
        row_issues: Mutable row-index issue mapping.
    """
    row_thumbnail_count = 0
    rows_without_thumbnails = 0
    for expected_index, row in enumerate(contact_rows, start=1):
        row_index = _contact_row_index(row, fallback=expected_index)
        thumbnail_count = _non_negative_int(row.get("thumbnail_count"))
        row_thumbnail_count += thumbnail_count
        if thumbnail_count == 0:
            rows_without_thumbnails += 1
            row_issues[row_index].add("row_without_thumbnail")
    if row_thumbnail_count != _non_negative_int(summary.get("thumbnail_count")):
        issue_counts["thumbnail_count_mismatch"] += 1
    if rows_without_thumbnails != _non_negative_int(summary.get("rows_without_thumbnails")):
        issue_counts["rows_without_thumbnails_mismatch"] += 1
    if require_all_rows_with_thumbnails and rows_without_thumbnails:
        issue_counts["required_thumbnail_missing"] += rows_without_thumbnails


def _row_hints(
    *,
    row_issues: Mapping[int, set[str]],
    max_row_hints: int,
) -> list[dict[str, Any]]:
    """Return bounded redacted row hints.

    Args:
        row_issues: Row-index issue mapping.
        max_row_hints: Maximum rows to include.

    Returns:
        Row hint list.
    """
    return [
        {"row_index": row_index, "issue_codes": sorted(issues)}
        for row_index, issues in sorted(row_issues.items())
        if issues
    ][:max_row_hints]


def _operator_next_steps(*, status: str, issue_counts: Mapping[str, int]) -> list[str]:
    """Return safe operator next-step tokens.

    Args:
        status: Preflight status.
        issue_counts: Aggregate issue counts.

    Returns:
        Next-step tokens.
    """
    if status == "passed":
        return [
            "continue_operator_brand_product_review",
            "run_csv_apply_after_review_decisions_are_filled",
            "run_strict_brand_review_preflight_before_db_manifest",
        ]
    steps = ["regenerate_contact_sheet_or_review_csv_before_apply"]
    if issue_counts.get("required_thumbnail_missing", 0):
        steps.append("rebuild_contact_sheet_with_missing_thumbnail_rows")
    if issue_counts.get("fixture_order_mismatch", 0):
        steps.append("do_not_apply_csv_until_fixture_order_matches_contact_sheet")
    return steps


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read review CSV rows with unsafe column and path checks.

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
                raise BrandReviewContactSheetPreflightError("Batch review CSV is missing a header.")
            _validate_csv_columns(fieldnames)
            rows = []
            for row in reader:
                _reject_unsafe_csv_row(row)
                rows.append({key: value or "" for key, value in row.items()})
    except OSError as exc:
        raise BrandReviewContactSheetPreflightError(
            "Batch review CSV is missing or unreadable."
        ) from exc
    if not rows:
        raise BrandReviewContactSheetPreflightError("Batch review CSV is empty.")
    return rows


def _load_contact_summary(path: Path) -> dict[str, Any]:
    """Load contact sheet summary.

    Args:
        path: Contact summary JSON path.

    Returns:
        Contact summary mapping.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BrandReviewContactSheetPreflightError("Contact sheet summary must be a JSON object.")
    if payload.get("schema_version") != CONTACT_SHEET_SCHEMA:
        raise BrandReviewContactSheetPreflightError("Unsupported contact sheet summary schema.")
    _reject_unsafe_input_payload(payload)
    return payload


def _contact_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return contact rows.

    Args:
        summary: Contact sheet summary.

    Returns:
        Contact row mappings.
    """
    rows = summary.get("contact_rows")
    if not isinstance(rows, list):
        raise BrandReviewContactSheetPreflightError("Contact sheet summary is missing rows.")
    for row in rows:
        if not isinstance(row, Mapping):
            raise BrandReviewContactSheetPreflightError("Contact sheet row must be an object.")
    return rows


def _validate_csv_columns(fieldnames: list[str]) -> None:
    """Validate review CSV headers.

    Args:
        fieldnames: CSV header names.
    """
    normalized = {field.strip() for field in fieldnames}
    missing = sorted(REQUIRED_CSV_COLUMNS - normalized)
    if missing:
        raise BrandReviewContactSheetPreflightError(
            "Batch review CSV is missing a required column."
        )
    for fieldname in fieldnames:
        if fieldname.strip().casefold() in UNSAFE_INPUT_KEYS:
            raise BrandReviewContactSheetPreflightError(
                "Unsafe raw/provider key found in review CSV."
            )


def _reject_unsafe_csv_row(row: Mapping[str, str | None]) -> None:
    """Reject local paths and URLs in CSV cells.

    Args:
        row: CSV row.
    """
    for value in row.values():
        if value and any(
            marker in value for marker in csv_applier.applier.LOCAL_PATH_OR_URL_MARKERS
        ):
            raise BrandReviewContactSheetPreflightError(
                "Unsafe local path or URL marker found in review CSV."
            )


def _reject_unsafe_input_payload(value: Any) -> None:
    """Reject unsafe raw payload keys or local paths in an input object.

    Args:
        value: JSON-like input payload.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key.casefold() in UNSAFE_INPUT_KEYS:
                raise BrandReviewContactSheetPreflightError("Unsafe raw/provider key found.")
            if key == "source_doc_urls":
                _validate_source_doc_urls(item)
                continue
            _reject_unsafe_input_payload(item)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_input_payload(item)
    elif isinstance(value, str) and any(
        marker in value for marker in csv_applier.applier.LOCAL_PATH_OR_URL_MARKERS
    ):
        raise BrandReviewContactSheetPreflightError("Unsafe local path or URL marker found.")


def _validate_source_doc_urls(value: Any) -> None:
    """Validate official documentation URLs carried by prior artifacts.

    Args:
        value: Candidate URL list.
    """
    if not isinstance(value, list):
        raise BrandReviewContactSheetPreflightError("source_doc_urls must be a list.")
    allowed = set(SOURCE_DOC_URLS)
    for item in value:
        if item not in allowed:
            raise BrandReviewContactSheetPreflightError("Unexpected source documentation URL.")


def _reject_public_payload(value: Any) -> None:
    """Reject unsafe public summary or Markdown payloads.

    Args:
        value: Public payload.
    """
    try:
        csv_applier._reject_unsafe_payload(value)
    except ValueError as exc:
        raise BrandReviewContactSheetPreflightError(str(exc)) from exc
    dumped = (
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        if not isinstance(value, str)
        else value
    )
    if any(marker in dumped for marker in UNSAFE_PUBLIC_MARKERS):
        raise BrandReviewContactSheetPreflightError(
            "Public payload contains contact sheet row text."
        )


def _duplicate_row_issues(values: Sequence[str]) -> dict[int, str]:
    """Return duplicate row-index issue mapping.

    Args:
        values: Safe fixture id values.

    Returns:
        Mapping of duplicate row index to issue code.
    """
    counts = Counter(values)
    return {
        row_index: "duplicate_fixture_id"
        for row_index, value in enumerate(values, start=1)
        if counts[value] > 1
    }


def _contact_row_index(row: Mapping[str, Any], *, fallback: int) -> int:
    """Return safe contact row index.

    Args:
        row: Contact row.
        fallback: Fallback index.

    Returns:
        Positive row index.
    """
    row_index = _non_negative_int(row.get("row_index"))
    return row_index if row_index > 0 else fallback


def _safe_fixture_id(value: Any) -> str:
    """Return safe fixture id.

    Args:
        value: Candidate fixture id.

    Returns:
        Fixture id token.
    """
    try:
        return csv_applier.applier._required_safe_token(value, field_name="fixture_id")
    except ValueError as exc:
        raise BrandReviewContactSheetPreflightError("Unsafe fixture token found.") from exc


def _safe_filename(value: str) -> str:
    """Return safe filename.

    Args:
        value: Candidate filename.

    Returns:
        Safe filename.
    """
    return csv_applier.batch_preflight._safe_filename(value)


def _safe_token(value: str) -> str:
    """Return safe token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    return csv_applier.applier._required_safe_token(value, field_name="token")


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
    """Return row hints as Markdown.

    Args:
        value: Candidate row hints.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, list) or not value:
        return "- none"
    lines = []
    for item in value:
        if not isinstance(item, Mapping):
            raise BrandReviewContactSheetPreflightError("Expected row hint mapping.")
        issue_codes = ", ".join(_safe_token(str(code)) for code in item.get("issue_codes", []))
        lines.append(
            f"- row `{_non_negative_int(item.get('row_index'))}`: `{issue_codes or 'unknown'}`"
        )
    return "\n".join(lines)


def _markdown_list(value: Any) -> str:
    """Return a Markdown token list.

    Args:
        value: Candidate list.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, list) or not value:
        return "- none"
    return "\n".join(f"- `{_safe_token(str(item))}`" for item in value)


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return one required input path.

    Args:
        input_paths: Input path mapping.
        key: Required key.

    Returns:
        Existing file path.
    """
    path = input_paths.get(key)
    if path is None or not path.is_file():
        raise BrandReviewContactSheetPreflightError("Required preflight input is missing.")
    return path


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for local artifact identity.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _path_fingerprint(path: Path) -> str:
    """Return a short non-secret path fingerprint for public artifacts.

    Args:
        path: Path to identify without exposing it.

    Returns:
        Short hexadecimal fingerprint.
    """
    return f"fp-{_sha256_text(str(path.expanduser()))[:8]}"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON payload.

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
        Failure payload.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_fingerprints": {
            key: _path_fingerprint(path) for key, path in sorted(input_paths.items())
        },
        "output_name": _safe_filename(output_path.name),
        "output_fingerprint": _path_fingerprint(output_path),
        "error_code": _safe_error_code(error),
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed_by_preflight": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_public_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a public-safe error code.

    Args:
        error: Raised exception.

    Returns:
        Error code token.
    """
    text = str(error).casefold()
    if "unsafe" in text:
        return "unsafe_input"
    if "missing" in text:
        return "missing_input"
    if "schema" in text:
        return "schema_mismatch"
    return "validation_error"


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI summary.

    Args:
        summary: Preflight summary.

    Returns:
        CLI-safe summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary.get("status"),
        "row_count": _non_negative_int(summary.get("row_count")),
        "contact_row_count": _non_negative_int(summary.get("contact_row_count")),
        "issue_counts": summary.get("issue_counts"),
        "db_write_performed": False,
    }


if __name__ == "__main__":
    main()
