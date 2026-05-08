"""Phase 4: 2단계 응답 엔진

1단계: 용어 사전 정확 매칭
2단계: RAG 보충 검색 (항상 수행)
→ LLM 답변 생성 (두 소스 종합)
"""

from pathlib import Path

from features.onboarding.glossary_matcher import GlossaryMatcher, GlossaryEntry
from features.onboarding.department_router import DepartmentRouter
from core.llm_client import get_llm, invoke_vision


class OnboardingBot:
    """신입 사원 온보딩 AI 챗봇 엔진"""

    def __init__(
        self,
        glossary_dir: Path,
        knowledge_store=None,
        prompts_dir: Path | None = None,
    ):
        self.glossary = GlossaryMatcher(glossary_dir)
        self.knowledge_store = knowledge_store
        self.router = DepartmentRouter()

        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "prompts"
        self.system_prompt = (prompts_dir / "onboarding_system.txt").read_text(
            encoding="utf-8"
        )

    async def answer(
        self,
        query: str,
        department: str = "",
        conversation_history: list[dict] | None = None,
        model: str | None = None,
        file_context: str = "",
        image_bytes: bytes | None = None,
        vision_model: str | None = None,
    ) -> dict:
        """사용자 질문에 대한 답변을 생성한다.

        Returns:
            {
                "answer": 답변 텍스트,
                "source": "both" | "rag" | "glossary_only",
                "glossary_entry": GlossaryEntry | None,
                "related_terms": list[GlossaryEntry],
            }
        """
        if conversation_history is None:
            conversation_history = []

        # 이미지가 첨부된 경우 비전 모델로 분석
        if image_bytes:
            vision_answer = invoke_vision(
                prompt=f"다음 질문에 대해 이미지를 분석하여 한국어로 답변하세요.\n\n질문: {query}",
                image_bytes=image_bytes,
                model=vision_model,
            )
            return {
                "answer": vision_answer,
                "source": "vision",
                "glossary_entry": None,
                "related_terms": [],
                "model_used": vision_model or "auto",
            }

        # 1단계: 용어 사전 정확 매칭
        glossary_entry = self.glossary.match(query)

        # 2단계: RAG 검색 (항상 수행)
        rag_context = self._search_knowledge(query)

        # 소스 판별
        if glossary_entry and rag_context:
            source = "both"
        elif glossary_entry:
            source = "glossary_only"
        else:
            source = "rag"

        # 3단계: LLM 답변 생성
        answer_text = await self._generate_answer(
            query=query,
            glossary_entry=glossary_entry,
            rag_context=rag_context,
            department=department,
            conversation_history=conversation_history,
            model=model,
            file_context=file_context,
        )

        # 관련 용어 수집
        related = self.glossary.get_related_entries(glossary_entry)

        return {
            "answer": answer_text,
            "source": source,
            "glossary_entry": glossary_entry,
            "related_terms": related,
            "model_used": model or "default",
        }

    def _search_knowledge(self, query: str, k: int = 3) -> str:
        """지식 베이스(SOP/가이드)에서 관련 문서를 검색한다."""
        if self.knowledge_store is None:
            return ""

        try:
            results = self.knowledge_store.similarity_search(query, k=k)
            if not results:
                return ""

            chunks = []
            for i, doc in enumerate(results, 1):
                source = doc.metadata.get("source", "알 수 없음")
                chunks.append(f"[참조 {i}] ({source})\n{doc.page_content}")
            return "\n\n".join(chunks)
        except Exception:
            return ""

    def _format_glossary_info(self, entry: GlossaryEntry | None) -> str:
        """용어 사전 정보를 프롬프트용 텍스트로 포맷팅한다."""
        if not entry:
            return "(용어 사전에서 직접 매칭되는 항목이 없습니다. RAG 검색 결과를 참고하세요.)"

        return (
            f"[매칭 용어: {entry.term}]\n"
            f"- 정식명: {entry.full_name} ({entry.korean_name})\n"
            f"- 정의: {entry.definition}\n"
            f"- 아진산업 맥락: {entry.ajin_context}\n"
            f"- 예시: {entry.example}\n"
            f"- 관련 부서: {', '.join(entry.departments_involved)}\n"
            f"- 난이도: {entry.difficulty}"
        )

    def _format_history(self, history: list[dict]) -> str:
        """대화 이력을 텍스트로 포맷팅한다."""
        if not history:
            return "(첫 번째 질문입니다)"

        lines = []
        for turn in history:
            role = "사용자" if turn["role"] == "user" else "AI 선배"
            lines.append(f"{role}: {turn['content'][:200]}")
        return "\n".join(lines)

    async def _generate_answer(
        self,
        query: str,
        glossary_entry: GlossaryEntry | None,
        rag_context: str,
        department: str,
        conversation_history: list[dict],
        model: str | None = None,
        file_context: str = "",
    ) -> str:
        """LLM을 사용하여 최종 답변을 생성한다."""
        dept_context = self.router.get_department_context(department)
        glossary_info = self._format_glossary_info(glossary_entry)
        history_text = self._format_history(conversation_history)

        # 프롬프트 인젝션 방어: 사용자 쿼리를 정제 후 삽입
        from core.security import sanitize_llm_input

        # 파일 컨텍스트가 있으면 RAG 컨텍스트에 합산
        combined_context = rag_context or "(참조 문서 없음)"
        if file_context:
            combined_context = (
                f"[사용자 첨부 파일 내용]\n{file_context}\n\n"
                f"[검색 참조 문서]\n{combined_context}"
            )

        filled_prompt = (
            self.system_prompt
            .replace("{department_context}", dept_context)
            .replace("{glossary_info}", glossary_info)
            .replace("{rag_context}", combined_context)
            .replace("{conversation_history}", history_text)
            .replace("{user_query}", sanitize_llm_input(query))
        )

        llm = get_llm(model=model, temperature=0.3) if model else get_llm(temperature=0.3)
        response = await llm.ainvoke(filled_prompt)
        return response.content
