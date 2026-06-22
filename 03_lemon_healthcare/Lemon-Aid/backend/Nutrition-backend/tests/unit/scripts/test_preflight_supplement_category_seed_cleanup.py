"""Tests for supplement category seed cleanup preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

preflight = importlib.import_module("scripts.preflight_supplement_category_seed_cleanup")


def test_cleanup_preflight_reports_no_cleanup_when_db_matches_staging(
    tmp_path: Path,
) -> None:
    """Verify exact category seed matches do not request DB cleanup."""
    staging_path = _write_staging(tmp_path, ["alpha", "beta"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "beta"])

    summary = preflight.build_category_seed_cleanup_preflight(
        taxonomy_staging=staging_path,
        active_category_dump=active_dump,
    )

    assert summary["status"] == "no_cleanup_required"
    assert summary["expected_category_count"] == 2
    assert summary["active_db_category_count"] == 2
    assert summary["extra_active_category_count"] == 0
    assert summary["category_seed_exact_match"] is True
    assert summary["cleanup_required"] is False
    assert summary["db_write_performed"] is False


def test_cleanup_preflight_hashes_extra_active_categories_without_literals(
    tmp_path: Path,
) -> None:
    """Verify extra active categories are hash-only and require manual approval."""
    staging_path = _write_staging(tmp_path, ["alpha", "beta"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "beta", "legacy-extra"])

    summary = preflight.build_category_seed_cleanup_preflight(
        taxonomy_staging=staging_path,
        active_category_dump=active_dump,
    )
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["status"] == "manual_cleanup_required"
    assert summary["expected_category_count"] == 2
    assert summary["active_db_category_count"] == 3
    assert summary["matched_category_count"] == 2
    assert summary["missing_category_count"] == 0
    assert summary["extra_active_category_count"] == 1
    assert len(summary["extra_active_category_key_hashes"]) == 1
    assert summary["cleanup_required"] is True
    assert summary["cleanup_requires_manual_approval"] is True
    assert summary["cleanup_plan"]["operation"] == "deactivate_extra_active_categories"
    assert summary["db_update_performed"] is False
    assert "legacy-extra" not in serialized
    assert "alpha" not in serialized
    assert "beta" not in serialized


def test_cleanup_preflight_blocks_when_expected_categories_are_missing(
    tmp_path: Path,
) -> None:
    """Verify missing expected category rows are not treated as a cleanup-only task."""
    staging_path = _write_staging(tmp_path, ["alpha", "beta"])
    active_dump = _write_active_dump(tmp_path, ["alpha"])

    summary = preflight.build_category_seed_cleanup_preflight(
        taxonomy_staging=staging_path,
        active_category_dump=active_dump,
    )

    assert summary["status"] == "blocked_missing_expected_categories"
    assert summary["missing_category_count"] == 1
    assert summary["extra_active_category_count"] == 0
    assert summary["cleanup_required"] is False
    assert summary["category_seed_exact_match"] is False


def test_cleanup_preflight_cli_writes_summary(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI writes a redacted summary file."""
    staging_path = _write_staging(tmp_path, ["alpha"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "legacy-extra"])
    summary_path = tmp_path / "cleanup.json"

    exit_code = preflight.run_cli(
        [
            "--taxonomy-staging",
            str(staging_path),
            "--active-category-dump",
            str(active_dump),
            "--summary",
            str(summary_path),
        ]
    )
    stdout = capsys.readouterr().out
    saved = json.loads(summary_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert saved["status"] == "manual_cleanup_required"
    assert "legacy-extra" not in stdout


def _write_staging(tmp_path: Path, category_keys: list[str]) -> Path:
    """Write category seed staging rows.

    Args:
        tmp_path: Pytest temporary directory.
        category_keys: Category keys to include.

    Returns:
        Staging JSONL path.
    """
    path = tmp_path / "taxonomy.jsonl"
    rows = [
        {
            "schema_version": "supplement-taxonomy-db-staging-v1",
            "row_type": "category_seed",
            "category_key": key,
            "display_name": f"Category {index}",
            "source_folder_name": f"Category {index}",
            "sort_order": index,
            "requires_human_review": False,
            "approved_for_db_write": True,
        }
        for index, key in enumerate(category_keys)
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def _write_active_dump(tmp_path: Path, category_keys: list[str]) -> Path:
    """Write a plain text active category dump.

    Args:
        tmp_path: Pytest temporary directory.
        category_keys: Active category keys.

    Returns:
        Dump file path.
    """
    path = tmp_path / "active-categories.txt"
    path.write_text("\n".join(category_keys) + "\n", encoding="utf-8")
    return path
