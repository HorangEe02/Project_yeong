"""Extract reviewed supplement PII decisions from a mixed operator queue.

Operator batch reconciliation can produce a queue-level decision JSONL that
still contains untouched blank stubs for batches that have not been reviewed.
This tool writes a reviewed-only JSONL copy so partial PII screening apply can
run without weakening the strict teacher-OCR transfer gate. Blank stubs are
counted and ignored; non-blank invalid rows still fail closed.

The script does not read image bytes, does not run OCR, does not call external
providers, does not write to the database, and never emits local absolute paths,
product directory literals, raw OCR text, provider payloads, or image bytes.

References:
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import apply_supplement_review_pii_screening_decisions as applier  # noqa: E402
from scripts import export_supplement_review_pii_screening_template as template  # noqa: E402
from scripts import preflight_supplement_review_pii_screening_decisions as preflight  # noqa: E402

SCHEMA_VERSION = "supplement-pii-reviewed-decision-extract-v1"
SOURCE_DOC_URLS = template.SOURCE_DOC_URLS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
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
    """Write reviewed-only PII decision rows and a redacted summary.

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
        rows, summary = extract_reviewed_pii_decisions(
            candidate_manifest=args.candidate_manifest,
            decisions_path=args.decisions,
        )
        _reject_unsafe_output(rows=rows, summary=summary)
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


def extract_reviewed_pii_decisions(
    *,
    candidate_manifest: Path,
    decisions_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return non-blank reviewed PII decision rows from a mixed queue.

    Args:
        candidate_manifest: Supplement review OCR candidate JSONL.
        decisions_path: Operator decision JSONL that may include blank stubs.

    Returns:
        Reviewed decision rows and redacted summary.

    Raises:
        ValueError: If a non-blank row is invalid, duplicated, or stale.
    """
    candidates = applier._read_candidate_rows(candidate_manifest)
    candidate_ids = {
        applier._required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        for row in candidates
    }
    seen_fixture_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()
    blank_count = 0
    cleared_count = 0
    blocked_count = 0
    unmatched_count = 0

    for row in _read_jsonl_objects(decisions_path):
        fixture_id = applier._required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        if fixture_id in seen_fixture_ids:
            raise ValueError(f"Duplicate supplement PII decision fixture_id: {fixture_id}")
        seen_fixture_ids.add(fixture_id)
        if fixture_id not in candidate_ids:
            unmatched_count += 1
            raise ValueError("PII decision fixture_id is not in candidate manifest.")
        if row.get("schema_version") not in {None, applier.DECISION_SCHEMA_VERSION}:
            raise ValueError("Supplement PII decision row uses an unsupported schema.")
        decision = row.get("pii_screening_decision")
        if not isinstance(decision, dict):
            raise ValueError("PII screening rows require pii_screening_decision object.")
        if preflight._decision_is_blank(decision):
            blank_count += 1
            decision_counts["blank"] += 1
            continue
        applier._validate_decision(decision)
        decision_value = applier._required_safe_token(
            decision.get("decision"), field_name="decision"
        )
        decision_counts[decision_value] += 1
        if decision_value == "cleared_no_personal_data":
            cleared_count += 1
        else:
            blocked_count += 1
        rows.append(dict(row))

    missing_decision_count = len(candidate_ids - seen_fixture_ids)
    reviewed_count = len(rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_manifest_name": candidate_manifest.name,
        "candidate_manifest_hash": _sha256_text(str(candidate_manifest.expanduser())),
        "decisions_name": decisions_path.name,
        "decisions_hash": _sha256_text(str(decisions_path.expanduser())),
        "candidate_row_count": len(candidates),
        "input_decision_row_count": len(seen_fixture_ids),
        "reviewed_decision_count": reviewed_count,
        "cleared_no_personal_data_count": cleared_count,
        "blocked_decision_count": blocked_count,
        "blank_decision_ignored_count": blank_count,
        "missing_decision_count": missing_decision_count,
        "unmatched_decision_count": unmatched_count,
        "decision_counts": dict(sorted(decision_counts.items())),
        "ready_for_partial_apply": reviewed_count > 0 and unmatched_count == 0,
        "ready_for_strict_apply": (
            reviewed_count > 0
            and blank_count == 0
            and missing_decision_count == 0
            and reviewed_count == len(candidates)
        ),
        "output_rows_written": reviewed_count,
        "db_write_performed": False,
        "approved_for_db_write_rows": 0,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_output(rows=rows, summary=summary)
    return rows, summary


def _reject_unsafe_output(*, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    """Reject unsafe row and summary payloads except explicit doc citations.

    Args:
        rows: Reviewed decision rows.
        summary: Redacted summary payload.
    """
    checked_summary = {key: value for key, value in summary.items() if key != "source_doc_urls"}
    applier._reject_unsafe_payload({"rows": rows, "summary": checked_summary})


def _sha256_text(value: str) -> str:
    """Return the SHA-256 hash for a string.

    Args:
        value: Text to hash.

    Returns:
        Hex encoded SHA-256 digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    """Read JSONL objects from disk.

    Args:
        path: JSONL input path.

    Returns:
        Parsed object rows.

    Raises:
        ValueError: If a row is not a JSON object.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("Decision JSONL rows must be objects.")
        applier._reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _failure_summary(
    *,
    candidate_manifest: Path,
    decisions_path: Path,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted CLI failure summary.

    Args:
        candidate_manifest: Candidate manifest path.
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
        "candidate_manifest_name": candidate_manifest.name,
        "decisions_name": decisions_path.name,
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_error_message(error),
        "reviewed_decision_count": 0,
        "output_rows_written": 0,
        "approved_for_db_write_rows": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    applier._reject_unsafe_payload(summary)
    return summary


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
    if "/" in message or "\\" in message:
        return "Validation failed."
    if any(marker in message for marker in applier.LOCAL_PATH_OR_URL_MARKERS):
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
