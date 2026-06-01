"""
CC (참조) 자동 추천 엔진
- 문서유형별 필수/권장/선택 CC 추천
- 부서 레지스트리의 cc_targets 활용
- B5 v4.0: draft_versions.db 빈도 학습 — 과거 동일 doc_type+sender_dept
  버전들의 template_vars.cc 빈출 인원을 frequent 티어로 추가.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
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
    if cc_data.get("frequent"):
        parts.append(f"**자주 함께 보낸 사람**: {', '.join(cc_data['frequent'])}")
    if cc_data["optional"]:
        parts.append(f"**선택 CC**: {', '.join(cc_data['optional'])}")
    return "\n\n".join(parts) if parts else "CC 추천 없음"


# ─────────────────────────────────────────────────────────────
# B5 v4.0 — 과거 버전 빈도 학습
# ─────────────────────────────────────────────────────────────


def learn_frequent_cc(
    doc_type: str,
    sender_department: str = "",
    db_path: Path = Path("data/draft_versions.db"),
    top_n: int = 3,
    min_count: int = 2,
) -> List[str]:
    """draft_versions.db 의 template_vars.cc 필드에서 (doc_type, sender_dept) 매칭
    버전들의 빈출 CC 항목 Top N 을 반환.

    - cc 필드는 list[str] 또는 콤마 구분 문자열 가정 (둘 다 허용).
    - min_count 이상 등장한 항목만 채택 (잡음 필터).
    """
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        # documents JOIN 으로 doc_type + department 매칭
        params: list = [doc_type]
        query = """
            SELECT v.template_vars_json
            FROM versions v
            JOIN documents d ON v.document_id = d.id
            WHERE d.doc_type = ?
        """
        if sender_department:
            query += " AND d.department = ?"
            params.append(sender_department)
        # 최근 200건만 학습 (과도한 과거 영향 차단)
        query += " ORDER BY v.created_at DESC LIMIT 200"
        rows = conn.execute(query, params).fetchall()
        conn.close()
    except Exception:
        return []

    counter: Counter[str] = Counter()
    for row in rows:
        try:
            tv = json.loads(row["template_vars_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        cc = tv.get("cc")
        if isinstance(cc, str):
            items = [c.strip() for c in cc.split(",") if c.strip()]
        elif isinstance(cc, list):
            items = [str(c).strip() for c in cc if str(c).strip()]
        else:
            continue
        for item in items:
            counter[item] += 1

    # min_count 이상 + Top N
    return [name for name, count in counter.most_common(top_n) if count >= min_count]


def recommend_cc_with_history(
    doc_type: str,
    sender_department: str = "",
    sender_division: str = "",
) -> Dict[str, List[str]]:
    """B5 v4.0 — 정적 룰 + 과거 빈도 학습을 결합한 4-tier 추천.

    Returns:
        {"mandatory": [...], "recommended": [...], "frequent": [...], "optional": [...]}
    """
    base = recommend_cc(doc_type, sender_department, sender_division)

    frequent = learn_frequent_cc(doc_type, sender_department)
    # 중복 제거 — 이미 mandatory/recommended/optional 에 있으면 제외
    existing = set(base["mandatory"]) | set(base["recommended"]) | set(base["optional"])
    frequent = [f for f in frequent if f not in existing]

    return {
        "mandatory": base["mandatory"],
        "recommended": base["recommended"],
        "frequent": frequent,
        "optional": base["optional"],
    }
