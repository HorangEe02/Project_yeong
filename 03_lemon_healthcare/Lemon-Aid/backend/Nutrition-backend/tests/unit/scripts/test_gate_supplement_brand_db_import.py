"""Tests for supplement brand DB import gate reports."""

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

gate = importlib.import_module("scripts.gate_supplement_brand_db_import")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _preflight_payload(
    *,
    require_all_reviewed: bool = True,
    ready: bool = False,
    approved_count: int = 0,
    blank_count: int = 388,
    pending_count: int = 388,
) -> dict[str, Any]:
    """Return a brand decision preflight fixture.

    Args:
        require_all_reviewed: Whether strict review was requested.
        ready: Whether strict/requested apply flags are true.
        approved_count: Approved decision count.
        blank_count: Blank decision count.
        pending_count: Pending operator action count.

    Returns:
        Preflight payload.
    """
    valid_count = approved_count if ready else 0
    return {
        "schema_version": "supplement-brand-review-decision-preflight-v1",
        "brand_candidate_count": 388,
        "decision_row_count": 388,
        "valid_decision_count": valid_count,
        "approved_decision_count": approved_count,
        "blocked_decision_count": 0,
        "blank_decision_count": blank_count,
        "invalid_decision_count": 0,
        "unmatched_decision_count": 0,
        "missing_decision_count": 0,
        "pending_operator_action_count": pending_count,
        "decision_counts": {"blank": blank_count} if blank_count else {"approve": approved_count},
        "invalid_reason_counts": {},
        "require_all_reviewed": require_all_reviewed,
        "ready_for_partial_apply": ready,
        "ready_for_strict_apply": ready,
        "ready_for_requested_apply": ready if require_all_reviewed else True,
        "next_operator_action": (
            "build_approved_product_import_manifest" if ready else "complete_operator_brand_review"
        ),
        "db_write_performed": False,
        "approved_for_db_write_rows": 0,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def test_brand_db_import_gate_blocks_blank_review(tmp_path: Path) -> None:
    """Verify blank decision rows block product import manifest creation."""
    preflight_path = _write_json(tmp_path / "preflight.json", _preflight_payload())

    summary = gate.build_brand_db_import_gate(brand_decision_preflight=preflight_path)
    markdown = gate.build_markdown(summary)

    assert summary["schema_version"] == "supplement-brand-db-import-gate-v1"
    assert summary["status"] == "blocked_by_operator_review"
    assert summary["product_import_manifest_allowed"] is False
    assert summary["db_import_apply_allowed_now"] is False
    assert summary["db_import_apply_allowed_after_dry_run"] is False
    assert summary["brand_decision_preflight_hash"].startswith("fp-")
    assert len(summary["brand_decision_preflight_hash"]) == 15
    assert summary["blank_decision_count"] == 388
    assert "complete_operator_brand_review" in summary["next_steps"]
    assert "blocked_by_operator_review" in markdown
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False) + markdown


def test_brand_db_import_gate_allows_manifest_after_strict_ready_preflight(
    tmp_path: Path,
) -> None:
    """Verify strict complete review allows manifest build but not direct DB apply."""
    preflight_path = _write_json(
        tmp_path / "preflight.json",
        _preflight_payload(ready=True, approved_count=17, blank_count=0, pending_count=0),
    )

    summary = gate.build_brand_db_import_gate(brand_decision_preflight=preflight_path)

    assert summary["status"] == "ready_for_product_import_manifest"
    assert summary["product_import_manifest_allowed"] is True
    assert summary["db_import_apply_allowed_now"] is False
    assert summary["db_import_apply_allowed_after_dry_run"] is True
    assert summary["approved_decision_count"] == 17
    assert summary["next_steps"] == [
        "run_apply_supplement_brand_review_decisions_require_all_reviewed",
        "run_taxonomy_approved_manifest_import_dry_run_require_approved_products",
        "run_taxonomy_approved_manifest_db_apply_only_after_dry_run_ready",
    ]


def test_brand_db_import_gate_blocks_partial_apply_readiness(tmp_path: Path) -> None:
    """Verify partial apply readiness is insufficient for DB import preparation."""
    payload = _preflight_payload(
        require_all_reviewed=False,
        ready=True,
        approved_count=2,
        blank_count=0,
        pending_count=0,
    )
    payload["ready_for_strict_apply"] = False
    preflight_path = _write_json(tmp_path / "preflight.json", payload)

    summary = gate.build_brand_db_import_gate(brand_decision_preflight=preflight_path)

    assert summary["status"] == "blocked_by_operator_review"
    assert summary["strict_review_requested"] is False
    assert summary["product_import_manifest_allowed"] is False


def test_brand_db_import_gate_rejects_unsafe_preflight_payload(tmp_path: Path) -> None:
    """Verify unsafe preflight payloads fail closed."""
    payload = _preflight_payload()
    payload["raw_ocr_text"] = "unsafe"
    preflight_path = _write_json(tmp_path / "preflight.json", payload)

    with pytest.raises(ValueError, match="raw key"):
        gate.build_brand_db_import_gate(brand_decision_preflight=preflight_path)


def test_brand_db_import_gate_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted JSON and Markdown outputs."""
    preflight_path = _write_json(tmp_path / "preflight.json", _preflight_payload())
    output_path = tmp_path / "gate.json"
    markdown_path = tmp_path / "gate.md"

    gate.main(
        [
            "--brand-decision-preflight",
            str(preflight_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert summary["status"] == "blocked_by_operator_review"
    assert "blocked_by_operator_review" in markdown
    assert '"product_import_manifest_allowed": false' in stdout
    assert str(tmp_path) not in stdout
