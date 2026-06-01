"""
부서 적응형 설정 레지스트리 — 27개 부서별 기능 A·B·C 커스터마이즈 정보를 한 곳에서 관리

v3.0: 각 기능 모듈은 이 레지스트리에서 부서별 설정을 조회하여 동작을 적응시킵니다.
개별 기능 모듈에 부서 하드코딩을 방지하고, 부서 추가/변경 시 이 파일만 수정합니다.

참고: core/auth/department_config.py (v2.x)는 사원번호 접두어/설명 전용 — 별도 유지
"""
from typing import Optional


# ── 부서별 설정 레지스트리 ──

DEPARTMENT_REGISTRY = {

    # ═══════════════════════════════════════
    # 경영지원본부
    # ═══════════════════════════════════════
    "내부감사팀": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["사내 이메일", "회의록"],
        "cc_targets": [],
        "glossary_focus": ["경영", "감사", "내부통제"],
        "onboarding_essentials": ["내부감사 절차", "윤리강령"],
        "quick_questions": ["내부감사 프로세스 알려줘", "윤리강령 내용이 뭐야?"],
    },
    "재무팀": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["사내 이메일", "회의록"],
        "cc_targets": ["회계팀"],
        "glossary_focus": ["재무", "회계", "예산"],
        "onboarding_essentials": ["예산 편성 절차", "결산 프로세스"],
        "quick_questions": ["예산 신청 절차", "결산 일정 알려줘"],
    },
    "회계팀": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["사내 이메일", "회의록"],
        "cc_targets": ["재무팀"],
        "glossary_focus": ["회계", "세무", "원가"],
        "onboarding_essentials": ["전표 처리 절차", "세무 신고 일정"],
        "quick_questions": ["전표 입력 방법", "부가세 신고 일정"],
    },
    "원가기획팀": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["사내 이메일", "회의록", "제안서"],
        "cc_targets": ["재무팀"],
        "glossary_focus": ["원가", "BOM", "단가"],
        "onboarding_essentials": ["원가 산출 기준", "BOM 구조 이해"],
        "quick_questions": ["원가 계산 방법", "BOM이 뭐야?"],
    },
    "총무인사팀": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["사내 이메일", "회의록", "업무인수인계서"],
        "cc_targets": [],
        "glossary_focus": ["인사", "급여", "복리후생"],
        "onboarding_essentials": ["근태 관리 규정", "복리후생 안내", "인사평가 절차"],
        "quick_questions": ["연차 사용 방법", "급여일 언제야?", "복지 제도 알려줘"],
    },
    "ESG경영팀": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["규제 변경 영향 보고서", "규제 시행 계획서", "규제 대비 체크리스트"],
        "cc_targets": ["안전보건팀", "품질경영팀"],
        "glossary_focus": ["ESG", "탄소중립", "지속가능"],
        "onboarding_essentials": ["ESG 경영 방침", "탄소배출 관리"],
        "quick_questions": ["ESG 경영 방침 알려줘", "탄소배출 규제 현황"],
    },
    "IT전략팀": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["사내 이메일", "회의록", "제안서"],
        "cc_targets": [],
        "glossary_focus": ["IT", "시스템", "보안", "MES", "ERP"],
        "onboarding_essentials": ["사내 시스템 목록", "정보보안 정책", "MES/ERP 사용법"],
        "quick_questions": ["사내 시스템 뭐가 있어?", "VPN 연결 방법", "MES 사용법"],
    },

    # ═══════════════════════════════════════
    # 영업본부
    # ═══════════════════════════════════════
    "기술영업팀": {
        "division": "영업본부",
        "category": "sales",
        "doc_priority": ["이메일(외부)", "OEM 규제 대응 통보문", "출장보고서"],
        "cc_targets": ["해외지원팀"],
        "glossary_focus": ["영업", "OEM", "RFQ", "수주"],
        "onboarding_essentials": ["수주 프로세스", "OEM 고객 관리", "견적 작성"],
        "quick_questions": ["RFQ 대응 절차", "현대/기아 담당자 연락처", "수주 현황 확인"],
    },
    "해외지원팀": {
        "division": "영업본부",
        "category": "sales",
        "doc_priority": ["이메일(외부)", "OEM 규제 대응 통보문", "출장보고서"],
        "cc_targets": ["기술영업팀"],
        "glossary_focus": ["해외", "HMGMA", "JOON", "수출"],
        "onboarding_essentials": ["해외법인 현황", "수출 절차", "통관 프로세스"],
        "quick_questions": ["해외법인 목록 보여줘", "JOON INC 현황", "통관 절차"],
    },
    "상생협력팀": {
        "division": "영업본부",
        "category": "sales",
        "doc_priority": ["협력사 준수 요청서", "이메일(외부)"],
        "cc_targets": [],
        "glossary_focus": ["협력사", "상생", "동반성장"],
        "onboarding_essentials": ["협력사 관리 기준", "동반성장 프로그램"],
        "quick_questions": ["2차 협력사 목록", "협력사 평가 기준"],
    },

    # ═══════════════════════════════════════
    # 구매본부
    # ═══════════════════════════════════════
    "구매팀": {
        "division": "구매본부",
        "category": "management",
        "doc_priority": ["사급 반출 요청서", "이메일(외부)", "협력사 준수 요청서"],
        "cc_targets": ["자재관리팀"],
        "glossary_focus": ["구매", "발주", "단가", "사급"],
        "onboarding_essentials": ["구매 발주 프로세스", "사급자재 관리", "협력사 평가"],
        "quick_questions": ["구매 발주 절차", "사급자재가 뭐야?", "협력사 평가 기준"],
    },
    "자재관리팀": {
        "division": "구매본부",
        "category": "management",
        "doc_priority": ["사급 반출 요청서", "납입용기 규격 설정서"],
        "cc_targets": ["구매팀", "생산관리팀"],
        "glossary_focus": ["자재", "재고", "입출고", "납입용기"],
        "onboarding_essentials": ["자재 입출고 절차", "재고 관리 기준", "납입용기 규격"],
        "quick_questions": ["자재 입출고 절차", "재고 조회 방법", "납입용기 규격"],
    },

    # ═══════════════════════════════════════
    # 생산본부
    # ═══════════════════════════════════════
    "생산관리팀": {
        "division": "생산본부",
        "category": "production",
        "doc_priority": ["납입용기 규격 설정서", "회의록", "사내 이메일", "업무일지"],
        "cc_targets": ["생산기술팀", "품질보증팀"],
        "glossary_focus": ["생산", "공정", "라인", "택트타임"],
        "onboarding_essentials": ["생산 계획 수립", "라인 운영 기초", "MES 활용"],
        "quick_questions": ["생산 계획 어떻게 세워?", "MES 사용법", "택트타임이 뭐야?"],
    },
    "금형생산팀": {
        "division": "생산본부",
        "category": "production",
        "doc_priority": ["업무일지", "사내 이메일", "회의록"],
        "cc_targets": [],
        "glossary_focus": ["금형", "프레스", "사출", "트라이"],
        "onboarding_essentials": ["금형 관리 기초", "프레스 공정 종류", "금형 수명 관리"],
        "quick_questions": ["금형 종류 알려줘", "트라이가 뭐야?", "금형 수명 관리 방법"],
    },
    "용기운영팀": {
        "division": "생산본부",
        "category": "production",
        "doc_priority": ["납입용기 규격 설정서", "업무일지"],
        "cc_targets": [],
        "glossary_focus": ["용기", "납입", "포장", "물류"],
        "onboarding_essentials": ["납입용기 규격 기준", "포장 표준"],
        "quick_questions": ["납입용기 규격 기준", "포장 방법 알려줘"],
    },
    "안전보건팀": {
        "division": "생산본부",
        "category": "production",
        "doc_priority": ["안전 인시던트 리포트", "규제 시행 계획서", "교육이수보고서"],
        "cc_targets": ["ESG경영팀", "생산관리팀"],
        "glossary_focus": ["안전", "보건", "PSM", "MSDS", "산안법"],
        "onboarding_essentials": ["산업안전보건법 기초", "안전 인시던트 보고", "PSM 공정안전관리"],
        "quick_questions": ["안전사고 보고 절차", "PSM이 뭐야?", "MSDS 어디서 확인해?"],
    },

    # ═══════════════════════════════════════
    # 기술본부
    # ═══════════════════════════════════════
    "생산기술팀": {
        "division": "기술본부",
        "category": "engineering",
        "doc_priority": ["ECN 변경통보", "회의록", "사내 이메일", "제안서"],
        "cc_targets": ["품질보증팀", "생산관리팀"],
        "glossary_focus": ["공정", "프레스", "용접", "조립", "자동화"],
        "onboarding_essentials": ["프레스 공정 기초", "ECN 변경 절차", "MES 시스템"],
        "quick_questions": ["프레스 공정 종류", "ECN 작성 방법", "공정 개선 사례"],
    },
    "자동화기술팀": {
        "division": "기술본부",
        "category": "engineering",
        "doc_priority": ["제안서", "회의록", "출장보고서"],
        "cc_targets": [],
        "glossary_focus": ["자동화", "로봇", "PLC", "비전"],
        "onboarding_essentials": ["자동화 설비 현황", "PLC 기초", "로봇 운영"],
        "quick_questions": ["자동화 설비 목록", "PLC가 뭐야?", "로봇 운영 매뉴얼"],
    },
    "FA사업팀": {
        "division": "기술본부",
        "category": "engineering",
        "doc_priority": ["제안서", "이메일(외부)", "출장보고서"],
        "cc_targets": [],
        "glossary_focus": ["FA", "설비", "치공구"],
        "onboarding_essentials": ["FA사업 소개", "주요 프로젝트"],
        "quick_questions": ["FA사업이 뭐야?", "주요 납품처 알려줘"],
    },
    "플랜트사업팀": {
        "division": "기술본부",
        "category": "engineering",
        "doc_priority": ["제안서", "이메일(외부)", "출장보고서"],
        "cc_targets": [],
        "glossary_focus": ["플랜트", "설비", "시공"],
        "onboarding_essentials": ["플랜트사업 소개", "시공 프로세스"],
        "quick_questions": ["플랜트사업 소개해줘", "시공 프로세스 알려줘"],
    },

    # ═══════════════════════════════════════
    # 품질본부
    # ═══════════════════════════════════════
    "품질보증팀": {
        "division": "품질본부",
        "category": "quality",
        "doc_priority": ["8D Report", "품질문제 개선대책서", "PPAP 제출 문서", "ECN 변경통보"],
        "cc_targets": ["품질경영팀"],
        "glossary_focus": ["품질", "8D", "SPC", "PPAP", "불량", "Cpk"],
        "onboarding_essentials": ["IATF 16949 기본", "8D 보고서 작성법", "SPC 관리도", "부적합품 처리"],
        "quick_questions": ["8D 보고서 작성법", "SPC가 뭐야?", "PPAP 절차 알려줘", "Cpk 기준치"],
    },
    "품질경영팀": {
        "division": "품질본부",
        "category": "quality",
        "doc_priority": ["8D Report", "품질문제 개선대책서", "규제 변경 영향 보고서"],
        "cc_targets": ["품질보증팀"],
        "glossary_focus": ["품질경영", "ISO", "IATF", "심사", "인증"],
        "onboarding_essentials": ["ISO 9001 기초", "IATF 16949 요건", "품질 심사 대응"],
        "quick_questions": ["ISO 인증 현황", "IATF 심사 일정", "품질 방침 알려줘"],
    },

    # ═══════════════════════════════════════
    # 기술연구소
    # ═══════════════════════════════════════
    "제품설계팀": {
        "division": "기술연구소",
        "category": "engineering",
        "doc_priority": ["ECN 변경통보", "제안서", "출장보고서"],
        "cc_targets": ["공법계획팀", "부품개발팀"],
        "glossary_focus": ["설계", "CAD", "BOM", "도면", "해석"],
        "onboarding_essentials": ["CAD 시스템 사용", "BOM 구조", "ECN 절차", "도면 관리"],
        "quick_questions": ["CAD 시스템 뭐 써?", "BOM 작성 방법", "ECN 절차 알려줘"],
    },
    "공법계획팀": {
        "division": "기술연구소",
        "category": "engineering",
        "doc_priority": ["제안서", "회의록"],
        "cc_targets": ["제품설계팀"],
        "glossary_focus": ["공법", "성형", "금형", "공정설계"],
        "onboarding_essentials": ["공법 계획 프로세스", "성형 해석 기초"],
        "quick_questions": ["공법 계획 절차", "성형 해석이 뭐야?"],
    },
    "비전연구팀": {
        "division": "기술연구소",
        "category": "engineering",
        "doc_priority": ["제안서", "출장보고서", "교육이수보고서"],
        "cc_targets": [],
        "glossary_focus": ["비전", "AI", "머신러닝", "검사"],
        "onboarding_essentials": ["비전 검사 시스템", "AI 적용 현황"],
        "quick_questions": ["비전 검사 시스템 소개", "AI 적용 사례"],
    },
    "바디선행개발팀": {
        "division": "기술연구소",
        "category": "engineering",
        "doc_priority": ["제안서", "회의록", "출장보고서"],
        "cc_targets": ["전장선행개발팀"],
        "glossary_focus": ["바디", "차체", "경량화", "핫스탬핑"],
        "onboarding_essentials": ["차체 부품 개발 프로세스", "경량화 기술"],
        "quick_questions": ["바디 부품 종류", "핫스탬핑이 뭐야?", "경량화 기술 알려줘"],
    },
    "전장선행개발팀": {
        "division": "기술연구소",
        "category": "engineering",
        "doc_priority": ["제안서", "회의록", "출장보고서"],
        "cc_targets": ["바디선행개발팀"],
        "glossary_focus": ["전장", "EV", "EWP", "CCH", "배터리"],
        "onboarding_essentials": ["전장 부품 개발", "EV 부품 종류", "EWP/CCH 이해"],
        "quick_questions": ["EV 부품 뭐가 있어?", "EWP가 뭐야?", "전장 부품 개발 프로세스"],
    },

    # ═══════════════════════════════════════
    # 기타
    # ═══════════════════════════════════════
    "부품개발팀": {
        "division": "기술본부",
        "category": "engineering",
        "doc_priority": ["ECN 변경통보", "PPAP 제출 문서", "제안서"],
        "cc_targets": ["제품설계팀"],
        "glossary_focus": ["부품", "개발", "양산", "PPAP"],
        "onboarding_essentials": ["부품 개발 프로세스", "PPAP 절차", "양산 이관"],
        "quick_questions": ["부품 개발 단계", "PPAP가 뭐야?", "양산 이관 절차"],
    },
    "기술교육원": {
        "division": "경영지원본부",
        "category": "management",
        "doc_priority": ["교육이수보고서", "사내 이메일", "회의록"],
        "cc_targets": [],
        "glossary_focus": ["교육", "훈련", "OJT", "자격"],
        "onboarding_essentials": ["교육 체계", "필수 교육 목록", "OJT 프로그램"],
        "quick_questions": ["필수 교육 목록", "OJT 일정", "자격증 지원 제도"],
    },
}


# ── 유틸리티 함수 ──

def get_dept_config(department: str) -> dict:
    """부서 설정 조회 (없으면 기본값 반환)"""
    default = {
        "division": "기타",
        "category": "management",
        "doc_priority": ["사내 이메일", "회의록", "업무일지"],
        "cc_targets": [],
        "glossary_focus": [],
        "onboarding_essentials": ["회사 소개", "조직도 확인"],
        "quick_questions": ["회사 소개해줘", "조직도 보여줘"],
    }
    return DEPARTMENT_REGISTRY.get(department, default)


def get_all_departments_by_category(category: str) -> list[str]:
    """카테고리별 부서 목록 (management/production/engineering/quality/sales)"""
    return [
        dept for dept, config in DEPARTMENT_REGISTRY.items()
        if config.get("category") == category
    ]


def get_departments_in_division(division: str) -> list[str]:
    """본부 소속 부서 목록"""
    return [
        dept for dept, config in DEPARTMENT_REGISTRY.items()
        if config.get("division") == division
    ]


def get_all_divisions() -> list[str]:
    """전체 본부 목록"""
    return sorted(set(c["division"] for c in DEPARTMENT_REGISTRY.values()))


def get_all_categories() -> list[str]:
    """전체 카테고리 목록"""
    return sorted(set(c["category"] for c in DEPARTMENT_REGISTRY.values()))


def get_doc_priority_for_dept(department: str) -> list[str]:
    """부서의 문서 유형 우선순위 반환"""
    config = get_dept_config(department)
    return config.get("doc_priority", [])


def get_quick_questions_for_dept(department: str) -> list[str]:
    """부서의 빠른 질문 목록 반환"""
    config = get_dept_config(department)
    return config.get("quick_questions", [])
