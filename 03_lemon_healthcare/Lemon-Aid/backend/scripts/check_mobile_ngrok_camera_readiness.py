"""Check local readiness for mobile ngrok camera smoke testing.

The script prints sanitized status flags only. It does not print bearer tokens,
gateway tokens, raw OCR payloads, image bytes, or public ngrok URLs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEV_GATEWAY_TOKEN_HEADER = "X-Lemon-Dev-Gateway-Token"


@dataclass(frozen=True)
class DeviceSummary:
    """Summarized Flutter device visibility.

    Args:
        ios_simulators: Number of visible iOS simulator devices.
        ios_physical: Number of visible physical iOS devices.
        android_emulators: Number of visible Android emulator devices.
        android_physical: Number of visible physical Android devices.
        probe_status: Sanitized Flutter device probe status.
    """

    ios_simulators: int
    ios_physical: int
    android_emulators: int
    android_physical: int
    probe_status: str = "ok"


@dataclass(frozen=True)
class NgrokSummary:
    """Summarized local ngrok tunnel state.

    Args:
        https_tunnels: Number of visible HTTPS tunnels.
        gateway_matches: Number of HTTPS tunnels that point to the expected gateway.
    """

    https_tunnels: int
    gateway_matches: int


@dataclass(frozen=True)
class OllamaSummary:
    """Summarized local Ollama parser readiness.

    Args:
        model_present: Whether the configured parser model appears in `/api/tags`.
        model_count: Number of models returned by the local Ollama API.
        probe_status: Sanitized status for the Ollama probe.
    """

    model_present: bool
    model_count: int
    probe_status: str = "ok"


@dataclass(frozen=True)
class ReadinessResult:
    """Computed readiness result.

    Args:
        exit_code: Process exit code for the selected requirements.
        status: Human-readable status label.
        details: Sanitized key/value details.
    """

    exit_code: int
    status: str
    details: dict[str, str | int | bool]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Optional CLI arguments.

    Returns:
        Parsed namespace.
    """
    parser = argparse.ArgumentParser(
        description="Check mobile ngrok camera smoke readiness without printing secrets.",
    )
    parser.add_argument("--backend-health-url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--gateway-health-url", default="http://127.0.0.1:8010/health")
    parser.add_argument(
        "--gateway-contract-url",
        default="http://127.0.0.1:8010/api/v1/me/privacy/consents",
        help="Gateway URL for the first backend-connected mobile app contract check.",
    )
    parser.add_argument("--expected-gateway-url", default="http://127.0.0.1:8010")
    parser.add_argument("--ngrok-api-url", default="http://127.0.0.1:4041/api/tunnels")
    parser.add_argument("--ollama-tags-url", default="http://127.0.0.1:11434/api/tags")
    parser.add_argument("--ollama-model", default="qwen3.5:9b")
    parser.add_argument("--flutter-bin", default="flutter")
    parser.add_argument("--flutter-workdir", default="mobile")
    parser.add_argument("--timeout-seconds", type=float, default=3.0)
    parser.add_argument("--check-device-deploy", action="store_true")
    parser.add_argument("--deploy-device-id")
    parser.add_argument(
        "--deploy-api-base-url",
        default="http://127.0.0.1:8010/api/v1",
    )
    parser.add_argument("--deploy-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--require-physical-device", action="store_true")
    parser.add_argument("--require-gateway", action="store_true")
    parser.add_argument("--require-ngrok", action="store_true")
    parser.add_argument("--require-ollama", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run readiness checks and print a sanitized one-line summary.

    Args:
        argv: Optional CLI arguments.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    token = os.environ.get("LEMON_DEV_GATEWAY_TOKEN", "").strip()
    backend_status = fetch_http_status(args.backend_health_url, timeout=args.timeout_seconds)
    gateway_status = fetch_http_status(
        args.gateway_health_url,
        timeout=args.timeout_seconds,
        gateway_token=token or None,
    )
    gateway_contract_status = fetch_http_status(
        args.gateway_contract_url,
        timeout=args.timeout_seconds,
        gateway_token=token or None,
    )
    devices = load_flutter_devices(args.flutter_bin)
    ngrok = load_ngrok_summary(
        args.ngrok_api_url,
        expected_gateway_url=args.expected_gateway_url,
        timeout=args.timeout_seconds,
    )
    ollama = load_ollama_summary(
        args.ollama_tags_url,
        model=args.ollama_model,
        timeout=args.timeout_seconds,
    )
    deploy_probe_status = "not_checked"
    if args.check_device_deploy:
        deploy_probe_status = probe_flutter_device_deploy(
            flutter_bin=args.flutter_bin,
            device_id=args.deploy_device_id,
            api_base_url=args.deploy_api_base_url,
            gateway_token=token or None,
            flutter_workdir=args.flutter_workdir,
            timeout=args.deploy_timeout_seconds,
        )
    result = evaluate_readiness(
        backend_status=backend_status,
        gateway_status=gateway_status,
        gateway_contract_status=gateway_contract_status,
        devices=devices,
        ngrok=ngrok,
        ollama=ollama,
        deploy_probe_status=deploy_probe_status,
        require_physical_device=args.require_physical_device,
        require_gateway=args.require_gateway,
        require_ngrok=args.require_ngrok,
        require_ollama=args.require_ollama,
    )
    print(format_result(result))
    return result.exit_code


def fetch_http_status(
    url: str,
    *,
    timeout: float,
    gateway_token: str | None = None,
) -> int | None:
    """Fetch only an HTTP status code from a URL.

    Args:
        url: URL to request.
        timeout: Request timeout in seconds.
        gateway_token: Optional gateway token header value.

    Returns:
        HTTP status code, or ``None`` when the URL is unreachable.
    """
    headers = {}
    if gateway_token:
        headers[DEV_GATEWAY_TOKEN_HEADER] = gateway_token
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except HTTPError as error:
        return int(error.code)
    except (OSError, URLError, ValueError):
        return None


def load_flutter_devices(flutter_bin: str) -> DeviceSummary:
    """Load Flutter device visibility using `flutter devices --machine`.

    Args:
        flutter_bin: Flutter executable path or command name.

    Returns:
        Summarized device counts. Command failures return an empty summary.
    """
    try:
        completed = subprocess.run(
            [flutter_bin, "devices", "--machine"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return DeviceSummary(
            ios_simulators=0,
            ios_physical=0,
            android_emulators=0,
            android_physical=0,
            probe_status="timeout",
        )
    except OSError:
        return DeviceSummary(
            ios_simulators=0,
            ios_physical=0,
            android_emulators=0,
            android_physical=0,
            probe_status="unavailable",
        )
    if completed.returncode != 0:
        probe_status = (
            "permission_error" if "Operation not permitted" in completed.stderr else "error"
        )
        return DeviceSummary(
            ios_simulators=0,
            ios_physical=0,
            android_emulators=0,
            android_physical=0,
            probe_status=probe_status,
        )
    return parse_flutter_devices(completed.stdout)


def parse_flutter_devices(payload: str) -> DeviceSummary:
    """Parse `flutter devices --machine` output.

    Args:
        payload: JSON device list emitted by Flutter.

    Returns:
        Summarized device counts.
    """
    try:
        devices = json.loads(payload)
    except json.JSONDecodeError:
        devices = []
    ios_simulators = 0
    ios_physical = 0
    android_emulators = 0
    android_physical = 0
    for device in devices if isinstance(devices, list) else []:
        if not isinstance(device, dict):
            continue
        platform = str(device.get("targetPlatform", "")).lower()
        is_emulator = bool(device.get("emulator"))
        if platform == "ios" and is_emulator:
            ios_simulators += 1
        elif platform == "ios":
            ios_physical += 1
        elif platform == "android" and is_emulator:
            android_emulators += 1
        elif platform == "android":
            android_physical += 1
    return DeviceSummary(
        ios_simulators=ios_simulators,
        ios_physical=ios_physical,
        android_emulators=android_emulators,
        android_physical=android_physical,
    )


def load_ngrok_summary(
    ngrok_api_url: str,
    *,
    expected_gateway_url: str,
    timeout: float,
) -> NgrokSummary:
    """Load sanitized ngrok tunnel state from the local ngrok API.

    Args:
        ngrok_api_url: Local ngrok API URL.
        expected_gateway_url: Expected local gateway upstream URL.
        timeout: Request timeout in seconds.

    Returns:
        Summarized tunnel state. Unreachable API returns an empty summary.
    """
    try:
        with urlopen(ngrok_api_url, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except (OSError, URLError, ValueError):
        return NgrokSummary(https_tunnels=0, gateway_matches=0)
    return parse_ngrok_tunnels(payload, expected_gateway_url=expected_gateway_url)


def load_ollama_summary(
    ollama_tags_url: str,
    *,
    model: str,
    timeout: float,
) -> OllamaSummary:
    """Load sanitized local Ollama model readiness from `/api/tags`.

    Args:
        ollama_tags_url: Local Ollama Tags API URL.
        model: Configured parser model tag that must be present for OCR parsing.
        timeout: Request timeout in seconds.

    Returns:
        Sanitized model presence summary. Raw model names are not printed by the
        caller.
    """
    try:
        with urlopen(ollama_tags_url, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except HTTPError:
        return OllamaSummary(model_present=False, model_count=0, probe_status="http_error")
    except TimeoutError:
        return OllamaSummary(model_present=False, model_count=0, probe_status="timeout")
    except (OSError, URLError, ValueError):
        return OllamaSummary(model_present=False, model_count=0, probe_status="unavailable")
    return parse_ollama_tags(payload, model=model)


def parse_ollama_tags(payload: str, *, model: str) -> OllamaSummary:
    """Parse an Ollama `/api/tags` response into sanitized readiness flags.

    Args:
        payload: JSON payload from the Ollama Tags API.
        model: Expected parser model tag.

    Returns:
        Sanitized model count and expected-model presence.
    """
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return OllamaSummary(model_present=False, model_count=0, probe_status="invalid_json")
    models = parsed.get("models", []) if isinstance(parsed, dict) else []
    model_names: set[str] = set()
    for item in models if isinstance(models, list) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if isinstance(name, str) and name.strip():
            model_names.add(name.strip())
    expected = model.strip()
    return OllamaSummary(
        model_present=bool(expected) and expected in model_names,
        model_count=len(model_names),
    )


def probe_flutter_device_deploy(
    *,
    flutter_bin: str,
    device_id: str | None,
    api_base_url: str,
    gateway_token: str | None,
    flutter_workdir: str,
    timeout: float,
) -> str:
    """Run an optional sanitized Flutter device deployment probe.

    Args:
        flutter_bin: Flutter executable path or command name.
        device_id: Target Flutter device ID.
        api_base_url: API base URL passed to the app.
        gateway_token: Optional development gateway token.
        flutter_workdir: Directory where the Flutter app lives.
        timeout: Deployment command timeout in seconds.

    Returns:
        Sanitized deployment probe status.
    """
    if not device_id:
        return "missing_device_id"
    command = [
        flutter_bin,
        "run",
        "-d",
        device_id,
        "--no-resident",
        f"--dart-define=LEMON_API_BASE_URL={api_base_url}",
    ]
    if gateway_token:
        command.append(f"--dart-define=LEMON_DEV_GATEWAY_TOKEN={gateway_token}")
    workdir = Path(flutter_workdir)
    status = "failed"
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            cwd=workdir if workdir.exists() else None,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        status = "timeout"
    except OSError:
        status = "unavailable"
    else:
        status = classify_flutter_deploy_output(
            returncode=completed.returncode,
            output=f"{completed.stdout}\n{completed.stderr}",
        )
    return status


def classify_flutter_deploy_output(*, returncode: int, output: str) -> str:
    """Classify Flutter deploy output into a sanitized status label.

    Args:
        returncode: Flutter process return code.
        output: Combined stdout and stderr.

    Returns:
        Sanitized deployment probe status.
    """
    if returncode == 0:
        return "launched"
    lowered = output.lower()
    marker_statuses = (
        (("developer mode", "trust this computer"), "developer_mode_or_trust_required"),
        (("code signing", "development team"), "signing_error"),
        (("no devices", "device not found"), "device_unavailable"),
        (("operation not permitted",), "permission_error"),
    )
    for markers, status in marker_statuses:
        if any(marker in lowered for marker in markers):
            return status
    return "failed"


def parse_ngrok_tunnels(payload: str, *, expected_gateway_url: str) -> NgrokSummary:
    """Parse local ngrok tunnel API output without exposing public URLs.

    Args:
        payload: JSON payload from the ngrok local API.
        expected_gateway_url: Expected local gateway upstream URL.

    Returns:
        Sanitized tunnel summary.
    """
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = {}
    tunnels = parsed.get("tunnels", []) if isinstance(parsed, dict) else []
    https_tunnels = 0
    gateway_matches = 0
    for tunnel in tunnels if isinstance(tunnels, list) else []:
        if not isinstance(tunnel, dict):
            continue
        if tunnel.get("proto") != "https":
            continue
        https_tunnels += 1
        config = tunnel.get("config", {})
        addr = config.get("addr") if isinstance(config, dict) else None
        if isinstance(addr, str) and _same_loopback_endpoint(
            addr,
            expected_gateway_url,
        ):
            gateway_matches += 1
    return NgrokSummary(https_tunnels=https_tunnels, gateway_matches=gateway_matches)


def evaluate_readiness(
    *,
    backend_status: int | None,
    gateway_status: int | None,
    gateway_contract_status: int | None,
    devices: DeviceSummary,
    ngrok: NgrokSummary,
    deploy_probe_status: str,
    require_physical_device: bool,
    require_gateway: bool,
    require_ngrok: bool,
    ollama: OllamaSummary | None = None,
    require_ollama: bool = False,
) -> ReadinessResult:
    """Evaluate selected mobile ngrok readiness requirements.

    Args:
        backend_status: Local backend health status.
        gateway_status: Local gateway health status.
        gateway_contract_status: Mobile app contract status through the local gateway.
        devices: Flutter device visibility summary.
        ngrok: Local ngrok tunnel summary.
        ollama: Local Ollama model readiness summary.
        deploy_probe_status: Optional Flutter device deployment probe status.
        require_physical_device: Whether at least one physical mobile device is required.
        require_gateway: Whether gateway health must be HTTP 200.
        require_ngrok: Whether a matching HTTPS ngrok tunnel is required.
        require_ollama: Whether the configured local Ollama parser model is required.

    Returns:
        Readiness result with sanitized details.
    """
    ollama = ollama or OllamaSummary(
        model_present=False,
        model_count=0,
        probe_status="not_checked",
    )
    physical_count = devices.ios_physical + devices.android_physical
    failures = []
    if backend_status != HTTPStatus.OK:
        failures.append("backend")
    if require_gateway and gateway_status != HTTPStatus.OK:
        failures.append("gateway")
    if gateway_status == HTTPStatus.OK and gateway_contract_status != HTTPStatus.OK:
        failures.append("gateway_contract")
    if require_ngrok and ngrok.gateway_matches < 1:
        failures.append("ngrok")
    if require_physical_device and physical_count < 1:
        failures.append("physical_device")
    if require_ollama and not ollama.model_present:
        failures.append("ollama")
    if deploy_probe_status not in {"not_checked", "launched"}:
        failures.append("device_deploy")

    details: dict[str, str | int | bool] = {
        "backend_health": backend_status or "unreachable",
        "gateway_health": gateway_status or "unreachable",
        "gateway_contract": gateway_contract_status or "unreachable",
        "ios_simulators": devices.ios_simulators,
        "ios_physical": devices.ios_physical,
        "android_emulators": devices.android_emulators,
        "android_physical": devices.android_physical,
        "flutter_devices_probe": devices.probe_status,
        "ngrok_https_tunnels": ngrok.https_tunnels,
        "ngrok_gateway_matches": ngrok.gateway_matches,
        "physical_device_ready": physical_count > 0,
        "device_deploy_probe": deploy_probe_status,
        "ngrok_ready": ngrok.gateway_matches > 0,
        "ollama_probe": ollama.probe_status,
        "ollama_model_present": ollama.model_present,
        "ollama_model_count": ollama.model_count,
    }
    if failures:
        return ReadinessResult(exit_code=1, status="failed", details=details)
    if (
        physical_count < 1
        or ngrok.gateway_matches < 1
        or gateway_status != HTTPStatus.OK
        or gateway_contract_status != HTTPStatus.OK
    ):
        return ReadinessResult(exit_code=0, status="incomplete", details=details)
    return ReadinessResult(exit_code=0, status="ready", details=details)


def format_result(result: ReadinessResult) -> str:
    """Format a readiness result as a sanitized single line.

    Args:
        result: Readiness result.

    Returns:
        Single-line status string.
    """
    parts = [f"status={result.status}"]
    for key, value in result.details.items():
        parts.append(f"{key}={value}")
    return " ".join(parts)


def _same_loopback_endpoint(left: str, right: str) -> bool:
    """Compare loopback URLs while treating common loopback hostnames equally."""
    left_parts = urlsplit(left)
    right_parts = urlsplit(right)
    return (
        _normalize_loopback_host(left_parts.hostname)
        == _normalize_loopback_host(right_parts.hostname)
        and left_parts.port == right_parts.port
        and left_parts.scheme == right_parts.scheme
    )


def _normalize_loopback_host(host: str | None) -> str | None:
    """Normalize common loopback aliases for local gateway matching."""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return "loopback"
    return host


if __name__ == "__main__":
    sys.exit(main())
