"""Tests for sanitized learning private storage smoke runner."""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

smoke_runner = importlib.import_module("scripts.smoke_learning_private_storage")


@dataclass(frozen=True)
class _StoredObject:
    """Minimal stored object reference for smoke tests."""

    object_uri: str
    provider: str
    version_id: str | None = None


class _FakeObjectStore:
    """Fake object store that records round-trip smoke calls."""

    def __init__(self, *, body: bytes | None = None) -> None:
        """Initialize the fake store.

        Args:
            body: Optional body returned by get_image.
        """
        self.body = body
        self.calls: list[str] = []

    async def put_image(self, payload: Any) -> _StoredObject:
        """Record the put call and retain image bytes for get."""
        self.calls.append("put")
        self.body = payload.image_bytes
        return _StoredObject(
            object_uri="s3://learning-images/private/secret-object",
            provider="supabase_s3",
            version_id="private-version",
        )

    async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
        """Record the get call."""
        _ = (object_uri, version_id)
        self.calls.append("get")
        assert self.body is not None
        return self.body

    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        """Record the delete call."""
        _ = (object_uri, version_id)
        self.calls.append("delete")


@pytest.mark.asyncio
async def test_run_cli_skips_without_live_gate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify live storage smoke is opt-in by environment variable."""
    monkeypatch.delenv(smoke_runner.RUN_GATE_ENV, raising=False)

    exit_code = await smoke_runner.run_cli([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status=skipped" in captured.out


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify success output excludes object URI, metadata, and secrets."""
    store = _FakeObjectStore()
    monkeypatch.setenv(smoke_runner.RUN_GATE_ENV, "1")
    monkeypatch.setattr(
        smoke_runner,
        "get_settings",
        lambda: SimpleNamespace(learning_object_storage_provider="supabase_s3"),
    )
    monkeypatch.setattr(smoke_runner, "build_learning_object_store", lambda _settings: store)

    exit_code = await smoke_runner.run_cli([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert store.calls == ["put", "get", "delete"]
    assert "status=passed" in captured.out
    assert "round_trip=true" in captured.out
    assert "s3://" not in captured.out
    assert "object_uri" not in captured.out
    assert "metadata" not in captured.out
    assert "secret" not in captured.out.lower()


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify failures omit SDK exception details and retained object references."""

    class FailingObjectStore(_FakeObjectStore):
        """Fake store that fails during get with a sensitive exception message."""

        async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
            """Raise a sensitive error that should not be printed."""
            _ = (object_uri, version_id)
            self.calls.append("get")
            raise RuntimeError("secret=https://example.invalid/private-object")

    store = FailingObjectStore()
    monkeypatch.setenv(smoke_runner.RUN_GATE_ENV, "1")
    monkeypatch.setattr(
        smoke_runner,
        "get_settings",
        lambda: SimpleNamespace(learning_object_storage_provider="supabase_s3"),
    )
    monkeypatch.setattr(smoke_runner, "build_learning_object_store", lambda _settings: store)

    exit_code = await smoke_runner.run_cli([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert store.calls == ["put", "get", "delete"]
    assert "status=failed" in captured.out
    assert "error_type=RuntimeError" in captured.out
    assert "s3://" not in captured.out
    assert "example.invalid" not in captured.out
    assert "secret" not in captured.out.lower()


@pytest.mark.asyncio
async def test_run_cli_deletes_object_on_round_trip_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify failed byte comparison still cleans up the smoke object."""

    class MismatchObjectStore(_FakeObjectStore):
        """Fake store that returns different bytes during get."""

        async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
            """Return mismatched bytes."""
            _ = (object_uri, version_id)
            self.calls.append("get")
            return b"different"

    store = MismatchObjectStore()
    monkeypatch.setenv(smoke_runner.RUN_GATE_ENV, "1")
    monkeypatch.setattr(
        smoke_runner,
        "get_settings",
        lambda: SimpleNamespace(learning_object_storage_provider="supabase_s3"),
    )
    monkeypatch.setattr(smoke_runner, "build_learning_object_store", lambda _settings: store)

    exit_code = await smoke_runner.run_cli([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert store.calls == ["put", "get", "delete"]
    assert "error_type=RoundTripMismatch" in captured.out
    assert "s3://" not in captured.out
    assert "secret" not in captured.out.lower()
