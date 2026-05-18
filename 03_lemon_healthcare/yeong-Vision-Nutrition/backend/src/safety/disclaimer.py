"""docs/10 §2.3 표준 면책 고지.

본 모듈의 텍스트들은 "진단·처방을 대체하지 않습니다" 류의 의료법 회피 문구를
의도적으로 포함하므로 ``response_filter.assert_response_safe`` 가 검사하는
사용자 콘텐츠 그룹과는 별도로 응답에 주입된다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 5
    docs/10-compliance-checklist.md §2.3
"""

from __future__ import annotations

from typing import Final

MAIN_DISCLAIMER_KO: Final[str] = (
    "본 서비스에서 제공하는 정보는 일반적인 건강 관리를 위한 참고 자료이며, "
    "의사·약사·영양사의 전문적 판단을 대체하지 않습니다. "
    "증상이 있거나 만성질환을 앓고 계신 경우, 반드시 전문가와 상담하시기 바랍니다."
)
"""모든 권고 화면 상·하단에 표시되는 메인 면책 문구."""

SUPPLEMENT_DISCLAIMER_KO: Final[str] = (
    "영양제는 의약품이 아니며, 질병의 예방이나 효과를 보장하지 않습니다. "
    "약을 복용 중이신 경우, 영양제와의 상호작용에 대해 의료진과 상담하세요."
)
"""영양제 화면 부속 면책 문구."""

CONSULT_PROFESSIONAL_MESSAGE_KO: Final[str] = (
    "섭취 가능 여부와 복용 시점은 약사 또는 의료진과 상담하시기 바랍니다."
)

EMERGENCY_RESOURCES_KO: Final[list[dict[str, str]]] = [
    {"name": "정신건강위기상담", "phone": "1577-0199"},
    {"name": "자살예방상담", "phone": "109"},
    {"name": "응급의료정보", "phone": "1339"},
]
"""사용자 위급 신호 시 안내할 공공 상담 자원 (docs/10 §11.1)."""
