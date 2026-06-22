"""Tests for the failed learning image deletion retry runner."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

retry_runner = importlib.import_module("scripts.retry_failed_learning_image_deletions")


class _FakeSessionContext:
    """Async context manager that returns a fake DB session."""

    def __init__(self) -> None:
        """Initialize context tracking."""
        self.session = object()

    async def __aenter__(self) -> object:
        """Return the fake session.

        Returns:
            Fake session object.
        """
        return self.session

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        """Close the fake session context.

        Args:
            exc_type: Exception type when the block failed.
            exc: Exception instance when the block failed.
            traceback: Exception traceback when the block failed.
        """
        _ = (exc_type, exc, traceback)


def _fake_sessionmaker() -> _FakeSessionContext:
    """Return a fresh fake async session context.

    Returns:
        Fake session context manager.
    """
    return _FakeSessionContext()


@pytest.mark.asyncio
async def test_run_cli_skips_when_object_storage_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify disabled storage does not enter DB retry cleanup."""
    monkeypatch.setattr(
        retry_runner,
        "get_settings",
        lambda: SimpleNamespace(learning_object_storage_provider="disabled"),
    )

    exit_code = await retry_runner.run_cli(["--limit", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status=skipped" in captured.out
    assert "reason=learning_object_storage_disabled" in captured.out
    assert "secret" not in captured.out.lower()


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify retry success output contains counts but no object references."""
    session_context = _FakeSessionContext()
    object_store = object()
    calls: dict[str, object] = {}

    async def fake_retry_failed_learning_image_object_deletions(
        *,
        session: object,
        object_store: object,
        limit: int,
    ) -> dict[str, int]:
        """Record retry arguments and return sanitized counts."""
        calls["session"] = session
        calls["object_store"] = object_store
        calls["limit"] = limit
        return {"scanned": 4, "deleted": 4, "failures": 0}

    monkeypatch.setattr(
        retry_runner,
        "get_settings",
        lambda: SimpleNamespace(learning_object_storage_provider="supabase_s3"),
    )
    monkeypatch.setattr(
        retry_runner,
        "build_learning_object_store",
        lambda _settings: object_store,
    )
    monkeypatch.setattr(retry_runner, "get_sessionmaker", lambda: lambda: session_context)
    monkeypatch.setattr(
        retry_runner,
        "retry_failed_learning_image_object_deletions",
        fake_retry_failed_learning_image_object_deletions,
    )

    exit_code = await retry_runner.run_cli(["--limit", "25"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == {
        "session": session_context.session,
        "object_store": object_store,
        "limit": 25,
    }
    assert "status=completed" in captured.out
    assert "scanned=4" in captured.out
    assert "deleted=4" in captured.out
    assert "failures=0" in captured.out
    assert "s3://" not in captured.out
    assert "object_uri" not in captured.out
    assert "secret" not in captured.out.lower()


@pytest.mark.asyncio
async def test_run_cli_returns_failure_when_retry_counts_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify retained failures return a non-zero exit code with sanitized counts."""

    async def fake_retry_failed_learning_image_object_deletions(
        *,
        session: object,
        object_store: object,
        limit: int,
    ) -> dict[str, int]:
        """Return a partial retry result."""
        _ = (session, object_store, limit)
        return {"scanned": 4, "deleted": 3, "failures": 1}

    monkeypatch.setattr(
        retry_runner,
        "get_settings",
        lambda: SimpleNamespace(learning_object_storage_provider="supabase_s3"),
    )
    monkeypatch.setattr(retry_runner, "build_learning_object_store", lambda _settings: object())
    monkeypatch.setattr(retry_runner, "get_sessionmaker", lambda: _fake_sessionmaker)
    monkeypatch.setattr(
        retry_runner,
        "retry_failed_learning_image_object_deletions",
        fake_retry_failed_learning_image_object_deletions,
    )

    exit_code = await retry_runner.run_cli(["--limit", "10"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "status=completed" in captured.out
    assert "scanned=4" in captured.out
    assert "deleted=3" in captured.out
    assert "failures=1" in captured.out
    assert "s3://" not in captured.out
    assert "secret" not in captured.out.lower()


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_exception_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify retry exceptions omit messages that may include private URLs."""

    async def fake_retry_failed_learning_image_object_deletions(
        *,
        session: object,
        object_store: object,
        limit: int,
    ) -> dict[str, int]:
        """Raise a sensitive error that should not be printed."""
        _ = (session, object_store, limit)
        raise RuntimeError("secret=s3://learning-images/private-object")

    monkeypatch.setattr(
        retry_runner,
        "get_settings",
        lambda: SimpleNamespace(learning_object_storage_provider="supabase_s3"),
    )
    monkeypatch.setattr(retry_runner, "build_learning_object_store", lambda _settings: object())
    monkeypatch.setattr(retry_runner, "get_sessionmaker", lambda: _fake_sessionmaker)
    monkeypatch.setattr(
        retry_runner,
        "retry_failed_learning_image_object_deletions",
        fake_retry_failed_learning_image_object_deletions,
    )

    exit_code = await retry_runner.run_cli(["--limit", "10"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "status=failed" in captured.out
    assert "error_type=RuntimeError" in captured.out
    assert "s3://" not in captured.out
    assert "private-object" not in captured.out
    assert "secret" not in captured.out.lower()


def test_limit_parser_rejects_unbounded_retry() -> None:
    """Verify the operator must choose a bounded retry batch size."""
    with pytest.raises(argparse.ArgumentTypeError):
        retry_runner._bounded_limit("0")
    with pytest.raises(argparse.ArgumentTypeError):
        retry_runner._bounded_limit("1001")
