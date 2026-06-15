"""P1 D3 — 통합 라우터 (Slack + SMS).

`BaseCrawler._run_diff()` 의 `route_batch` 호출을 본 모듈로 대체:

  Slack 라우팅 (전 등급) + CRITICAL → 임원 SMS 추가 발송.

순서:
  1. Slack 발송 (notify_slack.route)
  2. CRITICAL 이면 추가로 SMS broadcast_critical
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def route_one(change: dict, change_id: int | None = None) -> dict[str, Any]:
    """단일 변경 라우팅 — Slack + (CRITICAL 시) SMS.

    Returns:
        {slack: bool, sms: {sent, skipped, failed}}
    """
    from features.compliance.alerts.notify_slack import route as slack_route
    from features.compliance.alerts.notify_sms import broadcast_critical

    slack_ok = slack_route(change, change_id=change_id)
    sms_counts = {"sent": 0, "skipped": 0, "failed": 0}

    grade = (change.get("grade") or "MEDIUM").upper()
    if grade == "CRITICAL":
        try:
            sms_counts = broadcast_critical(change, change_id=change_id)
        except Exception as e:
            logger.exception("broadcast_critical 실패 change_id=%s: %s", change_id, e)
            sms_counts["failed"] = 1

    return {"slack": slack_ok, "sms": sms_counts}


def route_batch(changes: list[dict], change_ids: list[int]) -> dict[str, Any]:
    """여러 변경 일괄 라우팅. 카운트 누적 반환.

    Returns:
        {slack: {sent, skipped, failed}, sms: {sent, skipped, failed}}
    """
    from features.compliance.alerts.notify_slack import route as slack_route
    from features.compliance.alerts.notify_sms import broadcast_critical

    slack_counts = {"sent": 0, "skipped": 0, "failed": 0}
    sms_counts = {"sent": 0, "skipped": 0, "failed": 0}

    _IMMEDIATE = {"CRITICAL", "HIGH"}

    for ch, cid in zip(changes, change_ids):
        grade = (ch.get("grade") or "MEDIUM").upper()

        # Slack — CRITICAL/HIGH 즉시 발송, 그 외는 주간 누적
        if grade in _IMMEDIATE:
            if slack_route(ch, change_id=cid):
                slack_counts["sent"] += 1
            else:
                slack_counts["failed"] += 1
        else:
            slack_counts["skipped"] += 1

        # SMS — CRITICAL 만 임원 brodcast
        if grade == "CRITICAL":
            try:
                cnt = broadcast_critical(ch, change_id=cid)
                sms_counts["sent"] += cnt["sent"]
                sms_counts["skipped"] += cnt["skipped"]
                sms_counts["failed"] += cnt["failed"]
            except Exception as e:
                logger.exception("SMS broadcast 실패 cid=%s: %s", cid, e)
                sms_counts["failed"] += 1

    return {"slack": slack_counts, "sms": sms_counts}
