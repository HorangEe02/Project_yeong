"""Tests for the mobile ngrok backend gateway."""

from __future__ import annotations

import importlib
import io
import sys
from collections.abc import Iterable
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

gateway = importlib.import_module("scripts.dev_mobile_ngrok_backend_gateway")


class _FakeHeaders:
    """Case-insensitive request header container for handler unit tests."""

    def __init__(self, values: dict[str, str]) -> None:
        """Initialize fake headers.

        Args:
            values: Header values keyed by their original names.
        """
        self._values = values

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return a header value by case-insensitive key.

        Args:
            key: Header name.
            default: Value returned when the header is absent.

        Returns:
            Matching header value or ``default``.
        """
        normalized_key = key.lower()
        for header_key, value in self._values.items():
            if header_key.lower() == normalized_key:
                return value
        return default

    def items(self) -> Iterable[tuple[str, str]]:
        """Return original header items.

        Returns:
            Header item iterable.
        """
        return self._values.items()


class _FakeUpstreamResponse:
    """Context manager that mimics a urllib upstream response."""

    def __init__(self, *, status: int, body: bytes) -> None:
        """Initialize response data.

        Args:
            status: HTTP status code exposed to the gateway.
            body: Response body exposed to the gateway.
        """
        self.status = status
        self.headers = _FakeHeaders(
            {
                "server": "upstream-server",
                "date": "Mon, 25 May 2026 00:00:00 GMT",
                "content-type": "application/json",
            }
        )
        self._body = body

    def __enter__(self) -> _FakeUpstreamResponse:
        """Return the fake response."""
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        """Close the fake response context."""
        _ = (exc_type, exc, traceback)

    def read(self) -> bytes:
        """Return the fake response body.

        Returns:
            Response body bytes.
        """
        return self._body


def _new_handler(
    *,
    headers: dict[str, str],
    path: str = "/health",
    method: str = "GET",
    body: bytes = b"",
    gateway_token: str | None = None,
) -> gateway.MobileNgrokGatewayHandler:
    """Build a gateway request handler without opening sockets.

    Args:
        headers: Incoming request headers.
        path: Incoming request path.
        method: Incoming request method.
        body: Incoming request body.
        gateway_token: Optional token configured on the gateway.

    Returns:
        Partially initialized gateway handler for private-method unit tests.
    """
    handler = object.__new__(gateway.MobileNgrokGatewayHandler)
    handler.command = method
    handler.path = path
    handler.headers = _FakeHeaders(headers)
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.server = SimpleNamespace(
        config=gateway.GatewayConfig(
            backend_url="http://127.0.0.1:8000",
            timeout_seconds=2.0,
            gateway_token=gateway_token,
        )
    )
    return handler


def _lower_headers(request: Request) -> dict[str, str]:
    """Normalize urllib request headers for assertions.

    Args:
        request: Captured urllib request.

    Returns:
        Headers keyed by lowercase names.
    """
    return {key.lower(): value for key, value in request.header_items()}


def test_gateway_token_env_is_explicitly_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify env tokens are ignored unless token auth is explicitly required."""
    monkeypatch.setenv("LEMON_DEV_GATEWAY_TOKEN", "local-smoke-token")

    assert gateway._gateway_token_from_environment(require_token=False) is None
    assert gateway._gateway_token_from_environment(require_token=True) == "local-smoke-token"

    monkeypatch.delenv("LEMON_DEV_GATEWAY_TOKEN")
    with pytest.raises(SystemExit):
        gateway._gateway_token_from_environment(require_token=True)


def test_gateway_requires_token_before_proxying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify missing gateway tokens are rejected before upstream access."""
    handler = _new_handler(headers={}, gateway_token="local-smoke-token")
    responses: list[dict[str, object]] = []

    def fail_urlopen(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("unauthorized requests must not reach upstream")

    monkeypatch.setattr(gateway, "urlopen", fail_urlopen)
    handler._send_response = lambda **kwargs: responses.append(kwargs)  # type: ignore[method-assign]

    handler._proxy()

    assert responses == [
        {
            "status": HTTPStatus.UNAUTHORIZED,
            "headers": (("content-type", "application/json"),),
            "body": b'{"detail":"Development gateway token required."}',
        }
    ]


def test_gateway_rewrites_host_and_strips_gateway_token_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify public Host is rewritten and the gateway token is not forwarded."""
    handler = _new_handler(
        headers={
            "Host": "example.ngrok.app",
            "X-Lemon-Dev-Gateway-Token": "local-smoke-token",
            "Authorization": "Bearer local-test-token",
        },
        path="/health?source=mobile",
        gateway_token="local-smoke-token",
    )
    responses: list[dict[str, object]] = []
    captured_requests: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> _FakeUpstreamResponse:
        assert timeout == 2.0
        captured_requests.append(request)
        return _FakeUpstreamResponse(status=200, body=b'{"ok":true}')

    monkeypatch.setattr(gateway, "urlopen", fake_urlopen)
    handler._send_response = lambda **kwargs: responses.append(kwargs)  # type: ignore[method-assign]

    handler._proxy()

    assert len(captured_requests) == 1
    request = captured_requests[0]
    headers = _lower_headers(request)
    assert request.full_url == "http://127.0.0.1:8000/health?source=mobile"
    assert request.get_method() == "GET"
    assert headers["host"] == "127.0.0.1:8000"
    assert headers["x-forwarded-host"] == "example.ngrok.app"
    assert headers["authorization"] == "Bearer local-test-token"
    assert "x-lemon-dev-gateway-token" not in headers
    assert responses[0]["status"] == 200
    assert list(responses[0]["headers"]) == [
        ("server", "upstream-server"),
        ("date", "Mon, 25 May 2026 00:00:00 GMT"),
        ("content-type", "application/json"),
    ]
    assert responses[0]["body"] == b'{"ok":true}'


def test_gateway_forwards_post_body_for_image_upload_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify POST request bodies are forwarded for multipart image upload smoke."""
    upload_body = b"--boundary\r\nfake-image-bytes\r\n--boundary--\r\n"
    handler = _new_handler(
        headers={
            "Content-Type": "multipart/form-data; boundary=boundary",
            "Content-Length": str(len(upload_body)),
            "X-Lemon-Dev-Gateway-Token": "local-smoke-token",
        },
        path="/api/v1/supplements/analyze",
        method="POST",
        body=upload_body,
        gateway_token="local-smoke-token",
    )
    responses: list[dict[str, object]] = []
    captured_requests: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> _FakeUpstreamResponse:
        assert timeout == 2.0
        captured_requests.append(request)
        return _FakeUpstreamResponse(status=202, body=b'{"accepted":true}')

    monkeypatch.setattr(gateway, "urlopen", fake_urlopen)
    handler._send_response = lambda **kwargs: responses.append(kwargs)  # type: ignore[method-assign]

    handler._proxy()

    assert len(captured_requests) == 1
    request = captured_requests[0]
    headers = _lower_headers(request)
    assert request.full_url == "http://127.0.0.1:8000/api/v1/supplements/analyze"
    assert request.get_method() == "POST"
    assert request.data == upload_body
    assert headers["content-type"] == "multipart/form-data; boundary=boundary"
    assert "x-lemon-dev-gateway-token" not in headers
    assert responses[-1]["status"] == 202
