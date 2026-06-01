"""D3 job — outbox pending 발송 (2분 cron). dispatcher 단순 래퍼."""
from __future__ import annotations

from typing import Any

from backend.services.notify.dispatcher import dispatch_pending


def run(batch_size: int = 50) -> dict[str, Any]:
    return dispatch_pending(batch_size=batch_size)
