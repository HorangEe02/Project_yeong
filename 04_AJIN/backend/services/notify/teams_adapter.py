"""D2 — Teams 어댑터 (Mock + Real Adaptive Card)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from backend.services.notify.base import (
    CAPTURES_DIR, DispatchResult, NotificationContext, Notifier,
)


def _build_card(ctx: NotificationContext) -> dict:
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": ctx.subject},
                        {"type": "TextBlock", "wrap": True, "text": ctx.body_text[:3000]},
                    ],
                },
            }
        ],
    }


class MockTeamsAdapter(Notifier):
    channel = "teams"

    def send(self, ctx: NotificationContext) -> DispatchResult:
        path: Path = CAPTURES_DIR / f"mock_teams_{ctx.user_id}_{ctx.change_id or 'na'}_{ctx.template}.json"
        try:
            path.write_text(
                json.dumps(_build_card(ctx), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            return DispatchResult(success=False, detail=f"capture write 실패: {e}")
        return DispatchResult(success=True, detail="sent_mock", captured_path=str(path))


class RealTeamsAdapter(Notifier):
    channel = "teams"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, ctx: NotificationContext) -> DispatchResult:
        if not self.webhook_url:
            return DispatchResult(success=False, detail="webhook_url 미설정")
        try:
            r = httpx.post(self.webhook_url, json=_build_card(ctx), timeout=10)
            r.raise_for_status()
        except Exception as e:
            return DispatchResult(success=False, detail=f"Teams webhook 실패: {e}")
        return DispatchResult(success=True, detail="sent")


def get_teams_adapter(webhook_url: str = "") -> Notifier:
    if webhook_url:
        return RealTeamsAdapter(webhook_url)
    return MockTeamsAdapter()
