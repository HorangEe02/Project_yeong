"""KDRIs source manifest loading and validation helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from src.nutrition.kdris import DEFAULT_KDRIS_SOURCE_MANIFEST

DEFAULT_SOURCE_MANIFEST = DEFAULT_KDRIS_SOURCE_MANIFEST
CURRENT_OFFICIAL_REFERENCE_YEAR = 2025
LOCAL_DATASET_STATUS = "official_2025_approved"


class KDRISource(TypedDict):
    """Source entry recorded in the KDRIs source manifest."""

    id: str
    reference_year: int
    publisher: str
    title: str
    artifact_type: str
    source_url: str
    release_date: str
    retrieved_at: str
    license_note: str
    errata_note: str
    checksum_sha256: str | None
    usage_status: str


class KDRIDatasetArtifact(TypedDict):
    """Dataset artifact entry recorded in the KDRIs source manifest."""

    id: str
    version: str
    path: str
    reference_year: int
    status: str
    checksum_sha256: str | None
    review_status: str


class KDRISourceManifest(TypedDict):
    """KDRIs source manifest structure."""

    schema_version: str
    current_official_reference_year: int
    local_dataset_year: int
    local_dataset_status: str
    operational_dataset_version: NotRequired[str]
    candidate_dataset_version: NotRequired[str]
    candidate_dataset_status: NotRequired[str]
    current_errata_version: NotRequired[str]
    retrieved_at: str
    dataset_artifacts: NotRequired[list[KDRIDatasetArtifact]]
    sources: list[KDRISource]
    production_quality_gates: list[str]


def _validate_source(source: dict[str, object]) -> KDRISource:
    """Validate and normalize one KDRIs source manifest entry.

    Args:
        source: Raw source mapping loaded from JSON.

    Returns:
        Normalized source entry.

    Raises:
        ValueError: If a required field is missing or has an invalid type.
    """
    required_string_fields = (
        "id",
        "publisher",
        "title",
        "artifact_type",
        "source_url",
        "release_date",
        "retrieved_at",
        "license_note",
        "errata_note",
        "usage_status",
    )
    normalized: dict[str, object] = {}
    for field_name in required_string_fields:
        value = source.get(field_name)
        if not isinstance(value, str) or value == "":
            raise ValueError(f"KDRIs source field is required: {field_name}")
        normalized[field_name] = value

    reference_year = source.get("reference_year")
    if not isinstance(reference_year, int):
        raise ValueError("KDRIs source field must be an integer: reference_year")
    normalized["reference_year"] = reference_year

    checksum = source.get("checksum_sha256")
    if checksum is not None and not isinstance(checksum, str):
        raise ValueError("KDRIs source field must be a string or null: checksum_sha256")
    normalized["checksum_sha256"] = checksum

    return cast(KDRISource, normalized)


def _validate_dataset_artifact(artifact: dict[str, object]) -> KDRIDatasetArtifact:
    """Validate and normalize one manifest dataset artifact.

    Args:
        artifact: Raw dataset artifact mapping loaded from JSON.

    Returns:
        Normalized dataset artifact entry.

    Raises:
        ValueError: If a required field is missing or has an invalid type.
    """
    required_string_fields = ("id", "version", "path", "status", "review_status")
    normalized: dict[str, object] = {}
    for field_name in required_string_fields:
        value = artifact.get(field_name)
        if not isinstance(value, str) or value == "":
            raise ValueError(f"KDRIs dataset artifact field is required: {field_name}")
        normalized[field_name] = value

    reference_year = artifact.get("reference_year")
    if not isinstance(reference_year, int):
        raise ValueError("KDRIs dataset artifact field must be an integer: reference_year")
    normalized["reference_year"] = reference_year

    checksum = artifact.get("checksum_sha256")
    if checksum is not None and not isinstance(checksum, str):
        raise ValueError("KDRIs dataset artifact checksum must be a string or null.")
    normalized["checksum_sha256"] = checksum

    return cast(KDRIDatasetArtifact, normalized)


def _validate_manifest_years(raw_manifest: dict[str, object]) -> tuple[int, int, str]:
    """Validate manifest reference year and local dataset status fields.

    Args:
        raw_manifest: Raw manifest mapping.

    Returns:
        Current official year, local dataset year, and local dataset status.

    Raises:
        ValueError: If required fields are missing or unsafe for production tracking.
    """
    current_year = raw_manifest.get("current_official_reference_year")
    local_dataset_year = raw_manifest.get("local_dataset_year")
    if not isinstance(current_year, int):
        raise ValueError("KDRIs current official reference year must be an integer.")
    if current_year != CURRENT_OFFICIAL_REFERENCE_YEAR:
        raise ValueError("KDRIs source manifest must point to the 2025 official reference.")
    if not isinstance(local_dataset_year, int):
        raise ValueError("KDRIs local dataset year must be an integer.")

    local_status = raw_manifest.get("local_dataset_status")
    if not isinstance(local_status, str):
        raise ValueError("KDRIs local dataset status must be a string.")
    if local_status != LOCAL_DATASET_STATUS:
        raise ValueError("KDRIs local dataset must be marked as the approved 2025 dataset.")
    return current_year, local_dataset_year, local_status


def _validate_manifest_header(raw_manifest: dict[str, object]) -> tuple[str, str]:
    """Validate manifest schema version and retrieval date fields.

    Args:
        raw_manifest: Raw manifest mapping.

    Returns:
        Schema version and retrieved_at value.

    Raises:
        ValueError: If header fields are missing.
    """
    schema_version = raw_manifest.get("schema_version")
    retrieved_at = raw_manifest.get("retrieved_at")
    if not isinstance(schema_version, str) or schema_version == "":
        raise ValueError("KDRIs source manifest schema_version is required.")
    if not isinstance(retrieved_at, str) or retrieved_at == "":
        raise ValueError("KDRIs source manifest retrieved_at is required.")
    return schema_version, retrieved_at


def _optional_manifest_string(raw_manifest: dict[str, object], field_name: str) -> str | None:
    """Validate one optional manifest string field.

    Args:
        raw_manifest: Raw manifest mapping.
        field_name: Optional field name.

    Returns:
        String value or None.

    Raises:
        ValueError: If the optional value is present but invalid.
    """
    value = raw_manifest.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or value == "":
        raise ValueError(f"KDRIs manifest field must be a non-empty string: {field_name}")
    return value


def _attach_optional_manifest_fields(
    manifest: KDRISourceManifest,
    raw_manifest: dict[str, object],
) -> KDRISourceManifest:
    """Attach validated optional v2 manifest fields.

    Args:
        manifest: Normalized manifest.
        raw_manifest: Raw manifest mapping.

    Returns:
        Manifest with optional fields.
    """
    operational_version = _optional_manifest_string(raw_manifest, "operational_dataset_version")
    candidate_version = _optional_manifest_string(raw_manifest, "candidate_dataset_version")
    candidate_status = _optional_manifest_string(raw_manifest, "candidate_dataset_status")
    errata_version = _optional_manifest_string(raw_manifest, "current_errata_version")
    if operational_version is not None:
        manifest["operational_dataset_version"] = operational_version
    if candidate_version is not None:
        manifest["candidate_dataset_version"] = candidate_version
    if candidate_status is not None:
        manifest["candidate_dataset_status"] = candidate_status
    if errata_version is not None:
        manifest["current_errata_version"] = errata_version
    return manifest


@lru_cache
def load_kdris_source_manifest(
    manifest_path: Path | None = DEFAULT_SOURCE_MANIFEST,
) -> KDRISourceManifest:
    """Load and validate the KDRIs source manifest.

    Args:
        manifest_path: Source manifest JSON path.

    Returns:
        Validated KDRIs source manifest.

    Raises:
        ValueError: If the JSON file does not match the expected manifest shape.
    """
    resolved_manifest_path = DEFAULT_SOURCE_MANIFEST if manifest_path is None else manifest_path
    with resolved_manifest_path.open(encoding="utf-8") as manifest_file:
        loaded: object = json.load(manifest_file)
    if not isinstance(loaded, dict):
        raise ValueError("KDRIs source manifest must be a JSON object.")

    raw_manifest = cast(dict[str, object], loaded)
    sources = raw_manifest.get("sources")
    quality_gates = raw_manifest.get("production_quality_gates")
    if not isinstance(sources, list) or not sources:
        raise ValueError("KDRIs source manifest must include at least one source.")
    if not isinstance(quality_gates, list) or not all(
        isinstance(gate, str) and gate for gate in quality_gates
    ):
        raise ValueError("KDRIs source manifest must include production quality gates.")

    normalized_sources = [
        _validate_source(cast(dict[str, object], source))
        for source in sources
        if isinstance(source, dict)
    ]
    if len(normalized_sources) != len(sources):
        raise ValueError("KDRIs source entries must be JSON objects.")

    raw_dataset_artifacts = raw_manifest.get("dataset_artifacts", [])
    if not isinstance(raw_dataset_artifacts, list):
        raise ValueError("KDRIs dataset_artifacts must be a list when present.")
    dataset_artifacts = [
        _validate_dataset_artifact(cast(dict[str, object], artifact))
        for artifact in raw_dataset_artifacts
        if isinstance(artifact, dict)
    ]
    if len(dataset_artifacts) != len(raw_dataset_artifacts):
        raise ValueError("KDRIs dataset_artifacts entries must be JSON objects.")

    current_year, local_dataset_year, local_status = _validate_manifest_years(raw_manifest)
    schema_version, retrieved_at = _validate_manifest_header(raw_manifest)

    manifest: KDRISourceManifest = {
        "schema_version": schema_version,
        "current_official_reference_year": current_year,
        "local_dataset_year": local_dataset_year,
        "local_dataset_status": local_status,
        "retrieved_at": retrieved_at,
        "sources": normalized_sources,
        "production_quality_gates": cast(list[str], quality_gates),
    }
    manifest = _attach_optional_manifest_fields(manifest, raw_manifest)
    if dataset_artifacts:
        manifest["dataset_artifacts"] = dataset_artifacts
    return manifest


def get_current_official_reference_year() -> int:
    """Return the current official KDRIs reference year tracked by the manifest.

    Returns:
        Official reference year currently expected for production KDRIs work.
    """
    manifest = load_kdris_source_manifest()
    return manifest["current_official_reference_year"]
