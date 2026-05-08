"""기능 C: 신입 사원 온보딩 AI 챗봇

용어 사전 정확 매칭 + RAG 보충 검색 + 부서별 맞춤 응답 +
멀티턴 대화 관리를 하나의 파이프라인으로 묶는다.
"""

from pathlib import Path

from features.onboarding.glossary_matcher import GlossaryMatcher
from features.onboarding.onboarding_bot import OnboardingBot
from features.onboarding.department_router import DepartmentRouter
from features.onboarding.conversation_manager import ConversationManager


class OnboardingPipeline:
    """온보딩 챗봇 전체 파이프라인"""

    def __init__(
        self,
        knowledge_base_dir: Path | None = None,
        knowledge_store=None,
    ):
        base = Path(__file__).parent.parent.parent
        if knowledge_base_dir is None:
            knowledge_base_dir = base / "data" / "knowledge_base"

        self.bot = OnboardingBot(
            glossary_dir=knowledge_base_dir / "glossary",
            knowledge_store=knowledge_store,
        )
        self.router = DepartmentRouter()
        self.conv_manager = ConversationManager()

    async def chat(
        self,
        query: str,
        session_id: str,
        department: str = "",
        model: str | None = None,
        file_context: str = "",
        image_bytes: bytes | None = None,
        vision_model: str | None = None,
    ) -> dict:
        """사용자 질문에 대한 답변을 생성한다.

        Args:
            query: 사용자 질문
            session_id: 대화 세션 ID
            department: 사용자 부서
            model: 사용할 LLM 모델 (None이면 기본값)
            file_context: 첨부 파일에서 추출한 텍스트
            image_bytes: 첨부 이미지 바이트
            vision_model: 비전 모델 이름
        Returns:
            {"answer": 최종 답변, "source": 소스 유형}
        """
        session = self.conv_manager.get_or_create_session(session_id, department)

        # FAQ 기록
        self.conv_manager.record_question(query)

        # 봇 응답 생성
        result = await self.bot.answer(
            query=query,
            department=session.department,
            conversation_history=session.get_recent_history(),
            model=model,
            file_context=file_context,
            image_bytes=image_bytes,
            vision_model=vision_model,
        )

        # 매칭된 용어 기록
        if result.get("glossary_entry"):
            session.record_asked_term(result["glossary_entry"].term)

        # 관련 용어 추천 (중복 제거)
        term_suggestion = self.conv_manager.format_related_terms(
            session, result.get("related_terms", [])
        )
        final_answer = result["answer"] + term_suggestion

        # 대화 이력 저장
        session.add_turn("user", query)
        session.add_turn("assistant", final_answer)

        return {
            "answer": final_answer,
            "source": result["source"],
            "model_used": result.get("model_used", "default"),
        }

    def get_faq_stats(self, n: int = 10) -> list[tuple[str, int]]:
        """FAQ 통계를 반환한다."""
        return self.conv_manager.get_top_faqs(n)
