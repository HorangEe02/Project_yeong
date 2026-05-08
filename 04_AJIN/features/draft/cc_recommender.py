"""
CC (참조) 자동 추천 엔진
- 문서유형별 필수/권장/선택 CC 추천
- 부서 레지스트리의 cc_targets 활용
"""

from typing import Dict, List


# 문서유형별 CC 규칙
DOC_TYPE_CC_RULES = {
    "8D 보고서": {
        "mandatory": ["품질보증팀", "품질경영팀"],
        "conditional": {
            "생산본부": ["생산관리팀", "생산기술팀"],
            "구매본부": ["구매팀", "협력업체관리팀"],
        },
    },
    "ECN 변경통보": {
        "mandatory": ["부품개발팀", "생산기술팀"],
        "conditional": {
            "품질": ["품질보증팀"],
            "생산": ["생산관리팀"],
        },
    },
    "PPAP 체크리스트": {
        "mandatory": ["품질보증팀", "부품개발팀"],
        "conditional": {},
    },
    "회의록": {
        "mandatory": [],
        "conditional": {},
    },
    "사내 이메일": {
        "mandatory": [],
        "conditional": {},
    },
    "품질문제 개선대책서": {
        "mandatory": ["품질보증팀", "품질경영팀"],
        "conditional": {
            "설비": ["설비보전팀"],
            "금형": ["금형생산팀"],
        },
    },
    "안전 인시던트 리포트": {
        "mandatory": ["안전보건팀"],
        "conditional": {
            "생산": ["생산관리팀"],
        },
    },
    "규제 변경 영향 보고서": {
        "mandatory": ["품질경영팀", "ESG경영팀"],
        "conditional": {
            "해외": ["해외지원팀"],
            "구매": ["구매팀"],
        },
    },
    "OEM 이메일": {
        "mandatory": ["영업팀"],
        "conditional": {},
    },
    "협력사 이메일": {
        "mandatory": ["구매팀"],
        "conditional": {},
    },
}


def recommend_cc(
    doc_type: str,
    sender_department: str = "",
    sender_division: str = "",
) -> Dict[str, List[str]]:
    """
    문서유형 + 발신 부서 기반 CC 추천

    Returns:
        {"mandatory": [...], "recommended": [...], "optional": [...]}
    """
    rules = DOC_TYPE_CC_RULES.get(doc_type, {"mandatory": [], "conditional": {}})

    mandatory = [d for d in rules["mandatory"] if d != sender_department]

    # 조건부 CC
    recommended = []
    for keyword, depts in rules.get("conditional", {}).items():
        if keyword in sender_department or keyword in sender_division:
            for d in depts:
                if d != sender_department and d not in mandatory:
                    recommended.append(d)

    # department_config에서 cc_targets 가져오기
    optional = []
    try:
        from core.department_config import DEPARTMENT_REGISTRY
        dept_info = DEPARTMENT_REGISTRY.get(sender_department, {})
        cc_targets = dept_info.get("cc_targets", [])
        for d in cc_targets:
            if d != sender_department and d not in mandatory and d not in recommended:
                optional.append(d)
    except Exception:
        pass

    return {
        "mandatory": mandatory,
        "recommended": recommended,
        "optional": optional,
    }


def format_cc_display(cc_data: Dict[str, List[str]]) -> str:
    """CC 추천 결과 포맷팅"""
    parts = []
    if cc_data["mandatory"]:
        parts.append(f"**필수 CC**: {', '.join(cc_data['mandatory'])}")
    if cc_data["recommended"]:
        parts.append(f"**권장 CC**: {', '.join(cc_data['recommended'])}")
    if cc_data["optional"]:
        parts.append(f"**선택 CC**: {', '.join(cc_data['optional'])}")
    return "\n\n".join(parts) if parts else "CC 추천 없음"
