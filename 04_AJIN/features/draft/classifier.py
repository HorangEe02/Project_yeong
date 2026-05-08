"""Phase 2: 문서 유형 및 수신처 분류기

사용자의 자연어 지시에서 문서 유형, 수신처, 부품 정보, 상황을 구조화하여 추출한다.
규칙 기반 분류를 기본으로 하고, LLM 분류를 옵션으로 제공한다.
"""

import json
import re
from enum import Enum

from pydantic import BaseModel, Field


class DocType(str, Enum):
    EMAIL_OEM = "email_oem"
    EMAIL_SUPPLIER = "email_supplier"
    EMAIL_INTERNAL = "email_internal"
    EMAIL_OVERSEAS = "email_overseas"
    REPORT_8D = "report_8d"
    REPORT_ECN = "report_ecn"
    REPORT_MEETING = "report_meeting"


# 문서 유형 → Jinja2 템플릿 경로 매핑
TEMPLATE_MAP = {
    DocType.EMAIL_OEM: "email/to_oem.j2",
    DocType.EMAIL_SUPPLIER: "email/to_supplier.j2",
    DocType.EMAIL_INTERNAL: "email/to_internal.j2",
    DocType.EMAIL_OVERSEAS: "email/to_overseas.j2",
    DocType.REPORT_8D: "report/8d_report.j2",
    DocType.REPORT_ECN: "report/ecn_notice.j2",
    DocType.REPORT_MEETING: "report/meeting_note.j2",
}


class DraftRequest(BaseModel):
    """사용자의 초안 작성 요청을 구조화한 모델"""

    doc_type: DocType = Field(description="문서 유형")
    template_key: str = Field(description="Jinja2 템플릿 경로 키")

    # 수신처 정보
    recipient_company: str | None = Field(default=None, description="수신 회사명")
    recipient_department: str | None = Field(default=None, description="수신 부서")
    recipient_name: str | None = Field(default=None, description="수신자 이름")

    # 부품 정보
    part_name: str | None = Field(default=None, description="관련 부품명")
    part_number: str | None = Field(default=None, description="부품 번호")

    # 상황 정보
    situation_type: str = Field(description="상황 유형")
    situation_summary: str = Field(description="상황 요약")
    key_facts: list[str] = Field(default_factory=list, description="핵심 사실 목록")

    # 참조 검색 키워드
    reference_search_query: str = Field(description="유사 문서 검색을 위한 키워드")


# ---------------------------------------------------------------------------
# 규칙 기반 분류 (LLM 호출 없이)
# ---------------------------------------------------------------------------

PART_INFO = {
    # 차체 패널류 (경산 본사 주력 제품)
    "쿼터패널": ("쿼터 패널 (PNL ASS'Y QTR COMPL)", "AJ-QTR-001"),
    "쿼터 패널": ("쿼터 패널 (PNL ASS'Y QTR COMPL)", "AJ-QTR-001"),
    "대시패널": ("대시 패널 (PNL ASS'Y DASH COMPL)", "AJ-DASH-001"),
    "대시 패널": ("대시 패널 (PNL ASS'Y DASH COMPL)", "AJ-DASH-001"),
    "리어플로어": ("리어 플로어 (PNL ASS'Y RR FLR)", "AJ-FLR-001"),
    "리어 플로어": ("리어 플로어 (PNL ASS'Y RR FLR)", "AJ-FLR-001"),
    "패키지트레이": ("리어 패키지 트레이 (PNL ASS'Y RR PACKAGE TRAY)", "AJ-PKG-001"),
    # 경산 제2공장 제품
    "카울멤버": ("카울 멤버 (MBR ASSY-COWL COMPL)", "AJ-COWL-001"),
    "카울 멤버": ("카울 멤버 (MBR ASSY-COWL COMPL)", "AJ-COWL-001"),
    # 범용 키워드
    "사이드멤버": ("사이드 멤버", "AJ-SIDE-001"),
    "범퍼빔": ("범퍼 빔", "AJ-BUMP-001"),
    "A필러": ("A-Pillar", "AJ-AP-001"),
    "A-Pillar": ("A-Pillar", "AJ-AP-001"),
    "B필러": ("B-Pillar", "AJ-BP-002"),
    "B-Pillar": ("B-Pillar", "AJ-BP-002"),
}

OEM_KEYWORDS = ["현대", "현대차", "현대자동차", "기아", "기아차", "완성차", "울산", "아산", "화성", "광주"]
SUPPLIER_KEYWORDS = [
    "협력사", "부품사", "외주", "2차", "납품사",
    "한국실링", "대한모터", "삼성SDI", "LG에너지",  # 알려진 협력사명
    "납품 요청", "납품요청", "소재 납품", "부품 납품",
]
# 아진산업 실제 부서명 (본부-팀 2계층)
INTERNAL_DEPTS = [
    # 생산본부
    "품질보증팀", "안전보건팀", "생산관리팀", "영업팀", "자재관리팀",
    # 관리본부
    "품질경영팀", "ESG경영팀", "기술교육원", "총무인사팀",
    # 재경본부
    "IT전략팀", "재무팀", "회계팀", "원가기획팀",
    # 구매본부
    "구매팀", "해외지원팀", "상생협력팀",
    # 개발본부
    "기술영업팀", "부품개발팀", "금형생산팀",
    # 생산기술본부
    "생산기술팀", "자동화기술팀", "FA사업팀", "제품설계팀", "공법계획팀", "비전연구팀",
    # 기술연구소
    "바디선행개발팀", "전장선행개발팀",
    # 레거시 호환
    "품질관리팀", "연구소", "관리팀",
]
OVERSEAS_KEYWORDS = ["해외", "USA", "중국", "베트남", "법인", "overseas", "english"]

SITUATION_KEYWORDS = {
    "납기지연": ["납기", "지연", "연기", "조정", "딜레이"],
    "클레임대응": ["클레임", "불량", "8D", "8d", "대응", "회신"],
    "설계변경": ["ECN", "ecn", "설계변경", "사양변경", "소재변경"],
    "협조요청": ["협조", "요청", "납품", "긴급", "공급"],
    "업무연락": ["공유", "전달", "안내", "일정", "통보"],
    "품질회의": ["회의", "미팅", "회의록"],
    "승인요청": ["승인", "PPAP", "ppap", "검토"],
}


def _detect_doc_type(query: str) -> DocType:
    """쿼리에서 문서 유형을 추론한다."""
    q = query.lower()

    # 보고서 유형 먼저 체크 (키워드가 명확)
    if any(kw in query for kw in ["8D", "8d", "클레임 대응 보고서"]):
        return DocType.REPORT_8D
    if any(kw in query for kw in ["ECN", "ecn", "설계변경통보", "설계변경 보고"]):
        return DocType.REPORT_ECN
    if any(kw in query for kw in ["회의록", "미팅노트", "회의 기록"]):
        return DocType.REPORT_MEETING

    # 이메일 유형
    is_email = any(kw in query for kw in ["메일", "이메일", "회신", "mail"])
    if is_email or not any(kw in query for kw in ["보고서", "리포트", "report"]):
        if any(kw in query for kw in OVERSEAS_KEYWORDS):
            return DocType.EMAIL_OVERSEAS
        if any(kw in query for kw in OEM_KEYWORDS):
            return DocType.EMAIL_OEM
        if any(kw in query for kw in SUPPLIER_KEYWORDS):
            return DocType.EMAIL_SUPPLIER
        # 사내 부서 언급 체크
        if any(dept in query for dept in INTERNAL_DEPTS):
            return DocType.EMAIL_INTERNAL

    # 기본: 완성차 이메일 (아진산업의 주요 업무)
    return DocType.EMAIL_OEM


def _detect_situation(query: str) -> str:
    """쿼리에서 상황 유형을 추론한다."""
    for situation, keywords in SITUATION_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            return situation
    return "업무연락"


def _detect_part(query: str) -> tuple[str | None, str | None]:
    """쿼리에서 부품명과 품번을 추출한다."""
    for keyword, (name, number) in PART_INFO.items():
        if keyword in query:
            return name, number
    return None, None


def _detect_recipient(query: str, doc_type: DocType) -> tuple[str | None, str | None]:
    """쿼리에서 수신처 정보를 추출한다."""
    company = None
    department = None

    if doc_type in (DocType.EMAIL_OEM, DocType.REPORT_8D):
        if any(kw in query for kw in ["현대", "현대차", "현대자동차"]):
            company = "현대자동차"
        elif any(kw in query for kw in ["기아", "기아차"]):
            company = "기아자동차"

    for dept in INTERNAL_DEPTS:
        if dept in query:
            department = dept
            break

    # 부서 패턴 매칭 (예: "구매팀", "SQ팀")
    dept_match = re.search(r"(\w{2,5}팀)", query)
    if dept_match and department is None:
        department = dept_match.group(1)

    return company, department


def rule_based_classify(user_request: str) -> DraftRequest:
    """규칙 기반으로 사용자 요청을 분류한다."""
    doc_type = _detect_doc_type(user_request)
    template_key = TEMPLATE_MAP[doc_type]
    situation_type = _detect_situation(user_request)
    part_name, part_number = _detect_part(user_request)
    company, department = _detect_recipient(user_request, doc_type)

    # 검색 키워드 생성
    search_parts = []
    if part_name:
        search_parts.append(part_name)
    search_parts.append(situation_type)
    reference_search_query = " ".join(search_parts) if search_parts else user_request

    return DraftRequest(
        doc_type=doc_type,
        template_key=template_key,
        recipient_company=company,
        recipient_department=department,
        part_name=part_name,
        part_number=part_number,
        situation_type=situation_type,
        situation_summary=user_request,
        reference_search_query=reference_search_query,
    )


# ---------------------------------------------------------------------------
# LLM 기반 분류 (규칙 기반으로 부족할 때)
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """당신은 아진산업의 업무 문서 유형 분류기입니다.
사용자의 요청을 분석하여 JSON 형식으로 구조화하세요.

[문서 유형 판별 규칙]
- "메일", "이메일", "회신" → 이메일 계열
  - "현대", "기아", "완성차" → email_oem (템플릿: email/to_oem.j2)
  - "협력사", "부품사", "외주" → email_supplier (템플릿: email/to_supplier.j2)
  - "팀", "부서", 사내 부서명 언급 → email_internal (템플릿: email/to_internal.j2)
  - "해외", "USA", "중국", "베트남" → email_overseas (템플릿: email/to_overseas.j2)
- "8D", "클레임", "불량 대응" → report_8d (템플릿: report/8d_report.j2)
- "ECN", "설계변경", "사양변경" → report_ecn (템플릿: report/ecn_notice.j2)
- "회의록", "미팅노트" → report_meeting (템플릿: report/meeting_note.j2)

[상황 유형]
납기지연, 클레임대응, 설계변경, 협조요청, 업무연락, 품질회의, 승인요청

[알려진 부품]
EMP 워터펌프(AJ-EMP-W100), CCH 냉난방장치(AJ-CCH-H200),
OBC 충전장치(AJ-OBC-C300), A-Panel(AJ-AP-001), B-Pillar(AJ-BP-002),
냉각수 히터(AJ-CWH-400)

[사용자 요청]
{user_request}

[응답] 아래 JSON 형식으로만 응답하세요:
{{"doc_type": "...", "template_key": "...", "recipient_company": ..., "recipient_department": ..., "recipient_name": ..., "part_name": ..., "part_number": ..., "situation_type": "...", "situation_summary": "...", "key_facts": [...], "reference_search_query": "..."}}"""


async def llm_classify(user_request: str) -> DraftRequest:
    """LLM을 사용하여 사용자 요청을 분류한다."""
    from core.llm_client import get_llm
    from core.security import sanitize_llm_input, safe_json_loads

    llm = get_llm(temperature=0.0)
    sanitized = sanitize_llm_input(user_request)
    response = await llm.ainvoke(CLASSIFY_PROMPT.format(user_request=sanitized))

    text = response.content.strip()
    data = safe_json_loads(text)
    if data and isinstance(data, dict):
        try:
            return DraftRequest(**data)
        except Exception:
            pass
    return rule_based_classify(user_request)


async def classify_draft_request(
    user_request: str, use_llm: bool = False
) -> DraftRequest:
    """사용자의 초안 작성 요청을 분류한다.

    기본적으로 규칙 기반 분류를 사용하고, use_llm=True이면 LLM을 활용한다.
    """
    if use_llm:
        return await llm_classify(user_request)
    return rule_based_classify(user_request)
