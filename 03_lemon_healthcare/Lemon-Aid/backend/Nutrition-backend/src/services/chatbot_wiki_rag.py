"""Tiered wiki-RAG fallback for the safety-bounded Lemon Aid chatbot.

The chatbot answers from a small set of reviewed ``medical_evidence_items`` and
otherwise refuses (``answerability == "unknown_no_reviewed_source"``). This module
adds a fallback for exactly that refusal case: it retrieves from the populated
LLM-WIKI pgvector corpus and lets the local Gemma model synthesize a grounded,
cited Korean answer. When nothing relevant is retrieved it returns a brief general
answer with a disclaimer instead of refusing.

The boundary/safety policies (dangerous queries: stop meds, diagnosis,
symptoms+red-flags) fire earlier in the agent and produce a *different*
answerability, so this path only runs for benign "no reviewed card" questions.

This module is fail-open everywhere: any retrieval, LLM, or parse failure returns
a safe minimal Korean message rather than raising, so the chatbot route never
breaks on the fallback path.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.config import Settings
from src.llm.ollama import OllamaChatClient
from src.services.llm_wiki_retrieval import (
    LlmWikiCitation,
    retrieve_llm_wiki_context_db,
)

logger = logging.getLogger(__name__)

# Top citations injected into the grounding prompt. Bounded so the prompt stays
# small and the model can attend to every "참고 자료 [N]" block.
_MAX_PROMPT_CITATIONS = 4
# Per-citation excerpt length in the prompt. Generation dominates latency, but a
# smaller prompt still trims input-processing time on the local GPU.
_MAX_EXCERPT_CHARS = 400
# Generous ceiling on TOTAL generated tokens (the local model emits internal
# reasoning before the JSON answer). A tight cap (e.g. 600) truncates mid-reasoning
# and returns EMPTY content with done_reason=length, so this is only a runaway
# backstop — answer brevity (and thus latency) is driven by the "3~5문장" prompt
# instruction, which already cut a grounded reply from ~29s to ~17s.
_MAX_ANSWER_TOKENS = 1500

# ---------------------------------------------------------------------------
# Post-generation safety screen
# ---------------------------------------------------------------------------
# The upstream classifier blocks explicitly dangerous queries before this path
# runs, but an adversarial benign-classified message could still make Gemma
# hallucinate dangerous medical directives.  Any answer containing one of these
# Korean phrases is degraded to the safe fallback message.
#
# HIGH-PRECISION ONLY: command/permission-form medication-change directives. Bare
# informational words (진단/치료/처방) and negated-safe forms (먹으면 안 됩니다,
# 임의로 중단하지 마세요) are deliberately EXCLUDED — the prompt makes Gemma recommend
# "전문가 상담", so a safe answer routinely says "정확한 진단은 전문가와 상담하세요";
# screening on those bare words would degrade nearly every legitimate answer and
# re-create the "can't answer" problem. The command forms below do not appear in
# safe deferrals ("중단하지 마세요", "중단 전 의사와 상담"), so false positives are rare
# while a real "stop your medication" directive is still caught.
_DANGEROUS_DIRECTIVE_PHRASES: tuple[str, ...] = (
    # Direct medication-change commands (the user is told to alter prescribed meds).
    "약을 끊으세요",
    "약을 중단하세요",
    "복용을 중단하세요",
    "복용을 멈추세요",
    "복용을 끊으세요",
    "약을 줄이세요",
    "약을 늘리세요",
    "용량을 늘리세요",
    "용량을 줄이세요",
    "복용량을 바꾸세요",
    "복용량을 늘리세요",
    "복용량을 줄이세요",
    # Dangerous permission to stop/skip prescribed medication.
    "약을 끊어도 됩니다",
    "약을 중단해도 됩니다",
    "복용을 중단해도 됩니다",
    "복용을 멈춰도 됩니다",
)


def _violates_safety(text: str) -> bool:
    """Return True if *text* contains a dangerous medical directive phrase.

    Performs a case-insensitive substring match against a bounded tuple of
    Korean forbidden directive patterns.  Any match causes the wiki-RAG answer
    to be degraded to the safe fallback instead of being returned to the user.

    Args:
        text: The model-generated answer text to screen.

    Returns:
        ``True`` when a dangerous phrase is detected, ``False`` otherwise.
    """
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in _DANGEROUS_DIRECTIVE_PHRASES)


# Answerability values exposed back to the chatbot route. "answered_from_wiki" is
# used when at least one wiki source is cited; "general_fallback" otherwise.
ANSWERABILITY_FROM_WIKI = "answered_from_wiki"
ANSWERABILITY_GENERAL = "general_fallback"
PROVIDER = "gemma_wiki_rag"
USED_TOOL = "llm_wiki_rag"
# Shown to the user with every fallback answer: this path is not a reviewed
# medical source, so it always defers to professionals for real decisions.
SAFETY_DISCLAIMER = (
    "이 답변은 검수된 의료 진단이 아니라 일반 정보예요. "
    "복약·치료 변경이나 정확한 판단은 의사 또는 약사와 상담해 주세요."
)
# Returned when the whole fallback fails (retrieval down, LLM down, bad parse).
_SAFE_FALLBACK_MESSAGE = (
    "지금은 정확한 정보를 찾지 못했어요. 식단·영양제 관련해서 다시 물어봐 주시거나, "
    "정확한 건 전문가와 상담해 주세요."
)

_SYSTEM_PROMPT = (
    "너는 영양·건강 도우미 '레몬'이다. 사용자의 식단·영양제·건강 질문에 친절한 한국어로 답한다. "
    "아래 '참고 자료'에 근거해 답하되, 자료가 질문과 무관하거나 비어 있으면 일반적인 정보로만 "
    "간단히 답하고 그 사실을 밝힌다. 진단, 처방, 복약 중단·변경 권고는 절대 하지 않고 전문가 "
    "상담을 권한다. 출력은 마크다운 없이 JSON 하나로만 한다."
)


@dataclass(frozen=True)
class WikiRagAnswer:
    """A grounded or general fallback answer produced from the LLM-WIKI corpus.

    Attributes:
        message: User-facing Korean answer.
        sources: Public-safe source dicts (subset of PUBLIC_CHATBOT_SOURCE_FIELDS).
        answerability: ``answered_from_wiki`` when sources are cited, else
            ``general_fallback``.
        safety_warnings: Korean disclaimer surfaced with the answer.
        provider: Stable provider label (``gemma_wiki_rag``).
        used_tools: Tool labels used to build the answer (``["llm_wiki_rag"]``).
    """

    message: str
    sources: list[dict[str, str]]
    answerability: str
    safety_warnings: list[str]
    provider: str
    used_tools: list[str]


async def answer_with_wiki_rag(
    message: str,
    *,
    settings: Settings,
    user_context_summary: str = "",
) -> WikiRagAnswer:
    """Answer an unreviewed chatbot question from the LLM-WIKI corpus.

    Retrieves wiki citations, asks the local Gemma model to synthesize a grounded
    Korean answer with citations, and maps the cited citations to public-safe
    source dicts. When no relevant citation is used (or the model declines to
    ground), a brief general answer with a disclaimer is returned instead.

    This function never raises: retrieval, LLM, and parse failures all degrade to
    a safe minimal Korean message with ``answerability="general_fallback"``.

    Args:
        message: The user's question (already past the safety boundary policies).
        settings: Runtime settings (WIKI retrieval + local Ollama controls).
        user_context_summary: Short, sanitized summary of the user's medications,
            supplements, and conditions, used to personalize interaction/duplication
            notes. Never a diagnosis source; the model is told to defer to experts.

    Returns:
        A :class:`WikiRagAnswer` with a user-facing message, public sources, and
        the resolved answerability.
    """
    try:
        retrieval = await retrieve_llm_wiki_context_db(message, settings)
        citations = list(retrieval.citations[:_MAX_PROMPT_CITATIONS])
        logger.info("Wiki-RAG retrieval returned %d citation(s).", len(citations))

        payload = _build_chat_payload(
            message=message,
            citations=citations,
            user_context_summary=user_context_summary,
            settings=settings,
        )
        response = await OllamaChatClient(settings).post_chat(payload)
        answer_text, used_indices = _parse_answer(response)

        if _violates_safety(answer_text):
            logger.warning(
                "Wiki-RAG answer failed post-generation safety screen; "
                "degrading to safe fallback."
            )
            return WikiRagAnswer(
                message=_SAFE_FALLBACK_MESSAGE,
                sources=[],
                answerability=ANSWERABILITY_GENERAL,
                safety_warnings=[SAFETY_DISCLAIMER],
                provider=PROVIDER,
                used_tools=[USED_TOOL],
            )

        sources = _sources_from_indices(citations, used_indices)
        if sources:
            logger.info("Wiki-RAG grounded answer cites %d source(s).", len(sources))
            answerability = ANSWERABILITY_FROM_WIKI
        else:
            logger.info("Wiki-RAG produced a general (off-topic) answer with no sources.")
            answerability = ANSWERABILITY_GENERAL
        return WikiRagAnswer(
            message=answer_text or _SAFE_FALLBACK_MESSAGE,
            sources=sources,
            answerability=answerability,
            safety_warnings=[SAFETY_DISCLAIMER],
            provider=PROVIDER,
            used_tools=[USED_TOOL],
        )
    except Exception:
        # Fail-open by design: a degraded fallback must never break the chatbot
        # route. Every cause (retrieval, LLM, parse) is logged with a traceback.
        logger.warning("Wiki-RAG fallback failed; returning safe general answer.", exc_info=True)
        return WikiRagAnswer(
            message=_SAFE_FALLBACK_MESSAGE,
            sources=[],
            answerability=ANSWERABILITY_GENERAL,
            safety_warnings=[SAFETY_DISCLAIMER],
            provider=PROVIDER,
            used_tools=[USED_TOOL],
        )


def _build_chat_payload(
    *,
    message: str,
    citations: list[LlmWikiCitation],
    user_context_summary: str,
    settings: Settings,
) -> dict[str, Any]:
    """Build the Gemma chat payload that synthesizes a grounded Korean answer.

    Args:
        message: The user's question.
        citations: Retrieved wiki citations (top-N) to ground the answer.
        user_context_summary: Short sanitized summary of the user's meds/supplements/conditions.
        settings: Runtime settings providing the model tag.

    Returns:
        An Ollama ``/api/chat`` JSON payload requesting a JSON answer object.
    """
    references = _format_references(citations)
    context_line = (
        f"사용자 건강 정보(복용 약·영양제·만성질환): {user_context_summary}\n\n"
        if user_context_summary.strip()
        else ""
    )
    user_prompt = (
        f"{context_line}"
        "참고 자료:\n"
        f"{references}\n\n"
        "질문:\n"
        f"{message}\n\n"
        '다음 JSON 형식으로만 답하라: {"answer": "<한국어 답변>", "used_sources": [<실제로 '
        "사용한 참고 자료의 1-기반 번호들>]}. 참고 자료가 질문과 관련 있으면 그 내용을 근거로 "
        "답하고 사용한 번호를 used_sources에 담는다. 참고 자료가 무관하거나 비어 있으면 일반적인 "
        "정보로 간단히 답하고 used_sources는 빈 배열([])로 두며, 일반 정보이며 정확한 내용은 "
        "전문가 상담을 권한다고 덧붙인다. 진단·처방·복약 중단/변경 권고는 하지 않는다. "
        "사용자 건강 정보가 있으면 복용 중인 약·영양제와의 상호작용이나 중복 섭취 가능성을 "
        "함께 짚어주되, 단정하지 말고 확인이 필요하면 전문가 상담을 권한다. "
        "answer는 핵심만 간결하게 5문장 이내로 작성한다."
    )
    return {
        "model": settings.ollama_model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": _MAX_ANSWER_TOKENS},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }


def _format_references(citations: list[LlmWikiCitation]) -> str:
    """Render citations as numbered ``참고 자료 [N]`` blocks for the prompt.

    Args:
        citations: Retrieved wiki citations.

    Returns:
        A newline-joined reference block, or a placeholder when empty.
    """
    if not citations:
        return "(관련 참고 자료 없음)"
    blocks: list[str] = []
    for index, citation in enumerate(citations, start=1):
        title = citation.heading or citation.title
        blocks.append(f"참고 자료 [{index}] {title}\n{citation.excerpt[:_MAX_EXCERPT_CHARS]}")
    return "\n\n".join(blocks)


def _parse_answer(response: Mapping[str, Any]) -> tuple[str, list[int]]:
    """Extract the answer text and used-source indices from a chat response.

    Fail-open: when the assistant content is not the expected JSON object, the
    whole content is treated as the answer with no cited sources.

    Args:
        response: Decoded Ollama chat response.

    Returns:
        A ``(answer_text, used_indices)`` tuple. ``used_indices`` is empty when the
        model cited nothing or the content was not parseable JSON.
    """
    content = _message_content(response)
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return content.strip(), []
    if not isinstance(parsed, dict):
        return content.strip(), []
    answer = parsed.get("answer")
    answer_text = answer.strip() if isinstance(answer, str) else content.strip()
    return answer_text, _coerce_indices(parsed.get("used_sources"))


def _message_content(response: Mapping[str, Any]) -> str:
    """Return the assistant message content from an Ollama chat response.

    Args:
        response: Decoded Ollama chat response.

    Returns:
        The assistant content string, or an empty string when absent.
    """
    message = response.get("message")
    if isinstance(message, Mapping):
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def _coerce_indices(value: Any) -> list[int]:
    """Coerce a raw ``used_sources`` value into a list of 1-based int indices.

    Args:
        value: Raw ``used_sources`` field from the model JSON.

    Returns:
        A de-duplicated list of positive integer indices in first-seen order.
    """
    if not isinstance(value, list):
        return []
    indices: list[int] = []
    seen: set[int] = set()
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if item <= 0 or item in seen:
            continue
        indices.append(item)
        seen.add(item)
    return indices


def _sources_from_indices(
    citations: list[LlmWikiCitation],
    used_indices: list[int],
) -> list[dict[str, str]]:
    """Map 1-based used-source indices to public-safe source dicts.

    Args:
        citations: Retrieved wiki citations the indices refer to.
        used_indices: 1-based indices the model reported using.

    Returns:
        Public source dicts for valid indices, in citation order.
    """
    sources: list[dict[str, str]] = []
    for index in used_indices:
        if 1 <= index <= len(citations):
            sources.append(_citation_to_public_source(citations[index - 1]))
    return sources


def _citation_to_public_source(citation: LlmWikiCitation) -> dict[str, str]:
    """Map a wiki citation to a public-safe source dict.

    Only keys within ``PUBLIC_CHATBOT_SOURCE_FIELDS`` are emitted so the route's
    public-source filter never leaks raw retrieval internals.

    Args:
        citation: A retrieved wiki citation.

    Returns:
        A public source dict for app/UI display.
    """
    return {
        # source_id is REQUIRED: the route's _public_chatbot_sources filter drops any
        # source without a non-empty source_id, so wiki citations would be invisible.
        "source_id": citation.source_path,
        "source_title": citation.heading or citation.title,
        "source_family": "lemon_wiki",
        "review_status": "reference",
        # source_url is intentionally omitted: citation.source_path is a repo-internal
        # relative path that renders as a dead link on the client.
    }
