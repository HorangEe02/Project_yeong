"""Import OCR benchmark fixture images as private media objects.

This bridge converts materialized OCR benchmark fixture manifests from
file-only ``crawling-image:<hash>`` source refs into DB-backed
``media:<uuid>`` source refs. The rewritten manifest can then feed
PaddleOCR improvement candidate generation and annotation-task creation.

The command is dry-run by default. ``--apply`` is required before it creates
``MediaObject`` rows, copies files into the configured local private media
root, or writes a rewritten manifest. The printed summary is intentionally
redacted: it does not expose owner hashes, source refs, object refs, local
paths, expected OCR text, or raw provider payloads.

References:
    https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.media import MediaObject  # noqa: E402

from scripts.build_supplement_ocr_benchmark_manifest import (  # noqa: E402
    ROW_SCHEMA_VERSION as BENCHMARK_ROW_SCHEMA_VERSION,
)
from scripts.build_supplement_ocr_benchmark_manifest import _reject_unsafe_payload  # noqa: E402

SUMMARY_SCHEMA_VERSION = "supplement-benchmark-media-object-import-summary-v1"
OUTPUT_ROW_SCHEMA_VERSION = BENCHMARK_ROW_SCHEMA_VERSION
OWNER_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
MAX_LIMIT = 100_000
DEFAULT_LIMIT = 10_000
DEFAULT_RETENTION_DAYS = 90
MAX_RETENTION_DAYS = 3650
ALLOWED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
ALLOWED_IMAGE_SUFFIXES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
SOURCE_DOC_URLS = (
    "https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html",
)


@dataclass(frozen=True)
class _FixtureImport:
    """Validated fixture image ready for DB media import.

    Attributes:
        row: Original benchmark row.
        source_path: Materialized private fixture file path.
        image_sha256: SHA-256 hash validated against the row.
        image_size_bytes: File size validated against the row when present.
        image_mime_type: MediaObject-compatible MIME type.
        object_ref: Private relative object-storage reference.
    """

    row: dict[str, Any]
    source_path: Path
    image_sha256: str
    image_size_bytes: int
    image_mime_type: str
    object_ref: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-manifest", type=Path, required=True)
    parser.add_argument(
        "--image-root",
        type=Path,
        help="Root used to resolve relative manifest image_path values. Defaults to manifest dir.",
    )
    parser.add_argument("--local-media-root", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--owner-subject-hash", required=True)
    parser.add_argument("--source-run-id")
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--apply", action="store_true")
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
        summary = await import_benchmark_fixtures_as_media_objects(
            benchmark_manifest=args.benchmark_manifest,
            image_root=args.image_root,
            local_media_root=args.local_media_root,
            output_manifest=args.output_manifest,
            owner_subject_hash=args.owner_subject_hash,
            source_run_id=args.source_run_id,
            retention_days=args.retention_days,
            limit=args.limit,
            apply=args.apply,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = _failure_summary(
            benchmark_manifest=args.benchmark_manifest,
            apply=args.apply,
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


async def import_benchmark_fixtures_as_media_objects(
    *,
    benchmark_manifest: Path,
    image_root: Path | None,
    local_media_root: Path,
    output_manifest: Path,
    owner_subject_hash: str,
    source_run_id: str | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    limit: int = DEFAULT_LIMIT,
    apply: bool = False,
) -> dict[str, object]:
    """Validate and optionally import OCR fixture images as MediaObject rows.

    Args:
        benchmark_manifest: JSONL manifest generated by
            ``build_supplement_ocr_benchmark_manifest.py`` with materialized
            private image fixture paths.
        image_root: Root used to resolve relative ``image_path`` references.
            When omitted, the benchmark manifest directory is used.
        local_media_root: Private local storage root for imported objects.
        output_manifest: Rewritten manifest destination used only with
            ``--apply``.
        owner_subject_hash: HMAC-SHA256 owner hash. Raw owner subjects must
            never be passed to this script.
        source_run_id: Optional UUID string linked to imported MediaObject rows.
        retention_days: Retention period for created rows.
        limit: Maximum manifest rows to scan.
        apply: Whether to write DB rows, copy files, and emit rewritten rows.

    Returns:
        Redacted import summary.

    Raises:
        ValueError: If CLI parameters or manifest rows are malformed.
    """
    _validate_args(
        owner_subject_hash=owner_subject_hash,
        source_run_id=source_run_id,
        retention_days=retention_days,
        limit=limit,
    )
    rows = _read_jsonl(benchmark_manifest)
    scanned_rows = rows[:limit]
    resolved_image_root = (image_root or benchmark_manifest.parent).expanduser().resolve()
    validated_rows, skip_reasons = _validated_fixture_imports(
        rows=scanned_rows,
        image_root=resolved_image_root,
    )
    if not apply:
        return _summary(
            benchmark_manifest=benchmark_manifest,
            input_count=len(rows),
            scanned_count=len(scanned_rows),
            validated_count=len(validated_rows),
            rewritten_count=0,
            created_media_count=0,
            reused_media_count=0,
            copied_object_count=0,
            skip_reasons=skip_reasons,
            apply=False,
            output_manifest_written=False,
        )

    source_run_uuid = UUID(source_run_id) if source_run_id else None
    retained_until = datetime.now(UTC) + timedelta(days=retention_days)
    rewritten_rows: list[dict[str, Any]] = []
    created_media_count = 0
    reused_media_count = 0
    copied_object_count = 0

    local_root = local_media_root.expanduser().resolve()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        for fixture in validated_rows:
            existing_media = await _find_existing_media_object(
                session=session,
                owner_subject_hash=owner_subject_hash,
                image_sha256=fixture.image_sha256,
            )
            if existing_media is None:
                copy_performed = _copy_private_fixture(
                    source_path=fixture.source_path,
                    local_media_root=local_root,
                    object_ref=fixture.object_ref,
                    expected_sha256=fixture.image_sha256,
                )
                copied_object_count += int(copy_performed)
                media_object = MediaObject(
                    id=uuid4(),
                    owner_subject_hash=owner_subject_hash,
                    domain="supplement_label",
                    source_run_id=source_run_uuid,
                    object_storage_provider="local",
                    object_ref=fixture.object_ref,
                    object_version_id=None,
                    image_sha256=fixture.image_sha256,
                    image_mime_type=fixture.image_mime_type,
                    image_size_bytes=fixture.image_size_bytes,
                    width_px=None,
                    height_px=None,
                    exif_stripped=False,
                    retained_until=retained_until,
                    status="retained",
                    consent_snapshot={
                        "consent_type": "image_learning_dataset",
                        "source": "supplement_ocr_benchmark_fixture",
                        "pii_screening_status": "operator_cleared_no_personal_data",
                        "exif_stripped": False,
                    },
                    deleted_at=None,
                )
                session.add(media_object)
                created_media_count += 1
            else:
                media_object = existing_media
                reused_media_count += 1

            rewritten_rows.append(
                _rewritten_row(
                    row=fixture.row,
                    media_object_id=media_object.id,
                )
            )

        await session.commit()

    _write_jsonl(output_manifest, rewritten_rows)
    return _summary(
        benchmark_manifest=benchmark_manifest,
        input_count=len(rows),
        scanned_count=len(scanned_rows),
        validated_count=len(validated_rows),
        rewritten_count=len(rewritten_rows),
        created_media_count=created_media_count,
        reused_media_count=reused_media_count,
        copied_object_count=copied_object_count,
        skip_reasons=skip_reasons,
        apply=True,
        output_manifest_written=True,
    )


def _validate_args(
    *,
    owner_subject_hash: str,
    source_run_id: str | None,
    retention_days: int,
    limit: int,
) -> None:
    """Validate import arguments.

    Args:
        owner_subject_hash: HMAC-SHA256 owner hash.
        source_run_id: Optional source run UUID string.
        retention_days: Retention period for created media objects.
        limit: Maximum manifest rows to scan.

    Raises:
        ValueError: If an argument is invalid.
    """
    if not OWNER_HASH_PATTERN.fullmatch(owner_subject_hash):
        raise ValueError("owner_subject_hash must be a 64-character hex digest.")
    if source_run_id is not None:
        UUID(source_run_id)
    if retention_days < 1 or retention_days > MAX_RETENTION_DAYS:
        raise ValueError("retention_days must be between 1 and 3650.")
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError("limit must be between 1 and 100000.")


def _validated_fixture_imports(
    *,
    rows: list[dict[str, Any]],
    image_root: Path,
) -> tuple[list[_FixtureImport], Counter[str]]:
    """Validate benchmark rows and resolve private fixture images.

    Args:
        rows: Benchmark manifest rows.
        image_root: Root used to resolve relative image paths.

    Returns:
        Importable fixtures and skip reason counts.
    """
    validated: list[_FixtureImport] = []
    skip_reasons: Counter[str] = Counter()
    if not image_root.is_dir():
        raise ValueError("image_root is not a directory.")

    for row in rows:
        try:
            fixture = _validated_fixture_import(row=row, image_root=image_root)
        except ValueError as exc:
            skip_reasons[_skip_reason_from_error(exc)] += 1
            continue
        validated.append(fixture)
    return validated, skip_reasons


def _validated_fixture_import(*, row: dict[str, Any], image_root: Path) -> _FixtureImport:
    """Validate one benchmark row for media object import.

    Args:
        row: Benchmark manifest row.
        image_root: Root used to resolve relative image paths.

    Returns:
        Validated fixture import.

    Raises:
        ValueError: If the row or image file cannot be safely imported.
    """
    image_path_value = row.get("image_path")
    if not isinstance(image_path_value, str):
        raise ValueError("missing_image_path")
    source_path = _resolve_relative_image_path(image_root=image_root, image_path=image_path_value)
    _reject_unsafe_payload(row)
    if row.get("schema_version") != BENCHMARK_ROW_SCHEMA_VERSION:
        raise ValueError("unsupported_schema_version")
    source_ref = row.get("source_ref")
    if not isinstance(source_ref, str) or not source_ref.startswith("crawling-image:"):
        raise ValueError("unsupported_source_ref")
    if row.get("contains_personal_data") is not False:
        raise ValueError("pii_gate_not_cleared")
    if row.get("pii_screening_status") != "operator_cleared_no_personal_data":
        raise ValueError("pii_gate_not_cleared")
    if not source_path.is_file():
        raise ValueError("image_file_not_found")

    expected_sha256 = _required_sha256(row.get("image_sha256"))
    actual_sha256 = _sha256_file(source_path)
    if actual_sha256 != expected_sha256:
        raise ValueError("image_sha256_mismatch")
    actual_size = source_path.stat().st_size
    row_size = row.get("image_size_bytes")
    if isinstance(row_size, int) and row_size > 0 and row_size != actual_size:
        raise ValueError("image_size_mismatch")
    image_mime_type = _validated_image_mime_type(row=row, source_path=source_path)
    object_ref = _object_ref_for_fixture(
        image_sha256=actual_sha256,
        suffix=source_path.suffix.lower(),
    )
    return _FixtureImport(
        row=row,
        source_path=source_path,
        image_sha256=actual_sha256,
        image_size_bytes=actual_size,
        image_mime_type=image_mime_type,
        object_ref=object_ref,
    )


def _resolve_relative_image_path(*, image_root: Path, image_path: str) -> Path:
    """Resolve a safe manifest-relative image path under image_root.

    Args:
        image_root: Trusted root.
        image_path: Manifest image path.

    Returns:
        Resolved path under image_root.

    Raises:
        ValueError: If the image path is absolute, URL-like, or escaping.
    """
    if "://" in image_path or "\\" in image_path or image_path.startswith("~"):
        raise ValueError("unsafe_image_path")
    pure_path = PurePosixPath(image_path)
    if pure_path.is_absolute() or any(part in {"", ".", ".."} for part in pure_path.parts):
        raise ValueError("unsafe_image_path")
    resolved = (image_root / Path(*pure_path.parts)).resolve()
    try:
        resolved.relative_to(image_root)
    except ValueError as exc:
        raise ValueError("unsafe_image_path") from exc
    return resolved


def _required_sha256(value: object) -> str:
    """Return a normalized SHA-256 hex string.

    Args:
        value: Candidate value.

    Returns:
        SHA-256 hex value.

    Raises:
        ValueError: If the value is malformed.
    """
    if isinstance(value, str) and SHA256_PATTERN.fullmatch(value):
        return value.lower()
    raise ValueError("invalid_image_sha256")


def _validated_image_mime_type(*, row: dict[str, Any], source_path: Path) -> str:
    """Return a MediaObject-compatible image MIME type.

    Args:
        row: Benchmark row.
        source_path: Materialized fixture file.

    Returns:
        Accepted MIME type.

    Raises:
        ValueError: If the MIME type cannot be stored in MediaObject.
    """
    row_mime = row.get("image_mime_type")
    suffix_mime = ALLOWED_IMAGE_SUFFIXES.get(source_path.suffix.lower())
    guessed_mime = mimetypes.guess_type(source_path.name)[0]
    candidate_mime = row_mime if isinstance(row_mime, str) and row_mime else suffix_mime
    candidate_mime = candidate_mime or guessed_mime
    if candidate_mime not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("unsupported_image_mime_type")
    if suffix_mime is not None and candidate_mime != suffix_mime:
        raise ValueError("image_mime_suffix_mismatch")
    return candidate_mime


def _object_ref_for_fixture(*, image_sha256: str, suffix: str) -> str:
    """Return a deterministic private object reference for one fixture.

    Args:
        image_sha256: SHA-256 hash of the fixture bytes.
        suffix: Source image suffix.

    Returns:
        Private relative object reference.

    Raises:
        ValueError: If the suffix is not MediaObject-compatible.
    """
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("unsupported_image_mime_type")
    extension = ".jpg" if suffix == ".jpeg" else suffix
    object_ref = f"supplement/ocr-benchmark/{image_sha256[:2]}/{image_sha256}{extension}"
    _validate_private_object_ref(object_ref)
    return object_ref


def _validate_private_object_ref(object_ref: str) -> None:
    """Validate a private relative object reference.

    Args:
        object_ref: Candidate object ref.

    Raises:
        ValueError: If the reference is not private and relative.
    """
    pure_path = PurePosixPath(object_ref)
    if (
        not object_ref
        or "://" in object_ref
        or "\\" in object_ref
        or pure_path.is_absolute()
        or any(part in {"", ".", ".."} for part in pure_path.parts)
    ):
        raise ValueError("unsafe_object_ref")


async def _find_existing_media_object(
    *,
    session: Any,
    owner_subject_hash: str,
    image_sha256: str,
) -> MediaObject | None:
    """Return an existing retained media row for the owner and image hash.

    Args:
        session: Async DB session.
        owner_subject_hash: Source owner hash.
        image_sha256: Validated image hash.

    Returns:
        Existing live MediaObject or None.
    """
    statement = (
        select(MediaObject)
        .where(
            MediaObject.owner_subject_hash == owner_subject_hash,
            MediaObject.domain == "supplement_label",
            MediaObject.image_sha256 == image_sha256,
            MediaObject.deleted_at.is_(None),
            MediaObject.status.notin_(["deleted", "failed"]),
        )
        .limit(1)
    )
    return await session.scalar(statement)


def _copy_private_fixture(
    *,
    source_path: Path,
    local_media_root: Path,
    object_ref: str,
    expected_sha256: str,
) -> bool:
    """Copy one fixture into private local media storage.

    Args:
        source_path: Validated source fixture file.
        local_media_root: Private local media root.
        object_ref: Relative destination object ref.
        expected_sha256: Expected SHA-256 hash.

    Returns:
        True if a copy was performed, False when a matching destination already
        exists.

    Raises:
        ValueError: If destination validation fails.
    """
    _validate_private_object_ref(object_ref)
    destination_path = (local_media_root / Path(*PurePosixPath(object_ref).parts)).resolve()
    try:
        destination_path.relative_to(local_media_root)
    except ValueError as exc:
        raise ValueError("unsafe_object_ref") from exc
    if destination_path.exists():
        if not destination_path.is_file() or _sha256_file(destination_path) != expected_sha256:
            raise ValueError("destination_object_hash_mismatch")
        return False
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination_path)
    if _sha256_file(destination_path) != expected_sha256:
        destination_path.unlink(missing_ok=True)
        raise ValueError("destination_object_hash_mismatch")
    return True


def _rewritten_row(*, row: dict[str, Any], media_object_id: UUID) -> dict[str, Any]:
    """Return a benchmark row with a DB-backed media source ref.

    Args:
        row: Original benchmark row.
        media_object_id: MediaObject id used as the new source ref.

    Returns:
        Rewritten JSON-safe benchmark row.
    """
    rewritten = json.loads(json.dumps(row, ensure_ascii=False, sort_keys=True))
    rewritten["schema_version"] = OUTPUT_ROW_SCHEMA_VERSION
    rewritten["source_ref"] = f"media:{media_object_id}"
    rewritten["source_ref_kind"] = "media_object"
    rewritten["db_write_performed"] = True
    rewritten["media_object_registered"] = True
    rewritten["object_ref_stored"] = False
    rewritten["local_path_stored"] = False
    rewritten["raw_ocr_text_stored"] = False
    rewritten["raw_provider_payload_stored"] = False
    _reject_unsafe_payload(rewritten)
    return rewritten


def _skip_reason_from_error(error: ValueError) -> str:
    """Return a stable skip reason from an internal ValueError.

    Args:
        error: Row validation error.

    Returns:
        Stable skip reason.
    """
    reason = str(error).strip()
    if re.fullmatch(r"[a-z0-9_]+", reason):
        return reason
    return "invalid_fixture_row"


def _summary(
    *,
    benchmark_manifest: Path,
    input_count: int,
    scanned_count: int,
    validated_count: int,
    rewritten_count: int,
    created_media_count: int,
    reused_media_count: int,
    copied_object_count: int,
    skip_reasons: Counter[str],
    apply: bool,
    output_manifest_written: bool,
) -> dict[str, object]:
    """Return a redacted import summary.

    Args:
        benchmark_manifest: Input manifest path.
        input_count: Total input rows.
        scanned_count: Rows scanned under the limit.
        validated_count: Rows with safe materialized fixture files.
        rewritten_count: Rows written to output manifest.
        created_media_count: New MediaObject rows.
        reused_media_count: Existing MediaObject rows reused.
        copied_object_count: New private object files copied.
        skip_reasons: Validation skip reason counts.
        apply: Whether writes were requested.
        output_manifest_written: Whether a rewritten manifest was emitted.

    Returns:
        Sanitized summary safe for operator logs.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "benchmark_manifest_name": benchmark_manifest.name,
        "benchmark_manifest_content_sha256": _sha256_file(benchmark_manifest),
        "input_count": input_count,
        "scanned_count": scanned_count,
        "validated_fixture_count": validated_count,
        "rewritten_count": rewritten_count,
        "created_media_count": created_media_count,
        "reused_media_count": reused_media_count,
        "copied_object_count": copied_object_count,
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "apply": apply,
        "media_object_write_performed": created_media_count > 0,
        "local_copy_performed": copied_object_count > 0,
        "output_manifest_written": output_manifest_written,
        "requires_db_backed_source_for_annotation_tasks": True,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "owner_subject_hash_printed": False,
        "source_ref_printed": False,
        "object_ref_printed": False,
        "local_path_printed": False,
        "expected_text_printed": False,
        "raw_payload_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _failure_summary(
    *,
    benchmark_manifest: Path,
    apply: bool,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted failure summary.

    Args:
        benchmark_manifest: Requested input manifest.
        apply: Whether writes were requested.
        error: Raised exception.

    Returns:
        Sanitized failure summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "failed",
        "benchmark_manifest_name": benchmark_manifest.name,
        "apply": apply,
        "error_code": type(error).__name__,
        "media_object_write_performed": False,
        "local_copy_performed": False,
        "output_manifest_written": False,
        "owner_subject_hash_printed": False,
        "source_ref_printed": False,
        "object_ref_printed": False,
        "local_path_printed": False,
        "expected_text_printed": False,
        "raw_payload_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: JSON object rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    """Return SHA-256 hash for file bytes.

    Args:
        path: File path.

    Returns:
        SHA-256 hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
