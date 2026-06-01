"""
문서 품질 자동 평가 엔진
- 5개 평가 기준으로 0~100점 자동 채점
- 문서유형별 필수 섹션/길이/용어 기준 적용
- TF-IDF 유사도로 템플릿 대비 적합도 측정
- 개선 포인트 자동 추출
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ──────────────────────────────────────────────
# 문서유형별 평가 기준
# ──────────────────────────────────────────────

DOC_REQUIRED_SECTIONS = {
    "8D 보고서": ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8",
                   "팀 구성", "문제 기술", "원인 분석", "시정 조치", "재발 방지"],
    "ECN": ["변경 사유", "변경 내용", "영향 범위", "적용 일자", "승인"],
    "PPAP": ["부품 정보", "치수 결과", "재료 성적서", "공정 흐름도", "관리 계획서"],
    "사내 이메일": ["수신", "제목", "본문", "발신"],
    "회의록": ["일시", "참석자", "안건", "논의 내용", "결정 사항", "후속 조치"],
    "품질문제 개선대책서": ["문제 현상", "발생 원인", "대책 내용", "효과 확인", "표준화"],
    "안전 인시던트 리포트": ["발생 일시", "발생 장소", "부상 여부", "원인", "재발 방지"],
    "규제 변경 영향 보고서": ["규제 개요", "영향 범위", "대응 방안", "일정", "담당"],
    # v3.7 — HR/행정 문서
    "휴가 신청서": ["신청자", "휴가 종류", "기간", "사유", "결재란"],
    "출장 신청서": ["신청자", "출장지", "기간", "출장 목적", "결재란"],
    "사직서": ["신청자", "입사일", "퇴직 희망일", "사직 사유", "인수인계", "결재란"],
    "인사발령 통지": ["수신", "발신", "제목", "발령 구분", "변경 전", "변경 후", "발령일"],
}

DOC_LENGTH_RANGE = {
    "8D 보고서": (500, 5000),
    "ECN": (200, 2000),
    "PPAP": (300, 3000),
    "사내 이메일": (50, 800),
    "회의록": (200, 3000),
    "품질문제 개선대책서": (300, 3000),
    "안전 인시던트 리포트": (200, 2000),
    "규제 변경 영향 보고서": (400, 4000),
    # v3.7 — HR/행정 문서
    "휴가 신청서": (150, 1000),
    "출장 신청서": (200, 1500),
    "사직서": (200, 1500),
    "인사발령 통지": (200, 1500),
}

FORMAL_DOC_TYPES = [
    "8D 보고서", "ECN", "PPAP", "규제 변경 영향 보고서", "안전 인시던트 리포트",
    "휴가 신청서", "출장 신청서", "사직서", "인사발령 통지",
]

# 금지 표현 (placeholder / 미완성 마커)
FORBIDDEN_PATTERNS = [
    r"\[작성\s*필요\]", r"\[입력\]", r"\[TODO\]", r"placeholder",
    r"_{3,}", r"\.\.\.\s*$", r"예시를\s*입력", r"\[여기에",
    r"XX월\s*XX일", r"OOO\s*(팀장|과장|대리)", r"내용을\s*입력",
]

# v3.7 — 도메인별 전문 용어 사전 (B-1)
# 자동차/제조 도메인 — 기존 PROFESSIONAL_TERMS 그대로
AUTO_MFG_TERMS = [
    "Cpk", "SPC", "PPAP", "APQP", "FMEA", "8D", "ECN", "MSA",
    "IATF", "ISO", "OEM", "공차", "규격", "불량률", "시정조치",
    "예방조치", "근본원인", "관리계획서", "공정흐름도", "양산",
    "초품", "금형", "프레스", "용접", "사출", "CNC",
    "검사성적서", "출하검사", "수입검사", "공정검사",
]

# HR/행정 도메인 — 휴가·출장·사직·인사발령에서 자주 쓰는 격식 용어
HR_ADMIN_TERMS = [
    "신청자", "결재", "결재란", "승인", "수신", "발신", "제목",
    "휴가", "연차", "반차", "병가", "특별 휴가", "경조사",
    "출장", "출장지", "출장 목적", "복귀일", "예상 경비",
    "인수인계", "담당자", "사번", "소속", "직급", "부서",
    "사직", "퇴직", "재직", "입사일", "퇴직 희망일",
    "발령", "부서 이동", "승진", "직무 변경", "발령일", "효력",
]

# 하위 호환 — 기존 PROFESSIONAL_TERMS 참조 코드를 위해 유지 (deprecated)
PROFESSIONAL_TERMS = AUTO_MFG_TERMS

# 도메인 매핑 — doc_type 별 적용 용어 사전.
#   None → 평가 비활성 (default 20점, 안내 메시지 제외)
#   리스트 → 그 리스트로 평가
DOC_PROFESSIONAL_TERMS: dict = {
    # 자동차/제조
    "8D 보고서":              AUTO_MFG_TERMS,
    "ECN":                     AUTO_MFG_TERMS,
    "PPAP":                    AUTO_MFG_TERMS,
    "품질문제 개선대책서":      AUTO_MFG_TERMS,
    "안전 인시던트 리포트":     AUTO_MFG_TERMS,
    "규제 변경 영향 보고서":    AUTO_MFG_TERMS,
    # HR/행정
    "휴가 신청서":              HR_ADMIN_TERMS,
    "출장 신청서":              HR_ADMIN_TERMS,
    "사직서":                   HR_ADMIN_TERMS,
    "인사발령 통지":            HR_ADMIN_TERMS,
    # 일반 행정 — terminology 평가 비활성
    "사내 이메일":              None,
    "회의록":                   None,
}


@dataclass
class QualityScore:
    """문서 품질 평가 결과"""
    total_score: float              # 총점 (0~100)
    grade: str                      # A/B/C/D/F
    structure_score: float          # 구조 완성도 (0~25)
    length_score: float             # 길이 적정성 (0~20)
    terminology_score: float        # 전문 용어 사용 (0~25)
    completeness_score: float       # 완성도 (미완성 마커 없음) (0~15)
    tone_score: float               # 톤/격식 적합도 (0~15)
    improvements: List[str]         # 개선 포인트 리스트
    details: Dict[str, any]         # 상세 분석 데이터


def evaluate_document(
    text: str,
    doc_type: str,
    reference_template: str = "",
) -> QualityScore:
    """
    문서 품질 자동 평가

    Args:
        text: 평가 대상 문서 텍스트
        doc_type: 문서유형 (예: "8D 보고서")
        reference_template: 참조 템플릿 텍스트 (TF-IDF 유사도용)
    """
    improvements = []
    details = {}

    # ── 1. 구조 완성도 (0~25) ──
    required = DOC_REQUIRED_SECTIONS.get(doc_type, [])
    if required:
        present = 0
        missing = []
        for section in required:
            # 섹션명 또는 유사 표현이 텍스트에 포함되는지
            if section.lower() in text.lower() or _fuzzy_section_match(section, text):
                present += 1
            else:
                missing.append(section)
        structure_score = (present / len(required)) * 25
        if missing:
            improvements.append(f"누락 섹션: {', '.join(missing[:5])}")
        details["required_sections"] = len(required)
        details["present_sections"] = present
        details["missing_sections"] = missing
    else:
        structure_score = 20.0  # 기준 없는 문서유형은 기본 점수

    # ── 2. 길이 적정성 (0~20) ──
    char_count = len(text)
    min_len, max_len = DOC_LENGTH_RANGE.get(doc_type, (100, 3000))

    if min_len <= char_count <= max_len:
        length_score = 20.0
    elif char_count < min_len:
        ratio = char_count / min_len
        length_score = max(0, ratio * 20)
        improvements.append(f"문서가 너무 짧음 ({char_count}자, 최소 {min_len}자 권장)")
    else:
        over_ratio = char_count / max_len
        length_score = max(5, 20 - (over_ratio - 1) * 10)
        improvements.append(f"문서가 다소 김 ({char_count}자, 최대 {max_len}자 권장)")

    details["char_count"] = char_count
    details["length_range"] = (min_len, max_len)

    # ── 3. 전문 용어 사용 (0~25) ── v3.7: doc_type 별 도메인 분리 (B-1)
    # DOC_PROFESSIONAL_TERMS 매핑:
    #   - 등록 + 리스트 → 해당 도메인 용어로 평가
    #   - 등록 + None → 평가 비활성 (default 20점)
    #   - 미등록 → 안전한 default (20점, 안내 메시지 제외)
    if doc_type in DOC_PROFESSIONAL_TERMS:
        domain_terms = DOC_PROFESSIONAL_TERMS[doc_type]
    else:
        domain_terms = None  # 미등록 doc_type 은 평가 skip

    terms_found = []
    if domain_terms:
        for term in domain_terms:
            if term.lower() in text.lower():
                terms_found.append(term)

        # 도메인 용어 사전 사이즈를 고려한 정규화 — 사전의 약 절반 또는 8개 중 작은 값을 만점 기준
        target = min(8, max(3, len(domain_terms) // 4))
        term_ratio = min(1.0, len(terms_found) / target)
        terminology_score = term_ratio * 25

        if len(terms_found) < max(2, target // 3):
            domain_label = "HR/행정" if domain_terms is HR_ADMIN_TERMS else "자동차/제조"
            improvements.append(
                f"{domain_label} 관련 전문 용어 사용이 부족합니다."
            )
    else:
        # 평가 비활성 — 사내 이메일/회의록/미등록 doc_type
        terminology_score = 20.0  # default 만점에 가까운 점수 (도메인 강요 X)

    # TF-IDF 유사도 (참조 템플릿이 있는 경우)
    if reference_template and len(reference_template) > 50:
        try:
            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=3000)
            tfidf = vectorizer.fit_transform([reference_template, text])
            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            # 유사도 높으면 보너스 (최대 +5점)
            terminology_score = min(25, terminology_score + sim * 5)
            details["template_similarity"] = round(float(sim), 3)
        except Exception:
            pass

    details["terms_found"] = terms_found
    details["terms_count"] = len(terms_found)

    # ── 4. 완성도 — 미완성 마커 검사 (0~15) ──
    violations = 0
    violation_details = []
    for pattern in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            violations += len(matches)
            violation_details.append(f"'{matches[0]}' ({len(matches)}회)")

    completeness_score = max(0, 15 - violations * 3)
    if violations > 0:
        improvements.append(f"미완성 표현 {violations}건 발견: {', '.join(violation_details[:3])}")

    details["placeholder_violations"] = violations

    # ── 5. 톤/격식 적합도 (0~15) ──
    tone_score = 15.0

    if doc_type in FORMAL_DOC_TYPES:
        informal_markers = ["해줘", "해주세요", "좀", "그냥", "뭐", "근데", "걍"]
        informal_count = sum(1 for m in informal_markers if m in text)
        if informal_count > 0:
            tone_score -= informal_count * 2
            improvements.append("공식 문서에 부적절한 비격식 표현이 포함되어 있습니다.")

        # 격식체 마커 확인
        formal_markers = ["드립니다", "바랍니다", "하겠습니다", "되었습니다", "확인하였습니다"]
        formal_count = sum(1 for m in formal_markers if m in text)
        if formal_count == 0 and char_count > 200:
            tone_score -= 3
            improvements.append("공식 문서에 격식체 표현이 부족합니다.")

    tone_score = max(0, tone_score)
    details["is_formal_doc"] = doc_type in FORMAL_DOC_TYPES

    # ── 총점 + 등급 ──
    total = structure_score + length_score + terminology_score + completeness_score + tone_score
    total = round(min(100, max(0, total)), 1)

    if total >= 90:
        grade = "A"
    elif total >= 75:
        grade = "B"
    elif total >= 60:
        grade = "C"
    elif total >= 40:
        grade = "D"
    else:
        grade = "F"

    return QualityScore(
        total_score=total,
        grade=grade,
        structure_score=round(structure_score, 1),
        length_score=round(length_score, 1),
        terminology_score=round(terminology_score, 1),
        completeness_score=round(completeness_score, 1),
        tone_score=round(tone_score, 1),
        improvements=improvements,
        details=details,
    )


def _fuzzy_section_match(section: str, text: str) -> bool:
    """섹션명 퍼지 매칭 (부분 일치)"""
    keywords = section.replace(" ", "").lower()
    text_lower = text.lower().replace(" ", "")
    # 2글자 이상 연속 매칭이면 OK
    if len(keywords) >= 2 and keywords in text_lower:
        return True
    # 섹션명의 각 단어가 텍스트에 포함되는지
    words = section.split()
    return all(w.lower() in text.lower() for w in words if len(w) >= 2)
