"""Tests for learning manual-review decision runner."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from uuid import uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

review_runner = importlib.import_module("scripts.apply_learning_manual_review_decision")


@pytest.mark.asyncio
async def test_run_cli_approve_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify approval output excludes metadata, object URI, and secrets."""
    image_object_id = uuid4()

    async def fake_apply_learning_manual_review_decision(
        *,
        image_object_id: object,
        decision: str,
    ) -> dict[str, object]:
        """Return a successful approval summary."""
        return {
            "decision": decision,
            "image_object_id": str(image_object_id),
            "embedding_job_created": True,
            "embedding_job_id": str(uuid4()),
        }

    monkeypatch.setattr(
        review_runner,
        "apply_learning_manual_review_decision",
        fake_apply_learning_manual_review_decision,
    )

    exit_code = await review_runner.run_cli(
        ["--image-object-id", str(image_object_id), "--decision", "approve"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "decision=approve" in captured.out
    assert "applied=true" in captured.out
    assert "object_uri" not in captured.out
    assert "metadata" not in captured.out
    assert "secret" not in captured.out.lower()


@pytest.mark.asyncio
async def test_run_cli_rejects_missing_pending_review(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify missing items fail without leaking private fields."""
    image_object_id = uuid4()

    async def fake_apply_learning_manual_review_decision(
        *,
        image_object_id: object,
        decision: str,
    ) -> dict[str, object]:
        """Return a rejected=false summary."""
        return {
            "decision": decision,
            "image_object_id": str(image_object_id),
            "rejected": False,
        }

    monkeypatch.setattr(
        review_runner,
        "apply_learning_manual_review_decision",
        fake_apply_learning_manual_review_decision,
    )

    exit_code = await review_runner.run_cli(
        ["--image-object-id", str(image_object_id), "--decision", "reject"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "decision=reject" in captured.out
    assert "rejected=false" in captured.out
    assert "object_uri" not in captured.out
    assert "metadata" not in captured.out
