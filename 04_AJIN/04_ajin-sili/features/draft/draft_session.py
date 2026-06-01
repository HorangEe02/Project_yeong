"""Phase 6: 대화형 수정 세션 관리

초안 생성 후 사용자가 부분 수정을 요청하면,
해당 섹션만 수정하는 대화형 세션 관리 모듈.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from features.draft.classifier import DraftRequest
from core.llm_client import get_llm


REVISION_PROMPT = """당신은 아진산업의 문서 수정 AI입니다.
아래 초안의 특정 부분을 사용자의 지시에 따라 수정해주세요.

[현재 초안]
{current_draft}

[현재 템플릿 변수 (JSON)]
{template_vars_json}

[사용자 수정 지시]
{user_instruction}

[규칙]
- 수정이 필요한 변수만 JSON으로 반환하세요
- 수정하지 않는 변수는 포함하지 마세요
- 기존 톤과 격식을 유지하세요
- 구조화된 항목(■)의 형식을 유지하세요

[응답] 수정할 변수만 JSON으로:"""


def _safe_json_dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


@dataclass
class DraftSession:
    """하나의 초안 작성 세션을 관리한다."""

    session_id: str
    request: DraftRequest
    template_vars: dict
    rendered_text: str
    revision_history: list = field(default_factory=list)

    async def revise(self, user_instruction: str) -> str:
        """사용자의 수정 지시를 받아 초안을 부분 수정한다."""
        revision_prompt = REVISION_PROMPT.format(
            current_draft=self.rendered_text,
            template_vars_json=_safe_json_dumps(self.template_vars),
            user_instruction=user_instruction,
        )

        llm = get_llm(temperature=0.3)
        response = await llm.ainvoke(revision_prompt)

        # 안전한 JSON 파싱
        from core.security import safe_json_loads

        text = response.content.strip()
        updated_vars = safe_json_loads(text, default={})

        if updated_vars:
            # 경로 A: JSON 파싱 성공 → 변경된 키만 업데이트 후 템플릿 재렌더링
            for key, value in updated_vars.items():
                if value is not None:
                    self.template_vars[key] = value

            self.revision_history.append({
                "instruction": user_instruction,
                "changed_keys": list(updated_vars.keys()),
            })

            # 재렌더링
            from features.draft.template_renderer import TemplateRenderer

            renderer = TemplateRenderer(
                Path(__file__).parent.parent.parent / "data" / "templates"
            )
            self.rendered_text = renderer.render(self.request, self.template_vars)
        else:
            # v1.2 경로 B: JSON 파싱 실패 → LLM 응답 텍스트를 직접 사용
            # LLM이 수정된 전체 문서를 자연어로 반환한 경우
            if text and len(text) > 50:
                self.rendered_text = text
                self.revision_history.append({
                    "instruction": user_instruction,
                    "changed_keys": ["__full_text_fallback__"],
                })

        return self.rendered_text
