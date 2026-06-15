"""v4.7 PR-E7 — 권한 변경 결재 escalation job.

24h 이상 대기 중 (pending / security_approved) 인 결재 요청을 식별하고,
가능하면 Slack 알림을 발송한다.

매 4 시간 주기 Celery beat 호출 (backend/celery_app.py).

본 job 은 IDP_PROVIDER 와 무관하게 동작하며, Slack/메일 어댑터 부재 시
로그만 남기는 no-op safe 디자인.

Returns:
    {"overdue_count": N, "notified": bool}
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _maybe_notify_slack(overdue: list[dict]) -> bool:
    """Slack webhook 발송 시도. 실패 시 silent."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.info(
            "permission_escalation: SLACK_WEBHOOK_URL 미설정 — 알림 생략"
        )
        return False
    try:
        import httpx  # type: ignore

        lines = [
            f"- #{r['request_id']} {r['permission_key']} "
            f"({r['status']}, {r['hours_pending']}h, by {r['requested_by']})"
            for r in overdue[:20]
        ]
        text = (
            f"권한 변경 결재 지연 알림 — {len(overdue)} 건 24h+\n"
            + "\n".join(lines)
        )
        with httpx.Client(timeout=5.0) as client:
            client.post(webhook, json={"text": text})
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("permission_escalation: Slack 알림 실패: %s", e)
        return False


def run_escalation(threshold_hours: int = 24) -> dict:
    """24h+ pending / security_approved 결재 요청 알림."""
    from features.admin.permission_workflow import escalate_overdue

    overdue = escalate_overdue(threshold_hours=threshold_hours)
    notified = False
    if overdue:
        logger.warning(
            "permission_escalation: %d 건의 결재가 %dh 이상 지연",
            len(overdue), threshold_hours,
        )
        notified = _maybe_notify_slack(overdue)
    else:
        logger.info("permission_escalation: 지연 요청 없음")

    return {"overdue_count": len(overdue), "notified": notified}
