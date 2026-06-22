"""Local-only gateway for mobile ngrok smoke tests.

This helper keeps the FastAPI TrustedHost policy narrow during physical-device
testing. ngrok forwards the public tunnel host, so the gateway rewrites the
upstream request to the local backend host without logging request bodies,
OCR payloads, image bytes, object URIs, or secrets.
"""

from __future__ import annotations

import argparse
import contextlib
import hmac
import logging
import os
from collections.abc import Iterable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("dev_mobile_ngrok_backend_gateway")
HOP_BY_HOP_HEADERS: Final[set[str]] = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
SENSITIVE_REQUEST_HEADERS: Final[set[str]] = {
    "authorization",
    "cookie",
    "x-api-key",
}
DEV_GATEWAY_TOKEN_HEADER: Final[str] = "x-lemon-dev-gateway-token"
UPSTREAM_RESPONSE_HEADERS_TO_DROP: Final[set[str]] = {
    "date",
    "server",
}


class GatewayConfig:
    """Runtime settings for the development gateway.

    Args:
        backend_url: Local backend base URL, for example ``http://127.0.0.1:8000``.
        timeout_seconds: Upstream request timeout.
        gateway_token: Optional development gateway token required for proxying.
    """

    def __init__(
        self,
        *,
        backend_url: str,
        timeout_seconds: float,
        gateway_token: str | None,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.gateway_token = gateway_token


class MobileNgrokGatewayHandler(BaseHTTPRequestHandler):
    """Proxy HTTP requests to a local backend with a local Host header."""

    server_version = "LemonAidDevGateway"
    sys_version = ""
    server: MobileNgrokGatewayServer

    def version_string(self) -> str:
        """Return the sanitized gateway server header value."""
        return self.server_version

    def do_GET(self) -> None:
        """Forward GET requests."""
        self._proxy()

    def do_POST(self) -> None:
        """Forward POST requests, including multipart image uploads."""
        self._proxy()

    def do_OPTIONS(self) -> None:
        """Forward OPTIONS requests for browser-based debug tools."""
        self._proxy()

    def do_PUT(self) -> None:
        """Forward PUT requests."""
        self._proxy()

    def do_PATCH(self) -> None:
        """Forward PATCH requests."""
        self._proxy()

    def do_DELETE(self) -> None:
        """Forward DELETE requests."""
        self._proxy()

    def log_message(self, _format: str, *_args: object) -> None:
        """Suppress default access logging because paths may contain identifiers."""
        return

    def _proxy(self) -> None:
        if not self._is_authorized():
            LOGGER.warning("unauthorized_request method=%s", self.command)
            self._send_response(
                status=HTTPStatus.UNAUTHORIZED,
                headers=(("content-type", "application/json"),),
                body=b'{"detail":"Development gateway token required."}',
            )
            return
        body = self._read_body()
        request = Request(
            url=self._target_url(),
            data=body,
            headers=self._forward_headers(),
            method=self.command,
        )
        try:
            with urlopen(request, timeout=self.server.config.timeout_seconds) as response:
                response_body = response.read()
                self._send_response(
                    status=response.status,
                    headers=response.headers.items(),
                    body=response_body,
                )
        except HTTPError as error:
            self._send_response(
                status=error.code,
                headers=error.headers.items(),
                body=error.read(),
            )
        except URLError:
            LOGGER.warning("upstream_unavailable method=%s", self.command)
            self._send_response(
                status=HTTPStatus.BAD_GATEWAY,
                headers=(("content-type", "application/json"),),
                body=b'{"detail":"Local backend gateway upstream unavailable."}',
            )

    def _read_body(self) -> bytes | None:
        content_length = self.headers.get("content-length")
        if content_length is None:
            return None
        try:
            length = int(content_length)
        except ValueError:
            return b""
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _target_url(self) -> str:
        return urljoin(f"{self.server.config.backend_url}/", self.path.lstrip("/"))

    def _is_authorized(self) -> bool:
        expected_token = self.server.config.gateway_token
        if expected_token is None:
            return True
        provided_token = self.headers.get(DEV_GATEWAY_TOKEN_HEADER, "").strip()
        return hmac.compare_digest(provided_token, expected_token)

    def _forward_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        backend_host = urlsplit(self.server.config.backend_url).netloc
        for key, value in self.headers.items():
            normalized_key = key.lower()
            if normalized_key in HOP_BY_HOP_HEADERS:
                continue
            if normalized_key == DEV_GATEWAY_TOKEN_HEADER:
                continue
            if normalized_key == "host":
                headers["x-forwarded-host"] = value
                continue
            if normalized_key in SENSITIVE_REQUEST_HEADERS:
                headers[key] = value
                continue
            headers[key] = value
        headers["Host"] = backend_host
        headers.setdefault("x-forwarded-proto", "https")
        return headers

    def _send_response(
        self,
        *,
        status: int | HTTPStatus,
        headers: Iterable[tuple[str, str]],
        body: bytes,
    ) -> None:
        self.send_response(int(status))
        for key, value in headers:
            normalized_key = key.lower()
            if (
                normalized_key in HOP_BY_HOP_HEADERS
                or normalized_key in UPSTREAM_RESPONSE_HEADERS_TO_DROP
            ):
                continue
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)
        LOGGER.info("responded method=%s status=%s", self.command, int(status))


class MobileNgrokGatewayServer(ThreadingHTTPServer):
    """Threaded gateway server carrying immutable gateway settings."""

    def __init__(
        self,
        server_address: tuple[str, int],
        config: GatewayConfig,
    ) -> None:
        super().__init__(server_address, MobileNgrokGatewayHandler)
        self.config = config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(
        description="Run a local gateway for ngrok-backed mobile camera smoke tests.",
    )
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8010)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--require-token",
        action="store_true",
        help=(
            "Require X-Lemon-Dev-Gateway-Token to match the "
            "LEMON_DEV_GATEWAY_TOKEN environment variable."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Start the development gateway until interrupted."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    gateway_token = _gateway_token_from_environment(require_token=args.require_token)
    config = GatewayConfig(
        backend_url=args.backend_url,
        timeout_seconds=args.timeout_seconds,
        gateway_token=gateway_token,
    )
    server = MobileNgrokGatewayServer((args.listen_host, args.listen_port), config)
    LOGGER.info(
        "mobile_ngrok_gateway_listening listen=%s:%s backend=%s",
        args.listen_host,
        args.listen_port,
        config.backend_url,
    )
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever(poll_interval=0.25)
    server.server_close()


def _gateway_token_from_environment(*, require_token: bool) -> str | None:
    """Read the optional gateway token from environment without logging it.

    Args:
        require_token: Whether missing token configuration should abort startup.

    Returns:
        The stripped gateway token, or ``None`` when token auth is disabled.

    Raises:
        SystemExit: If token auth is required but no token was provided.
    """
    if not require_token:
        return None
    token = os.environ.get("LEMON_DEV_GATEWAY_TOKEN", "").strip()
    if not token:
        raise SystemExit("LEMON_DEV_GATEWAY_TOKEN must be set when --require-token is used.")
    return token


if __name__ == "__main__":
    main()
