"""Phase 5: 부서별 맞춤 응답 라우터

같은 질문에 부서별로 다른 관점의 답변을 제공하기 위한 부서 프로필 관리.
조직 참조: AJIN_ORGANIZATION_REFERENCE.md (6본부 + 기술연구소 + 독립부서)
"""

from dataclasses import dataclass, field


@dataclass
class DepartmentProfile:
    """부서 프로필"""
    name: str
    division: str
    core_responsibilities: list[str]
    key_systems: list[str]
    frequent_collaborations: list[str]
    answer_perspective: str


DEPARTMENT_PROFILES: dict[str, DepartmentProfile] = {
    # ── 생산본부 ──
    "품질보증팀": DepartmentProfile(
        name="품질보증팀",
        division="생산본부",
        core_responsibilities=[
            "PPAP 주관", "클레임(8D) 대응", "SPC 관리",
            "심사 대응(IATF/고객)", "검사 관리(초물/정기/출하)",
            "고객 품질(CQA), 공정 품질(PQA), 수입 품질(IQC) 3파트 운영",
        ],
        key_systems=["SQ 포털", "품질 MES", "SPC 시스템", "ERP"],
        frequent_collaborations=["생산기술팀", "부품개발팀", "영업팀", "안전보건팀"],
        answer_perspective=(
            "당신이 품질보증팀(생산본부)이니까, 이 업무에서 당신의 역할은 "
            "품질 기준 설정과 검증, 고객사(현대·기아) 대응입니다. "
            "SQ 포털 관리, 8D Report 대응, PPAP 서류 취합이 핵심 업무입니다."
        ),
    ),
    "안전보건팀": DepartmentProfile(
        name="안전보건팀",
        division="생산본부",
        core_responsibilities=[
            "산업안전보건법 준수·관리", "안전점검·순회",
            "근로자 안전보건교육", "위험성 평가",
            "현장 중심 안전보건관리 실무", "산업재해 예방",
        ],
        key_systems=["안전관리 시스템", "위험성 평가 시스템", "MSDS DB", "산재 관리 시스템"],
        frequent_collaborations=["생산관리팀", "품질보증팀", "ESG경영팀", "생산기술팀"],
        answer_perspective=(
            "당신이 안전보건팀(생산본부)이니까, 이 업무에서 당신의 역할은 "
            "산안법 기반 현장 안전 확보와 재해 예방입니다. "
            "법규 변경 모니터링, 위험성 평가, 안전교육이 핵심입니다."
        ),
    ),
    "생산관리팀": DepartmentProfile(
        name="생산관리팀",
        division="생산본부",
        core_responsibilities=[
            "제조공장 생산 진도 관리", "설비 유지보수·개선",
            "원가 절감", "생산성 향상", "공장 프로세스 제어",
        ],
        key_systems=["MES", "ERP 생산모듈", "설비 PM 시스템"],
        frequent_collaborations=["생산기술팀", "안전보건팀", "품질보증팀", "자재관리팀"],
        answer_perspective=(
            "당신이 생산관리팀(생산본부)이니까, 이 업무에서 당신의 역할은 "
            "생산 현장의 일정·설비·인력 관리입니다. "
            "생산 진도 관리와 원가 절감이 핵심입니다."
        ),
    ),
    "영업팀": DepartmentProfile(
        name="영업팀",
        division="생산본부",
        core_responsibilities=[
            "납품관리", "외주자재 조달", "물류 협력사 관리",
            "생산과 고객(현대·기아) 연결", "납기 조율",
        ],
        key_systems=["ERP 영업모듈", "고객사 EDI", "납기 관리 시스템"],
        frequent_collaborations=["품질보증팀", "생산관리팀", "자재관리팀"],
        answer_perspective=(
            "당신이 영업팀(생산본부)이니까, 이 업무에서 당신의 역할은 "
            "고객(현대·기아) 커뮤니케이션 창구이며, 납기와 클레임 전달이 가장 중요합니다."
        ),
    ),

    "자재관리팀": DepartmentProfile(
        name="자재관리팀",
        division="생산본부",
        core_responsibilities=[
            "원자재 조달", "재고 관리", "공급망 최적화",
            "자재 수불 관리", "안전재고 유지",
        ],
        key_systems=["ERP 자재모듈", "WMS", "바코드 시스템"],
        frequent_collaborations=["구매팀", "생산관리팀", "영업팀"],
        answer_perspective=(
            "당신이 자재관리팀(생산본부)이니까, 이 업무에서 당신의 역할은 "
            "원자재 수급과 재고 최적화입니다. 결품 방지와 재고 회전율 관리가 핵심입니다."
        ),
    ),

    # ── 생산기술본부 ──
    "생산기술팀": DepartmentProfile(
        name="생산기술팀",
        division="생산기술본부",
        core_responsibilities=[
            "생산설비·공법 연구·개선", "생산성 향상",
            "4M 변경 관리", "금형 Try-out", "공정 설계",
        ],
        key_systems=["금형 관리 시스템", "설비 PM 시스템", "MES", "CAD/CAM"],
        frequent_collaborations=["품질보증팀", "부품개발팀", "생산관리팀", "자동화기술팀"],
        answer_perspective=(
            "당신이 생산기술팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "공정·설비 관점의 기술적 검토와 개선입니다. "
            "금형과 설비 조건을 최적화하는 것이 핵심입니다."
        ),
    ),
    "자동화기술팀": DepartmentProfile(
        name="자동화기술팀",
        division="생산기술본부",
        core_responsibilities=[
            "생산라인 3D 스캐닝·시뮬레이션", "기존/신차라인 자동화 구축",
            "스마트팩토리 AI 알고리즘 개발", "로봇 프로그래밍",
        ],
        key_systems=["3D 스캐너", "로봇 시뮬레이터", "PLC", "MES"],
        frequent_collaborations=["생산기술팀", "비전연구팀", "IT전략팀", "FA사업팀"],
        answer_perspective=(
            "당신이 자동화기술팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "생산 자동화와 스마트팩토리 구현입니다. 로봇·AI 기반 공정 혁신이 핵심입니다."
        ),
    ),
    "FA사업팀": DepartmentProfile(
        name="FA사업팀",
        division="생산기술본부",
        core_responsibilities=[
            "스마트팩토리·무인자동화 구축", "지능형 제조혁신 선도",
            "FA(Factory Automation) 시스템 설계·납품",
        ],
        key_systems=["PLC/HMI", "로봇 시스템", "MES", "IoT 센서"],
        frequent_collaborations=["자동화기술팀", "생산기술팀", "플랜트사업팀"],
        answer_perspective=(
            "당신이 FA사업팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "스마트팩토리 솔루션 개발과 무인자동화 사업입니다."
        ),
    ),
    "플랜트사업팀": DepartmentProfile(
        name="플랜트사업팀",
        division="생산기술본부",
        core_responsibilities=[
            "공장 건축~설비 설치·시운전 전 단계 책임",
            "최적 레이아웃 설계", "통합 프로젝트 관리",
        ],
        key_systems=["CAD", "프로젝트 관리 시스템", "설비 관리"],
        frequent_collaborations=["FA사업팀", "생산기술팀", "안전보건팀"],
        answer_perspective=(
            "당신이 플랜트사업팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "공장 건설·증설 프로젝트의 통합 관리입니다."
        ),
    ),
    "제품설계팀": DepartmentProfile(
        name="제품설계팀",
        division="생산기술본부",
        core_responsibilities=[
            "차체/클로저/의장 파트 제품 설계", "시작품 개발",
            "기술 표준류 제·개정", "고객사 평가 대응",
        ],
        key_systems=["CATIA", "NX", "CAE 해석", "PLM"],
        frequent_collaborations=["부품개발팀", "공법계획팀", "품질보증팀"],
        answer_perspective=(
            "당신이 제품설계팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "차체 제품 설계와 도면 작성, 고객사 기술 평가 대응입니다."
        ),
    ),
    "공법계획팀": DepartmentProfile(
        name="공법계획팀",
        division="생산기술본부",
        core_responsibilities=[
            "최적 프레스 공법 설정", "AUTOFORM 성형해석 활용",
            "품질 안정화 및 생산성 확보", "공법 표준화",
        ],
        key_systems=["AUTOFORM", "CAE", "금형 시뮬레이션"],
        frequent_collaborations=["제품설계팀", "생산기술팀", "금형생산팀"],
        answer_perspective=(
            "당신이 공법계획팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "프레스 공법 최적화와 성형해석 기반 품질 확보입니다."
        ),
    ),
    "용기운영팀": DepartmentProfile(
        name="용기운영팀",
        division="생산기술본부",
        core_responsibilities=[
            "납품용기 설계·개발·제작·개선",
            "제품 품질 보전", "물류 효율 확보",
        ],
        key_systems=["용기 관리 시스템", "CAD", "물류 관리"],
        frequent_collaborations=["생산관리팀", "영업팀", "자재관리팀"],
        answer_perspective=(
            "당신이 용기운영팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "납품용기 설계와 물류 효율 최적화입니다."
        ),
    ),
    "비전연구팀": DepartmentProfile(
        name="비전연구팀",
        division="생산기술본부",
        core_responsibilities=[
            "카메라·AI 기술 활용 자동 검사 시스템 개발·운영",
            "검사 공정 자동화", "머신비전 품질 향상",
        ],
        key_systems=["머신비전 카메라", "AI 검사 플랫폼", "GPU 서버", "딥러닝 프레임워크"],
        frequent_collaborations=["자동화기술팀", "품질보증팀", "IT전략팀"],
        answer_perspective=(
            "당신이 비전연구팀(생산기술본부)이니까, 이 업무에서 당신의 역할은 "
            "AI 비전 검사 시스템 개발과 품질 자동화입니다."
        ),
    ),

    # ── 개발본부 ──
    "기술영업팀": DepartmentProfile(
        name="기술영업팀",
        division="개발본부",
        core_responsibilities=[
            "아이템 수주 업무", "제품가 결정 및 투자비 회수",
            "양산 제품가 관리", "EO비 회수",
        ],
        key_systems=["ERP 영업모듈", "견적 시스템", "고객사 EDI"],
        frequent_collaborations=["부품개발팀", "원가기획팀", "영업팀"],
        answer_perspective=(
            "당신이 기술영업팀(개발본부)이니까, 이 업무에서 당신의 역할은 "
            "수주 확보와 제품가 결정, 투자비 회수입니다."
        ),
    ),
    "부품개발팀": DepartmentProfile(
        name="부품개발팀",
        division="개발본부",
        core_responsibilities=[
            "신차종 단품 양산 진척 관리", "금형 발주~최종 승인",
            "ECR/ECN 발의", "PPAP 설계 서류 작성",
            "시작품 제작", "도면 관리",
        ],
        key_systems=["CAD/CAE", "PLM", "시험장비", "도면관리시스템"],
        frequent_collaborations=["품질보증팀", "생산기술팀", "기술영업팀", "금형생산팀"],
        answer_perspective=(
            "당신이 부품개발팀(개발본부)이니까, 이 업무에서 당신의 역할은 "
            "설계 관점의 기술적 검토와 도면/사양 관리입니다. "
            "ECN 발의와 PPAP 설계 서류 작성이 핵심입니다."
        ),
    ),
    "금형생산팀": DepartmentProfile(
        name="금형생산팀",
        division="개발본부",
        core_responsibilities=[
            "프레스 금형 제작", "신공법 금형 제작",
            "전 계열사 금형 DATA 관리", "금형 유지보수 지원",
        ],
        key_systems=["CAD/CAM", "CNC", "금형 관리 시스템", "3D 스캐너"],
        frequent_collaborations=["부품개발팀", "생산기술팀", "공법계획팀"],
        answer_perspective=(
            "당신이 금형생산팀(개발본부)이니까, 이 업무에서 당신의 역할은 "
            "프레스 금형 제작과 전사 금형 데이터 관리입니다."
        ),
    ),

    # ── 관리본부 ──
    "총무인사팀": DepartmentProfile(
        name="총무인사팀",
        division="관리본부",
        core_responsibilities=[
            "직원 복리후생", "시설관리·보안", "사회 환원활동 지원",
            "채용·배치·훈련·평가·보상", "노사문화 구축",
        ],
        key_systems=["ERP 인사모듈", "근태관리 시스템", "채용 시스템"],
        frequent_collaborations=["기술교육원", "안전보건팀", "ESG경영팀"],
        answer_perspective=(
            "당신이 총무인사팀(관리본부)이니까, 이 업무에서 당신의 역할은 "
            "인사·총무 전반 관리와 직원 복리후생, 노사관계 구축입니다."
        ),
    ),
    "ESG경영팀": DepartmentProfile(
        name="ESG경영팀",
        division="관리본부",
        core_responsibilities=[
            "ESG 전략 수립·실행", "성과 평가",
            "지속가능성 추진", "탄소중립 대응", "사회공헌활동",
        ],
        key_systems=["ESG 관리 플랫폼", "탄소배출 관리 시스템"],
        frequent_collaborations=["안전보건팀", "품질경영팀", "총무인사팀"],
        answer_perspective=(
            "당신이 ESG경영팀(관리본부)이니까, 이 업무에서 당신의 역할은 "
            "ESG 전략 수립과 지속가능경영 실행입니다."
        ),
    ),
    "품질경영팀": DepartmentProfile(
        name="품질경영팀",
        division="관리본부",
        core_responsibilities=[
            "품질경영 혁신 프로젝트 기획·운영", "품질 5스타 PM",
            "내부 심사", "협력사 SQ 평가", "그룹사 품질경영 업무",
            "IATF 16949 인증 유지 관리",
        ],
        key_systems=["SQ Rating 시스템", "내부심사 관리 시스템", "ERP"],
        frequent_collaborations=["품질보증팀", "안전보건팀", "ESG경영팀"],
        answer_perspective=(
            "당신이 품질경영팀(관리본부)이니까, 이 업무에서 당신의 역할은 "
            "전사 품질경영 전략과 인증 심사 관리입니다. "
            "내부 심사, SQ Rating, 협력사 평가가 핵심입니다."
        ),
    ),
    "기술교육원": DepartmentProfile(
        name="기술교육원",
        division="관리본부",
        core_responsibilities=[
            "중소기업 직무능력 향상 교육", "전문기술인 양성",
            "고용노동부/한국산업인력공단 지원 교육",
            "안전보건교육 콘텐츠 제공",
        ],
        key_systems=["LMS(교육관리시스템)", "교육 이력 관리"],
        frequent_collaborations=["안전보건팀", "총무인사팀", "생산기술팀"],
        answer_perspective=(
            "당신이 기술교육원(관리본부)이니까, 이 업무에서 당신의 역할은 "
            "직무역량 향상 교육과 안전보건교육 운영입니다. "
            "교육 프로그램 기획과 평가가 핵심입니다."
        ),
    ),

    # ── 재경본부 ──
    "재무팀": DepartmentProfile(
        name="재무팀",
        division="재경본부",
        core_responsibilities=[
            "재무 건전성 관리", "효율적 자금 운용",
            "주주총회·이사회 운영", "투자자 관리(IR)", "자금 계획 수립",
        ],
        key_systems=["ERP 재무모듈", "자금관리 시스템", "IR 관리"],
        frequent_collaborations=["회계팀", "원가기획팀", "경영지원"],
        answer_perspective=(
            "당신이 재무팀(재경본부)이니까, 이 업무에서 당신의 역할은 "
            "재무 건전성 확보와 자금 운용 최적화입니다."
        ),
    ),
    "회계팀": DepartmentProfile(
        name="회계팀",
        division="재경본부",
        core_responsibilities=[
            "정확한 수치·분석 통한 경영 의사결정 지원",
            "세무 신고·관리", "결산·재무제표 작성", "원가 회계",
        ],
        key_systems=["ERP 회계모듈", "세무 시스템", "전표 관리"],
        frequent_collaborations=["재무팀", "원가기획팀", "구매팀"],
        answer_perspective=(
            "당신이 회계팀(재경본부)이니까, 이 업무에서 당신의 역할은 "
            "정확한 회계 처리와 경영 분석 데이터 제공입니다."
        ),
    ),
    "IT전략팀": DepartmentProfile(
        name="IT전략팀",
        division="재경본부",
        core_responsibilities=[
            "디지털 혁신", "사내 시스템 운영·개선",
            "중장기 IT 로드맵", "신기술 도입 검토",
            "전사 IT 거버넌스",
        ],
        key_systems=["ERP", "MES", "서버 인프라", "보안 시스템", "AI 플랫폼"],
        frequent_collaborations=["자동화기술팀", "비전연구팀", "전장선행개발팀", "품질보증팀"],
        answer_perspective=(
            "당신이 IT전략팀(재경본부)이니까, 이 업무에서 당신의 역할은 "
            "IT 시스템 관점의 의사결정과 기술 인프라 지원입니다. "
            "AI 도입, 시스템 통합, 보안이 핵심입니다."
        ),
    ),

    "원가기획팀": DepartmentProfile(
        name="원가기획팀",
        division="재경본부",
        core_responsibilities=[
            "제품 개발~양산 수익성 검토", "원가요소 분석·검토",
            "투자비 목표설정", "수익 극대화 기획",
        ],
        key_systems=["ERP 원가모듈", "원가 분석 시스템"],
        frequent_collaborations=["재무팀", "기술영업팀", "구매팀"],
        answer_perspective=(
            "당신이 원가기획팀(재경본부)이니까, 이 업무에서 당신의 역할은 "
            "제품 원가 분석과 수익성 확보입니다."
        ),
    ),

    # ── 구매본부 ──
    "구매팀": DepartmentProfile(
        name="구매팀",
        division="구매본부",
        core_responsibilities=[
            "최적 협력사 발굴 및 협업", "원가절감",
            "공급망 관리", "협력사 이메일·서신 관리",
        ],
        key_systems=["ERP 구매모듈", "협력사 관리 시스템", "EDI"],
        frequent_collaborations=["품질보증팀", "상생협력팀", "자재관리팀"],
        answer_perspective=(
            "당신이 구매팀(구매본부)이니까, 이 업무에서 당신의 역할은 "
            "협력사 관리와 원가 최적화입니다. "
            "품질·납기·가격 기반의 협력사 평가가 핵심입니다."
        ),
    ),
    "해외지원팀": DepartmentProfile(
        name="해외지원팀",
        division="구매본부",
        core_responsibilities=[
            "수출입 통관", "KD 부품 수급관리", "AEO 공인관리",
            "FTA 원산지관리", "관세환급", "해외사업 무역 실무",
        ],
        key_systems=["통관 시스템", "FTA 관리 시스템", "ERP 무역모듈"],
        frequent_collaborations=["구매팀", "영업팀", "자재관리팀"],
        answer_perspective=(
            "당신이 해외지원팀(구매본부)이니까, 이 업무에서 당신의 역할은 "
            "수출입 통관, FTA 원산지, AEO 관리 등 무역 실무입니다."
        ),
    ),
    "상생협력팀": DepartmentProfile(
        name="상생협력팀",
        division="구매본부",
        core_responsibilities=[
            "협력사 품질·납품·경영 다방면 지원",
            "지속 가능한 파트너십 구축", "동반성장 프로그램 운영",
        ],
        key_systems=["협력사 관리 시스템", "동반성장 포털"],
        frequent_collaborations=["구매팀", "품질보증팀", "품질경영팀"],
        answer_perspective=(
            "당신이 상생협력팀(구매본부)이니까, 이 업무에서 당신의 역할은 "
            "협력사 동반성장과 지속 가능한 공급망 구축입니다."
        ),
    ),

    # ── 독립 부서 ──
    "내부감사팀": DepartmentProfile(
        name="내부감사팀",
        division="(독립)",
        core_responsibilities=[
            "업무·프로세스 효율성·투명성 확인",
            "문제점·리스크 분석", "개선 권고 제공",
            "내부 감사 실시", "준법 점검",
        ],
        key_systems=["감사 관리 시스템", "ERP"],
        frequent_collaborations=["품질경영팀", "재무팀", "총무인사팀"],
        answer_perspective=(
            "당신이 내부감사팀이니까, 이 업무에서 당신의 역할은 "
            "조직 운영의 투명성 확보와 리스크 관리입니다."
        ),
    ),

    # ── 기술연구소 ──
    "기술연구소": DepartmentProfile(
        name="기술연구소",
        division="기술연구소",
        core_responsibilities=[
            "바디선행개발 (신소재·신공법 연구)",
            "전장선행개발 (전동화, 열관리, AI 안전시스템)",
            "미래 모빌리티 기술 경쟁력 확보",
        ],
        key_systems=["CAD/CAE", "시뮬레이션 장비", "시험 설비", "AI 연구 플랫폼"],
        frequent_collaborations=["생산기술팀", "부품개발팀", "자동화기술팀", "비전연구팀"],
        answer_perspective=(
            "당신이 기술연구소이니까, 이 업무에서 당신의 역할은 "
            "선행 기술 연구와 미래 제품 개발입니다. "
            "신소재·신공법 적용과 전동화 기술이 핵심입니다."
        ),
    ),
    "바디선행개발팀": DepartmentProfile(
        name="바디선행개발팀",
        division="기술연구소",
        core_responsibilities=[
            "신소재·신공법 적용 핵심 부품 개발",
            "미래 모빌리티 차체 기술 경쟁력 확보 연구",
            "경량화 소재(CFRP, 알루미늄, 핫스탬핑) 연구",
        ],
        key_systems=["CAD/CAE", "시험 설비", "시뮬레이션 장비"],
        frequent_collaborations=["전장선행개발팀", "제품설계팀", "부품개발팀"],
        answer_perspective=(
            "당신이 바디선행개발팀(기술연구소)이니까, 이 업무에서 당신의 역할은 "
            "신소재·신공법 기반의 차체 선행 개발입니다."
        ),
    ),
    "전장선행개발팀": DepartmentProfile(
        name="전장선행개발팀",
        division="기술연구소",
        core_responsibilities=[
            "전동화 부품 연구 (EWP, CCH)", "열관리 시스템 개발",
            "AI 기반 공장 안전시스템 연구",
            "미래차·스마트팩토리 융합 기술 선도",
        ],
        key_systems=["전장 시뮬레이터", "AI 연구 플랫폼", "열해석 소프트웨어"],
        frequent_collaborations=["바디선행개발팀", "자동화기술팀", "비전연구팀", "IT전략팀"],
        answer_perspective=(
            "당신이 전장선행개발팀(기술연구소)이니까, 이 업무에서 당신의 역할은 "
            "전동화·열관리·AI 안전시스템의 선행 연구입니다."
        ),
    ),
}

# 레거시 호환: 기존 "품질관리팀" → "품질보증팀"으로 매핑
_LEGACY_MAP = {
    "품질관리팀": "품질보증팀",
    "연구소": "기술연구소",
}

# v3.3: 외부에서 참조할 수 있도록 public alias 제공
DEPARTMENT_ALIASES = _LEGACY_MAP


class DepartmentRouter:
    """부서별 맞춤 응답을 위한 라우터"""

    def get_profile(self, department: str) -> DepartmentProfile | None:
        """부서 프로필을 반환한다."""
        dept = _LEGACY_MAP.get(department, department)
        return DEPARTMENT_PROFILES.get(dept)

    def get_perspective(self, department: str) -> str:
        """부서별 응답 관점 문구를 반환한다."""
        profile = self.get_profile(department)
        if profile:
            return profile.answer_perspective
        return "일반 직원으로서 이 업무를 이해하면 됩니다."

    def get_department_context(self, department: str) -> str:
        """LLM 프롬프트에 삽입할 부서 컨텍스트를 생성한다."""
        profile = self.get_profile(department)
        if not profile:
            return "부서 정보가 설정되지 않았습니다."

        lines = [
            f"[사용자 부서: {profile.name} ({profile.division})]",
            f"주요 업무: {', '.join(profile.core_responsibilities)}",
            f"사용 시스템: {', '.join(profile.key_systems)}",
            f"주요 협업 부서: {', '.join(profile.frequent_collaborations)}",
            f"응답 관점: {profile.answer_perspective}",
        ]
        return "\n".join(lines)

    @property
    def available_departments(self) -> list[str]:
        return list(DEPARTMENT_PROFILES.keys())
