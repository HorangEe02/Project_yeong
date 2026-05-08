"""
SOP(표준작업절차서) 단계별 가이드 엔진
- 6종 SOP를 구조화된 단계별 데이터로 관리
- Streamlit UI용 단계 네비게이션 제공
- 각 단계별 체크리스트 + 주의사항 + 관련 용어
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class SOPStep:
    """SOP 개별 단계"""
    step_number: int
    title: str
    description: str
    checklist: List[str] = field(default_factory=list)
    caution: str = ""
    related_terms: List[str] = field(default_factory=list)
    estimated_time: str = ""
    responsible: str = ""


@dataclass
class SOPDocument:
    """SOP 문서 전체"""
    sop_id: str
    title: str
    department: str
    category: str          # "설비", "품질", "안전", "생산"
    steps: List[SOPStep] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)
    related_sops: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# SOP 데이터 정의 (6종)
# ──────────────────────────────────────────────

SOP_DATABASE: Dict[str, SOPDocument] = {
    "SOP-001": SOPDocument(
        sop_id="SOP-001",
        title="프레스 금형 교체 절차",
        department="금형생산팀",
        category="설비",
        prerequisites=["교체 금형 사전 점검 완료", "크레인 운전 자격 보유", "안전장구 착용"],
        safety_warnings=["금형 중량물 취급 -- 크레인/호이스트 필수", "프레스 잔압 확인 후 작업", "상/하형 분리 시 핀 위치 확인"],
        steps=[
            SOPStep(1, "생산 중지 및 안전 조치",
                    "프레스 운전 정지 -> 메인 전원 OFF -> 잔압 확인 -> 안전 블록 삽입",
                    checklist=["프레스 정지 확인", "메인 전원 OFF", "잔압 0 확인", "안전 블록 삽입"],
                    caution="잔압이 남아있으면 슬라이드 낙하 위험",
                    related_terms=["잔압", "안전블록", "슬라이드"], estimated_time="5분"),
            SOPStep(2, "기존 금형 분리",
                    "클램프 해제 -> 유압/공압 라인 분리 -> 상형 크레인 체결 -> 상형 인양 -> 하형 인출",
                    checklist=["클램프 전수 해제", "유압라인 분리", "크레인 와이어 체결 확인", "상형 인양 완료"],
                    caution="인양 시 하부 작업자 퇴피 확인",
                    related_terms=["클램프", "크레인", "인양"], estimated_time="15분"),
            SOPStep(3, "볼스터/슬라이드 청소",
                    "금형 설치면 이물 제거 -> 볼스터 상면 청소 -> T홈 확인",
                    checklist=["이물 제거 완료", "볼스터 상면 청소", "T홈 손상 없음"],
                    estimated_time="10분"),
            SOPStep(4, "신규 금형 설치",
                    "하형 볼스터 진입 -> 기준핀 정렬 -> 하형 클램핑 -> 상형 크레인 인양 -> 상형 정렬 -> 상형 클램핑",
                    checklist=["기준핀 정렬 완료", "하형 클램핑 완료", "상형 정렬 완료", "상형 클램핑 완료", "유압/공압 라인 연결"],
                    caution="기준핀 미정렬 시 금형 파손 위험",
                    related_terms=["볼스터", "클램핑", "기준핀"], estimated_time="20분"),
            SOPStep(5, "시운전 및 초품 검사",
                    "저속 1회 운전 -> 상하사점 확인 -> 초품 생산 3매 -> 치수 측정 -> OK 판정",
                    checklist=["저속 시운전 완료", "상하사점 정상", "초품 3매 생산", "치수 검사 합격"],
                    caution="초품 NG 시 금형 재조정 필요",
                    related_terms=["초품", "치수검사", "상하사점"], estimated_time="15분"),
            SOPStep(6, "양산 개시 및 기록",
                    "자동 운전 전환 -> SPM 설정 -> 생산 일보 기록 -> 금형 이력 카드 업데이트",
                    checklist=["자동 운전 전환", "SPM 설정 완료", "생산 일보 기록", "금형 이력 카드 업데이트"],
                    related_terms=["SPM", "생산일보", "금형이력카드"], estimated_time="5분"),
        ],
    ),
    "SOP-002": SOPDocument(
        sop_id="SOP-002",
        title="용접 너겟 품질 검사 절차",
        department="품질보증팀",
        category="품질",
        prerequisites=["AWIS 시스템 가동 확인", "검사 기준서 확인"],
        safety_warnings=["용접 직후 고온 주의", "초음파 검사 장비 취급 주의"],
        steps=[
            SOPStep(1, "검사 대상 선정",
                    "생산 로트별 샘플링 기준에 따라 검사 대상 선정 -> 검사 기준서 확인",
                    checklist=["샘플링 기준 확인", "검사 기준서 준비"],
                    related_terms=["샘플링", "검사기준서"], estimated_time="3분"),
            SOPStep(2, "외관 검사",
                    "용접 비드/너겟 외관 육안 확인 -> 스패터/기공/언더컷 유무 -> 판정 기록",
                    checklist=["스패터 확인", "기공 유무", "언더컷 유무", "외관 판정 기록"],
                    related_terms=["스패터", "기공", "언더컷", "너겟"], estimated_time="5분"),
            SOPStep(3, "너겟 직경 측정",
                    "피일 테스트 또는 초음파 검사 -> 너겟 직경 측정 -> 기준 대비 합부 판정",
                    checklist=["너겟 직경 측정", "기준값 대비 판정", "데이터 기록"],
                    caution="최소 너겟 직경 미달 시 전수 검사 전환",
                    related_terms=["피일테스트", "초음파검사", "너겟직경"], estimated_time="10분"),
            SOPStep(4, "결과 기록 및 보고",
                    "검사 데이터 SPC 입력 -> Cpk 자동 계산 -> 이상 시 8D 보고서 개시",
                    checklist=["SPC 데이터 입력", "Cpk 확인", "이상 시 8D 개시"],
                    related_terms=["SPC", "Cpk", "8D"], estimated_time="5분"),
        ],
    ),
    "SOP-003": SOPDocument(
        sop_id="SOP-003",
        title="EWP 하우징 CNC 가공 절차",
        department="생산기술본부",
        category="생산",
        prerequisites=["NC 프로그램 로딩 완료", "공구 마모도 확인", "소재 입고 검사 합격"],
        safety_warnings=["회전체 접근 금지", "칩 비산 보호구 착용", "절삭유 피부 접촉 주의"],
        steps=[
            SOPStep(1, "소재 세팅",
                    "소재 바이스 고정 -> 원점 설정 -> 공구 오프셋 확인",
                    checklist=["바이스 클램핑 확인", "원점 설정 완료", "공구 오프셋 확인"],
                    related_terms=["바이스", "원점", "공구오프셋"], estimated_time="5분"),
            SOPStep(2, "황삭 가공",
                    "NC 프로그램 실행 -> 황삭 가공 -> 칩 배출 확인 -> 중간 치수 확인",
                    checklist=["황삭 프로그램 실행", "칩 배출 정상", "중간 치수 OK"],
                    related_terms=["황삭", "NC프로그램"], estimated_time="15분"),
            SOPStep(3, "정삭 가공",
                    "공구 교환 -> 정삭 프로그램 실행 -> 표면 조도 확인",
                    checklist=["정삭 공구 장착", "정삭 완료", "표면 조도 Ra 확인"],
                    caution="공구 마모 시 표면 조도 불량 발생",
                    related_terms=["정삭", "표면조도", "Ra"], estimated_time="20분"),
            SOPStep(4, "세척 및 검사",
                    "절삭유 세척 -> 버 제거 -> CMM 치수 측정 -> 합부 판정",
                    checklist=["세척 완료", "버 제거 완료", "CMM 측정 합격", "검사 성적서 발행"],
                    related_terms=["CMM", "버", "검사성적서"], estimated_time="10분"),
        ],
    ),

    # ── v3.4: 업무 프로세스 SOP 5종 추가 ──

    "SOP-PPAP": SOPDocument(
        sop_id="SOP-PPAP",
        title="PPAP(생산부품승인절차) 진행",
        department="부품개발팀",
        category="품질",
        prerequisites=["도면/사양서 접수 완료", "양산 금형 제작 완료", "측정 장비 교정 완료"],
        safety_warnings=["시작품은 반드시 양산 라인에서 제작 — 별도 라인 사용 시 SQ 미인정"],
        related_sops=["SOP-ECN"],
        steps=[
            SOPStep(1, "설계 도면 및 사양서 접수",
                    "완성차로부터 도면(2D/3D), 사양서, ECR/ECN 접수. 도면 번호·리비전·소재 규격 확인.",
                    checklist=["도면 번호 및 리비전 확인", "소재 규격(SPFC, SAPH 등) 확인", "변경 이력(ECR/ECN) 기록", "관련 부서에 도면 배포"],
                    caution="도면 리비전이 최신인지 반드시 확인 — 구 리비전 진행 시 전체 재작업",
                    related_terms=["ECR", "ECN", "리비전"], estimated_time="1일"),
            SOPStep(2, "공정 FMEA 작성",
                    "생산기술팀 주관, 각 공정별 잠재 고장모드·영향·원인 분석, RPN 산출.",
                    checklist=["공정 흐름도 최신화", "잠재 고장모드 식별", "심각도(S)×발생도(O)×검출도(D)=RPN 계산", "RPN 100 이상 개선 계획 수립"],
                    caution="FMEA는 Control Plan과 반드시 연동 — 항목 불일치 시 SQ 반려",
                    related_terms=["FMEA", "RPN", "고장모드"], estimated_time="3~5일", responsible="생산기술팀"),
            SOPStep(3, "관리계획서(Control Plan) 작성",
                    "품질보증팀 주관. FMEA 관리 항목을 공정별 정리, 측정 방법·빈도·반응 계획 명시.",
                    checklist=["FMEA 주요 항목 전수 반영", "측정 방법·게이지 번호 기재", "샘플링 주기 명시", "이상 시 반응 계획 기재"],
                    caution="Control Plan과 FMEA 항목 1:1 미매핑 → 승인 반려 사유",
                    related_terms=["Control Plan", "측정시스템", "게이지"], estimated_time="2~3일", responsible="품질보증팀"),
            SOPStep(4, "시작품 제작 및 치수 측정",
                    "양산 금형/설비로 시작품 제작, 도면 공차 기준 측정 수행.",
                    checklist=["양산 조건과 동일 조건으로 제작", "CMM/게이지로 주요 치수 측정", "측정 데이터 기록(Balloon Drawing 대비)", "외관 검사(크랙, 주름, 스프링백)"],
                    caution="양산 라인에서 제작 필수 — 시작 금형/별도 라인 SQ 미인정",
                    related_terms=["CMM", "시작품", "Balloon Drawing"], estimated_time="2~3일"),
            SOPStep(5, "PPAP 서류 패키지 구성 및 제출",
                    "PPAP 18개 항목(레벨 따라 일부 생략 가능) 패키지 구성하여 SQ 제출.",
                    checklist=["PSW 작성", "치수 측정 결과 첨부", "재료 시험 성적서 첨부", "공정 FMEA+CP+Flow 첨부", "MSA 결과 첨부", "SPC 초기 Cpk 첨부"],
                    caution="현대차 SQ: 제출 후 10영업일 내 회신, 2회 반려 시 긴급 회의 소집",
                    related_terms=["PSW", "MSA", "Cpk"], estimated_time="1~2일"),
        ],
    ),

    "SOP-8D": SOPDocument(
        sop_id="SOP-8D",
        title="8D Report 작성 (고객 클레임 대응)",
        department="품질보증팀",
        category="품질",
        prerequisites=["클레임 접수 완료", "불량 샘플 확보"],
        safety_warnings=["접수 당일 내로 팀 구성 완료", "잠정 조치 24시간 이내 실행"],
        related_sops=["SOP-PPAP"],
        steps=[
            SOPStep(1, "D1: 팀 구성",
                    "클레임 내용 파악 후 대응팀 구성. 품질+생산기술+해당 공정 담당자 포함.",
                    checklist=["클레임 접수 내용 확인(부품명, 불량, 수량, 로트)", "팀 리더 지정(품질보증팀 과장급)", "관련 부서 담당자 소집"],
                    caution="접수 당일 내로 팀 구성 완료",
                    estimated_time="당일"),
            SOPStep(2, "D2: 문제 기술",
                    "불량 현상을 5W2H 기준으로 정확히 기술.",
                    checklist=["불량 부위 사진 첨부", "불량 현상 수치 포함 서술", "발생 빈도·영향 범위 파악", "해당 로트 생산 일시/설비/작업자 확인"],
                    related_terms=["5W2H", "로트"], estimated_time="반일"),
            SOPStep(3, "D3: 잠정 조치",
                    "추가 불량 유출 방지 위한 즉각 격리/선별/교체 조치.",
                    checklist=["라인 내 재고+납품 대기분 전수 선별", "불량품 격리(적색 태그)", "대체품 긴급 납품 계획", "잠정 조치 SQ에 즉시 보고"],
                    caution="잠정 조치는 접수 후 24시간 이내 실행 및 보고",
                    estimated_time="24시간 이내"),
            SOPStep(4, "D4~D5: 근본 원인 분석 + 영구 대책",
                    "4M, 5-Why, FTA 등으로 근본 원인 규명, 재발 방지 영구 대책 수립.",
                    checklist=["4M(Man/Machine/Material/Method) 분석", "5-Why로 근본 원인 도달", "영구 대책 수립(설비개선/금형수정/검사강화)", "대책 실행 일정·담당자 명시"],
                    caution="'작업자 부주의'로 종결하면 SQ 반려 — 시스템적 원인 필수",
                    related_terms=["4M", "5-Why", "FTA"], estimated_time="2~3일"),
            SOPStep(5, "D6~D8: 대책 실행 + 효과 검증 + 종결",
                    "영구 대책 실행, 효과 검증(SPC/Cpk), 표준화 후 종결.",
                    checklist=["대책 실행 전후 비교 데이터 확보", "Cpk 개선 데이터 첨부", "SOP/CP/FMEA 업데이트", "유사 공정 수평 전개", "최종 8D Report SQ 제출"],
                    caution="현대차 기준: 접수 후 5영업일 이내 최종 보고",
                    related_terms=["Cpk", "수평전개", "표준화"], estimated_time="1~2일"),
        ],
    ),

    "SOP-ECN": SOPDocument(
        sop_id="SOP-ECN",
        title="ECN(설계변경통보) 접수 및 대응",
        department="부품개발팀",
        category="품질",
        prerequisites=["ECN 문서 접수 완료"],
        safety_warnings=["적용 시점 놓치면 불일치 부품 납품 → 클레임 직결"],
        related_sops=["SOP-PPAP"],
        steps=[
            SOPStep(1, "ECN 접수 및 영향 범위 파악",
                    "ECN 문서 접수 후 변경 내용(치수/소재/공법)과 적용 시점 파악.",
                    checklist=["ECN 번호, 적용 차종/부품 확인", "변경 내용(도면 변경점) 파악", "적용 시점(즉시/재고 소진 후) 확인", "영향 부서 목록 정리"],
                    caution="적용 시점 놓치면 불일치 부품 납품 → 클레임 직결",
                    related_terms=["ECN", "리비전", "적용 시점"], estimated_time="1일"),
            SOPStep(2, "금형/설비 변경 검토",
                    "금형 수정/신규 제작 필요 여부, 설비 조건 변경 필요 여부 검토.",
                    checklist=["금형 수정 필요 여부·소요 기간 확인", "설비 파라미터 변경 필요 여부", "시작품 제작 일정 수립", "비용 발생 시 견적·청구 절차 확인"],
                    related_terms=["금형 수정", "설비 조건"], estimated_time="2~3일", responsible="생산기술팀"),
            SOPStep(3, "변경 후 품질 검증 및 승인",
                    "변경 부품 치수/외관/기능 검증 후 PPAP 재제출 여부 결정.",
                    checklist=["변경 부위 치수 측정·도면 대비 확인", "PPAP 레벨 확인(전체/부분)", "CP/FMEA 업데이트", "SQ 승인 후 양산 전환"],
                    caution="Level 3 이상 변경은 반드시 PPAP 전체 재제출",
                    related_terms=["PPAP", "Control Plan"], estimated_time="3~5일"),
        ],
    ),

    "SOP-PRESS-TRIAL": SOPDocument(
        sop_id="SOP-PRESS-TRIAL",
        title="프레스 트라이(시타) 참관 준비",
        department="생산기술팀",
        category="생산",
        prerequisites=["해당 부품 도면 준비", "금형 정보 확인"],
        safety_warnings=["안전 장구 미착용 시 작업장 출입 불가 — 산안법 위반", "가동 중 프레스에 절대 손 넣지 말 것 — 안전거리 준수"],
        steps=[
            SOPStep(1, "사전 준비",
                    "트라이 전날까지 부품 도면, 금형 정보, 프레스 조건표 확인.",
                    checklist=["부품 도면 출력/태블릿 준비", "금형 번호·공정 수 확인", "이전 트라이 기록 확인(있으면)", "필기구+카메라(불량 사진용) 준비"],
                    related_terms=["금형 번호", "프레스 조건표"], estimated_time="30분"),
            SOPStep(2, "안전 장구 착용",
                    "프레스 작업장 진입 전 반드시 안전 장구 착용.",
                    checklist=["안전모 착용", "안전화 착용", "귀마개 착용(프레스 소음 80dB 이상)", "안전 조끼 착용(방문자 표시)"],
                    caution="안전 장구 미착용 시 작업장 출입 불가 — 산안법 위반",
                    related_terms=["PPE", "산안법"], estimated_time="5분"),
            SOPStep(3, "트라이 중 관찰 포인트",
                    "프레스 가동 중 소리, 성형성, 제품 상태 관찰·기록.",
                    checklist=["프레스 타격음 일정한지 확인", "성형 제품 크랙/주름/스프링백 확인", "소재 이송(피더) 원활한지 확인", "쿠션 압력계 수치 기록", "생산 속도(SPM) 기록"],
                    caution="가동 중 프레스에 절대 손 넣지 않기 — 안전거리 준수",
                    related_terms=["SPM", "스프링백", "쿠션압"], estimated_time="1~2시간"),
            SOPStep(4, "트라이 후 데이터 기록",
                    "결과 정리 및 관련 부서에 공유.",
                    checklist=["최종 프레스 조건(톤수, SPM, 쿠션압) 기록", "불량 시 사진+유형+발생 위치 기록", "판정 결과(OK/NG/조건부 OK) 기록", "다음 트라이/양산 전환 일정 확인"],
                    related_terms=["트라이 판정", "프레스 조건"], estimated_time="30분"),
        ],
    ),

    "SOP-MOLD-RECEIVE": SOPDocument(
        sop_id="SOP-MOLD-RECEIVE",
        title="신규 금형 입고 및 검수",
        department="금형생산팀",
        category="설비",
        prerequisites=["금형 발주서 확인", "프레스 톤수 적합성 사전 확인"],
        safety_warnings=["손상 발견 시 사진 촬영 후 즉시 구매팀 통보", "초도 트라이는 반드시 저속으로 시작 — 고속 투입 시 금형 파손 위험"],
        related_sops=["SOP-001"],
        steps=[
            SOPStep(1, "외관 검수 및 서류 확인",
                    "금형 도착 시 외관 손상 확인, 납품 서류(금형 이력카드, 검수 성적서) 대조.",
                    checklist=["운송 중 손상(찍힘, 크랙) 유무 확인", "금형 번호(각인)와 납품서 대조", "금형 이력카드 수령", "가이드 핀/스프링/센서 등 부속품 확인"],
                    caution="손상 발견 시 사진 촬영 후 즉시 구매팀 통보 — 클레임 기한 준수",
                    related_terms=["금형 이력카드", "검수 성적서"], estimated_time="30분"),
            SOPStep(2, "프레스 장착 및 초도 트라이",
                    "금형을 프레스에 장착하고 저속 트라이 실시.",
                    checklist=["프레스 톤수 적합성 확인", "금형 높이(Shut Height) 세팅", "안전장치(인터록, 비상정지) 동작 확인", "저속(5~10 SPM)으로 초도 트라이", "성형 제품 외관·치수 확인"],
                    caution="초도 트라이는 반드시 저속으로 시작 — 고속 투입 시 금형 파손 위험",
                    related_terms=["Shut Height", "인터록", "SPM"], estimated_time="1~2시간"),
            SOPStep(3, "검수 판정 및 등록",
                    "검수 결과 기록, 금형 관리 시스템에 등록.",
                    checklist=["검수 판정(합격/조건부 합격/불합격) 기록", "금형 관리 대장에 등록", "예방 보전 스케줄 초기 설정", "불합격 시 수정 요청서 작성"],
                    related_terms=["금형 관리 대장", "예방 보전"], estimated_time="30분"),
        ],
    ),
}

# 키워드 -> SOP 매핑
SOP_KEYWORD_MAP = {
    "금형 교체": "SOP-001",
    "금형 세팅": "SOP-001",
    "프레스 금형": "SOP-001",
    "용접 검사": "SOP-002",
    "너겟 검사": "SOP-002",
    "품질 검사": "SOP-002",
    "CNC 가공": "SOP-003",
    "EWP 가공": "SOP-003",
    "정밀 가공": "SOP-003",
    # v3.4: 업무 프로세스 SOP 키워드
    "PPAP": "SOP-PPAP",
    "생산부품승인": "SOP-PPAP",
    "양산 승인": "SOP-PPAP",
    "8D": "SOP-8D",
    "클레임 대응": "SOP-8D",
    "시정 조치": "SOP-8D",
    "ECN": "SOP-ECN",
    "설계변경": "SOP-ECN",
    "도면 변경": "SOP-ECN",
    "프레스 트라이": "SOP-PRESS-TRIAL",
    "시타 참관": "SOP-PRESS-TRIAL",
    "트라이 준비": "SOP-PRESS-TRIAL",
    "금형 입고": "SOP-MOLD-RECEIVE",
    "금형 검수": "SOP-MOLD-RECEIVE",
    "신규 금형": "SOP-MOLD-RECEIVE",
}


def find_sop_by_query(query: str) -> Optional[SOPDocument]:
    """사용자 질문에서 관련 SOP 검색"""
    query_lower = query.lower()
    for keyword, sop_id in SOP_KEYWORD_MAP.items():
        if keyword in query_lower or keyword.replace(" ", "") in query_lower.replace(" ", ""):
            return SOP_DATABASE.get(sop_id)
    return None


def get_all_sops() -> List[SOPDocument]:
    """전체 SOP 목록"""
    return list(SOP_DATABASE.values())
