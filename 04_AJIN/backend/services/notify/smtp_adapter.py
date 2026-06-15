"""D2 — Email 어댑터 (Mock + Real). SMTP_ENABLED env 로 게이팅."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from backend.services.notify.base import (
    CAPTURES_DIR, DispatchResult, NotificationContext, Notifier,
)


def _smtp_enabled() -> bool:
    return os.environ.get("SMTP_ENABLED", "false").strip().lower() in ("true", "1", "yes", "on")


class MockEmailAdapter(Notifier):
    channel = "email"

    def send(self, ctx: NotificationContext) -> DispatchResult:
        path: Path = CAPTURES_DIR / f"mock_email_{ctx.user_id}_{ctx.change_id or 'na'}_{ctx.template}.eml"
        msg = EmailMessage()
        msg["From"] = "AJIN Compliance Bot <noreply@ajin.example>"
        msg["To"] = ctx.user_email or ctx.user_id
        msg["Subject"] = ctx.subject
        msg.set_content(ctx.body_text)
        try:
            path.write_bytes(bytes(msg))
        except Exception as e:
            return DispatchResult(success=False, detail=f"capture write 실패: {e}")
        return DispatchResult(success=True, detail="sent_mock", captured_path=str(path))


class RealEmailAdapter(Notifier):
    channel = "email"

    def send(self, ctx: NotificationContext) -> DispatchResult:
        host = os.environ.get("SMTP_HOST", "")
        port = int(os.environ.get("SMTP_PORT", "587"))
        sender = os.environ.get("SMTP_SENDER", "noreply@ajin.example")
        username = os.environ.get("SMTP_USERNAME", "")
        password = os.environ.get("SMTP_PASSWORD", "")
        if not host or not ctx.user_email:
            return DispatchResult(success=False, detail="SMTP_HOST 또는 user_email 미설정")

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ctx.user_email
        msg["Subject"] = ctx.subject
        msg.set_content(ctx.body_text)

        try:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.starttls()
                if username:
                    s.login(username, password)
                s.send_message(msg)
        except Exception as e:
            return DispatchResult(success=False, detail=f"SMTP 실패: {e}")
        return DispatchResult(success=True, detail="sent")


def get_email_adapter() -> Notifier:
    return RealEmailAdapter() if _smtp_enabled() else MockEmailAdapter()
