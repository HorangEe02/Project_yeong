"""Extract reviewed supplement brand decisions from a mixed operator queue.

Operator batch reconciliation can produce a queue-level decision JSONL that
still contains untouched blank stubs for batches that have not been reviewed.
This tool writes a reviewed-only JSONL copy so partial manifest previews can run
without weakening the strict DB-import gate. Blank stubs are counted and ignored;
non-blank invalid rows still fail closed.

The script does not write to the database and never emits local absolute paths,
product directory literals, raw OCR text, provider payloads, or image bytes.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
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

from scripts import apply_supplement_brand_review_decisions as applier  # noqa: E402
from scripts import preflight_supplement_brand_review_decisions as preflight  # noqa: E402

SCHEMA_VERSION = "supplement-brand-reviewed-decision-extract-v1"
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-staging", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write reviewed-only brand decision rows and a redacted summary.

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
        rows, summary = extract_reviewed_brand_decisions(
            taxonomy_staging=args.taxonomy_staging,
            decisions_path=args.decisions,
        )
        applier._reject_unsafe_payload({"rows": rows, "summary": summary})
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
            taxonomy_staging=args.taxonomy_staging,
            decisions_path=args.decisions,
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


def extract_reviewed_brand_decisions(
    *,
    taxonomy_staging: Path,
    decisions_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return non-blank reviewed decision rows from a mixed queue.

    Args:
        taxonomy_staging: Taxonomy DB staging JSONL.
        decisions_path: Operator decision JSONL that may include blank stubs.

    Returns:
        Reviewed decision rows and redacted summary.

    Raises:
        ValueError: If a non-blank row is invalid, duplicated, or stale.
    """
    candidates = applier._brand_candidates_by_fixture_id(
        applier._read_jsonl_objects(taxonomy_staging)
    )
    candidate_ids = set(candidates)
    seen_fixture_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()
    blank_count = 0
    unmatched_count = 0

    for row in applier._read_jsonl_objects(decisions_path):
        fixture_id = applier._required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        if fixture_id in seen_fixture_ids:
            raise ValueError(f"Duplicate supplement brand decision fixture_id: {fixture_id}")
        seen_fixture_ids.add(fixture_id)
        if fixture_id not in candidate_ids:
            unmatched_count += 1
            raise ValueError("Brand review fixture_id is not in taxonomy staging.")
        if row.get("schema_version") not in {None, applier.DECISION_SCHEMA_VERSION}:
            raise ValueError("Supplement brand review decision row uses an unsupported schema.")
        decision = row.get("brand_review_decision")
        if not isinstance(decision, dict):
            raise ValueError("Brand review rows require brand_review_decision object.")
        if preflight._decision_is_blank(decision):
            blank_count += 1
            decision_counts["blank"] += 1
            continue
        applier._validate_decision(decision)
        decision_value = applier._required_safe_token(
            decision.get("decision"), field_name="decision"
        )
        decision_counts[decision_value] += 1
        rows.append(dict(row))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_hash": _fingerprint_text(str(taxonomy_staging.expanduser())),
        "decisions_name": decisions_path.name,
        "decisions_hash": _fingerprint_text(str(decisions_path.expanduser())),
        "brand_candidate_count": len(candidates),
        "input_decision_row_count": len(seen_fixture_ids),
        "reviewed_decision_count": len(rows),
        "blank_decision_ignored_count": blank_count,
        "unmatched_decision_count": unmatched_count,
        "decision_counts": dict(sorted(decision_counts.items())),
        "ready_for_partial_apply": bool(rows) and unmatched_count == 0,
        "ready_for_strict_apply": bool(rows) and blank_count == 0 and len(rows) == len(candidates),
        "output_rows_written": len(rows),
        "db_write_performed": False,
        "approved_for_db_write_rows": 0,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    applier._reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _failure_summary(
    *,
    taxonomy_staging: Path,
    decisions_path: Path,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted CLI failure summary.

    Args:
        taxonomy_staging: Staging JSONL path.
        decisions_path: Decision JSONL path.
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "taxonomy_staging_name": taxonomy_staging.name,
        "decisions_name": decisions_path.name,
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_error_message(error),
        "reviewed_decision_count": 0,
        "output_rows_written": 0,
        "approved_for_db_write_rows": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    applier._reject_unsafe_payload(summary)
    return summary


def _fingerprint_text(value: str) -> str:
    """Return a short non-secret fingerprint for public summaries.

    Args:
        value: Text value to fingerprint.

    Returns:
        Stable short fingerprint.
    """
    return f"fp-{applier.staging.audit._sha256_text(value)[:12]}"


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    if isinstance(error, OSError):
        return "local_file_read_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_error_message(error: Exception) -> str:
    """Return a bounded public error message.

    Args:
        error: Raised exception.

    Returns:
        Redacted message.
    """
    if isinstance(error, OSError):
        return "Local file read failed."
    message = str(error).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in applier.LOCAL_PATH_OR_URL_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
