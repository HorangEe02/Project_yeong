"""v4.7 C-3 — Slack HMAC-SHA256 request signature 검증.

Slack 문서: https://api.slack.com/authentication/verifying-requests-from-slack

원리:
  base = f"v0:{timestamp}:{raw_body}"
  expected = "v0=" + hmac_sha256(signing_secret, base).hexdigest()
  hmac.compare_digest(expected, X-Slack-Signature)

타임스탬프 5분 window — replay 공격 방어.
"""

from __future__ import annotations

import hashlib
import hmac
import time

_MAX_AGE_SEC = 60 * 5  # 5분


def verify_slack_signature(
    signing_secret: str,
    signature: str,
    timestamp: str,
    body: bytes,
    *,
    now: float | None = None,
) -> bool:
    """X-Slack-Signature 검증.

    Args:
        signing_secret: Slack 앱 Signing Secret (`.env` SLACK_SIGNING_SECRET).
        signature: 요청 헤더 `X-Slack-Signature` (예: 'v0=abcdef...').
        timestamp: 요청 헤더 `X-Slack-Request-Timestamp` (Unix epoch 초).
        body: 원본 raw request body (bytes — application/x-www-form-urlencoded).
        now: 테스트 주입용 현재 시각 (기본: time.time()).

    Returns:
        True 면 정상 요청, False 면 거부.
    """
    if not signing_secret or not signature or not timestamp:
        return False

    # 타임스탬프 유효성
    try:
        ts_int = int(timestamp)
    except (TypeError, ValueError):
        return False
    cur = now if now is not None else time.time()
    if abs(cur - ts_int) > _MAX_AGE_SEC:
        return False

    base = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}".encode("utf-8")
    expected = "v0=" + hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
