"""Shared fixtures for operator script CLI tests."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from src.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_process_environment() -> Iterator[None]:
    """Restore ``os.environ`` and the settings cache after each test.

    Script CLIs intentionally load operator dotenv files straight into the
    process environment (``_load_env_file`` → ``os.environ.setdefault``) and
    clear the ``get_settings`` cache. Without restoration those values leak
    into later tests (e.g. ``DATABASE_URL`` breaking
    ``test_default_development_settings_load``).

    Yields:
        None. Cleanup runs after the test completes.
    """
    snapshot = os.environ.copy()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)
        get_settings.cache_clear()
