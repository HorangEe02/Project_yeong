"""Phase 4: 2단계 응답 엔진

1단계: 용어 사전 정확 매칭
2단계: RAG 보충 검색 (항상 수행)
→ LLM 답변 생성 (두 소스 종합)
"""

from pathlib import Path
from typing import Literal

from features.onboarding.glossary_matcher import GlossaryMatcher, GlossaryEntry
from features.onboarding.department_router import DepartmentRouter
from features.onboarding.i18n_router import (
    resolve_language,
    build_language_instruction,
    verify_response_language,
)
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
        language: Literal["ko", "en", "auto"] = "auto",
        references: list[dict] | None = None,
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

        # v4.7 C-2 — 응답 언어 결정 ('auto' 이면 query 에서 감지)
        resolved_lang = resolve_language(query, language)

        # 이미지가 첨부된 경우 비전 모델로 분석
        if image_bytes:
            vision_instr = (
                "다음 질문에 대해 이미지를 분석하여 한국어로 답변하세요."
                if resolved_lang == "ko"
                else "Analyze the image and answer the following question in English."
            )
            vision_answer = invoke_vision(
                prompt=f"{vision_instr}\n\n{'질문' if resolved_lang == 'ko' else 'Question'}: {query}",
                image_bytes=image_bytes,
                model=vision_model,
            )
            return {
                "answer": vision_answer,
                "source": "vision",
                "glossary_entry": None,
                "related_terms": [],
                "model_used": vision_model or "auto",
                "language": resolved_lang,
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
            language=resolved_lang,
            references=references or [],
        )

        # v4.7 C-2 — 응답 언어 검증 (위반 시 1회 재요청)
        if not verify_response_language(answer_text, resolved_lang):
            retry_instr = build_language_instruction(resolved_lang)
            retry_prompt = (
                f"{retry_instr}\n\n"
                f"Rewrite the following response in the target language only:\n\n"
                f"{answer_text}"
            )
            try:
                llm = get_llm(model=model, temperature=0.1) if model else get_llm(temperature=0.1)
                retried = await llm.ainvoke(retry_prompt)
                if hasattr(retried, "content") and retried.content:
                    answer_text = retried.content
            except Exception:  # noqa: BLE001 — 재요청 실패는 원본 유지
                pass

        # 관련 용어 수집
        related = self.glossary.get_related_entries(glossary_entry)

        return {
            "answer": answer_text,
            "source": source,
            "glossary_entry": glossary_entry,
            "related_terms": related,
            "model_used": model or "default",
            "language": resolved_lang,
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

    def _format_references(self, references: list[dict]) -> str:
        """v4.7 Sprint 2 P0 (축 ①) — 사용자가 InputComposer "/" 으로 인용한 항목을
        system prompt 에 주입 가능한 텍스트 블록으로 포맷팅한다.

        Returns: "[사용자가 인용한 항목]\n- person 박준영(사원)\n..." 또는 빈 문자열.
        """
        if not references:
            return ""
        lines = ["[사용자가 인용한 항목]"]
        for ref in references:
            title = (ref.get("title") or "").strip()
            if not title:
                continue
            kind = (ref.get("kind") or "item").strip() or "item"
            lines.append(f"- 사용자가 인용한 항목: {kind} {title}")
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

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
        language: Literal["ko", "en"] = "ko",
        references: list[dict] | None = None,
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

        # v4.7 Sprint 2 P0 (축 ①) — 사용자가 인용한 검색 항목을 RAG 컨텍스트에 prepend.
        ref_block = self._format_references(references or [])
        if ref_block:
            combined_context = f"{ref_block}\n\n{combined_context}"

        # v4.7 C-2 — 언어 지시문 동적 주입.
        lang_instruction = build_language_instruction(language)

        filled_prompt = (
            self.system_prompt
            .replace("{department_context}", dept_context)
            .replace("{glossary_info}", glossary_info)
            .replace("{rag_context}", combined_context)
            .replace("{conversation_history}", history_text)
            .replace("{user_query}", sanitize_llm_input(query))
        )
        # system prompt 끝에 언어 지시 (template 가 {language_instruction} 토큰을 가지지 않아도 작동)
        filled_prompt = (
            f"{filled_prompt}\n\n"
            f"== Language Policy ==\n{lang_instruction}"
        )

        llm = get_llm(model=model, temperature=0.3) if model else get_llm(temperature=0.3)
        response = await llm.ainvoke(filled_prompt)
        return response.content
