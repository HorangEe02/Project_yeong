"""질문 의도 분류 라우터 — v3.0: 키워드 + LLM 하이브리드

분류 전략:
1. 키워드 점수 계산 (기존 v2.6 로직 유지)
2. 점수 차이 >= SCORE_GAP_THRESHOLD → 키워드 결과 사용 (빠름)
3. 점수 차이 < SCORE_GAP_THRESHOLD → LLM 재분류 (정확)
4. LLM 실패 → 키워드 결과 폴백
"""
import logging
from typing import Optional

from features.search.employee.search import DEPARTMENT_ALIASES, DIVISION_ALIASES

logger = logging.getLogger(__name__)

# ── 설정 상수 ──
SCORE_GAP_THRESHOLD = 2       # 이 이상이면 키워드 결과 신뢰
MIN_SCORE_FOR_KEYWORD = 2     # 최소 점수 (이하면 LLM 사용)

# ── 의도 목록 ──
VALID_INTENTS = {
    "employee_lookup",
    "company_info",
    "document_search",
    "document_compose",
    "regulation_query",
}

# ── LLM 분류 프롬프트 ──
INTENT_CLASSIFY_SYSTEM = """당신은 아진산업 사내 AI 시스템의 의도 분류기입니다.
사용자 질문의 의도를 아래 5가지 중 정확히 하나로 분류하세요.

## 의도 목록
1. employee_lookup — 인원/조직 조회 (이름, 부서, 직급, 연락처, 조직도, 팀원, 누구)
2. company_info — 회사 정보 (연혁, 매출, 복지, 해외법인, CEO, 사업장, 설립)
3. document_search — 문서/규정 검색 (SOP, 매뉴얼, 절차서, 가이드, 양식 찾기)
4. document_compose — 문서 작성 요청 (이메일 작성, 보고서 초안, 회의록 만들어줘)
5. regulation_query — 규제/법규 관련 (ISO, 안전법, 환경규제, REACH, 관세, OSHA)

## 구분 핵심
- "~팀 연락처" / "~팀 누구" → employee_lookup (부서 약어도 포함: 품보팀, 생기팀, QA)
- "~작성해줘" / "~초안" / "~메일 써줘" → document_compose
- "~절차" / "~규정 찾아" / "~매뉴얼" → document_search
- "~법 적용" / "ISO ~" / "REACH ~" → regulation_query

## 규칙
- 의도 이름만 출력 (예: employee_lookup)
- 설명이나 이유는 출력하지 마세요"""


# ── 키워드 목록 (v2.6 유지 + 보강) ──

EMPLOYEE_KEYWORDS = [
    "연락처", "전화번호", "이메일", "내선", "내선번호", "메일", "전번",
    "누구", "담당자", "책임자", "팀장", "팀원", "사람", "사람들",
    "인원", "몇 명", "몇명", "직원", "조직도", "조직 현황", "조직 구조",
    "인원 현황", "인원현황", "부서 인원",
    "사원", "대리", "과장", "차장", "부장", "이사", "상무", "주임", "인턴",
    "대리님", "과장님", "차장님", "부장님",
    "팀원들", "구성원", "멤버", "소속", "현황",
]

COMPANY_INFO_KEYWORDS = [
    "연혁", "역사", "설립", "창업", "창업주", "회장", "대표이사", "CEO",
    "복지", "급여", "연봉", "초임", "경조사", "해외연수", "해외 연수",
    "매출", "매출액", "영업이익", "실적", "주가", "코스닥", "상장",
    "해외법인", "해외 법인", "해외공장", "해외 공장", "미국 공장", "중국 공장",
    "조지아", "앨라배마", "JOON", "HMGMA", "메타플랜트",
    "글로벌", "해외 사업", "해외사업", "해외 진출",
    "ESG", "사회공헌", "봉사",
    "인증", "특허", "수상",
    "기업문화", "회사 문화", "근무 환경", "복리후생",
]

DOCUMENT_KEYWORDS = [
    "절차", "규정", "매뉴얼", "지침", "SOP", "프로세스",
    "방법", "어떻게", "뭐야", "설명",
    "8D", "PPAP", "SPC", "FMEA", "ECN", "ECR",
    "금형", "공법", "검사", "불량", "클레임",
]

COMPOSE_KEYWORDS = [
    "작성", "써줘", "써 줘", "만들어", "생성", "초안", "draft",
    "이메일 작성", "이메일 써줘", "메일 보내", "메일 작성",
    "보고서 작성", "보고서 만들어", "보고서 써줘",
    "8D 보고서", "8D 작성", "8D 써줘",
    "ECN 작성", "ECN 통보", "변경통보",
    "회의록 작성", "회의록 만들어",
    "통보문", "요청서", "시행 계획", "체크리스트",
    "PPAP 작성", "PPAP 문서",
    "영향 보고서", "영향보고서", "대응 통보",
]

REGULATION_KEYWORDS = [
    "규제", "법규", "규정", "법령", "컴플라이언스", "compliance",
    "REACH", "RoHS", "IRA", "관세", "USMCA", "OSHA", "EPA",
    "ISO", "IATF", "MSDS", "SDS",
    "심사", "감사", "인증 심사", "audit",
    "준수", "위반", "벌금", "과태료",
    "규제 현황", "규제 변경", "규제 업데이트",
    "적용 규제", "공장 규제", "사업장 규제",
    "EU 규제", "미국 규제", "국내법",
    "APQP", "OEM 기준", "품질기준",
    "탄소", "ESG", "EV 배터리", "배터리 안전",
    "산안법", "산업안전",
]

# 문서/규정 의도가 강한 키워드 (부서별칭과 동시 출현 시 부스트 억제)
_DOC_STRONG_KEYWORDS = frozenset([
    "절차", "규정", "매뉴얼", "지침", "sop", "프로세스",
    "방법", "어떻게",
])


def classify_intent(query: str, llm_client=None) -> str:
    """
    하이브리드 의도 분류 메인 함수.

    Args:
        query: 사용자 질문
        llm_client: LLM 클라이언트 (None이면 키워드만 사용)

    Returns:
        의도 문자열 (5가지 중 하나)
    """
    # ── 0단계: ML 분류기 (v3.1 신규 — 신뢰도 70% 이상 시 즉시 반환) ──
    try:
        from features.search.ml_intent_classifier import get_ml_classifier

        ml_classifier = get_ml_classifier()
        if ml_classifier._is_trained:
            ml_result = ml_classifier.predict(query)
            if ml_result.confidence >= 70.0:
                logger.debug(
                    f"의도[ML] '{query[:30]}' -> {ml_result.intent} "
                    f"(confidence={ml_result.confidence:.1f}%)"
                )
                return ml_result.intent
    except Exception:
        pass  # ML 분류기 미설치/오류 시 기존 로직으로 폴백

    # ── 1단계: 키워드 스코어링 ──
    scores = _keyword_scoring(query)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    top_intent, top_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
    score_gap = top_score - second_score

    # ── 2단계: 분기 결정 ──
    if score_gap >= SCORE_GAP_THRESHOLD and top_score >= MIN_SCORE_FOR_KEYWORD:
        logger.debug(
            f"의도[키워드] '{query[:30]}' -> {top_intent} "
            f"(score={top_score}, gap={score_gap})"
        )
        return top_intent

    # ── 3단계: LLM 보조 분류 ──
    if llm_client and top_score < MIN_SCORE_FOR_KEYWORD or (llm_client and score_gap < SCORE_GAP_THRESHOLD):
        llm_intent = _llm_classify(query, llm_client)
        if llm_intent:
            logger.debug(
                f"의도[LLM] '{query[:30]}' -> {llm_intent} "
                f"(keyword_top={top_intent}, score={top_score}, gap={score_gap})"
            )
            return llm_intent

    # ── 4단계: 키워드 폴백 ──
    if top_score == 0:
        return "document_search"

    logger.debug(
        f"의도[키워드 폴백] '{query[:30]}' -> {top_intent} "
        f"(score={top_score}, gap={score_gap})"
    )
    return top_intent


def _keyword_scoring(query: str) -> dict[str, int]:
    """키워드 기반 점수 계산 (v2.6 로직 유지)"""
    q = query.lower().strip()

    emp_score = sum(1 for kw in EMPLOYEE_KEYWORDS if kw in q)
    company_score = sum(1 for kw in COMPANY_INFO_KEYWORDS if kw in q)
    doc_score = sum(1 for kw in DOCUMENT_KEYWORDS if kw in q)
    compose_score = sum(1 for kw in COMPOSE_KEYWORDS if kw in q)
    reg_score = sum(1 for kw in REGULATION_KEYWORDS if kw in q)

    # "작성" 키워드는 doc_search와 겹칠 수 있으므로 compose에 가중치
    if compose_score > 0:
        compose_score += 1

    # 부서 별칭이 쿼리에 포함되면 employee_lookup 점수 부스트
    _dept_hit = any(alias in q for alias in DEPARTMENT_ALIASES)
    _div_hit = any(alias in q for alias in DIVISION_ALIASES)
    if _dept_hit or _div_hit:
        has_doc_signal = any(kw in q for kw in _DOC_STRONG_KEYWORDS)
        has_reg_signal = reg_score > 0
        if not has_doc_signal and not has_reg_signal:
            emp_score += 2

    return {
        "employee_lookup": emp_score,
        "company_info": company_score,
        "document_search": doc_score,
        "document_compose": compose_score,
        "regulation_query": reg_score,
    }


def _llm_classify(query: str, llm_client) -> Optional[str]:
    """LLM을 사용하여 의도를 분류합니다."""
    try:
        messages = [
            {"role": "system", "content": INTENT_CLASSIFY_SYSTEM},
            {"role": "user", "content": query},
        ]

        response = llm_client.generate(
            messages=messages,
            max_tokens=32,
            temperature=0.0,
            stream=False,
        )

        intent = response.strip().lower().replace(" ", "_")

        # 유효한 의도인지 확인
        if intent in VALID_INTENTS:
            return intent

        # 부분 매칭 시도
        for valid in VALID_INTENTS:
            if valid in intent:
                return valid

        logger.warning(f"LLM 의도 분류 결과 무효: '{intent}'")
        return None

    except Exception as e:
        logger.warning(f"LLM 의도 분류 실패: {e}")
        return None


def get_intent_scores(query: str) -> dict[str, int]:
    """디버깅용: 키워드 점수 반환"""
    return _keyword_scoring(query)
