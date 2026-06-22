"""Export privacy-reviewed retraining manifests for operator workflows."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import (  # noqa: E402
    DatasetFreezeError,
    RetrainingSecurityError,
    build_dataset_export_manifest,
    build_paddleocr_detection_export,
    build_paddleocr_recognition_export,
    build_supplement_section_yolo_detection_export,
    build_yolo_detection_export,
    candidate_from_dataset_item,
)
from src.models.db.retraining import (  # noqa: E402
    LearningDatasetItem,
    LearningDatasetVersion,
)

SUMMARY_SCHEMA_VERSION = "learning-training-manifest-export-summary-v1"
EXPORT_KIND_DATASET = "dataset"
EXPORT_KIND_YOLO_DETECTION = "yolo_detection"
EXPORT_KIND_SUPPLEMENT_SECTION_YOLO_DETECTION = "supplement_section_yolo_detection"
EXPORT_KIND_PADDLEOCR_DETECTION = "paddleocr_detection"
EXPORT_KIND_PADDLEOCR_RECOGNITION = "paddleocr_recognition"
EXPORT_KIND_CHOICES = (
    EXPORT_KIND_DATASET,
    EXPORT_KIND_YOLO_DETECTION,
    EXPORT_KIND_SUPPLEMENT_SECTION_YOLO_DETECTION,
    EXPORT_KIND_PADDLEOCR_DETECTION,
    EXPORT_KIND_PADDLEOCR_RECOGNITION,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-version-id", required=True, type=UUID)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--export-kind",
        choices=EXPORT_KIND_CHOICES,
        default=EXPORT_KIND_DATASET,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the CLI entrypoint.

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
        artifact, summary = asyncio.run(
            export_training_manifest(
                dataset_version_id=args.dataset_version_id,
                export_kind=args.export_kind,
            )
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (DatasetFreezeError, OSError, RetrainingSecurityError, ValueError) as exc:
        summary = _failure_summary(output_path=output_path, error=exc)
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


async def export_training_manifest(
    *,
    dataset_version_id: UUID,
    export_kind: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    """Export one sanitized retraining manifest.

    Args:
        dataset_version_id: Privacy-reviewed dataset version id.
        export_kind: Dataset or task-specific export kind.

    Returns:
        Export artifact and redacted summary.

    Raises:
        ValueError: If the dataset version is missing or export kind is unknown.
        DatasetFreezeError: If the dataset has not passed privacy/freeze gates.
        RetrainingSecurityError: If any exported label could expose raw data.
    """
    if export_kind not in EXPORT_KIND_CHOICES:
        raise ValueError("Unsupported training manifest export kind.")

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        dataset_version = await session.get(LearningDatasetVersion, dataset_version_id)
        if dataset_version is None:
            raise ValueError("Learning dataset version was not found.")
        dataset_items = await _load_dataset_items(
            session=session,
            dataset_version_id=dataset_version_id,
        )

    candidates = [candidate_from_dataset_item(item) for item in dataset_items]
    dataset_manifest = build_dataset_export_manifest(dataset_version, candidates)
    artifact = _artifact_for_export_kind(dataset_manifest=dataset_manifest, export_kind=export_kind)
    summary = _success_summary(
        dataset_manifest=dataset_manifest,
        artifact=artifact,
        export_kind=export_kind,
    )
    return artifact, summary


async def _load_dataset_items(
    *,
    session: Any,
    dataset_version_id: UUID,
) -> list[LearningDatasetItem]:
    """Return candidate dataset items for one version.

    Args:
        session: Async DB session.
        dataset_version_id: Dataset version id.

    Returns:
        Dataset item rows sorted deterministically by split and id.
    """
    statement = (
        select(LearningDatasetItem)
        .where(LearningDatasetItem.dataset_version_id == dataset_version_id)
        .order_by(LearningDatasetItem.split.asc(), LearningDatasetItem.id.asc())
    )
    return list((await session.scalars(statement)).all())


def _artifact_for_export_kind(
    *,
    dataset_manifest: dict[str, Any],
    export_kind: str,
) -> dict[str, Any]:
    """Build a dataset or task-specific export artifact.

    Args:
        dataset_manifest: Sanitized dataset manifest.
        export_kind: Dataset or task-specific export kind.

    Returns:
        Export artifact.
    """
    if export_kind == EXPORT_KIND_DATASET:
        return dataset_manifest
    if export_kind == EXPORT_KIND_YOLO_DETECTION:
        return build_yolo_detection_export(dataset_manifest)
    if export_kind == EXPORT_KIND_SUPPLEMENT_SECTION_YOLO_DETECTION:
        return build_supplement_section_yolo_detection_export(dataset_manifest)
    if export_kind == EXPORT_KIND_PADDLEOCR_DETECTION:
        return build_paddleocr_detection_export(dataset_manifest)
    if export_kind == EXPORT_KIND_PADDLEOCR_RECOGNITION:
        return build_paddleocr_recognition_export(dataset_manifest)
    raise ValueError("Unsupported training manifest export kind.")


def _success_summary(
    *,
    dataset_manifest: dict[str, Any],
    artifact: dict[str, Any],
    export_kind: str,
) -> dict[str, object]:
    """Return a redacted export summary.

    Args:
        dataset_manifest: Sanitized source dataset manifest.
        artifact: Export artifact written to disk.
        export_kind: Dataset or task-specific export kind.

    Returns:
        Summary without source refs, label text, output path, owner hash, or raw payloads.
    """
    manifest_hash = str(dataset_manifest["manifest_hash"])
    item_count = _item_count(artifact)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "dataset_version_id": str(dataset_manifest["dataset_version_id"]),
        "dataset_key": dataset_manifest["dataset_key"],
        "dataset_version": dataset_manifest["version"],
        "export_kind": export_kind,
        "manifest_hash": manifest_hash,
        "artifact_hash": _sha256_json(artifact),
        "item_count": item_count,
        "counts": dataset_manifest["counts"],
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "object_url_stored": False,
        "owner_subject_hash_stored": False,
    }


def _failure_summary(
    *,
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted failure summary.

    Args:
        output_path: Requested output path.
        error: Raised error.

    Returns:
        Failure summary without the raw output path.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_type": type(error).__name__,
        "item_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "object_url_stored": False,
        "owner_subject_hash_stored": False,
    }


def _item_count(artifact: dict[str, Any]) -> int:
    """Return the item count from a dataset or task export artifact.

    Args:
        artifact: Export artifact.

    Returns:
        Number of export items.
    """
    if isinstance(artifact.get("item_count"), int):
        return int(artifact["item_count"])
    items = artifact.get("items")
    return len(items) if isinstance(items, list) else 0


def _sha256_json(value: object) -> str:
    """Return a SHA-256 digest for deterministic JSON content.

    Args:
        value: JSON-serializable value.

    Returns:
        Hex digest.
    """
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for text.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
