"""Phase 4: Jinja2 템플릿 렌더링

LLM이 생성한 변수를 Jinja2 템플릿에 삽입하여 최종 문서를 렌더링한다.
"""

from datetime import date
from pathlib import Path

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import FileSystemLoader

from features.draft.classifier import DraftRequest


class TemplateRenderer:
    """Jinja2 기반 문서 템플릿 렌더러"""

    def __init__(self, templates_dir: Path):
        self.env = SandboxedEnvironment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, request: DraftRequest, template_vars: dict) -> str:
        """분류된 요청과 LLM 생성 변수를 사용하여 최종 문서를 렌더링한다.

        Args:
            request: 분류된 초안 요청
            template_vars: LLM이 생성한 변수 딕셔너리
        Returns:
            렌더링된 문서 텍스트 (마크다운)
        """
        template = self.env.get_template(request.template_key)

        # 기본 메타데이터 (LLM이 생성하지 않은 경우 사용)
        defaults = {
            "date": date.today().isoformat(),
            "created_date": date.today().isoformat(),
            "issue_date": date.today().isoformat(),
            "sender_department": "품질관리팀",
            "sender_name": "OOO",
            "sender_title": "대리",
        }
        merged = {**defaults, **template_vars}

        # 리스트가 아닌 항목을 리스트로 자동 변환 (LLM 출력 불안정성 대응)
        list_keys = [
            "structured_items", "action_items", "request_items",
            "todo_items", "cc_list", "d1_team", "d3_actions",
            "d6_schedule", "schedule", "department_actions",
            "attendees", "agenda_items", "decisions",
        ]
        for key in list_keys:
            if key in merged and not isinstance(merged[key], list):
                merged[key] = [merged[key]] if merged[key] else []

        return template.render(**merged)
