#!/usr/bin/env python3
"""Secret-gated local proxy for AJIN Cloud Run to host Ollama access.

The proxy listens on loopback by default and forwards only authorized Ollama API
requests to the local Ollama server. It intentionally does not expose raw
Ollama directly to Cloudflare Tunnel.
"""

from __future__ import annotations

import argparse
import hmac
import http.client
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.parse import urlsplit


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def is_authorized(provided: str | None, expected: str) -> bool:
    """Validate the caller secret using constant-time comparison.

    Args:
        provided: Header value from ``X-AJIN-Secret``.
        expected: Secret configured for this proxy.

    Returns:
        True when the header is present and exactly matches the configured
        secret.
    """
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def build_upstream_path(path: str) -> str:
    """Return a safe Ollama upstream path.

    Args:
        path: Incoming request target, including optional query string.

    Returns:
        The path to send to Ollama.

    Raises:
        ValueError: If the path is not under ``/api/``.
    """
    parsed = urlsplit(path)
    if parsed.path != "/api" and not parsed.path.startswith("/api/"):
        raise ValueError("only /api Ollama routes are proxied")
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def filtered_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Filter hop-by-hop and secret headers before forwarding upstream.

    Args:
        headers: Incoming HTTP request headers.

    Returns:
        Headers safe to forward to the local Ollama process.
    """
    out: dict[str, str] = {}
    for key, value in headers:
        lower = key.lower()
        if lower in HOP_BY_HOP_HEADERS or lower == "x-ajin-secret":
            continue
        out[key] = value
    out["Host"] = "127.0.0.1:11434"
    return out


class OllamaProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that gates and forwards Ollama API requests."""

    server: "OllamaProxyServer"

    def do_GET(self) -> None:
        """Proxy a GET request."""
        self._proxy()

    def do_HEAD(self) -> None:
        """Proxy a HEAD request."""
        self._proxy()

    def do_POST(self) -> None:
        """Proxy a POST request."""
        self._proxy()

    def do_OPTIONS(self) -> None:
        """Return a minimal CORS preflight response for diagnostic callers."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-AJIN-Secret")
        self.send_header("Access-Control-Allow-Methods", "GET,HEAD,POST,OPTIONS")
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        """Log method/path/status without secrets or request body."""
        sys.stderr.write("[ollama-proxy] " + fmt % args + "\n")

    def _proxy(self) -> None:
        if not is_authorized(self.headers.get("X-AJIN-Secret"), self.server.ajin_secret):
            self.send_error(401, "missing or invalid X-AJIN-Secret")
            return

        try:
            upstream_path = build_upstream_path(self.path)
        except ValueError as exc:
            self.send_error(404, str(exc))
            return

        content_length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(content_length) if content_length else None

        conn = self.server.make_connection()
        try:
            conn.request(
                self.command,
                upstream_path,
                body=body,
                headers=filtered_headers(self.headers.items()),
            )
            resp = conn.getresponse()
            self.send_response(resp.status, resp.reason)
            for key, value in resp.getheaders():
                if key.lower() in HOP_BY_HOP_HEADERS:
                    continue
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception as exc:
            self.send_error(502, f"ollama upstream error: {str(exc)[:160]}")
        finally:
            conn.close()


class OllamaProxyServer(ThreadingHTTPServer):
    """Threading HTTP server with Ollama upstream configuration.

    Args:
        server_address: Host and port tuple.
        handler_class: Request handler class.
        ajin_secret: Required proxy secret.
        upstream_url: Local Ollama upstream URL.

    Raises:
        ValueError: If ``upstream_url`` is not an HTTP URL.
    """

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        ajin_secret: str,
        upstream_url: str,
    ) -> None:
        parsed = urlsplit(upstream_url)
        if parsed.scheme != "http" or not parsed.hostname:
            raise ValueError("upstream_url must be an http URL")
        self.ajin_secret = ajin_secret
        self.upstream_host = parsed.hostname
        self.upstream_port = parsed.port or 80
        super().__init__(server_address, handler_class)

    def make_connection(self) -> http.client.HTTPConnection:
        """Create a connection to the configured local Ollama upstream.

        Returns:
            A new ``HTTPConnection`` instance.
        """
        return http.client.HTTPConnection(self.upstream_host, self.upstream_port, timeout=120)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="AJIN Ollama secret-gated proxy")
    parser.add_argument("--host", default=os.environ.get("OLLAMA_PROXY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OLLAMA_PROXY_PORT", "8434")))
    parser.add_argument(
        "--upstream",
        default=os.environ.get("OLLAMA_PROXY_UPSTREAM", "http://127.0.0.1:11434"),
    )
    return parser.parse_args()


def main() -> int:
    """Run the proxy process.

    Returns:
        Process exit code.
    """
    args = parse_args()
    secret = os.environ.get("AJIN_OLLAMA_SECRET", "").strip()
    if not secret:
        print("AJIN_OLLAMA_SECRET is required", file=sys.stderr)
        return 2

    server = OllamaProxyServer(
        (args.host, args.port),
        OllamaProxyHandler,
        ajin_secret=secret,
        upstream_url=args.upstream,
    )
    print(
        f"[ollama-proxy] listening on http://{args.host}:{args.port}, upstream={args.upstream}",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
