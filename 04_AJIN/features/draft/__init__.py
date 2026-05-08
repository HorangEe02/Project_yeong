"""기능 B: 이메일 및 공식 문서 초안 자동 작성

사용자 요청을 분류 → RAG 참조 검색 → LLM 초안 생성 → 템플릿 렌더링 →
대화형 수정 → .docx 출력까지의 전체 파이프라인을 관리한다.
"""

import uuid
from pathlib import Path

from features.draft.classifier import classify_draft_request, DraftRequest, DocType
from features.draft.generator import DraftGenerator
from features.draft.template_renderer import TemplateRenderer
from features.draft.docx_exporter import DocxExporter
from features.draft.hwpx_exporter import HwpxExporter
from features.draft.pdf_exporter import PdfExporter
from features.draft.draft_session import DraftSession


class DraftPipeline:
    """초안 작성 전체 파이프라인을 관리한다."""

    def __init__(self, searcher=None, prompts_dir: Path = None, templates_dir: Path = None):
        base = Path(__file__).parent.parent.parent
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "prompts"
        if templates_dir is None:
            templates_dir = base / "data" / "templates"

        self.generator = DraftGenerator(searcher, prompts_dir)
        self.renderer = TemplateRenderer(templates_dir)
        self.exporter = DocxExporter()
        self.hwpx_exporter = HwpxExporter()
        self.pdf_exporter = PdfExporter()
        self.active_sessions: dict[str, DraftSession] = {}

    async def create_draft(
        self, user_request: str, use_llm_classify: bool = False
    ) -> tuple[str, DraftSession]:
        """초안을 생성하고 세션을 반환한다.

        Returns:
            (렌더링된 초안 텍스트, DraftSession 객체)
        """
        # 1. 분류
        request = await classify_draft_request(user_request, use_llm=use_llm_classify)

        # 2. 생성
        template_vars = await self.generator.generate(request, user_request)

        # 3. 렌더링
        rendered = self.renderer.render(request, template_vars)

        # 4. 세션 생성
        session = DraftSession(
            session_id=str(uuid.uuid4())[:8],
            request=request,
            template_vars=template_vars,
            rendered_text=rendered,
        )
        self.active_sessions[session.session_id] = session

        return rendered, session

    async def revise_draft(self, session_id: str, instruction: str) -> str:
        """기존 세션의 초안을 수정한다."""
        session = self.active_sessions[session_id]
        return await session.revise(instruction)

    def export_docx(self, session_id: str, output_dir: Path) -> Path:
        """세션의 초안을 .docx로 내보낸다."""
        session = self.active_sessions[session_id]
        filename = f"{session.request.doc_type.value}_{session.session_id}.docx"
        output_path = output_dir / filename
        return self.exporter.export(
            markdown_text=session.rendered_text,
            output_path=output_path,
            doc_title=session.template_vars.get(
                "subject", session.template_vars.get("doc_number", "")
            ),
            doc_type=session.request.doc_type.value,
        )

    def export_hwpx(self, session_id: str, output_dir: Path) -> Path:
        """세션의 초안을 .hwpx로 내보낸다."""
        session = self.active_sessions[session_id]
        filename = f"{session.request.doc_type.value}_{session.session_id}.hwpx"
        output_path = output_dir / filename
        return self.hwpx_exporter.export(
            markdown_text=session.rendered_text,
            output_path=output_path,
            doc_title=session.template_vars.get(
                "subject", session.template_vars.get("doc_number", "")
            ),
            doc_type=session.request.doc_type.value,
        )

    def export_pdf(self, session_id: str, output_dir: Path) -> Path:
        """세션의 초안을 .pdf로 내보낸다."""
        session = self.active_sessions[session_id]
        filename = f"{session.request.doc_type.value}_{session.session_id}.pdf"
        output_path = output_dir / filename
        return self.pdf_exporter.export(
            markdown_text=session.rendered_text,
            output_path=output_path,
            doc_title=session.template_vars.get(
                "subject", session.template_vars.get("doc_number", "")
            ),
        )
