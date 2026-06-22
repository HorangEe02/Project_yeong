"""Tests for supplement category seed cleanup dry-run/apply."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

cleanup = importlib.import_module("scripts.apply_supplement_category_seed_cleanup")
preflight = importlib.import_module("scripts.preflight_supplement_category_seed_cleanup")


@pytest.mark.asyncio
async def test_cleanup_dry_run_plans_extra_categories_without_literals(tmp_path: Path) -> None:
    """Verify dry-run plans extra active category deactivation without DB writes."""
    staging_path = _write_staging(tmp_path, ["alpha", "beta"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "beta", "legacy-extra"])
    preflight_path = _write_preflight(tmp_path, staging_path, active_dump)

    summary = await cleanup.apply_category_seed_cleanup(
        taxonomy_staging=staging_path,
        active_category_dump=active_dump,
        cleanup_preflight=preflight_path,
    )
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["status"] == "ready_for_manual_category_seed_cleanup"
    assert summary["expected_category_count"] == 2
    assert summary["active_db_category_count"] == 3
    assert summary["extra_active_category_count"] == 1
    assert summary["planned_category_deactivation_count"] == 1
    assert summary["apply_requested"] is False
    assert summary["preflight_only"] is True
    assert summary["db_write_performed"] is False
    assert summary["db_update_performed"] is False
    assert summary["database_connection_opened"] is False
    assert "legacy-extra" not in serialized
    assert "alpha" not in serialized
    assert "beta" not in serialized


@pytest.mark.asyncio
async def test_cleanup_blocks_stale_preflight_counts(tmp_path: Path) -> None:
    """Verify stale preflight evidence fails closed before repository access."""
    staging_path = _write_staging(tmp_path, ["alpha", "beta"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "beta", "legacy-extra"])
    preflight_path = _write_preflight(tmp_path, staging_path, active_dump)
    preflight_summary = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight_summary["extra_active_category_count"] = 99
    preflight_path.write_text(json.dumps(preflight_summary), encoding="utf-8")

    with pytest.raises(cleanup.CategorySeedCleanupError, match="stale"):
        await cleanup.apply_category_seed_cleanup(
            taxonomy_staging=staging_path,
            active_category_dump=active_dump,
            cleanup_preflight=preflight_path,
        )


@pytest.mark.asyncio
async def test_cleanup_apply_requires_confirmation_token(tmp_path: Path) -> None:
    """Verify apply mode cannot run without explicit manual cleanup confirmation."""
    staging_path = _write_staging(tmp_path, ["alpha"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "legacy-extra"])
    preflight_path = _write_preflight(tmp_path, staging_path, active_dump)

    with pytest.raises(cleanup.CategorySeedCleanupError, match="confirmation"):
        await cleanup.apply_category_seed_cleanup(
            taxonomy_staging=staging_path,
            active_category_dump=active_dump,
            cleanup_preflight=preflight_path,
            apply_changes=True,
            confirm_manual_cleanup=False,
            repository=_FakeCleanupRepository(),
        )


@pytest.mark.asyncio
async def test_cleanup_apply_commits_repository_transaction(tmp_path: Path) -> None:
    """Verify confirmed apply soft-disables the planned extra categories."""
    staging_path = _write_staging(tmp_path, ["alpha", "beta"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "beta", "legacy-extra"])
    preflight_path = _write_preflight(tmp_path, staging_path, active_dump)
    repository = _FakeCleanupRepository()

    summary = await cleanup.apply_category_seed_cleanup(
        taxonomy_staging=staging_path,
        active_category_dump=active_dump,
        cleanup_preflight=preflight_path,
        apply_changes=True,
        confirm_manual_cleanup=True,
        repository=repository,
    )

    assert summary["status"] == "manual_category_seed_cleanup_applied"
    assert summary["preflight_only"] is False
    assert summary["db_write_performed"] is True
    assert summary["db_update_performed"] is True
    assert summary["db_delete_performed"] is False
    assert summary["deactivated_category_count"] == 1
    assert repository.commit_count == 1
    assert repository.rollback_count == 0
    assert repository.deactivated_batch_sizes == [1]


@pytest.mark.asyncio
async def test_cleanup_apply_rolls_back_on_repository_failure(tmp_path: Path) -> None:
    """Verify repository failures rollback the cleanup transaction."""
    staging_path = _write_staging(tmp_path, ["alpha"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "legacy-extra"])
    preflight_path = _write_preflight(tmp_path, staging_path, active_dump)
    repository = _FakeCleanupRepository(raise_on_deactivate=True)

    with pytest.raises(RuntimeError, match="repository failed"):
        await cleanup.apply_category_seed_cleanup(
            taxonomy_staging=staging_path,
            active_category_dump=active_dump,
            cleanup_preflight=preflight_path,
            apply_changes=True,
            confirm_manual_cleanup=True,
            repository=repository,
        )

    assert repository.commit_count == 0
    assert repository.rollback_count == 1


@pytest.mark.asyncio
async def test_cleanup_cli_writes_dry_run_summary(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI writes a redacted dry-run summary."""
    staging_path = _write_staging(tmp_path, ["alpha"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "legacy-extra"])
    preflight_path = _write_preflight(tmp_path, staging_path, active_dump)
    summary_path = tmp_path / "cleanup-apply.json"

    exit_code = await cleanup.run_cli(
        [
            "--taxonomy-staging",
            str(staging_path),
            "--active-category-dump",
            str(active_dump),
            "--cleanup-preflight",
            str(preflight_path),
            "--summary",
            str(summary_path),
        ]
    )
    stdout = capsys.readouterr().out
    saved = json.loads(summary_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert saved["status"] == "ready_for_manual_category_seed_cleanup"
    assert "legacy-extra" not in stdout


@pytest.mark.asyncio
async def test_cleanup_cli_loads_env_file_without_printing_database_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    """Verify cleanup CLI env-file loading keeps DB values out of output.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest output capture fixture.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    staging_path = _write_staging(tmp_path, ["alpha"])
    active_dump = _write_active_dump(tmp_path, ["alpha", "legacy-extra"])
    preflight_path = _write_preflight(tmp_path, staging_path, active_dump)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL='postgresql+asyncpg://example:secret@example.invalid/db'\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "cleanup-apply.json"
    seen_database_url: list[str] = []

    async def _fake_apply_category_seed_cleanup(**_kwargs: object) -> dict[str, object]:
        """Return count-only summary after checking env loading.

        Returns:
            Redacted fake cleanup summary.
        """
        seen_database_url.append(os.environ["DATABASE_URL"])
        return {
            "schema_version": cleanup.SCHEMA_VERSION,
            "status": "ready_for_manual_category_seed_cleanup",
            "db_write_performed": False,
            "db_update_performed": False,
            "db_delete_performed": False,
        }

    monkeypatch.setattr(
        cleanup,
        "apply_category_seed_cleanup",
        _fake_apply_category_seed_cleanup,
    )

    exit_code = await cleanup.run_cli(
        [
            "--taxonomy-staging",
            str(staging_path),
            "--active-category-dump",
            str(active_dump),
            "--cleanup-preflight",
            str(preflight_path),
            "--env-file",
            str(env_file),
            "--summary",
            str(summary_path),
            "--apply",
            "--confirm-manual-cleanup",
            cleanup.CONFIRMATION_TOKEN,
        ]
    )

    stdout = capsys.readouterr().out
    summary_text = summary_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert seen_database_url == ["postgresql+asyncpg://example:secret@example.invalid/db"]
    assert "secret" not in stdout
    assert "example.invalid" not in stdout
    assert "secret" not in summary_text
    assert "example.invalid" not in summary_text


class _FakeCleanupRepository:
    """Repository double for cleanup apply tests."""

    def __init__(self, *, raise_on_deactivate: bool = False) -> None:
        """Initialize the fake repository.

        Args:
            raise_on_deactivate: Whether deactivation should fail.
        """
        self.raise_on_deactivate = raise_on_deactivate
        self.commit_count = 0
        self.rollback_count = 0
        self.deactivated_batch_sizes: list[int] = []

    async def deactivate_active_categories(self, category_keys: list[str]) -> int:
        """Record the planned deactivation batch.

        Args:
            category_keys: Extra active category keys.

        Returns:
            Deactivated row count.

        Raises:
            RuntimeError: When configured to simulate a repository failure.
        """
        if self.raise_on_deactivate:
            raise RuntimeError("repository failed")
        self.deactivated_batch_sizes.append(len(category_keys))
        return len(category_keys)

    async def commit(self) -> None:
        """Record commit calls."""
        self.commit_count += 1

    async def rollback(self) -> None:
        """Record rollback calls."""
        self.rollback_count += 1


def _write_preflight(tmp_path: Path, staging_path: Path, active_dump: Path) -> Path:
    """Write a cleanup preflight summary.

    Args:
        tmp_path: Pytest temporary directory.
        staging_path: Staging JSONL path.
        active_dump: Active category dump path.

    Returns:
        Preflight summary path.
    """
    summary = preflight.build_category_seed_cleanup_preflight(
        taxonomy_staging=staging_path,
        active_category_dump=active_dump,
    )
    path = tmp_path / "cleanup-preflight.json"
    path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return path


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
