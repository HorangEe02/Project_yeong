"""v4.7 C-3 — Slack signature 검증 단위 테스트."""

import hashlib
import hmac
import time

from backend.services.slack.signing import verify_slack_signature


SECRET = "test-signing-secret"


def _make_signature(secret: str, ts: str, body: bytes) -> str:
    base = f"v0:{ts}:{body.decode('utf-8')}".encode("utf-8")
    return "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()


def test_signature_valid():
    ts = str(int(time.time()))
    body = b"command=/ajin&text=ask+8D"
    sig = _make_signature(SECRET, ts, body)
    assert verify_slack_signature(SECRET, sig, ts, body) is True


def test_signature_expired_timestamp():
    ts = str(int(time.time()) - 600)  # 10 분 전 → 5분 window 초과
    body = b"command=/ajin&text=ask+8D"
    sig = _make_signature(SECRET, ts, body)
    assert verify_slack_signature(SECRET, sig, ts, body) is False


def test_signature_wrong_secret():
    ts = str(int(time.time()))
    body = b"command=/ajin&text=ask+8D"
    sig = _make_signature("wrong-secret", ts, body)
    assert verify_slack_signature(SECRET, sig, ts, body) is False


def test_signature_missing_fields():
    assert verify_slack_signature("", "v0=abc", "12345", b"x") is False
    assert verify_slack_signature(SECRET, "", "12345", b"x") is False
    assert verify_slack_signature(SECRET, "v0=abc", "", b"x") is False


def test_signature_bad_timestamp_format():
    body = b"x"
    sig = _make_signature(SECRET, "not-a-number", body)
    assert verify_slack_signature(SECRET, sig, "not-a-number", body) is False
