"""Phase 5: 검색 결과 요약 및 포맷팅

검색된 문서를 사용자에게 보기 좋게 포맷팅하고, LLM으로 종합 요약을 생성한다.
"""

from features.search.searcher import SearchResult
from core.llm_client import get_llm


# 문서 유형별 아이콘
TYPE_ICONS = {
    "8D Report": "🔴",
    "ECN": "🔧",
    "PPAP": "📋",
    "Email": "✉️",
    "Meeting Note": "📝",
}


def format_results_for_display(
    query: str, results: list[SearchResult]
) -> str:
    """검색 결과를 사용자 표시용 마크다운 텍스트로 포맷팅한다."""
    if not results:
        return "🔍 검색 결과가 없습니다. 다른 키워드로 시도해보시겠어요?"

    lines = [f"🔍 관련 문서 **{len(results)}건**을 찾았습니다.\n"]

    for i, r in enumerate(results, 1):
        icon = TYPE_ICONS.get(r.doc_type, "📄")
        lines.append(f"{i}. {icon} **[{r.doc_type}] {r.title}**")
        lines.append(
            f"   - 부품: {r.part_name} | "
            f"날짜: {r.metadata.get('created_date', 'N/A')}"
        )
        if r.content:
            preview = r.content[:150].replace("\n", " ")
            lines.append(f"   - {preview}...")
        lines.append("")

    lines.append("---")
    lines.append(
        "💡 특정 문서를 자세히 보거나, "
        "이 결과를 바탕으로 초안을 작성해드릴 수 있어요."
    )

    return "\n".join(lines)


SUMMARY_PROMPT = """다음은 사용자 질의에 대한 문서 검색 결과입니다.
각 문서의 핵심 내용을 1~2문장으로 요약하고, 전체 결과를 종합하는 안내 메시지를 작성해주세요.

[사용자 질의]
{query}

[검색 결과]
{results_text}

[응답 형식]
1. 전체 안내 (1문장): 검색 결과 개수와 주요 내용을 간략히 안내
2. 각 문서별 요약: 번호, 문서 유형 아이콘, 문서 제목, 핵심 내용 1~2문장
3. 후속 제안: "이 중 하나를 바탕으로 초안을 작성해드릴까요?" 등"""


async def generate_summary(
    query: str, results: list[SearchResult]
) -> str:
    """LLM을 활용하여 검색 결과 종합 요약을 생성한다."""
    if not results:
        return "검색 결과가 없습니다."

    results_text = "\n".join([
        f"[{r.doc_id}] {r.doc_type} - {r.title}\n내용: {r.content[:300]}"
        for r in results
    ])

    llm = get_llm()
    response = await llm.ainvoke(
        SUMMARY_PROMPT.format(query=query, results_text=results_text)
    )
    return response.content
