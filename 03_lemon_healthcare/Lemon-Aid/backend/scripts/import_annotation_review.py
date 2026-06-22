"""Import sanitized annotation review decisions into annotation tasks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import (  # noqa: E402
    RetrainingSecurityError,
    validate_sanitized_label_snapshot,
)
from src.models.db.retraining import AnnotationTask  # noqa: E402

SUMMARY_SCHEMA_VERSION = "annotation-review-import-summary-v1"
MAX_IMPORT_RECORDS = 500
REVIEWER_HASH_LENGTH = 64
ALLOWED_DECISIONS = frozenset({"accept", "reject"})
UPDATABLE_TASK_STATUSES = frozenset({"pending", "in_review"})
REVIEW_NOTES_CODE_PATTERN = re.compile(r"^[a-z0-9_]{1,80}$")


@dataclass(frozen=True)
class AnnotationReviewDecision:
    """One sanitized annotation review decision.

    Attributes:
        annotation_task_id: Annotation task id to update.
        decision: Review decision, either ``accept`` or ``reject``.
        label_snapshot: Sanitized label payload. Accepted decisions require a non-empty object.
        review_notes_code: Optional stable review note code.
        reviewer_hash: HMAC of the reviewer subject.
    """

    annotation_task_id: UUID
    decision: str
    label_snapshot: dict[str, Any]
    review_notes_code: str | None
    reviewer_hash: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, import decisions, and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    input_path = args.input.expanduser().resolve()
    try:
        decisions = load_annotation_review_decisions(input_path)
        summary = await import_annotation_review_decisions(decisions)
    except (OSError, RetrainingSecurityError, ValueError) as exc:
        summary = _failure_summary(input_path=input_path, error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def load_annotation_review_decisions(input_path: Path) -> list[AnnotationReviewDecision]:
    """Load and validate annotation review decisions from JSONL.

    Args:
        input_path: JSONL file path.

    Returns:
        Validated decisions.

    Raises:
        ValueError: If the file shape or decision payload is invalid.
        RetrainingSecurityError: If labels contain raw data, paths, URLs, or secrets.
    """
    decisions: list[AnnotationReviewDecision] = []
    seen_task_ids: set[UUID] = set()
    for line_number, raw_line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        if len(decisions) >= MAX_IMPORT_RECORDS:
            raise ValueError("Annotation review import limit exceeded.")
        record = _parse_json_object(raw_line, line_number=line_number)
        decision = _decision_from_record(record, line_number=line_number)
        if decision.annotation_task_id in seen_task_ids:
            raise ValueError("Duplicate annotation task decision.")
        seen_task_ids.add(decision.annotation_task_id)
        decisions.append(decision)
    if not decisions:
        raise ValueError("Annotation review import file is empty.")
    return decisions


async def import_annotation_review_decisions(
    decisions: Sequence[AnnotationReviewDecision],
) -> dict[str, object]:
    """Apply validated annotation review decisions in one commit.

    Args:
        decisions: Validated annotation review decisions.

    Returns:
        Sanitized import summary.

    Raises:
        ValueError: If a task is missing or not updateable.
    """
    if not decisions:
        raise ValueError("At least one annotation review decision is required.")
    if len(decisions) > MAX_IMPORT_RECORDS:
        raise ValueError("Annotation review import limit exceeded.")

    sessionmaker = get_sessionmaker()
    accepted_count = 0
    rejected_count = 0
    async with sessionmaker() as session:
        tasks_by_id: dict[UUID, AnnotationTask] = {}
        for decision in decisions:
            task = await session.get(AnnotationTask, decision.annotation_task_id)
            if task is None:
                raise ValueError("Annotation task was not found.")
            if task.status not in UPDATABLE_TASK_STATUSES:
                raise ValueError("Annotation task is not updateable.")
            tasks_by_id[decision.annotation_task_id] = task

        completed_at = datetime.now(UTC)
        for decision in decisions:
            task = tasks_by_id[decision.annotation_task_id]
            if decision.decision == "accept":
                task.status = "accepted"
                accepted_count += 1
            else:
                task.status = "rejected"
                rejected_count += 1
            task.label_snapshot = decision.label_snapshot
            task.review_notes_code = decision.review_notes_code
            task.reviewer_hash = decision.reviewer_hash
            task.completed_at = completed_at
        await session.commit()

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "record_count": len(decisions),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "label_snapshot_printed": False,
        "reviewer_hash_printed": False,
        "media_ref_printed": False,
        "raw_payload_printed": False,
    }


def _parse_json_object(raw_line: str, *, line_number: int) -> dict[str, Any]:
    """Parse one JSONL object.

    Args:
        raw_line: Raw JSON line.
        line_number: One-based line number.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If the line is not a JSON object.
    """
    try:
        record = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Line {line_number} must be valid JSON.") from exc
    if not isinstance(record, dict):
        raise ValueError(f"Line {line_number} must be a JSON object.")
    return record


def _decision_from_record(
    record: Mapping[str, Any],
    *,
    line_number: int,
) -> AnnotationReviewDecision:
    """Validate and normalize one decision record.

    Args:
        record: Parsed decision record.
        line_number: One-based line number.

    Returns:
        Validated annotation review decision.

    Raises:
        ValueError: If required fields are missing or malformed.
        RetrainingSecurityError: If label snapshot is unsafe.
    """
    annotation_task_id = _required_uuid(record, "annotation_task_id", line_number=line_number)
    decision = _required_string(record, "decision", line_number=line_number)
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"Line {line_number} has unsupported decision.")
    reviewer_hash = _required_string(record, "reviewer_hash", line_number=line_number)
    if len(reviewer_hash) != REVIEWER_HASH_LENGTH:
        raise ValueError(f"Line {line_number} reviewer_hash must be 64 characters.")
    review_notes_code = _optional_review_notes_code(record.get("review_notes_code"), line_number)
    raw_label_snapshot = record.get("label_snapshot", {})
    if not isinstance(raw_label_snapshot, dict):
        raise ValueError(f"Line {line_number} label_snapshot must be an object.")
    label_snapshot = dict(raw_label_snapshot)
    validate_sanitized_label_snapshot(label_snapshot)
    if decision == "accept" and not label_snapshot:
        raise ValueError(f"Line {line_number} accepted decisions require label_snapshot.")
    if decision == "reject":
        label_snapshot = {}
    return AnnotationReviewDecision(
        annotation_task_id=annotation_task_id,
        decision=decision,
        label_snapshot=label_snapshot,
        review_notes_code=review_notes_code,
        reviewer_hash=reviewer_hash,
    )


def _required_uuid(record: Mapping[str, Any], key: str, *, line_number: int) -> UUID:
    """Return a required UUID field.

    Args:
        record: Parsed record.
        key: Field name.
        line_number: One-based line number.

    Returns:
        Parsed UUID.

    Raises:
        ValueError: If the field is missing or invalid.
    """
    raw_value = record.get(key)
    if not isinstance(raw_value, str):
        raise ValueError(f"Line {line_number} {key} must be a UUID string.")
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise ValueError(f"Line {line_number} {key} must be a UUID string.") from exc


def _required_string(record: Mapping[str, Any], key: str, *, line_number: int) -> str:
    """Return a required non-empty string field.

    Args:
        record: Parsed record.
        key: Field name.
        line_number: One-based line number.

    Returns:
        Stripped string value.

    Raises:
        ValueError: If the field is missing or empty.
    """
    raw_value = record.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError(f"Line {line_number} {key} must be a non-empty string.")
    return raw_value.strip()


def _optional_review_notes_code(raw_value: object, line_number: int) -> str | None:
    """Validate an optional stable review note code.

    Args:
        raw_value: Candidate review note code.
        line_number: One-based line number.

    Returns:
        Validated code or None.

    Raises:
        ValueError: If the code is not in the stable code format.
    """
    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not REVIEW_NOTES_CODE_PATTERN.fullmatch(raw_value):
        raise ValueError(f"Line {line_number} review_notes_code must be a stable code.")
    return raw_value


def _failure_summary(*, input_path: Path, error: BaseException) -> dict[str, object]:
    """Return a redacted failure summary.

    Args:
        input_path: Requested input path.
        error: Raised error.

    Returns:
        Summary without the raw input path or payload.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "input_name": input_path.name,
        "input_path_hash": hashlib.sha256(str(input_path).encode("utf-8")).hexdigest(),
        "error_type": type(error).__name__,
        "label_snapshot_printed": False,
        "reviewer_hash_printed": False,
        "media_ref_printed": False,
        "raw_payload_printed": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
