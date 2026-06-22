"""Tests for the mobile ngrok camera readiness preflight."""

from __future__ import annotations

import importlib
import json
import sys
from http import HTTPStatus
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

readiness = importlib.import_module("scripts.check_mobile_ngrok_camera_readiness")


def test_parse_flutter_devices_counts_simulators_and_physical_devices() -> None:
    """Verify Flutter machine output is reduced to mobile device counts."""
    payload = json.dumps(
        [
            {
                "name": "iPhone 17",
                "targetPlatform": "ios",
                "emulator": True,
            },
            {
                "name": "iPhone",
                "targetPlatform": "ios",
                "emulator": False,
            },
            {
                "name": "Pixel",
                "targetPlatform": "android",
                "emulator": False,
            },
            {
                "name": "Android SDK",
                "targetPlatform": "android",
                "emulator": True,
            },
            {
                "name": "Chrome",
                "targetPlatform": "web-javascript",
                "emulator": False,
            },
        ]
    )

    summary = readiness.parse_flutter_devices(payload)

    assert summary == readiness.DeviceSummary(
        ios_simulators=1,
        ios_physical=1,
        android_emulators=1,
        android_physical=1,
    )


def test_parse_ngrok_tunnels_counts_only_matching_https_gateway() -> None:
    """Verify ngrok parsing avoids printing URLs and matches loopback gateway."""
    payload = json.dumps(
        {
            "tunnels": [
                {
                    "proto": "https",
                    "public_url": "https://example.ngrok.app",
                    "config": {"addr": "http://localhost:8010"},
                },
                {
                    "proto": "https",
                    "public_url": "https://other.ngrok.app",
                    "config": {"addr": "http://localhost:8765"},
                },
                {
                    "proto": "http",
                    "public_url": "http://example.ngrok.app",
                    "config": {"addr": "http://127.0.0.1:8010"},
                },
            ]
        }
    )

    summary = readiness.parse_ngrok_tunnels(
        payload,
        expected_gateway_url="http://127.0.0.1:8010",
    )

    assert summary == readiness.NgrokSummary(https_tunnels=2, gateway_matches=1)


def test_parse_ollama_tags_reports_model_presence_without_names() -> None:
    """Verify Ollama tags parsing keeps only sanitized count and presence flags."""
    payload = json.dumps(
        {
            "models": [
                {"name": "qwen3.5:9b"},
                {"name": "gemma4:e4b"},
            ]
        }
    )

    summary = readiness.parse_ollama_tags(payload, model="qwen3.5:9b")

    assert summary == readiness.OllamaSummary(
        model_present=True,
        model_count=2,
    )


def test_parse_ollama_tags_handles_missing_model_safely() -> None:
    """Verify missing Ollama parser model is reduced to a stable readiness flag."""
    payload = json.dumps({"models": [{"name": "gemma4:e4b"}]})

    summary = readiness.parse_ollama_tags(payload, model="qwen3.5:9b")

    assert summary == readiness.OllamaSummary(
        model_present=False,
        model_count=1,
    )


def test_load_flutter_devices_reports_sanitized_permission_error(monkeypatch) -> None:
    """Verify Flutter command failures do not leak raw stderr."""

    def fake_run(*_args, **_kwargs):
        return readiness.subprocess.CompletedProcess(
            args=["flutter", "devices", "--machine"],
            returncode=1,
            stdout="",
            stderr="/path/to/cache/engine.stamp: Operation not permitted",
        )

    monkeypatch.setattr(readiness.subprocess, "run", fake_run)

    summary = readiness.load_flutter_devices("flutter")

    assert summary == readiness.DeviceSummary(
        ios_simulators=0,
        ios_physical=0,
        android_emulators=0,
        android_physical=0,
        probe_status="permission_error",
    )


def test_probe_flutter_device_deploy_reports_developer_mode_blocker(monkeypatch) -> None:
    """Verify optional deploy probe classifies device trust failures safely."""

    def fake_run(*_args, **_kwargs):
        return readiness.subprocess.CompletedProcess(
            args=["flutter", "run"],
            returncode=1,
            stdout="",
            stderr="enable Developer Mode in Settings and trust this computer",
        )

    monkeypatch.setattr(readiness.subprocess, "run", fake_run)

    status = readiness.probe_flutter_device_deploy(
        flutter_bin="flutter",
        device_id="ios-device",
        api_base_url="http://127.0.0.1:8010/api/v1",
        gateway_token="local-token",
        flutter_workdir="mobile",
        timeout=1.0,
    )

    assert status == "developer_mode_or_trust_required"


def test_evaluate_readiness_reports_incomplete_when_optional_live_gates_missing() -> None:
    """Verify missing physical device and ngrok are incomplete unless required."""
    result = readiness.evaluate_readiness(
        backend_status=HTTPStatus.OK,
        gateway_status=HTTPStatus.OK,
        gateway_contract_status=HTTPStatus.OK,
        devices=readiness.DeviceSummary(
            ios_simulators=1,
            ios_physical=0,
            android_emulators=0,
            android_physical=0,
        ),
        ngrok=readiness.NgrokSummary(https_tunnels=0, gateway_matches=0),
        deploy_probe_status="not_checked",
        require_physical_device=False,
        require_gateway=False,
        require_ngrok=False,
    )

    assert result.exit_code == 0
    assert result.status == "incomplete"
    assert result.details["flutter_devices_probe"] == "ok"
    assert result.details["physical_device_ready"] is False
    assert result.details["device_deploy_probe"] == "not_checked"
    assert result.details["ngrok_ready"] is False


def test_evaluate_readiness_fails_when_required_live_gates_missing() -> None:
    """Verify required physical device and ngrok gates fail closed."""
    result = readiness.evaluate_readiness(
        backend_status=HTTPStatus.OK,
        gateway_status=HTTPStatus.UNAUTHORIZED,
        gateway_contract_status=HTTPStatus.UNAUTHORIZED,
        devices=readiness.DeviceSummary(
            ios_simulators=1,
            ios_physical=0,
            android_emulators=0,
            android_physical=0,
        ),
        ngrok=readiness.NgrokSummary(https_tunnels=1, gateway_matches=0),
        deploy_probe_status="not_checked",
        require_physical_device=True,
        require_gateway=True,
        require_ngrok=True,
    )

    assert result.exit_code == 1
    assert result.status == "failed"
    assert result.details["gateway_health"] == HTTPStatus.UNAUTHORIZED


def test_evaluate_readiness_fails_when_mobile_contract_is_broken() -> None:
    """Verify health-only success cannot hide a broken mobile API contract."""
    result = readiness.evaluate_readiness(
        backend_status=HTTPStatus.OK,
        gateway_status=HTTPStatus.OK,
        gateway_contract_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        devices=readiness.DeviceSummary(
            ios_simulators=1,
            ios_physical=0,
            android_emulators=0,
            android_physical=0,
        ),
        ngrok=readiness.NgrokSummary(https_tunnels=0, gateway_matches=0),
        deploy_probe_status="not_checked",
        require_physical_device=False,
        require_gateway=False,
        require_ngrok=False,
    )

    assert result.exit_code == 1
    assert result.status == "failed"
    assert result.details["gateway_contract"] == HTTPStatus.INTERNAL_SERVER_ERROR


def test_evaluate_readiness_fails_when_deploy_probe_is_blocked() -> None:
    """Verify device visibility alone is not treated as deploy readiness."""
    result = readiness.evaluate_readiness(
        backend_status=HTTPStatus.OK,
        gateway_status=HTTPStatus.OK,
        gateway_contract_status=HTTPStatus.OK,
        devices=readiness.DeviceSummary(
            ios_simulators=1,
            ios_physical=1,
            android_emulators=0,
            android_physical=0,
        ),
        ngrok=readiness.NgrokSummary(https_tunnels=0, gateway_matches=0),
        deploy_probe_status="developer_mode_or_trust_required",
        require_physical_device=True,
        require_gateway=True,
        require_ngrok=False,
    )

    assert result.exit_code == 1
    assert result.status == "failed"
    assert result.details["physical_device_ready"] is True
    assert result.details["device_deploy_probe"] == "developer_mode_or_trust_required"


def test_evaluate_readiness_fails_when_required_ollama_model_missing() -> None:
    """Verify a live OCR/parser smoke can require the local Ollama parser model."""
    result = readiness.evaluate_readiness(
        backend_status=HTTPStatus.OK,
        gateway_status=HTTPStatus.OK,
        gateway_contract_status=HTTPStatus.OK,
        devices=readiness.DeviceSummary(
            ios_simulators=1,
            ios_physical=1,
            android_emulators=0,
            android_physical=0,
        ),
        ngrok=readiness.NgrokSummary(https_tunnels=1, gateway_matches=1),
        deploy_probe_status="not_checked",
        require_physical_device=True,
        require_gateway=True,
        require_ngrok=True,
        ollama=readiness.OllamaSummary(
            model_present=False,
            model_count=1,
            probe_status="ok",
        ),
        require_ollama=True,
    )

    assert result.exit_code == 1
    assert result.status == "failed"
    assert result.details["ollama_probe"] == "ok"
    assert result.details["ollama_model_present"] is False


def test_format_result_is_single_line_and_sanitized() -> None:
    """Verify result formatting contains only sanitized key/value fields."""
    result = readiness.ReadinessResult(
        exit_code=0,
        status="ready",
        details={
            "backend_health": 200,
            "gateway_health": 200,
            "gateway_contract": 200,
            "ngrok_gateway_matches": 1,
            "physical_device_ready": True,
            "device_deploy_probe": "not_checked",
        },
    )

    formatted = readiness.format_result(result)

    assert formatted == (
        "status=ready backend_health=200 gateway_health=200 gateway_contract=200 "
        "ngrok_gateway_matches=1 physical_device_ready=True "
        "device_deploy_probe=not_checked"
    )
    assert "ngrok.app" not in formatted
    assert "token" not in formatted.lower()
