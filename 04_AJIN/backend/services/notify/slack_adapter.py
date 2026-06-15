"""D2 — Slack 어댑터 (Mock + Real Webhook)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from backend.services.notify.base import (
    CAPTURES_DIR, DispatchResult, NotificationContext, Notifier,
)


def _build_payload(ctx: NotificationContext) -> dict:
    """Slack Block Kit 페이로드. notify_slack._build_block_kit_payload 와
    유사하나 사용자 채널 알림용으로 단순화."""
    return {
        "text": ctx.subject,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": ctx.subject, "emoji": False}},
            {"type": "section", "text": {"type": "mrkdwn", "text": ctx.body_text[:3000]}},
        ],
    }


class MockSlackAdapter(Notifier):
    channel = "slack"

    def send(self, ctx: NotificationContext) -> DispatchResult:
        path: Path = CAPTURES_DIR / f"mock_slack_{ctx.user_id}_{ctx.change_id or 'na'}_{ctx.template}.json"
        try:
            path.write_text(
                json.dumps(_build_payload(ctx), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            return DispatchResult(success=False, detail=f"capture write 실패: {e}")
        return DispatchResult(success=True, detail="sent_mock", captured_path=str(path))


class RealSlackAdapter(Notifier):
    channel = "slack"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, ctx: NotificationContext) -> DispatchResult:
        if not self.webhook_url:
            return DispatchResult(success=False, detail="webhook_url 미설정")
        try:
            r = httpx.post(self.webhook_url, json=_build_payload(ctx), timeout=10)
            r.raise_for_status()
        except Exception as e:
            return DispatchResult(success=False, detail=f"Slack webhook 실패: {e}")
        return DispatchResult(success=True, detail="sent")


def get_slack_adapter(webhook_url: str = "") -> Notifier:
    if webhook_url:
        return RealSlackAdapter(webhook_url)
    return MockSlackAdapter()
