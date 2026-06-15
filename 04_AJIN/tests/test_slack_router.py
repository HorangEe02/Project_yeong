"""v4.7 C-3 — Slack router 통합 테스트 (TestClient)."""

import hashlib
import hmac
import os
import time
import urllib.parse

import pytest
from fastapi.testclient import TestClient


SECRET = "test-router-secret"


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SECRET)


def _make_signed(body_form: dict) -> tuple[bytes, str, str]:
    body = urllib.parse.urlencode(body_form).encode("utf-8")
    ts = str(int(time.time()))
    base = f"v0:{ts}:{body.decode('utf-8')}".encode("utf-8")
    sig = "v0=" + hmac.new(SECRET.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return body, ts, sig


def _client():
    # main.py import 가 무거우므로 router 만 단독 마운트
    from fastapi import FastAPI
    from backend.routers import slack as slack_router

    app = FastAPI()
    app.include_router(slack_router.router)
    return TestClient(app)


def test_ask_returns_ack_and_schedules_task():
    client = _client()
    body, ts, sig = _make_signed(
        {
            "command": "/ajin",
            "text": "ask 8D 절차",
            "response_url": "https://hooks.slack.example/T/B/X",
        }
    )
    resp = client.post(
        "/slack/command",
        content=body,
        headers={
            "X-Slack-Signature": sig,
            "X-Slack-Request-Timestamp": ts,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert resp.status_code == 200
    body_json = resp.json()
    assert body_json["response_type"] == "ephemeral"
    assert "준비" in body_json["text"]


def test_help_returns_usage():
    client = _client()
    body, ts, sig = _make_signed(
        {"command": "/ajin", "text": "help", "response_url": "https://x"}
    )
    resp = client.post(
        "/slack/command",
        content=body,
        headers={
            "X-Slack-Signature": sig,
            "X-Slack-Request-Timestamp": ts,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert resp.status_code == 200
    assert "/ajin ask" in resp.json()["text"]


def test_invalid_signature_returns_401():
    client = _client()
    body = urllib.parse.urlencode({"command": "/ajin", "text": "ask hi"}).encode("utf-8")
    ts = str(int(time.time()))
    resp = client.post(
        "/slack/command",
        content=body,
        headers={
            "X-Slack-Signature": "v0=deadbeef",
            "X-Slack-Request-Timestamp": ts,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert resp.status_code == 401
