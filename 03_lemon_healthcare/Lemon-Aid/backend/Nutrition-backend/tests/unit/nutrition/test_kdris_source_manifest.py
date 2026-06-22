"""KDRIs source manifest tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.nutrition.kdris import DEFAULT_KDRIS_2025_CSV, DEFAULT_KDRIS_CSV, PROJECT_ROOT
from src.nutrition.source_manifest import (
    CURRENT_OFFICIAL_REFERENCE_YEAR,
    LOCAL_DATASET_STATUS,
    get_current_official_reference_year,
    load_kdris_source_manifest,
)


def _sha256(path: Path) -> str:
    """Return a file SHA-256 digest.

    Args:
        path: File path to hash.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_tracks_2025_as_current_official_reference() -> None:
    """Verify manifest tracks the promoted 2025 dataset as local production data."""
    manifest = load_kdris_source_manifest()

    assert manifest["current_official_reference_year"] == CURRENT_OFFICIAL_REFERENCE_YEAR
    assert manifest["local_dataset_year"] == 2025
    assert manifest["local_dataset_status"] == LOCAL_DATASET_STATUS
    assert manifest["schema_version"] == "2.0"
    assert manifest["candidate_dataset_version"] == "2025"
    assert manifest["candidate_dataset_status"] == "promoted_to_production"
    assert manifest["operational_dataset_version"] == "2025"
    assert manifest["current_errata_version"] == "2026-03-16"
    assert get_current_official_reference_year() == CURRENT_OFFICIAL_REFERENCE_YEAR


def test_manifest_contains_required_official_and_local_sources() -> None:
    """Verify manifest includes current official, legacy, and fixture sources."""
    manifest = load_kdris_source_manifest()
    source_ids = {source["id"] for source in manifest["sources"]}

    assert "mohw_2025_kdris_press_release" in source_ids
    assert "kns_2025_kdris_publication" in source_ids
    assert "mohw_2020_kdris_publication" in source_ids
    assert "local_kdris_2020_sample_fixture" in source_ids


def test_manifest_source_urls_and_license_notes_are_recorded() -> None:
    """Verify every source has a URL, retrieval date, and license note."""
    manifest = load_kdris_source_manifest()

    for source in manifest["sources"]:
        assert source["source_url"].startswith(("https://", "data/"))
        assert source["retrieved_at"]
        assert source["license_note"]
        assert source["errata_note"]


def test_local_fixture_checksum_matches_manifest() -> None:
    """Verify the manifest checksum matches the local KDRIs fixture file."""
    manifest = load_kdris_source_manifest()
    fixture = next(
        source
        for source in manifest["sources"]
        if source["id"] == "local_kdris_2020_sample_fixture"
    )

    assert fixture["checksum_sha256"] == _sha256(DEFAULT_KDRIS_CSV)


def test_2025_dataset_checksum_matches_manifest() -> None:
    """Verify the manifest checksum matches the approved 2025 dataset."""
    manifest = load_kdris_source_manifest()
    artifact = next(
        artifact
        for artifact in manifest["dataset_artifacts"]
        if artifact["id"] == "kdris_2025_candidate"
    )

    assert artifact["status"] == "official_2025_approved"
    assert artifact["review_status"] == "approved"
    assert artifact["checksum_sha256"] == _sha256(DEFAULT_KDRIS_2025_CSV)


def test_2025_review_artifact_checksums_match_manifest() -> None:
    """Verify review artifact checksums are tracked before production promotion."""
    manifest = load_kdris_source_manifest()
    review_artifacts = {
        artifact["id"]: artifact
        for artifact in manifest["dataset_artifacts"]
        if artifact["id"].startswith("kdris_2025_") and artifact["status"] == "review_artifact"
    }

    assert set(review_artifacts) == {
        "kdris_2025_target_nutrient_inventory",
        "kdris_2025_candidate_review_rows",
        "kdris_2025_candidate_schema_issues",
        "kdris_2025_schema_decisions",
    }
    for artifact in review_artifacts.values():
        artifact_path = PROJECT_ROOT / artifact["path"]
        assert artifact["checksum_sha256"] == _sha256(artifact_path)


def test_manifest_requires_quality_gates_before_production() -> None:
    """Verify production promotion gates are explicit."""
    manifest = load_kdris_source_manifest()

    assert len(manifest["production_quality_gates"]) >= 4
    assert any("license" in gate for gate in manifest["production_quality_gates"])
