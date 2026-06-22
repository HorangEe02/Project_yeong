"""Tests for the sanitized supplement OCR provider smoke script."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

smoke = importlib.import_module("scripts.smoke_supplement_ocr_providers")


def test_parse_providers_rejects_unknown_selector() -> None:
    """Verify unsupported provider selectors fail before any request is sent."""
    with pytest.raises(SystemExit, match="unsupported providers"):
        smoke.parse_providers("configured,unknown")


def test_build_headers_uses_tokens_without_printing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify auth headers can be built from env vars for gateway smoke."""
    monkeypatch.setenv("LEMON_DEV_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setenv("LEMON_API_TOKEN", "api-token")

    headers = smoke.build_headers(
        gateway_token_env="LEMON_DEV_GATEWAY_TOKEN",
        bearer_token_env="LEMON_API_TOKEN",
    )

    assert headers == {
        "X-Lemon-Dev-Gateway-Token": "gateway-token",
        "Authorization": "Bearer api-token",
    }


def test_summarize_preview_returns_only_counts_and_metadata() -> None:
    """Verify preview summaries do not include raw OCR evidence fields."""
    summary = smoke.summarize_preview(
        {
            "status": "requires_confirmation",
            "pipeline_metadata": {
                "ocr_provider": "paddleocr_local",
                "llm_parser_used": True,
                "vision_roi_used": False,
            },
            "ingredient_candidates": [{"display_name": "Vitamin C"}],
            "label_sections": [{"section_id": "s1"}],
            "warnings": ["safe warning"],
            "layout_available": False,
            "action_required": "review_required",
            "evidence_spans": [{"text_excerpt": "do not echo"}],
        }
    )

    assert summary == {
        "preview_status": "requires_confirmation",
        "ocr_provider": "paddleocr_local",
        "llm_parser_used": True,
        "vision_roi_used": False,
        "ingredient_count": 1,
        "section_count": 1,
        "warning_count": 1,
        "layout_available": False,
        "action_required": "review_required",
    }
    assert "do not echo" not in repr(summary)


def test_summarize_error_keeps_only_stable_error_fields() -> None:
    """Verify error summaries avoid provider payload or detail text echoing."""
    summary = smoke.summarize_error(
        {
            "detail": {
                "code": "ocr_provider_unconfigured",
                "message": "contains operational detail",
                "requested_ocr_provider": "google_vision",
            }
        }
    )

    assert summary == {
        "error_code": "ocr_provider_unconfigured",
        "requested_ocr_provider": "google_vision",
    }
    assert "operational detail" not in repr(summary)


def test_content_type_for_path_maps_supported_images() -> None:
    """Verify multipart image content types match supported upload types."""
    assert smoke.content_type_for_path(Path("label.jpg")) == "image/jpeg"
    assert smoke.content_type_for_path(Path("label.jpeg")) == "image/jpeg"
    assert smoke.content_type_for_path(Path("label.webp")) == "image/webp"
    assert smoke.content_type_for_path(Path("label.png")) == "image/png"


def test_build_headers_omits_missing_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing optional tokens produce no auth headers."""
    monkeypatch.delenv("LEMON_DEV_GATEWAY_TOKEN", raising=False)
    monkeypatch.delenv("LEMON_API_TOKEN", raising=False)

    headers = smoke.build_headers(
        gateway_token_env="LEMON_DEV_GATEWAY_TOKEN",
        bearer_token_env="LEMON_API_TOKEN",
    )

    assert headers == {}
    assert "LEMON_DEV_GATEWAY_TOKEN" not in os.environ


def test_build_client_request_id_keeps_route_safe_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify smoke ids stay within the analyze route max_length."""
    monkeypatch.setattr(
        smoke,
        "uuid4",
        lambda: SimpleNamespace(hex="abcdef1234567890"),
    )

    request_id = smoke.build_client_request_id("x" * 120, "google_vision")

    assert len(request_id) <= smoke.CLIENT_REQUEST_ID_MAX_LENGTH
    assert request_id.endswith("google_vision-abcdef123456")
