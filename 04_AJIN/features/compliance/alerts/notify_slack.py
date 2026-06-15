"""MVP Stage 6 — Slack 라우팅 (변경 등급별).

`SLACK_WEBHOOK_URL` 환경변수에 등록된 단일 webhook 으로 메시지 전송.
다중 채널 분기는 webhook 본문의 `channel` 필드로 지정 (Slack Incoming
Webhook 의 표준 패턴).

미설정·실패시 graceful skip — Stage 6 실패가 Stage 1~5 (수집·분류·DB) 를
막아서는 안 된다. 알림이 빠지더라도 DB 에는 row 가 들어있고, 사용자가
프런트 변경 피드 페이지에서 직접 조회할 수 있다.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 등급별 라우팅 룰 — Slack 채널 + 색상 (이모지 제거: 디자인 시스템 v2 Hard Rule)
_GRADE_ROUTING: dict[str, dict[str, str]] = {
    "CRITICAL": {"channel": "#alerts-critical", "color": "#D32F2F"},
    "HIGH":     {"channel": "#alerts-high",     "color": "#F57C00"},
    "MEDIUM":   {"channel": "#alerts-weekly",   "color": "#FBC02D"},
    "LOW":      {"channel": "#alerts-weekly",   "color": "#388E3C"},
}

# CRITICAL 만 즉시 발송. MEDIUM/LOW 는 주간 리포트로 누적 (cron job 별도 — P1).
_IMMEDIATE_GRADES = {"CRITICAL", "HIGH"}


def route(change: dict, change_id: int | None = None,
          frontend_base_url: str = "https://ajin-cb.web.app",
          timeout_sec: float = 5.0) -> bool:
    """변경 1건을 Slack 으로 라우팅. 즉시 발송 또는 누적 큐.

    Args:
        change: classify_change 후 enrich 된 ChangeRecord
        change_id: DB row id (변경 피드 deeplink 용)
        frontend_base_url: 프런트 base URL
        timeout_sec: HTTP 타임아웃

    Returns:
        True — 발송 성공 또는 의도적 누적 큐
        False — 발송 시도 후 실패
    """
    try:
        from config import SLACK_WEBHOOK_URL
    except ImportError:
        logger.debug("config import 실패 — Slack 라우팅 skip")
        return True

    if not SLACK_WEBHOOK_URL:
        logger.info("SLACK_WEBHOOK_URL 미설정 — change_id=%s 알림 skip", change_id)
        return True

    grade = (change.get("grade") or "MEDIUM").upper()
    if grade not in _IMMEDIATE_GRADES:
        # MEDIUM/LOW — 주간 누적 (별도 cron 이 처리). 현재는 skip 하되 True 반환.
        logger.debug("change_id=%s grade=%s — 주간 리포트 큐", change_id, grade)
        return True

    payload = _build_block_kit_payload(change, change_id, grade, frontend_base_url)

    try:
        resp = httpx.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            timeout=timeout_sec,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        logger.info("Slack 알림 발송 — change_id=%s grade=%s", change_id, grade)
        return True
    except httpx.HTTPError as e:
        logger.warning("Slack webhook 실패 — change_id=%s: %s", change_id, e)
        return False


def _build_block_kit_payload(
    change: dict, change_id: int | None, grade: str, base_url: str
) -> dict[str, Any]:
    """Slack Block Kit 페이로드 구성."""
    routing = _GRADE_ROUTING.get(grade, _GRADE_ROUTING["MEDIUM"])
    item_title = change.get("item_title") or "(미상)"
    summary = change.get("summary_ko") or change.get("item_title") or "(요약 없음)"
    change_type = change.get("change_type", "modified")
    deps = change.get("affected_departments") or []
    plants = change.get("affected_plants") or []
    deeplink = f"{base_url}/compliance"
    if change_id:
        deeplink += f"?change_id={change_id}"

    type_label = {"added": "신설", "removed": "폐지", "modified": "개정"}.get(
        change_type, change_type
    )

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"[{grade}] {type_label}: {item_title[:60]}",
                "emoji": False,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*요약*\n{summary[:200]}"},
        },
    ]

    fields: list[dict[str, str]] = []
    if deps:
        fields.append({"type": "mrkdwn", "text": f"*영향 부서*\n{', '.join(deps[:5])}"})
    if plants:
        fields.append({"type": "mrkdwn", "text": f"*영향 시설*\n{', '.join(plants[:5])}"})
    if fields:
        blocks.append({"type": "section", "fields": fields})

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "변경 피드 열기", "emoji": False},
                "url": deeplink,
                "style": "primary",
            }
        ],
    })

    return {
        "channel": routing["channel"],
        "username": "AJIN Compliance Bot",
        "attachments": [{"color": routing["color"], "blocks": blocks}],
    }


def route_batch(changes: list[dict], change_ids: list[int]) -> dict[str, int]:
    """여러 변경 일괄 라우팅. {sent, skipped, failed} 카운트 반환."""
    counts = {"sent": 0, "skipped": 0, "failed": 0}
    for ch, cid in zip(changes, change_ids):
        grade = (ch.get("grade") or "MEDIUM").upper()
        if grade not in _IMMEDIATE_GRADES:
            counts["skipped"] += 1
            continue
        if route(ch, change_id=cid):
            counts["sent"] += 1
        else:
            counts["failed"] += 1
    return counts
