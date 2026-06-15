"""v4.7 C-3 — Slack Slash Command inbound router.

엔드포인트:
  POST /slack/command   (Slack 슬래시 명령어 — application/x-www-form-urlencoded)

흐름:
  1. HMAC-SHA256 서명 검증 (5분 timestamp window) — 실패 시 401
  2. 명령어 파싱 (`/ajin ask <query>` / `/ajin help`)
  3. 즉시 200 ack 응답 ("AJIN이 답변을 준비하고 있어요…")
  4. asyncio.create_task 로 비동기 LLM 처리 + response_url 로 follow-up POST

사용자 매핑은 본 phase 'guest' 부서 통일. `--dept` 인자로 부서 컨텍스트 변경 가능.
"""

from __future__ import annotations

import asyncio
import logging
import os
import urllib.parse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.services.slack.command_parser import parse_command, SlackCommand
from backend.services.slack.responder import build_response_blocks, send_to_response_url
from backend.services.slack.signing import verify_slack_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])


def _get_signing_secret() -> str:
    return os.environ.get("SLACK_SIGNING_SECRET", "").strip()


def _get_public_base_url() -> str:
    return os.environ.get("AJIN_PUBLIC_BASE_URL", "").strip()


def _help_text() -> str:
    return (
        "*AJIN AI Assistant — 사용법*\n"
        "• `/ajin ask <질문>` — AI에게 질문\n"
        "• `/ajin ask --dept <부서명> <질문>` — 특정 부서 컨텍스트로 질문\n"
        "• `/ajin help` — 도움말\n\n"
        "예) `/ajin ask 8D 절차 알려줘`\n"
        "예) `/ajin ask --dept HR 휴가 신청 방법`"
    )


async def _run_async_followup(
    response_url: str,
    cmd: SlackCommand,
    *,
    public_base: str,
) -> None:
    """LLM 호출 + response_url 로 follow-up POST.

    onboarding_bot.answer() 의 의존성(KnowledgeStore 등)이 부족한 경우에도 graceful — 단순 LLM 호출로 폴백.
    """
    department = cmd.department or "guest"
    try:
        # OnboardingBot 의 의존 자원(KnowledgeStore, GlossaryMatcher 등) 가 무거우므로
        # Slack inbound 는 LLMRouter 를 직접 사용 (KB 매칭은 web 콘솔에서)
        from core.llm_router import LLMRouter
        from core.llm_types import LLMMode
        from features.onboarding.i18n_router import resolve_language, build_language_instruction

        lang = resolve_language(cmd.query, "auto")
        lang_instr = build_language_instruction(lang)
        prompt = (
            "당신은 아진산업 AI 업무 도우미입니다. 사내 직원이 Slack 에서 질문했습니다.\n"
            f"소속(추정): {department}\n\n"
            f"== Language Policy ==\n{lang_instr}\n\n"
            f"[질문]\n{cmd.query}\n\n"
            "간결하게(800자 이내) 답변하세요. 한국 자동차 부품 제조 맥락 기준."
        )
        llm_router = LLMRouter()
        answer_chunks: list[str] = []
        async for ev in llm_router.stream(
            prompt=prompt,
            mode=LLMMode.CHAT_KOREAN if lang == "ko" else LLMMode.CHAT,
            history=[],
        ):
            if isinstance(ev, dict) and ev.get("type") == "token":
                answer_chunks.append(ev.get("content", ""))
        answer = "".join(answer_chunks).strip() or "(응답이 비어 있습니다. 잠시 후 다시 시도해 주세요.)"
    except Exception as e:  # noqa: BLE001
        logger.exception("Slack followup LLM error")
        answer = f"⚠️ AI 응답 처리 중 오류가 발생했습니다: {e}"

    payload = build_response_blocks(
        question=cmd.query,
        answer=answer,
        full_view_url=public_base or "",
        response_type="in_channel",
    )
    await send_to_response_url(response_url, payload)


@router.post("/command")
async def slack_command(request: Request) -> JSONResponse:
    """Slack 슬래시 명령어 entry point.

    Slack 은 3초 내 응답이 없으면 timeout 표시 → 즉시 200 ack 후 비동기 처리.
    """
    raw_body: bytes = await request.body()
    signature = request.headers.get("x-slack-signature", "")
    timestamp = request.headers.get("x-slack-request-timestamp", "")

    secret = _get_signing_secret()
    if not secret:
        logger.error("SLACK_SIGNING_SECRET 미설정 — Slack inbound 차단")
        raise HTTPException(status_code=503, detail="Slack 통합이 구성되지 않았습니다.")

    if not verify_slack_signature(secret, signature, timestamp, raw_body):
        logger.warning("Slack signature verify FAILED (ts=%s)", timestamp[:20] if timestamp else "")
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    # x-www-form-urlencoded → dict
    form = urllib.parse.parse_qs(raw_body.decode("utf-8", errors="replace"))
    text = form.get("text", [""])[0]
    response_url = form.get("response_url", [""])[0]

    cmd = parse_command(text)

    if cmd.kind == "help" or cmd.kind == "unknown":
        return JSONResponse(
            {
                "response_type": "ephemeral",
                "text": _help_text(),
            }
        )

    # ask — 즉시 ack + 비동기 처리
    if not response_url:
        return JSONResponse(
            {
                "response_type": "ephemeral",
                "text": "⚠️ response_url 누락 — Slack 앱 구성을 확인해 주세요.",
            }
        )

    asyncio.create_task(
        _run_async_followup(
            response_url=response_url,
            cmd=cmd,
            public_base=_get_public_base_url(),
        )
    )

    return JSONResponse(
        {
            "response_type": "ephemeral",
            "text": "🤖 AJIN이 답변을 준비하고 있어요… (몇 초 이내 표시됩니다)",
        }
    )


@router.get("/health")
async def slack_health() -> dict:
    """Slack 통합 헬스: signing_secret 설정 여부."""
    return {
        "signing_secret_configured": bool(_get_signing_secret()),
        "public_base_url": _get_public_base_url() or None,
    }
