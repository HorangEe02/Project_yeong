"""대화 요약 메모리 — 긴 대화의 컨텍스트를 유지한다.

ConversationSession.get_recent_history(max_turns=6)만으로는
10턴 이상의 대화에서 이전 맥락이 소실된다.

이 모듈은:
1. 일정 턴 이상 쌓이면 이전 대화를 요약
2. 요약 + 최근 6턴을 결합하여 LLM에 전달
3. Ollama 미연결 시 키워드 기반 단순 요약으로 폴백
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

SUMMARIZE_THRESHOLD = 10  # 이 턴 수 초과 시 요약 트리거
RECENT_TURNS = 6          # 항상 원문 유지하는 최근 턴 수

SUMMARY_PROMPT = """아래 대화를 200자 이내로 요약하세요.
핵심 주제, 질문한 용어, 얻은 정보를 중심으로 정리하세요.

[대화 내용]
{conversation}

[요약]"""


@dataclass
class ConversationMemory:
    """세션별 대화 요약 메모리"""
    session_id: str
    summaries: list[str] = field(default_factory=list)
    total_summarized_turns: int = 0

    def get_combined_summary(self) -> str:
        """누적된 모든 요약을 하나의 문자열로 반환한다."""
        if not self.summaries:
            return ""
        return "\n".join(self.summaries)


# ── 세션별 메모리 저장소 (인메모리) ──
_memory_store: dict[str, ConversationMemory] = {}


def get_memory(session_id: str) -> ConversationMemory:
    """세션의 메모리를 가져오거나 새로 생성한다."""
    if session_id not in _memory_store:
        _memory_store[session_id] = ConversationMemory(session_id=session_id)
    return _memory_store[session_id]


def should_summarize(history: list[dict]) -> bool:
    """요약이 필요한지 판단한다."""
    return len(history) > SUMMARIZE_THRESHOLD


def _extract_keywords(text: str) -> list[str]:
    """텍스트에서 주요 키워드를 추출한다 (폴백용)."""
    # 영문 약어 (대문자 2글자 이상)
    abbrs = re.findall(r'\b[A-Z]{2,}[a-z]*\b', text)
    # 한글 명사 패턴 (2-4글자 연속 한글)
    korean = re.findall(r'[가-힣]{2,4}(?:팀|부|실|법|제|서|표|값|율|도|기)', text)
    combined = list(dict.fromkeys(abbrs + korean))  # 중복 제거, 순서 유지
    return combined[:10]


def _simple_summarize(turns: list[dict]) -> str:
    """LLM 없이 단순 키워드 요약을 생성한다."""
    all_text = " ".join(t.get("content", "") for t in turns)
    keywords = _extract_keywords(all_text)

    user_questions = [
        t["content"][:40] for t in turns if t.get("role") == "user"
    ][:5]

    parts = []
    if keywords:
        parts.append(f"다룬 주제: {', '.join(keywords)}")
    if user_questions:
        parts.append(f"주요 질문: {'; '.join(user_questions)}")

    return " | ".join(parts) if parts else "이전 대화 내용 있음"


def summarize_history(
    history: list[dict],
    llm_client=None,
) -> str:
    """대화 이력을 요약한다.

    Args:
        history: 요약할 대화 턴 리스트
        llm_client: Ollama LLM 클라이언트 (None이면 단순 요약)

    Returns:
        요약 문자열
    """
    if not history:
        return ""

    # LLM 사용 시도
    if llm_client is not None:
        try:
            conversation_text = "\n".join(
                f"{'사용자' if t['role'] == 'user' else 'AI'}: {t['content']}"
                for t in history
            )
            prompt = SUMMARY_PROMPT.format(conversation=conversation_text)
            response = llm_client.invoke(prompt)
            summary = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            if summary and len(summary) > 10:
                return summary
        except Exception as e:
            logger.warning(f"LLM 요약 실패, 단순 요약 사용: {e}")

    # 폴백: 단순 키워드 요약
    return _simple_summarize(history)


def build_context_with_memory(
    history: list[dict],
    memory: ConversationMemory,
    llm_client=None,
) -> list[dict]:
    """요약 메모리 + 최근 대화를 결합하여 LLM에 전달할 컨텍스트를 생성한다.

    긴 대화의 경우:
    1. 오래된 턴들을 요약하여 memory에 저장
    2. 요약 텍스트를 system 메시지로 삽입
    3. 최근 RECENT_TURNS만 원문으로 유지

    Returns:
        LLM에 전달할 대화 이력 (요약 포함)
    """
    if not should_summarize(history):
        return history

    # 요약 대상: 최근 RECENT_TURNS을 제외한 이전 턴들
    turns_to_summarize = history[:-RECENT_TURNS]
    recent_turns = history[-RECENT_TURNS:]

    if turns_to_summarize:
        summary = summarize_history(turns_to_summarize, llm_client)
        if summary:
            memory.summaries.append(summary)
            memory.total_summarized_turns += len(turns_to_summarize)

    # 컨텍스트 조합: 요약(system) + 최근 턴(원문)
    result = []
    combined_summary = memory.get_combined_summary()
    if combined_summary:
        result.append({
            "role": "system",
            "content": f"[이전 대화 요약] {combined_summary}",
        })
    result.extend(recent_turns)

    return result


def get_memory_stats(session_id: str) -> dict:
    """메모리 통계"""
    mem = get_memory(session_id)
    return {
        "session_id": session_id,
        "summary_count": len(mem.summaries),
        "total_summarized_turns": mem.total_summarized_turns,
        "has_memory": len(mem.summaries) > 0,
    }
