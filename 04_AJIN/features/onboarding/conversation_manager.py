"""Phase 6: 멀티턴 대화 및 관련 용어 추천

대화 세션을 관리하고, 이전 대화 맥락을 유지하며,
이미 질문/추천한 용어를 중복 추천하지 않는다.
"""

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class ConversationSession:
    """하나의 대화 세션"""
    session_id: str
    department: str
    history: list[dict] = field(default_factory=list)
    asked_terms: list[str] = field(default_factory=list)
    suggested_terms: list[str] = field(default_factory=list)

    def add_turn(self, role: str, content: str):
        """대화 턴을 추가한다."""
        self.history.append({"role": role, "content": content})

    def get_recent_history(self, max_turns: int = 6) -> list[dict]:
        """최근 N턴만 반환 (컨텍스트 윈도우 관리)."""
        return self.history[-max_turns:]

    def record_asked_term(self, term: str):
        """질문한 용어를 기록한다."""
        if term not in self.asked_terms:
            self.asked_terms.append(term)

    def record_suggested_terms(self, terms: list[str]):
        """추천한 용어를 기록한다."""
        for t in terms:
            if t not in self.suggested_terms:
                self.suggested_terms.append(t)

    def should_suggest(self, term: str) -> bool:
        """이미 질문하거나 추천한 용어는 재추천하지 않는다."""
        return term not in self.asked_terms and term not in self.suggested_terms


class ConversationManager:
    """전체 대화 세션 관리자"""

    def __init__(self):
        self.sessions: dict[str, ConversationSession] = {}
        self.global_faq_counter: Counter = Counter()

    def get_or_create_session(
        self, session_id: str, department: str = ""
    ) -> ConversationSession:
        """세션을 가져오거나 새로 생성한다."""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationSession(
                session_id=session_id,
                department=department,
            )
        session = self.sessions[session_id]
        if department and not session.department:
            session.department = department
        return session

    def record_question(self, query: str):
        """FAQ 카운터에 질문을 기록한다."""
        normalized = query.strip().rstrip("?？")
        self.global_faq_counter[normalized] += 1

    def get_top_faqs(self, n: int = 10) -> list[tuple[str, int]]:
        """가장 많이 물어본 질문 상위 N개."""
        return self.global_faq_counter.most_common(n)

    def format_related_terms(
        self, session: ConversationSession, related_terms: list
    ) -> str:
        """중복을 제거하고 관련 용어 추천 텍스트를 생성한다."""
        new_terms = []
        for entry in related_terms:
            term_name = entry.term if hasattr(entry, "term") else str(entry)
            if session.should_suggest(term_name):
                new_terms.append(term_name)

        if not new_terms:
            return ""

        session.record_suggested_terms(new_terms)
        terms_str = ", ".join(new_terms[:5])
        return f"\n\n💡 관련 용어: {terms_str}"
