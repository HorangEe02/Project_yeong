from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROXY_PATH = PROJECT_ROOT / "scripts" / "ollama_secure_proxy.py"


def _load_proxy_module():
    spec = importlib.util.spec_from_file_location("ollama_secure_proxy", PROXY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_proxy_authorization_helper():
    proxy = _load_proxy_module()

    assert proxy.is_authorized("secret", "secret") is True
    assert proxy.is_authorized("wrong", "secret") is False
    assert proxy.is_authorized(None, "secret") is False


def test_proxy_rejects_non_api_paths():
    proxy = _load_proxy_module()

    assert proxy.build_upstream_path("/api/tags") == "/api/tags"
    assert proxy.build_upstream_path("/api/chat?stream=false") == "/api/chat?stream=false"
    try:
        proxy.build_upstream_path("/admin")
    except ValueError as exc:
        assert "/api" in str(exc)
    else:
        raise AssertionError("non-API path should fail")


class FakeOllamaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        payload = json.dumps({"models": [{"name": "qwen3.5:9b"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def _start_server(server: ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def test_proxy_requires_secret_and_forwards_authorized_request():
    proxy = _load_proxy_module()
    try:
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
    except PermissionError as exc:
        pytest.skip(f"loopback socket bind not permitted in this sandbox: {exc}")
    _start_server(upstream)
    proxy_server = proxy.OllamaProxyServer(
        ("127.0.0.1", 0),
        proxy.OllamaProxyHandler,
        ajin_secret="expected",
        upstream_url=f"http://127.0.0.1:{upstream.server_port}",
    )
    _start_server(proxy_server)

    base = f"http://127.0.0.1:{proxy_server.server_port}/api/tags"
    try:
        try:
            urllib.request.urlopen(base, timeout=3)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("missing secret should return 401")

        req = urllib.request.Request(base, headers={"X-AJIN-Secret": "expected"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read().decode())
        assert body["models"][0]["name"] == "qwen3.5:9b"
    finally:
        proxy_server.shutdown()
        upstream.shutdown()
