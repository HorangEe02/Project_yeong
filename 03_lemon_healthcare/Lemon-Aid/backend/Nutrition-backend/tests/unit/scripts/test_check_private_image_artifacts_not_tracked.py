"""Tests for private image artifact Git tracking checks."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

check = importlib.import_module("scripts.check_private_image_artifacts_not_tracked")


def test_tracking_report_passes_without_tracked_images(tmp_path: Path) -> None:
    """Verify non-image tracked files do not block the private image gate."""
    protected = tmp_path / "outputs"
    protected.mkdir()

    payload = check.build_private_image_tracking_report(
        repo_root=tmp_path,
        paths=[protected],
        tracked_files=[
            "outputs/generated/report.json",
            "outputs/generated/review.md",
        ],
    )

    assert payload["passed"] is True
    assert payload["tracked_private_image_count"] == 0
    assert payload["tracked_private_image_extension_counts"] == {}


def test_tracking_report_blocks_tracked_private_images_without_paths(tmp_path: Path) -> None:
    """Verify tracked image files fail without leaking file or local paths."""
    protected = tmp_path / "outputs"
    protected.mkdir()

    payload = check.build_private_image_tracking_report(
        repo_root=tmp_path,
        paths=[protected],
        tracked_files=[
            "outputs/generated/private-review-photo.jpg",
            "outputs/generated/private-detail.png",
            "docs/public-diagram.png",
        ],
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert payload["passed"] is False
    assert payload["tracked_private_image_count"] == 2
    assert payload["tracked_private_image_extension_counts"] == {
        ".jpg": 1,
        ".png": 1,
    }
    assert "private-review-photo" not in serialized
    assert "private-detail" not in serialized
    assert str(tmp_path) not in serialized
    assert "/Users/" not in serialized
    assert "/Volumes/" not in serialized


def test_tracking_report_rejects_outside_paths(tmp_path: Path) -> None:
    """Verify protected paths must stay inside the repository."""
    outside = tmp_path.parent / "outside"

    with pytest.raises(check.PrivateImageTrackingError, match="outside the repository"):
        check.build_private_image_tracking_report(
            repo_root=tmp_path,
            paths=[outside],
            tracked_files=[],
        )


def test_tracking_report_normalizes_extensions(tmp_path: Path) -> None:
    """Verify suffix matching is case-insensitive and dot-normalized."""
    protected = tmp_path / "outputs"
    protected.mkdir()

    payload: dict[str, Any] = check.build_private_image_tracking_report(
        repo_root=tmp_path,
        paths=[protected],
        image_extensions=("JPG",),
        tracked_files=[
            "outputs/generated/private-review-photo.JPG",
            "outputs/generated/private-review-photo.png",
        ],
    )

    assert payload["tracked_private_image_count"] == 1
    assert payload["image_extensions"] == [".jpg"]
