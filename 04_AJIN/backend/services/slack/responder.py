"""v4.7 C-3 — Slack Block Kit 응답 생성 + response_url POST.

흐름:
  Slack → POST /slack/command → 즉시 200 ack ("AJIN이 답변을 준비하고 있어요...")
  비동기 task → onboarding_bot.answer() → send_to_response_url(response_url, blocks)

응답 길이 3000자 제한 — 초과 시 "...웹에서 보기" 링크로 절단.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Slack section block text 한도 (3000자) — 안전 마진 2800
_SECTION_MAX = 2800


def _truncate_with_link(text: str, full_view_url: str = "") -> str:
    if len(text) <= _SECTION_MAX:
        return text
    truncated = text[: _SECTION_MAX - 60]
    if full_view_url:
        return f"{truncated}…\n\n<{full_view_url}|… 웹에서 전체 답변 보기>"
    return f"{truncated}…\n\n_(답변이 길어 일부가 생략되었습니다.)_"


def build_response_blocks(
    question: str,
    answer: str,
    *,
    full_view_url: str = "",
    response_type: str = "in_channel",
) -> dict[str, Any]:
    """Block Kit 페이로드 생성.

    Args:
        question: 사용자 질문
        answer: AI 답변 (markdown)
        full_view_url: 길이 초과 시 노출할 외부 링크 (없으면 단순 절단)
        response_type: 'in_channel' (모두 보임) | 'ephemeral' (요청자만 보임)
    """
    safe_answer = _truncate_with_link(answer, full_view_url)
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Q:* {question}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": safe_answer}},
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": ":robot_face: AJIN AI Assistant"},
            ],
        },
    ]
    # 전체 보기 링크 (있을 때만)
    public_base = full_view_url or os.environ.get("AJIN_PUBLIC_BASE_URL", "").strip()
    if public_base:
        chat_url = public_base if public_base.startswith("http") else f"https://{public_base}"
        chat_url = chat_url.rstrip("/") + "/chat"
        blocks[-1]["elements"].append(
            {"type": "mrkdwn", "text": f"<{chat_url}|웹에서 더 자세히 보기>"}
        )

    return {"response_type": response_type, "blocks": blocks, "text": question}


async def send_to_response_url(
    response_url: str,
    payload: dict[str, Any],
    *,
    timeout: float = 5.0,
    retries: int = 1,
) -> bool:
    """response_url 로 POST. 실패 시 1회 재시도.

    Returns True on 2xx.
    """
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(response_url, json=payload)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning("Slack response_url non-2xx: %s (%s)", resp.status_code, resp.text[:200])
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("Slack response_url POST attempt %d failed: %s", attempt + 1, e)
    if last_err:
        logger.error("Slack response_url POST gave up: %s", last_err)
    return False
