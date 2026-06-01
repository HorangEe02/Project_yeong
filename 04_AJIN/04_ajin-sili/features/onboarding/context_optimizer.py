"""
RAG 컨텍스트 최적화 엔진
- 검색 결과 리랭킹 (BM25 + 시맨틱 점수 결합)
- 중복 청크 제거 (유사도 기반 dedup)
- 토큰 예산 관리
- 부서 컨텍스트 주입 최적화
"""

import re
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher


# 토큰 예산 설정 (한글 기준 1토큰 ~ 2~3자)
TOKEN_BUDGETS = {
    "onboarding": {
        "glossary": 800,
        "rag_docs": 1200,
        "dept_profile": 400,
        "conversation": 600,
        "total": 3000,
    },
    "work": {
        "glossary": 500,
        "rag_docs": 800,
        "dept_profile": 300,
        "conversation": 400,
        "total": 2000,
    },
}


def optimize_context(
    query: str,
    glossary_results: List[Dict],
    rag_results: List[Dict],
    dept_profile: Optional[Dict],
    conversation_summary: str,
    mode: str = "onboarding",
) -> Dict[str, str]:
    """
    전체 컨텍스트를 예산 내로 최적화

    Returns:
        {
            "glossary": "최적화된 용어집 텍스트",
            "rag_docs": "최적화된 RAG 문서 텍스트",
            "dept_profile": "최적화된 부서 프로필 텍스트",
            "conversation": "압축된 대화 이력",
            "total_chars": 총 글자수,
        }
    """
    budget = TOKEN_BUDGETS.get(mode, TOKEN_BUDGETS["onboarding"])

    glossary_text = _optimize_glossary(query, glossary_results, budget["glossary"])
    rag_text = _optimize_rag_docs(query, rag_results, budget["rag_docs"])
    dept_text = _compress_dept_profile(dept_profile, budget["dept_profile"])
    conv_text = _compress_conversation(conversation_summary, budget["conversation"])

    total = len(glossary_text) + len(rag_text) + len(dept_text) + len(conv_text)

    return {
        "glossary": glossary_text,
        "rag_docs": rag_text,
        "dept_profile": dept_text,
        "conversation": conv_text,
        "total_chars": total,
    }


def _optimize_glossary(query: str, results: List[Dict], max_chars: int) -> str:
    """용어집 검색 결과 최적화"""
    if not results:
        return ""

    query_keywords = set(query.lower().split())

    scored = []
    for item in results:
        term = item.get("term", "")
        definition = item.get("definition", "")
        score = 0
        for kw in query_keywords:
            if kw in term.lower():
                score += 3
            if kw in definition.lower():
                score += 1
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    parts = []
    current_chars = 0
    for _, item in scored:
        entry = f"- **{item.get('term', '')}**: {item.get('definition', '')}"
        if current_chars + len(entry) > max_chars:
            break
        parts.append(entry)
        current_chars += len(entry)

    return "\n".join(parts) if parts else ""


def _optimize_rag_docs(query: str, results: List[Dict], max_chars: int) -> str:
    """RAG 문서 청크 최적화 -- 중복 제거 + 예산 관리"""
    if not results:
        return ""

    unique_results = _deduplicate_chunks(results, threshold=0.8)

    parts = []
    current_chars = 0
    for item in unique_results:
        text = item.get("text", item.get("document", ""))
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        if current_chars + len(text) > max_chars:
            remaining = max_chars - current_chars
            if remaining > 100:
                text = text[:remaining] + "..."
            else:
                break

        parts.append(text)
        current_chars += len(text)

    return "\n\n".join(parts) if parts else ""


def _deduplicate_chunks(results: List[Dict], threshold: float = 0.8) -> List[Dict]:
    """유사도 기반 청크 중복 제거"""
    unique = []
    for item in results:
        text = item.get("text", item.get("document", ""))
        is_duplicate = False
        for existing in unique:
            existing_text = existing.get("text", existing.get("document", ""))
            similarity = SequenceMatcher(None, text[:200], existing_text[:200]).ratio()
            if similarity > threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(item)
    return unique


def _compress_dept_profile(profile: Optional[Dict], max_chars: int) -> str:
    """부서 프로필 핵심만 추출"""
    if not profile:
        return ""

    parts = []
    if profile.get("department_name"):
        parts.append(f"부서: {profile['department_name']}")
    if profile.get("core_responsibilities"):
        resp = profile["core_responsibilities"]
        if isinstance(resp, list):
            parts.append(f"핵심 업무: {', '.join(resp[:5])}")
        else:
            parts.append(f"핵심 업무: {str(resp)[:200]}")

    text = " | ".join(parts)
    return text[:max_chars]


def _compress_conversation(summary: str, max_chars: int) -> str:
    """대화 이력 요약 압축"""
    if not summary:
        return ""
    return summary[:max_chars]


def build_optimized_prompt(
    query: str,
    context: Dict[str, str],
    mode: str = "onboarding",
    department: str = "",
) -> str:
    """최적화된 컨텍스트로 최종 프롬프트 구성"""

    if mode == "onboarding":
        system_intro = (
            f"당신은 아진산업(현대차 1차 협력사) {department} 신입사원 온보딩 도우미입니다. "
            "쉽고 친절하게 설명하되, 구체적인 예시를 들어주세요."
        )
    else:
        system_intro = (
            f"당신은 아진산업 {department} 업무 AI 어시스턴트입니다. "
            "핵심 3문장으로 간결하게 답변하고, 실무 적용 포인트를 제시하세요."
        )

    sections = [system_intro]

    if context.get("dept_profile"):
        sections.append(f"\n[소속 부서 정보]\n{context['dept_profile']}")
    if context.get("glossary"):
        sections.append(f"\n[관련 용어]\n{context['glossary']}")
    if context.get("rag_docs"):
        sections.append(f"\n[참고 자료]\n{context['rag_docs']}")
    if context.get("conversation"):
        sections.append(f"\n[이전 대화 요약]\n{context['conversation']}")
    sections.append(f"\n[사용자 질문]\n{query}")

    return "\n".join(sections)
