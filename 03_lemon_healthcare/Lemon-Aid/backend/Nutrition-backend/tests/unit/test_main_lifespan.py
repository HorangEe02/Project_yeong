"""Lifespan side-effect tests for ``src.main`` startup hooks."""

from __future__ import annotations

import os
from typing import Self, cast

import pytest
from fastapi import FastAPI
from PIL import Image
from src.config import Settings, get_settings
from src.main import lifespan


class _Sentinel:
    """Placeholder app object passed to the lifespan context manager.

    The real FastAPI application is unused by the current lifespan body, so a
    simple sentinel keeps the test free of FastAPI construction cost.
    """

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


@pytest.mark.asyncio
async def test_lifespan_sets_paddle_disable_model_source_check_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lifespan defaults the PaddleOCR connectivity-check env var to true."""
    monkeypatch.delenv("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", raising=False)
    get_settings.cache_clear()
    try:
        async with lifespan(cast(FastAPI, _Sentinel())):
            assert os.environ.get("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK") == "true"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_preserves_explicit_paddle_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lifespan does not overwrite an explicit PADDLE env override.

    Operators may set the env var to ``false`` directly when they need PaddleOCR
    to attempt a model-source probe; the lifespan must respect that choice.
    """
    monkeypatch.setenv("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "false")
    get_settings.cache_clear()
    try:
        async with lifespan(cast(FastAPI, _Sentinel())):
            assert os.environ.get("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK") == "false"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_applies_configured_pillow_pixel_limit() -> None:
    """Verify lifespan applies the configured Pillow safety pixel limit."""
    get_settings.cache_clear()
    try:
        async with lifespan(cast(FastAPI, _Sentinel())):
            settings = Settings(_env_file=None)
            assert settings.supplement_image_max_pixels == Image.MAX_IMAGE_PIXELS
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_logs_trusted_host_active_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify lifespan emits the active TrustedHost host list at startup.

    The startup log makes the host policy visible to operators so a missing
    ALLOWED_HOSTS env var cannot quietly degrade to the dev sentinel without
    being seen in routine log inspection.
    """
    monkeypatch.setenv("ALLOWED_HOSTS", '["example.com"]')
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    get_settings.cache_clear()
    try:
        async with lifespan(cast(FastAPI, _Sentinel())):
            pass
    finally:
        get_settings.cache_clear()

    stdout = capsys.readouterr().out
    assert "TrustedHost allowed_hosts" in stdout
    assert "example.com" in stdout
    assert "active=explicit" in stdout


@pytest.mark.asyncio
async def test_lifespan_rejects_lemon_app_without_privileged_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify startup fails fast when the lemon_app request role lacks privileged URLs.

    This proves the Stage-2 misconfiguration guard is actually wired into the
    startup path: a DATABASE_URL connecting as the non-superuser ``lemon_app``
    role without AUDIT/LEARNING privileged URLs must abort boot rather than let
    out-of-band audit and post-commit learning writes fail closed under FORCE RLS.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://lemon_app:pw@localhost:5432/lemon")
    monkeypatch.delenv("AUDIT_DATABASE_URL", raising=False)
    monkeypatch.delenv("LEARNING_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="lemon_app"):
            async with lifespan(cast(FastAPI, _Sentinel())):
                pass
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_rejects_inconsistent_ocr_provider_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify startup fails fast on an OCR config that yields no working primary OCR.

    PaddleOCR selected as primary while local OCR is disabled — the drift state when a
    CLOVA-only deployment (PaddleOCR retraining) loses its env overrides — must abort boot
    via the lifespan OCR pre-flight rather than surface as a 500 on the first analyze
    request. Proves the OCR provider guard is wired into the startup path.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("OCR_PRIMARY_PROVIDER", "paddleocr")
    monkeypatch.setenv("ENABLE_LOCAL_OCR", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="OCR provider configuration is invalid"):
            async with lifespan(cast(FastAPI, _Sentinel())):
                pass
    finally:
        get_settings.cache_clear()
