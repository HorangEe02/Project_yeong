"""Create PaddleOCR annotation tasks from improvement candidates.

This script bridges redacted PaddleOCR improvement candidate manifests into
pending human-review ``ocr_textline_label`` annotation tasks. It does not call
OCR providers and does not train PaddleOCR. File-only ``crawling-image`` rows
are skipped because annotation tasks must reference a retained private source
row through ``media:<uuid>`` or ``learning_image:<uuid>``.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
    https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import (  # noqa: E402
    RetrainingSecurityError,
    validate_sanitized_label_snapshot,
)
from src.models.db.learning import LearningImageObject  # noqa: E402
from src.models.db.media import MediaObject  # noqa: E402
from src.models.db.retraining import AnnotationTask  # noqa: E402

from scripts.build_paddleocr_improvement_candidates import (  # noqa: E402
    ROW_SCHEMA_VERSION as IMPROVEMENT_ROW_SCHEMA_VERSION,
)
from scripts.build_paddleocr_improvement_candidates import (  # noqa: E402
    _reject_unsafe_payload,
)

SUMMARY_SCHEMA_VERSION = "paddleocr-improvement-annotation-task-create-summary-v1"
LABEL_SNAPSHOT_SCHEMA_VERSION = "paddleocr-improvement-annotation-task-seed-v1"
ANNOTATION_TASK_TYPE = "ocr_textline_label"
DEFAULT_ASSIGNEE_ROLE = "data_reviewer"
DEFAULT_LIMIT = 500
MAX_LIMIT = 2000
OWNER_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
ACTIVE_TASK_STATUSES = frozenset({"pending", "in_review", "accepted"})
ALLOWED_ASSIGNEE_ROLES = frozenset({"operator", "nutrition_reviewer", "data_reviewer"})
TRAINABLE_TASK_TYPES = frozenset({"paddleocr_detection", "paddleocr_recognition"})
SUPPORTED_SOURCE_PREFIXES = ("media:", "learning_image:")
UNSUPPORTED_SOURCE_PREFIXES = ("crawling-image:",)
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html",
    "https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html",
)


@dataclass(frozen=True)
class _ResolvedSource:
    """DB-backed private source for an annotation task.

    Attributes:
        source_type: Source type token, either ``media`` or ``learning_image``.
        source_id: Source row id.
        owner_subject_hash: Source owner hash copied from the DB row.
    """

    source_type: str
    source_id: UUID
    owner_subject_hash: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--improvement-manifest", type=Path, required=True)
    parser.add_argument("--owner-subject-hash", required=True)
    parser.add_argument("--assignee-role", default=DEFAULT_ASSIGNEE_ROLE)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Run the CLI and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await create_paddleocr_annotation_tasks_from_improvement_candidates(
            improvement_manifest=args.improvement_manifest,
            owner_subject_hash=args.owner_subject_hash,
            assignee_role=args.assignee_role,
            limit=args.limit,
        )
    except (OSError, ValueError, json.JSONDecodeError, RetrainingSecurityError) as exc:
        summary = _failure_summary(
            improvement_manifest=args.improvement_manifest,
            error=exc,
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> None:
    """Run the CLI entrypoint.

    Args:
        argv: Optional argument list for tests.
    """
    raise SystemExit(asyncio.run(run_cli(argv)))


async def create_paddleocr_annotation_tasks_from_improvement_candidates(
    *,
    improvement_manifest: Path,
    owner_subject_hash: str,
    assignee_role: str = DEFAULT_ASSIGNEE_ROLE,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, object]:
    """Create pending OCR annotation tasks from improvement candidates.

    Args:
        improvement_manifest: JSONL candidate manifest from
            ``build_paddleocr_improvement_candidates.py``.
        owner_subject_hash: HMAC-SHA256 hash of the source owner. The raw owner
            subject must never be passed here.
        assignee_role: Reviewer role assigned to created tasks.
        limit: Maximum manifest rows to scan.

    Returns:
        Redacted creation summary.

    Raises:
        ValueError: If CLI parameters are invalid.
        RetrainingSecurityError: If any candidate label seed is unsafe.
    """
    _validate_args(owner_subject_hash=owner_subject_hash, assignee_role=assignee_role, limit=limit)
    rows = _read_jsonl(improvement_manifest)
    scanned_rows = rows[:limit]
    skip_reasons: Counter[str] = Counter()
    created_count = 0

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        for row in scanned_rows:
            try:
                _reject_unsafe_payload(row)
            except ValueError:
                skip_reasons["unsafe_candidate_payload"] += 1
                continue

            if row.get("schema_version") != IMPROVEMENT_ROW_SCHEMA_VERSION:
                skip_reasons["unsupported_schema_version"] += 1
                continue

            target_dataset_task_types = _target_dataset_task_types(row)
            if not target_dataset_task_types:
                skip_reasons["no_trainable_task"] += 1
                continue

            source_ref = row.get("source_ref")
            parsed_source = _parse_private_source_ref(source_ref)
            if parsed_source is None:
                skip_reasons["unsupported_source_ref"] += 1
                continue

            source = await _load_live_source(session=session, parsed_source=parsed_source)
            if source is None:
                skip_reasons["missing_or_inactive_source"] += 1
                continue
            if source.owner_subject_hash != owner_subject_hash:
                skip_reasons["owner_mismatch"] += 1
                continue

            if await _existing_active_task_exists(session=session, source=source):
                skip_reasons["existing_active_task"] += 1
                continue

            try:
                label_snapshot = _build_label_snapshot(
                    row=row,
                    target_dataset_task_types=target_dataset_task_types,
                )
                validate_sanitized_label_snapshot(label_snapshot)
            except (RetrainingSecurityError, ValueError):
                skip_reasons["rejected_label_snapshot"] += 1
                continue

            session.add(
                AnnotationTask(
                    owner_subject_hash=owner_subject_hash,
                    media_object_id=source.source_id if source.source_type == "media" else None,
                    learning_image_object_id=(
                        source.source_id if source.source_type == "learning_image" else None
                    ),
                    task_type=ANNOTATION_TASK_TYPE,
                    status="pending",
                    assignee_role=assignee_role,
                    label_snapshot=label_snapshot,
                    review_notes_code="paddleocr_improvement_candidate",
                    reviewer_hash=None,
                    completed_at=None,
                )
            )
            created_count += 1

        await session.commit()

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "improvement_manifest_name": improvement_manifest.name,
        "improvement_manifest_hash": _sha256_text(str(improvement_manifest.expanduser())),
        "input_candidate_count": len(rows),
        "scanned_count": len(scanned_rows),
        "created_count": created_count,
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "task_type": ANNOTATION_TASK_TYPE,
        "assignee_role": assignee_role,
        "requires_manual_review_before_training": True,
        "annotation_task_write_performed": created_count > 0,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "owner_subject_hash_printed": False,
        "source_ref_printed": False,
        "label_snapshot_printed": False,
        "expected_text_printed": False,
        "raw_payload_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _validate_args(*, owner_subject_hash: str, assignee_role: str, limit: int) -> None:
    """Validate task creation arguments.

    Args:
        owner_subject_hash: HMAC-SHA256 owner hash.
        assignee_role: Annotation task assignee role.
        limit: Maximum rows to scan.

    Raises:
        ValueError: If an argument is invalid.
    """
    if not OWNER_HASH_PATTERN.fullmatch(owner_subject_hash):
        raise ValueError("owner_subject_hash must be a 64-character hex digest.")
    if assignee_role not in ALLOWED_ASSIGNEE_ROLES:
        raise ValueError("assignee_role is not allowed.")
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError("limit must be between 1 and 2000.")


def _target_dataset_task_types(row: dict[str, Any]) -> list[str]:
    """Return safe PaddleOCR dataset task suggestions.

    Args:
        row: Candidate manifest row.

    Returns:
        Sorted list of trainable PaddleOCR task types.
    """
    suggestions = row.get("training_task_suggestions")
    if not isinstance(suggestions, list):
        return []
    return sorted(
        task_type
        for task_type in {str(value) for value in suggestions}
        if task_type in TRAINABLE_TASK_TYPES
    )


def _parse_private_source_ref(source_ref: object) -> tuple[str, UUID] | None:
    """Parse a DB-backed private source ref.

    Args:
        source_ref: Candidate source ref.

    Returns:
        Source type and id, or ``None`` for file-only/unsupported refs.
    """
    if not isinstance(source_ref, str):
        return None
    if source_ref.startswith(UNSUPPORTED_SOURCE_PREFIXES):
        return None
    for prefix in SUPPORTED_SOURCE_PREFIXES:
        if source_ref.startswith(prefix):
            try:
                source_id = UUID(source_ref.removeprefix(prefix))
            except ValueError:
                return None
            source_type = "media" if prefix == "media:" else "learning_image"
            return source_type, source_id
    return None


async def _load_live_source(
    *,
    session: Any,
    parsed_source: tuple[str, UUID],
) -> _ResolvedSource | None:
    """Load and validate a retained private source row.

    Args:
        session: Async DB session.
        parsed_source: Source type and id.

    Returns:
        Resolved source metadata, or ``None`` when unavailable.
    """
    source_type, source_id = parsed_source
    if source_type == "media":
        media_object = await session.get(MediaObject, source_id)
        if media_object is None or media_object.deleted_at is not None:
            return None
        if media_object.status in {"deleted", "failed"}:
            return None
        return _ResolvedSource(
            source_type="media",
            source_id=source_id,
            owner_subject_hash=media_object.owner_subject_hash,
        )
    image_object = await session.get(LearningImageObject, source_id)
    if image_object is None or image_object.deleted_at is not None:
        return None
    if image_object.status in {
        "deleted",
        "cancelled",
        "failed",
        "rejected_by_auto_filter",
        "rejected_by_review",
    }:
        return None
    return _ResolvedSource(
        source_type="learning_image",
        source_id=source_id,
        owner_subject_hash=image_object.owner_subject_hash,
    )


async def _existing_active_task_exists(*, session: Any, source: _ResolvedSource) -> bool:
    """Return whether a live OCR annotation task already exists for a source.

    Args:
        session: Async DB session.
        source: Resolved source metadata.

    Returns:
        True when a pending/in-review/accepted OCR task already exists.
    """
    statement = select(AnnotationTask).where(
        AnnotationTask.task_type == ANNOTATION_TASK_TYPE,
        AnnotationTask.status.in_(sorted(ACTIVE_TASK_STATUSES)),
    )
    if source.source_type == "media":
        statement = statement.where(AnnotationTask.media_object_id == source.source_id)
    else:
        statement = statement.where(AnnotationTask.learning_image_object_id == source.source_id)
    return await session.scalar(statement.limit(1)) is not None


def _build_label_snapshot(
    *,
    row: dict[str, Any],
    target_dataset_task_types: list[str],
) -> dict[str, Any]:
    """Build a sanitized seed label snapshot for manual review.

    The seed intentionally does not include source refs, object storage refs,
    provider payloads, or raw OCR text. Reviewers must replace this seed with a
    task-specific accepted label such as ``text_label`` or ``textline_boxes``
    before dataset promotion.

    Args:
        row: Improvement candidate row.
        target_dataset_task_types: Candidate PaddleOCR task types.

    Returns:
        Sanitized annotation task seed.

    Raises:
        ValueError: If the candidate is malformed.
    """
    expected = row.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("Candidate expected snapshot must be an object.")
    snapshot = {
        "schema_version": LABEL_SNAPSHOT_SCHEMA_VERSION,
        "candidate_source": "paddleocr_improvement_candidate",
        "fixture_id": _required_string(row.get("fixture_id")),
        "image_ref_hash": _required_sha256(row.get("image_ref_hash")),
        "image_sha256": _required_sha256(row.get("image_sha256")),
        "category_key": _required_string(row.get("category_key")),
        "source_kind": "review",
        "target_provider": "paddleocr_local",
        "target_dataset_task_types": target_dataset_task_types,
        "failure_codes": _safe_string_list(row.get("failure_codes")),
        "score_snapshot": _safe_score_snapshot(row.get("score_snapshot")),
        "expected_snapshot": expected,
        "requires_manual_review": True,
        "training_export_allowed": False,
        "reviewer_instruction_code": "create_paddleocr_detection_or_recognition_label",
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "source_ref_stored": False,
    }
    _reject_unsafe_payload(snapshot)
    return json.loads(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))


def _required_string(value: object) -> str:
    """Return a required non-empty string.

    Args:
        value: Candidate value.

    Returns:
        Trimmed string.

    Raises:
        ValueError: If the value is missing.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a non-empty string.")
    return value.strip()


def _required_sha256(value: object) -> str:
    """Return a required SHA-256 hex value.

    Args:
        value: Candidate value.

    Returns:
        SHA-256 hex string.

    Raises:
        ValueError: If the value is malformed.
    """
    if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
        return value
    raise ValueError("Expected SHA-256 hex string.")


def _safe_string_list(value: object) -> list[str]:
    """Return bounded safe strings from a candidate list.

    Args:
        value: Candidate list.

    Returns:
        Safe string list.
    """
    if not isinstance(value, list):
        return []
    rows = []
    for item in value[:40]:
        if isinstance(item, str) and item.strip():
            rows.append(item.strip()[:160])
    return rows


def _safe_score_snapshot(value: object) -> dict[str, int | float | str]:
    """Return numeric/string score metadata safe for review routing.

    Args:
        value: Candidate score snapshot.

    Returns:
        Sanitized score snapshot.
    """
    if not isinstance(value, dict):
        return {}
    snapshot: dict[str, int | float | str] = {}
    for key, raw_value in value.items():
        if not isinstance(key, str) or not key.strip():
            continue
        if isinstance(raw_value, bool) or raw_value is None:
            continue
        if isinstance(raw_value, int | float):
            snapshot[key[:80]] = raw_value
        elif isinstance(raw_value, str) and raw_value.strip():
            snapshot[key[:80]] = raw_value.strip()[:160]
    return snapshot


def _failure_summary(*, improvement_manifest: Path, error: BaseException) -> dict[str, object]:
    """Return a redacted failure summary.

    Args:
        improvement_manifest: Requested manifest path.
        error: Raised error.

    Returns:
        Failure summary without source refs, labels, or owner hashes.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "improvement_manifest_name": improvement_manifest.name,
        "improvement_manifest_hash": _sha256_text(str(improvement_manifest.expanduser())),
        "error_type": type(error).__name__,
        "annotation_task_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "owner_subject_hash_printed": False,
        "source_ref_printed": False,
        "label_snapshot_printed": False,
        "expected_text_printed": False,
        "raw_payload_printed": False,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: Input JSONL path.

    Returns:
        JSON object rows.

    Raises:
        ValueError: If a row is not an object.
    """
    rows = []
    with path.expanduser().open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row {line_number} must be an object.")
            rows.append(row)
    return rows


def _sha256_text(value: str) -> str:
    """Return SHA-256 for a string value.

    Args:
        value: Input text.

    Returns:
        SHA-256 hexadecimal digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
