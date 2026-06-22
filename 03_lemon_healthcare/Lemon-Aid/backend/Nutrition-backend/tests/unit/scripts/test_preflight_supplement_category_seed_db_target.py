"""Tests for category seed DB target safety preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

preflight = importlib.import_module("scripts.preflight_supplement_category_seed_db_target")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON object fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _category_seed_gate(
    *,
    allowed: bool = True,
    status: str = "ready_for_category_seed_db_apply",
    product_allowed: bool = False,
    db_write_performed: bool = False,
) -> dict[str, Any]:
    """Return a redacted category seed apply gate fixture.

    Args:
        allowed: Category seed apply gate value.
        status: Gate status token.
        product_allowed: Product DB apply flag.
        db_write_performed: Whether the gate claims a DB write happened.

    Returns:
        Gate payload.
    """
    return {
        "schema_version": "supplement-category-seed-db-apply-gate-v1",
        "status": status,
        "category_seed_db_apply_allowed": allowed,
        "product_db_apply_allowed": product_allowed,
        "product_category_db_apply_allowed": product_allowed,
        "db_write_performed": db_write_performed,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": [
            "https://docs.python.org/3/library/json.html",
            "https://www.postgresql.org/docs/current/ddl-constraints.html",
        ],
    }


def _gate_path(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    """Write a default gate fixture.

    Args:
        tmp_path: Temporary directory.
        payload: Optional gate payload override.

    Returns:
        Gate fixture path.
    """
    return _write_json(tmp_path / "category-seed-gate.json", payload or _category_seed_gate())


def test_db_target_preflight_allows_local_development_target(tmp_path: Path) -> None:
    """Verify local development PostgreSQL target passes without opening a DB connection."""
    summary = preflight.build_db_target_preflight(
        category_seed_apply_gate=_gate_path(tmp_path),
        database_url="postgresql+asyncpg://localhost:5432/lemon",
        environment="development",
    )

    assert summary["schema_version"] == "supplement-category-seed-db-target-preflight-v1"
    assert summary["status"] == "ready_for_local_category_seed_apply"
    assert summary["category_seed_db_apply_target_allowed"] is True
    assert summary["database_host_class"] == "local"
    assert summary["database_target_kind"] == "local_postgres"
    assert summary["database_driver"] == "postgresql+asyncpg"
    assert summary["database_name_present"] is True
    assert summary["database_auth_present"] is False
    assert summary["db_connection_opened"] is False
    assert summary["db_write_performed"] is False
    assert summary["failed_conditions"] == []


def test_db_target_preflight_blocks_remote_host(tmp_path: Path) -> None:
    """Verify remote or unknown DB hosts fail closed."""
    summary = preflight.build_db_target_preflight(
        category_seed_apply_gate=_gate_path(tmp_path),
        database_url="postgresql+asyncpg://db.example.test:5432/lemon",
        environment="development",
    )

    assert summary["status"] == "blocked_by_db_target_safety"
    assert summary["category_seed_db_apply_target_allowed"] is False
    assert summary["database_host_class"] == "remote_or_unknown"
    assert "database_host_is_local" in summary["failed_conditions"]


def test_db_target_preflight_blocks_production_environment(tmp_path: Path) -> None:
    """Verify production environment fails closed even with a local-looking URL."""
    summary = preflight.build_db_target_preflight(
        category_seed_apply_gate=_gate_path(tmp_path),
        database_url="postgresql+asyncpg://localhost:5432/lemon",
        environment="production",
    )

    assert summary["status"] == "blocked_by_db_target_safety"
    assert summary["category_seed_db_apply_target_allowed"] is False
    assert "environment_is_development" in summary["failed_conditions"]


def test_db_target_preflight_blocks_when_gate_is_not_category_only(tmp_path: Path) -> None:
    """Verify product DB apply permission in the prior gate blocks this preflight."""
    gate_payload = _category_seed_gate(product_allowed=True)

    summary = preflight.build_db_target_preflight(
        category_seed_apply_gate=_gate_path(tmp_path, gate_payload),
        database_url="postgresql+asyncpg://localhost:5432/lemon",
        environment="development",
    )

    assert summary["status"] == "blocked_by_db_target_safety"
    assert summary["category_seed_db_apply_target_allowed"] is False
    assert "product_apply_blocked" in summary["failed_conditions"]
    assert "product_category_apply_blocked" in summary["failed_conditions"]


def test_db_target_preflight_blocks_when_gate_claims_db_write(tmp_path: Path) -> None:
    """Verify any previous DB write claim fails closed before another apply step."""
    gate_payload = _category_seed_gate(db_write_performed=True)

    summary = preflight.build_db_target_preflight(
        category_seed_apply_gate=_gate_path(tmp_path, gate_payload),
        database_url="postgresql+asyncpg://localhost:5432/lemon",
        environment="development",
    )

    assert summary["status"] == "blocked_by_db_target_safety"
    assert summary["category_seed_db_apply_target_allowed"] is False
    assert "apply_gate_performed_no_db_write" in summary["failed_conditions"]


def test_db_target_preflight_rejects_raw_database_url_in_gate_payload(tmp_path: Path) -> None:
    """Verify unsafe raw DB URL keys are rejected instead of copied into reports."""
    gate_payload = _category_seed_gate()
    gate_payload["database_url"] = "postgresql+asyncpg://localhost:5432/lemon"

    with pytest.raises(preflight.CategorySeedDbTargetPreflightError, match="unsafe key"):
        preflight.build_db_target_preflight(
            category_seed_apply_gate=_gate_path(tmp_path, gate_payload),
            database_url="postgresql+asyncpg://localhost:5432/lemon",
            environment="development",
        )


def test_db_target_preflight_cli_writes_redacted_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output omits raw DB URL, credentials, and absolute paths."""
    gate_path = _gate_path(tmp_path)
    output_path = tmp_path / "target-preflight.json"
    markdown_path = tmp_path / "target-preflight.md"
    monkeypatch.setattr(
        preflight,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+asyncpg://localhost:5432/lemon",
            environment="development",
        ),
    )

    preflight.main(
        [
            "--category-seed-apply-gate",
            str(gate_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    combined = "\n".join(
        [stdout, json.dumps(summary, ensure_ascii=False, sort_keys=True), markdown]
    )
    assert summary["status"] == "ready_for_local_category_seed_apply"
    assert "Supplement Category Seed DB Target Preflight" in markdown
    assert str(tmp_path) not in combined
    assert "postgresql+asyncpg://" not in combined
    assert "lemon:lemon" not in combined
    assert "@localhost" not in combined
