"""Phase 4: RAG 참조 + LLM 초안 생성 엔진

기능 A의 검색 엔진으로 유사 문서를 찾고,
수신처별 시스템 프롬프트로 LLM에 초안 생성을 요청한다.
"""

import json
from pathlib import Path

from features.draft.classifier import DraftRequest, DocType
from core.llm_client import get_llm


# 문서 유형 → 프롬프트 파일 매핑
PROMPT_MAP = {
    DocType.EMAIL_OEM: "email_to_oem.txt",
    DocType.EMAIL_SUPPLIER: "email_to_supplier.txt",
    DocType.EMAIL_INTERNAL: "email_to_internal.txt",
    DocType.EMAIL_OVERSEAS: "email_to_overseas.txt",
    DocType.REPORT_8D: "report_8d.txt",
    DocType.REPORT_ECN: "report_ecn.txt",
    DocType.REPORT_MEETING: "report_meeting.txt",
}

# 초안 문서 유형 → 참조 검색 문서 유형 매핑
REFERENCE_DOC_TYPE_MAP = {
    DocType.EMAIL_OEM: "Email",
    DocType.EMAIL_SUPPLIER: "Email",
    DocType.EMAIL_INTERNAL: "Email",
    DocType.EMAIL_OVERSEAS: "Email",
    DocType.REPORT_8D: "8D Report",
    DocType.REPORT_ECN: "ECN",
    DocType.REPORT_MEETING: "Meeting Note",
}


class DraftGenerator:
    """RAG 참조 + LLM을 활용한 초안 생성 엔진"""

    def __init__(self, searcher, prompts_dir: Path):
        self.searcher = searcher
        self.prompts_dir = prompts_dir

    def _load_prompt(self, doc_type: DocType) -> str:
        """문서 유형에 맞는 시스템 프롬프트를 로드한다."""
        filename = PROMPT_MAP[doc_type]
        prompt_path = self.prompts_dir / filename
        return prompt_path.read_text(encoding="utf-8")

    def _search_references(self, request: DraftRequest, k: int = 3) -> str:
        """유사 문서를 검색하여 참조 텍스트로 포맷팅한다."""
        if self.searcher is None:
            return "(검색 엔진이 초기화되지 않았습니다. 일반적인 양식으로 작성합니다.)"

        results = self.searcher.search(
            query=request.reference_search_query,
            k=k,
            doc_type_filter=REFERENCE_DOC_TYPE_MAP.get(request.doc_type),
            part_name_filter=request.part_name,
        )

        if not results:
            return "(유사 참조 문서를 찾지 못했습니다. 일반적인 양식으로 작성합니다.)"

        ref_texts = []
        for i, r in enumerate(results, 1):
            ref_texts.append(f"[참조 {i}] {r.title}\n{r.content}")
        return "\n\n".join(ref_texts)

    def _build_situation_info(self, request: DraftRequest) -> str:
        """상황 정보를 텍스트로 정리한다."""
        lines = [f"- 문서 유형: {request.doc_type.value}"]
        if request.recipient_company:
            lines.append(
                f"- 수신처: {request.recipient_company} "
                f"{request.recipient_department or ''}"
            )
        if request.part_name:
            lines.append(
                f"- 관련 부품: {request.part_name} "
                f"({request.part_number or '품번 미정'})"
            )
        lines.append(f"- 상황: {request.situation_type}")
        lines.append(f"- 요약: {request.situation_summary}")
        if request.key_facts:
            lines.append("- 핵심 사실:")
            for fact in request.key_facts:
                lines.append(f"  · {fact}")
        return "\n".join(lines)

    async def generate(self, request: DraftRequest, user_request: str) -> dict:
        """초안을 생성한다.

        Returns:
            LLM이 생성한 템플릿 변수 딕셔너리
        """
        # 1. 유사 문서 검색 (RAG)
        reference_docs = self._search_references(request)

        # 2. 시스템 프롬프트 로드 및 변수 삽입 (프롬프트 인젝션 방어)
        from core.security import sanitize_llm_input, safe_json_loads

        system_prompt = self._load_prompt(request.doc_type)
        filled_prompt = (
            system_prompt
            .replace("{reference_docs}", reference_docs)
            .replace("{user_request}", sanitize_llm_input(user_request))
            .replace("{situation_info}", self._build_situation_info(request))
        )

        # 3. LLM 호출
        llm = get_llm(temperature=0.3)
        response = await llm.ainvoke(filled_prompt)

        # 4. 안전한 JSON 파싱
        text = response.content.strip()
        template_vars = safe_json_loads(text)
        if template_vars is None:
            template_vars = {"subject": "초안", "body": text}

        return template_vars
