"""Phase 4: 질의 이해 모듈

사용자의 자연어 질의에서 메타데이터(부품명, 문서 유형, 날짜 범위 등)를 추출한다.
"""

import json
import re
from datetime import date, timedelta

from pydantic import BaseModel, Field

from core.llm_client import get_llm


class QueryMetadata(BaseModel):
    """사용자 질의에서 추출한 메타데이터"""
    search_query: str = Field(description="핵심 검색 키워드")
    part_name: str | None = Field(default=None, description="부품명")
    doc_type: str | None = Field(
        default=None,
        description="문서 유형 (8D Report / ECN / PPAP / Email / Meeting Note)",
    )
    date_from: str | None = Field(default=None, description="검색 시작일 (YYYY-MM-DD)")
    date_to: str | None = Field(default=None, description="검색 종료일 (YYYY-MM-DD)")
    customer: str | None = Field(default=None, description="고객사명")
    department: str | None = Field(default=None, description="작성 부서")


# ---------------------------------------------------------------------------
# 규칙 기반 빠른 추출 (LLM 호출 없이)
# ---------------------------------------------------------------------------

PART_NAMES = {
    "EMP": "EMP 워터펌프",
    "워터펌프": "EMP 워터펌프",
    "CCH": "CCH 냉난방장치",
    "냉난방": "CCH 냉난방장치",
    "OBC": "OBC 충전장치",
    "충전장치": "OBC 충전장치",
    "A-Panel": "A-Panel",
    "A패널": "A-Panel",
    "B-Pillar": "B-Pillar",
    "B필러": "B-Pillar",
    "냉각수 히터": "냉각수 히터",
    "냉각수히터": "냉각수 히터",
}

DOC_TYPE_KEYWORDS = {
    "8D Report": ["8D", "8d", "클레임", "불량", "대응"],
    "ECN": ["ECN", "ecn", "설계변경", "사양변경", "소재변경"],
    "PPAP": ["PPAP", "ppap", "승인", "생산부품"],
    "Email": ["메일", "이메일", "회신", "납기"],
    "Meeting Note": ["회의", "미팅", "회의록"],
}

CUSTOMER_KEYWORDS = {
    "현대차": ["현대", "현대차", "현대자동차", "울산", "아산"],
    "기아": ["기아", "기아차", "화성", "광주"],
}


def rule_based_extract(query: str) -> QueryMetadata:
    """규칙 기반으로 빠르게 메타데이터를 추출한다."""
    part_name = None
    for keyword, name in PART_NAMES.items():
        if keyword in query:
            part_name = name
            break

    doc_type = None
    for dtype, keywords in DOC_TYPE_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            doc_type = dtype
            break

    customer = None
    for cust, keywords in CUSTOMER_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            customer = cust
            break

    # 날짜 범위 추출
    today = date.today()
    date_from = None
    date_to = None

    if "지난 달" in query or "저번 달" in query:
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        date_from = last_month_start.isoformat()
        date_to = last_month_end.isoformat()
    elif "지난 분기" in query or "전 분기" in query:
        quarter = (today.month - 1) // 3
        if quarter == 0:
            date_from = f"{today.year - 1}-10-01"
            date_to = f"{today.year - 1}-12-31"
        else:
            q_start_month = (quarter - 1) * 3 + 1
            q_end_month = quarter * 3
            date_from = f"{today.year}-{q_start_month:02d}-01"
            if q_end_month in (1, 3, 5, 7, 8, 10, 12):
                last_day = 31
            elif q_end_month in (4, 6, 9, 11):
                last_day = 30
            else:
                last_day = 28
            date_to = f"{today.year}-{q_end_month:02d}-{last_day}"
    elif "올해" in query:
        date_from = f"{today.year}-01-01"
        date_to = f"{today.year}-12-31"

    # 연도 패턴 매칭 (예: "2025년", "2026년")
    year_match = re.search(r"(20\d{2})년", query)
    if year_match and date_from is None:
        year = year_match.group(1)
        date_from = f"{year}-01-01"
        date_to = f"{year}-12-31"

    # 검색 키워드 정제: 메타데이터 관련 단어 제거
    search_query = query
    remove_patterns = [
        r"지난\s*(달|분기)", r"올해", r"20\d{2}년",
        r"찾아줘", r"검색해줘", r"보여줘", r"조회해줘", r"알려줘",
        r"관련", r"문서", r"보고서",
    ]
    for pat in remove_patterns:
        search_query = re.sub(pat, "", search_query)
    search_query = re.sub(r"\s+", " ", search_query).strip()

    if not search_query:
        search_query = query

    return QueryMetadata(
        search_query=search_query,
        part_name=part_name,
        doc_type=doc_type,
        date_from=date_from,
        date_to=date_to,
        customer=customer,
    )


# ---------------------------------------------------------------------------
# LLM 기반 정밀 추출 (규칙 기반으로 부족할 때)
# ---------------------------------------------------------------------------

EXTRACT_PROMPT = """사용자의 문서 검색 질의에서 메타데이터를 추출하세요.
오늘 날짜는 {today}입니다.

[부품명 목록] EMP 워터펌프, CCH 냉난방장치, OBC 충전장치, A-Panel, B-Pillar, 냉각수 히터
[문서 유형] 8D Report, ECN, PPAP, Email, Meeting Note
[고객사] 현대차, 기아
[부서] 품질관리팀, 생산기술팀, 영업팀, 연구소

[질의]
{query}

[규칙]
- "지난 달" = 전월 1일 ~ 전월 말일
- "지난 분기" = 전분기 시작~종료
- "올해" = {year}-01-01 ~ {year}-12-31
- "클레임", "불량" → doc_type: "8D Report"
- "설계변경", "소재 변경" → doc_type: "ECN"
- 추출할 수 없는 필드는 null로 둡니다

JSON 형식으로만 응답하세요:
{{"search_query": "...", "part_name": ..., "doc_type": ..., "date_from": ..., "date_to": ..., "customer": ..., "department": ...}}"""


async def llm_extract_metadata(query: str) -> QueryMetadata:
    """LLM을 사용하여 질의에서 메타데이터를 추출한다."""
    today = date.today()
    llm = get_llm(temperature=0.0)
    prompt = EXTRACT_PROMPT.format(
        today=today.isoformat(),
        year=today.year,
        query=query,
    )
    response = await llm.ainvoke(prompt)

    text = response.content.strip()
    # ```json ... ``` 래핑 제거
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text.strip())
        return QueryMetadata(**data)
    except (json.JSONDecodeError, Exception):
        # 파싱 실패 시 규칙 기반 폴백
        return rule_based_extract(query)


async def extract_metadata(query: str, use_llm: bool = False) -> QueryMetadata:
    """사용자 질의에서 메타데이터를 추출한다.

    기본적으로 규칙 기반 추출을 사용하고, use_llm=True이면 LLM을 활용한다.
    """
    if use_llm:
        return await llm_extract_metadata(query)
    return rule_based_extract(query)
