"""부서 카테고리 설정 — 사원번호 접두어 + 부서 설명 (v2.2)"""

# 본부 → 부서 → (접두어, 설명) 매핑
DEPARTMENT_CATEGORIES: dict[str, dict[str, tuple[str, str]]] = {
    "재경본부": {
        "IT전략팀": ("IT", "사내 IT 인프라, DX 전략, AI 시스템 운영"),
        "재무팀": ("FN", "재무 관리, 자금 운용, 투자 분석"),
        "회계팀": ("AC", "재무회계, 세무, 결산"),
        "원가기획팀": ("CP", "제품 원가 분석/관리, 원가 절감 전략"),
    },
    "관리본부": {
        "총무인사팀": ("HR", "인사/채용/교육, 총무, 조직 관리"),
        "품질경영팀": ("QM", "ISO/IATF 인증, 품질경영 시스템 관리"),
        "ESG경영팀": ("ES", "ESG 전략, 탄소중립, 지속가능경영"),
        "기술교육원": ("ED", "기술 교육, 신입 연수, 직무 훈련"),
    },
    "구매본부": {
        "구매팀": ("PU", "원자재/부품 구매, 공급망 관리"),
        "해외지원팀": ("GS", "해외법인 지원, 글로벌 물류"),
        "상생협력팀": ("SC", "협력사 상생 협력, 동반 성장"),
    },
    "생산본부": {
        "품질보증팀": ("QA", "제품 품질 검사, 출하 보증, 고객 클레임 대응"),
        "안전보건팀": ("SF", "산업안전, 보건관리, 환경 규제 대응"),
        "생산관리팀": ("PM", "생산 계획/일정 관리, 공정 효율화"),
        "영업팀": ("SL", "OEM 영업, 고객 관리, 수주/매출"),
        "자재관리팀": ("MM", "자재 입출고 관리, 재고 관리"),
    },
    "개발본부": {
        "기술영업팀": ("TS", "기술 제안/영업, 고객 기술 대응"),
        "부품개발팀": ("PD", "신규 부품 설계/개발, PPAP 승인"),
        "금형생산팀": ("MD", "프레스 금형 설계/제작, 금형 보전"),
    },
    "생산기술본부": {
        "생산기술팀": ("PT", "공정 기술 개선, 설비 도입, 자동화"),
        "자동화기술팀": ("AT", "로봇/자동화 시스템, PLC, 비전 검사"),
        "비전연구팀": ("VR", "비전 AI 연구, 불량 검출 알고리즘"),
        "FA사업팀": ("FA", "FA(공장자동화) 시스템 사업, 외부 수주"),
        "플랜트사업팀": ("PL", "플랜트 설비 구축, 공장 건설 사업"),
        "제품설계팀": ("DS", "제품 설계, 3D 모델링, 도면 관리"),
        "공법계획팀": ("PP", "공법 기획, 공정 계획, 생산성 분석"),
        "용기운영팀": ("CN", "납입 용기 관리, 포장 사양 설정"),
    },
    "기술연구소": {
        "바디선행개발팀": ("RB", "차체 선행 R&D, 경량화, 핫스탬핑"),
        "전장선행개발팀": ("RE", "전장 선행 R&D, EWP/CCH 개발"),
    },
    "독립부서": {
        "내부감사팀": ("AU", "내부 감사, 경영 투명성, 컴플라이언스"),
    },
}

# 직급 목록 (높은 직급순)
POSITION_LIST = [
    "전무", "상무", "이사", "부장", "차장", "과장", "대리", "주임", "사원", "인턴",
]

# 역할 목록
ROLE_LIST = [
    "SYS_ADMIN", "HR_ADMIN", "TEAM_LEAD", "MANAGER", "EMPLOYEE", "INACTIVE",
]


def get_all_departments() -> list[str]:
    """전체 부서 목록을 반환한다."""
    depts = []
    for div_depts in DEPARTMENT_CATEGORIES.values():
        depts.extend(div_depts.keys())
    return depts


def get_all_divisions() -> list[str]:
    """전체 본부 목록을 반환한다."""
    return list(DEPARTMENT_CATEGORIES.keys())


def get_departments_by_division(division: str) -> list[str]:
    """특정 본부의 부서 목록을 반환한다."""
    return list(DEPARTMENT_CATEGORIES.get(division, {}).keys())


def get_dept_prefix(department: str) -> str:
    """부서의 사원번호 접두어를 반환한다."""
    for div_depts in DEPARTMENT_CATEGORIES.values():
        if department in div_depts:
            return div_depts[department][0]
    return "EMP"


def get_dept_description(department: str) -> str:
    """부서의 설명을 반환한다."""
    for div_depts in DEPARTMENT_CATEGORIES.values():
        if department in div_depts:
            return div_depts[department][1]
    return ""


def generate_employee_id(department: str, sequence: int) -> str:
    """부서 접두어 + 순번으로 사원번호를 생성한다."""
    prefix = get_dept_prefix(department)
    return f"{prefix}-{sequence:04d}"
