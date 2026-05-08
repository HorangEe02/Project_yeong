"""
문서 유형별 입력 필드 + LLM 프롬프트 템플릿 정의

- INTERNAL_DOC_TYPES: 내부용 문서 유형 정의
- EXTERNAL_DOC_TYPES: 외부용 문서 유형 정의
- 각 문서 유형마다: fields(입력 필드), prompt_template(LLM 프롬프트), tone, language
"""
import re


# ═══════════════════════════════════════════════════════
# 내부용 문서 유형
# ═══════════════════════════════════════════════════════
INTERNAL_DOC_TYPES = {
    "사내 이메일": {
        "icon": "✉️",
        "description": "사내 부서 간 업무 이메일",
        "tone": "semi_formal",
        "language": "ko",
        "fields": [
            {"key": "recipient",   "label": "수신자 (부서/이름)",  "type": "text",     "required": True,  "placeholder": "품질관리팀 홍길동 과장님"},
            {"key": "subject",     "label": "제목",               "type": "text",     "required": True,  "placeholder": "○○ 관련 협조 요청의 건"},
            {"key": "sender",      "label": "발신자",             "type": "text",     "required": True,  "placeholder": "생산기술팀 김철수 대리"},
            {"key": "cc",          "label": "CC (참조)",          "type": "text",     "required": False, "placeholder": "관련 부서/담당자"},
            {"key": "body_hint",   "label": "요청사항 / 본문 내용", "type": "textarea", "required": True,  "placeholder": "이메일에 담을 핵심 내용을 간략히 입력하세요"},
        ],
        "prompt_template": """당신은 아진산업의 사내 이메일 작성 전문가입니다. 사내 이메일을 작성하세요.

수신: {recipient}
제목: {subject}
발신: {sender}
{cc_line}

요청 내용:
{body_hint}

작성 규칙:
- 정중한 사내 존댓말 사용 (○○님, ~드립니다)
- 불필요한 인사말 최소화, 핵심부터 전달
- 마무리: "검토 부탁드립니다" 또는 "회신 부탁드립니다"
- 서명: {sender}
- [여기에 내용 입력], OOO 같은 placeholder를 절대 사용하지 마세요
- 완성된 이메일을 작성하세요""",
    },

    "회의록": {
        "icon": "📋",
        "description": "사내 회의록 표준 양식",
        "tone": "semi_formal",
        "language": "ko",
        "fields": [
            {"key": "meeting_title", "label": "회의명",         "type": "text",     "required": True,  "placeholder": "2026 Q2 품질 검토 회의"},
            {"key": "date",          "label": "일시",           "type": "text",     "required": True,  "placeholder": "2026-04-15 14:00~15:30"},
            {"key": "location",      "label": "장소",           "type": "text",     "required": False, "placeholder": "본사 3층 대회의실"},
            {"key": "attendees",     "label": "참석자",         "type": "textarea", "required": True,  "placeholder": "홍길동(품질), 김영희(생산기술), 박민수(연구소)"},
            {"key": "agenda",        "label": "안건 (주제)",     "type": "textarea", "required": True,  "placeholder": "1. Q1 품질 실적 검토\n2. 클레임 감소 방안\n3. Q2 목표 설정"},
            {"key": "context_hint",  "label": "논의 내용 / 배경", "type": "textarea", "required": False, "placeholder": "주요 논의 사항이나 배경을 입력하면 회의록에 반영됩니다"},
        ],
        "prompt_template": """당신은 아진산업의 회의록 작성 전문가입니다. 회의록을 작성하세요.

■ 회의명: {meeting_title}
■ 일시: {date}
■ 장소: {location}
■ 참석자: {attendees}

■ 안건:
{agenda}

{context_section}

작성 규칙:
- 안건별로 "논의 내용 → 결정사항 → 후속조치(담당자/기한)" 구조로 작성
- 결정되지 않은 사항은 "추후 검토"로 명시
- 문체: 간결한 개조식 (~함, ~하기로 함)
- 마지막에 "차기 회의: [미정]" 포함
- placeholder를 절대 사용하지 마세요. 모든 내용을 구체적으로 작성하세요""",
    },

    # ─── Plan v1.0 — 누락된 INTERNAL 5종 복원 (canonical Draft.jsx 13종 정합) ───

    "주간 보고": {
        "icon": "📊",
        "description": "팀/개인 주간 업무 실적 및 차주 계획 보고",
        "tone": "semi_formal",
        "language": "ko",
        "fields": [
            {"key": "reporter",       "label": "보고자 (이름/부서)",   "type": "text",     "required": True,  "placeholder": "품질관리팀 박품질 대리"},
            {"key": "week",           "label": "보고 주차 / 기간",      "type": "text",     "required": True,  "placeholder": "2026년 17주차 (4/22~4/28)"},
            {"key": "this_week",      "label": "금주 실적",            "type": "textarea", "required": True,  "placeholder": "1. EMP 워터펌프 SPC 모니터링 (Cpk 1.42)\n2. PPAP Level 3 제출\n3. 8D-2026-005 D4 진행"},
            {"key": "next_week",      "label": "차주 계획",            "type": "textarea", "required": True,  "placeholder": "1. CCH 신모델 양산 검증\n2. 협력사 정기 감사 2건"},
            {"key": "issues",         "label": "이슈/지원 요청",        "type": "textarea", "required": False, "placeholder": "금형 보수 일정 1주 지연 → 영업팀 납기 협의 필요"},
        ],
        "prompt_template": """당신은 아진산업의 주간 업무 보고서 작성 전문가입니다. 주간 보고서를 작성하세요.

■ 보고자: {reporter}
■ 보고 주차: {week}

■ 금주 실적:
{this_week}

■ 차주 계획:
{next_week}

{issues_section}

작성 규칙:
- 섹션 구조: "1. 금주 실적 → 2. 차주 계획 → 3. 이슈/지원 요청"
- 정량 지표(수치/일정) 우선, 추상적 표현 지양
- 문체: 간결한 개조식 (~함, ~예정, ~완료)
- 이슈가 있는 경우 담당자/지원 요청 사항을 명시
- placeholder를 절대 사용하지 마세요""",
    },

    "휴가 신청서": {
        "icon": "🏖️",
        "description": "연차/반차/특별 휴가 신청서",
        "tone": "formal",
        "language": "ko",
        "fields": [
            {"key": "applicant",   "label": "신청자",             "type": "text",     "required": True,  "placeholder": "품질관리팀 박품질 대리"},
            {"key": "leave_type",  "label": "휴가 종류",           "type": "select",   "required": True,  "options": ["연차", "반차(오전)", "반차(오후)", "특별 휴가", "병가", "경조사"]},
            {"key": "start_date",  "label": "시작일",             "type": "text",     "required": True,  "placeholder": "2026-05-02"},
            {"key": "end_date",    "label": "종료일",             "type": "text",     "required": True,  "placeholder": "2026-05-04"},
            {"key": "reason",      "label": "사유",               "type": "textarea", "required": True,  "placeholder": "가족 행사 참석"},
            {"key": "handover",    "label": "업무 인수인계",        "type": "textarea", "required": False, "placeholder": "긴급 SPC 관제: 김생산 사원 / 8D 회의 대리참석: 이품질 사원"},
        ],
        "prompt_template": """당신은 아진산업의 인사 행정 문서 작성 전문가입니다. 휴가 신청서를 작성하세요.

■ 신청자: {applicant}
■ 휴가 종류: {leave_type}
■ 기간: {start_date} ~ {end_date}
■ 사유: {reason}

{handover_section}

작성 규칙:
- 양식 구조:
  1. 제목: "휴가 신청서"
  2. 신청자 / 부서 / 직급 명시
  3. 휴가 종류 / 기간 / 사유
  4. 업무 인수인계 (담당자 명시)
  5. 결재란: 신청자 / 팀장 / 부서장
- 사유는 정중하고 구체적으로 (1~2문장)
- 마지막에 "위와 같이 휴가를 신청하오니 승인하여 주시기 바랍니다." 포함
- placeholder 사용 금지""",
    },

    "견적서": {
        "icon": "💰",
        "description": "고객사 대상 부품/서비스 견적서",
        "tone": "formal",
        "language": "ko",
        "fields": [
            {"key": "customer",     "label": "고객사",             "type": "text",     "required": True,  "placeholder": "현대자동차 구매팀"},
            {"key": "quote_no",     "label": "견적번호",           "type": "text",     "required": True,  "placeholder": "AJ-Q-2026-0042"},
            {"key": "issue_date",   "label": "발행일",             "type": "text",     "required": True,  "placeholder": "2026-04-28"},
            {"key": "items",        "label": "품목 (품명/품번/수량/단가)", "type": "textarea", "required": True,  "placeholder": "A-Panel / AJ-AP-001 / 5,000 EA / 12,500원\nB-Pillar / AJ-BP-002 / 3,000 EA / 18,200원"},
            {"key": "validity",     "label": "유효기간",           "type": "text",     "required": False, "placeholder": "발행일로부터 30일"},
            {"key": "remarks",      "label": "특이사항",           "type": "textarea", "required": False, "placeholder": "VAT 별도 / 운송비 포함 / 결제: 60일 어음"},
        ],
        "prompt_template": """당신은 아진산업의 영업 견적서 작성 전문가입니다. 견적서를 작성하세요.

■ 고객사: {customer}
■ 견적번호: {quote_no}
■ 발행일: {issue_date}

■ 품목:
{items}

{validity_section}
{remarks_section}

작성 규칙:
- 양식 구조:
  1. 상단: 회사명/주소/연락처/담당자 (아진산업(주))
  2. 견적번호 + 발행일 + 고객사
  3. 품목 표 (품명 | 품번 | 수량 | 단가 | 금액 | 비고) — 마크다운 표
  4. 합계 (공급가액 / VAT / 총액)
  5. 유효기간 + 결제조건
  6. 하단 서명/직인 영역
- 단위는 "원" + 천 단위 콤마
- 합계는 자동 계산하여 명시
- placeholder 사용 금지""",
    },

    "출장 보고서": {
        "icon": "🚗",
        "description": "출장 종료 후 결과/소요 비용 보고서",
        "tone": "semi_formal",
        "language": "ko",
        "fields": [
            {"key": "reporter",     "label": "출장자",             "type": "text",     "required": True,  "placeholder": "생산기술팀 김생산 과장"},
            {"key": "destination",  "label": "출장지",             "type": "text",     "required": True,  "placeholder": "현대자동차 울산공장 5라인"},
            {"key": "period",       "label": "출장 기간",          "type": "text",     "required": True,  "placeholder": "2026-04-22 ~ 2026-04-23 (1박 2일)"},
            {"key": "purpose",      "label": "출장 목적",          "type": "textarea", "required": True,  "placeholder": "A-Panel 품질 이슈 현장 확인 및 시정 조치 협의"},
            {"key": "result",       "label": "주요 결과",          "type": "textarea", "required": True,  "placeholder": "1. 도장 부스 온도 5도 하락 확인\n2. 4/30까지 시정 조치 합의\n3. 4/25 재방문 일정 확정"},
            {"key": "expense",      "label": "출장 경비 (선택)",    "type": "textarea", "required": False, "placeholder": "교통비 180,000원 / 숙박 95,000원 / 식비 60,000원 = 합계 335,000원"},
        ],
        "prompt_template": """당신은 아진산업의 출장 보고서 작성 전문가입니다. 출장 보고서를 작성하세요.

■ 출장자: {reporter}
■ 출장지: {destination}
■ 기간: {period}
■ 목적: {purpose}

■ 주요 결과:
{result}

{expense_section}

작성 규칙:
- 양식 구조:
  1. 출장자 / 출장지 / 기간 / 목적
  2. 일자별 활동 내역 (Day 1, Day 2, ...)
  3. 주요 결과 (정량 지표/합의 사항/후속 조치)
  4. 시사점 및 건의 사항
  5. 출장 경비 (있는 경우, 표 형식)
- 문체: 간결한 개조식 (~함, ~확인)
- 후속 조치는 담당자/기한 명시
- placeholder 사용 금지""",
    },

    "SPC Report": {
        "icon": "📈",
        "description": "공정능력 SPC(통계적 공정 관리) 보고서",
        "tone": "formal",
        "language": "ko",
        "fields": [
            {"key": "process",       "label": "공정명 / 부품명",       "type": "text",     "required": True,  "placeholder": "EMP 워터펌프 임펠러 가공 공정 / AJ-EMP-W100"},
            {"key": "period",        "label": "관제 기간",            "type": "text",     "required": True,  "placeholder": "2026-04-01 ~ 2026-04-28"},
            {"key": "ctq",           "label": "CTQ 항목 / 규격",       "type": "text",     "required": True,  "placeholder": "임펠러 외경 ø42.0 ± 0.05mm"},
            {"key": "cpk",           "label": "Cpk / 측정값",          "type": "text",     "required": True,  "placeholder": "Cpk=1.42 (Cp=1.55, mean=42.012, σ=0.011)"},
            {"key": "n_samples",     "label": "측정 샘플 수",          "type": "text",     "required": False, "placeholder": "n=320 (8샘플 × 40서브그룹)"},
            {"key": "findings",      "label": "주요 발견 사항",        "type": "textarea", "required": True,  "placeholder": "관리한계 이탈 0건. 4/15 이후 평균이 +0.005mm 미세 시프트 — 절삭 인서트 마모 추정. 4/30 인서트 교체 예정."},
            {"key": "actions",       "label": "조치 / 건의 사항",      "type": "textarea", "required": False, "placeholder": "1. 인서트 교체 후 30샘플 재검증\n2. 다음 분기부터 공구 수명 기반 PM 도입 검토"},
        ],
        "prompt_template": """당신은 아진산업의 SPC(통계적 공정 관리) 보고서 작성 전문가입니다. SPC Report 를 작성하세요.

■ 공정/부품: {process}
■ 관제 기간: {period}
■ CTQ 항목: {ctq}
■ 공정능력: {cpk}
■ 샘플 수: {n_samples}

■ 주요 발견 사항:
{findings}

{actions_section}

작성 규칙:
- 양식 구조:
  1. 표제 + 공정/부품 정보 (마크다운 표)
  2. 측정 데이터 요약 (Cp, Cpk, mean, σ, n)
  3. 관리도 / 능력 분석 결과 서술
  4. 이상 패턴(Nelson Rules) 검출 여부 명시
  5. 시정 조치 + 후속 일정
- Cpk ≥ 1.33 → "양호", 1.00~1.33 → "주의", < 1.00 → "부적합" 평가어 포함
- 문체: 간결한 정량 서술
- placeholder 사용 금지""",
    },
}


# ═══════════════════════════════════════════════════════
# 외부용 문서 유형
# ═══════════════════════════════════════════════════════
EXTERNAL_DOC_TYPES = {
    "이메일": {
        "icon": "✉️",
        "description": "외부 거래처 대상 공식 이메일",
        "fields": [
            {"key": "recipient_type", "label": "수신처",           "type": "select",   "required": True,  "options": ["현대/기아 (한국어)", "HMGMA (영문)", "HMGMA (국영문)", "2차 협력사", "해외법인"]},
            {"key": "recipient_name", "label": "수신자명 / 직함",   "type": "text",     "required": True,  "placeholder": "현대자동차 구매팀 ○○○ 과장님"},
            {"key": "subject",        "label": "제목",             "type": "text",     "required": True,  "placeholder": "[아진산업] ○○ 관련 회신의 건"},
            {"key": "sender",         "label": "발신자",           "type": "text",     "required": True,  "placeholder": "아진산업 ○○팀 ○○○"},
            {"key": "cc",             "label": "CC (참조)",        "type": "text",     "required": False, "placeholder": ""},
            {"key": "part_info",      "label": "부품명 / 품번",     "type": "text",     "required": False, "placeholder": "A-Panel (XXXX-XXXXX)"},
            {"key": "body_hint",      "label": "요청사항 / 본문 내용", "type": "textarea", "required": True,  "placeholder": "이메일 핵심 내용"},
        ],
        "prompt_template": """당신은 아진산업의 외부 공식 이메일 작성 전문가입니다. 이메일을 작성하세요.

수신처 유형: {recipient_type}
수신: {recipient_name}
제목: {subject}
발신: {sender}
{cc_line}
{part_line}

요청 내용:
{body_hint}

{language_instruction}
- [여기에 내용 입력], OOO 같은 placeholder를 절대 사용하지 마세요
- 완성된 이메일을 작성하세요""",
    },

    "8D Report": {
        "icon": "🔴",
        "description": "고객 클레임 원인분석 및 시정조치 보고서",
        "fields": [
            {"key": "recipient_type", "label": "수신처",            "type": "select",   "required": True,  "options": ["현대/기아", "HMGMA", "2차 협력사"]},
            {"key": "customer",       "label": "고객사 / 공장",     "type": "text",     "required": True,  "placeholder": "현대자동차 울산공장"},
            {"key": "part_name",      "label": "부품명",           "type": "text",     "required": True,  "placeholder": "EWP (전동식 워터펌프)"},
            {"key": "part_number",    "label": "품번",             "type": "text",     "required": True,  "placeholder": "26410-XXXXX"},
            {"key": "defect_desc",    "label": "불량 현상",         "type": "textarea", "required": True,  "placeholder": "조립 후 누수 발생, 시동 후 30분 내 냉각수 누출 확인"},
            {"key": "plant_line",     "label": "발생 공장 / 라인",  "type": "text",     "required": True,  "placeholder": "경산 제1공장 EWP 조립라인 #2"},
            {"key": "quantity",       "label": "발생 수량 / 불량률", "type": "text",     "required": False, "placeholder": "5EA / 1,000EA (0.5%)"},
            {"key": "lot_number",     "label": "로트 번호",         "type": "text",     "required": False, "placeholder": "LOT-2026-0401-A"},
            {"key": "emergency",      "label": "긴급 대응 조치 (D3)", "type": "textarea", "required": False, "placeholder": "전수 검사 실시, 의심 로트 출하 보류"},
            {"key": "d1_team",        "label": "D1: 팀 구성 (선택)", "type": "text",     "required": False, "placeholder": "품질관리팀, 생산기술팀, 연구소"},
        ],
        "prompt_template": """당신은 아진산업의 8D 보고서 작성 전문가입니다. 8D Report를 작성하세요.

수신: {customer} ({recipient_type})
대상 부품: {part_name} (품번: {part_number})

■ 불량 현상:
{defect_desc}

■ 발생 위치: {plant_line}
{quantity_line}
{lot_line}

{emergency_section}
{d1_section}

작성 규칙:
- D1(팀 구성) ~ D8(최종 검증) 전 항목을 순서대로 작성
- D4(근본 원인 분석): 특성요인도(어골도) 기반 4M 분석
- 톤: 정중하고 객관적, 기술적 용어 사용
- placeholder를 절대 사용하지 마세요. 모든 내용을 구체적으로 작성하세요""",
    },

    "ECN 변경통보": {
        "icon": "🔄",
        "description": "승인된 설계변경 통보 문서",
        "fields": [
            {"key": "recipient_type", "label": "수신처",          "type": "select",   "required": True,  "options": ["현대/기아", "HMGMA", "2차 협력사", "해외법인"]},
            {"key": "ecn_number",     "label": "ECN 번호",       "type": "text",     "required": True,  "placeholder": "ECN-2026-0078"},
            {"key": "part_name",      "label": "부품명",          "type": "text",     "required": True,  "placeholder": "A-Panel Reinforce"},
            {"key": "part_number",    "label": "품번",            "type": "text",     "required": True,  "placeholder": "64XXX-XXXXX"},
            {"key": "before_spec",    "label": "변경 전 사양",    "type": "textarea", "required": True,  "placeholder": "두께 1.2mm / SPCC 440"},
            {"key": "after_spec",     "label": "변경 후 사양",    "type": "textarea", "required": True,  "placeholder": "두께 1.4mm / SPCC 590"},
            {"key": "reason",         "label": "변경 사유",       "type": "textarea", "required": True,  "placeholder": "충돌 시험 결과 보강 필요"},
            {"key": "effective_date", "label": "적용 시점",       "type": "text",     "required": True,  "placeholder": "2026-06-01 (LOT-2026-0601부터)"},
            {"key": "impact_scope",   "label": "영향 범위",       "type": "text",     "required": False, "placeholder": "경산 제1공장 프레스라인, 금형 2종 수정"},
            {"key": "related_docs",   "label": "관련 문서",       "type": "text",     "required": False, "placeholder": "ECR-2026-0065, 도면번호 DWG-XXXXX"},
        ],
        "prompt_template": """당신은 아진산업의 ECN 변경통보 작성 전문가입니다. ECN 변경통보 문서를 작성하세요.

ECN 번호: {ecn_number}
수신: {recipient_type}
대상 부품: {part_name} (품번: {part_number})

■ 변경 전: {before_spec}
■ 변경 후: {after_spec}
■ 변경 사유: {reason}
■ 적용 시점: {effective_date}
{impact_line}
{related_line}

작성 규칙:
- 변경 내용을 명확한 대비표로 정리
- 영향 범위(공정, 금형, 치구, 검사기준) 구체적 명시
- 적용 시점 이전 재고 처리 방안 언급
- 톤: 공식적, 명확, 간결
- placeholder를 절대 사용하지 마세요""",
    },

    "PPAP 제출 문서": {
        "icon": "📦",
        "description": "생산부품승인절차 제출 문서",
        "fields": [
            {"key": "recipient_type", "label": "제출처",           "type": "select",   "required": True,  "options": ["현대/기아 SQ", "HMGMA SQ"]},
            {"key": "part_name",      "label": "부품명",           "type": "text",     "required": True,  "placeholder": "CCH (전동식 냉난방 장치)"},
            {"key": "part_number",    "label": "품번",             "type": "text",     "required": True,  "placeholder": "97XXX-XXXXX"},
            {"key": "ppap_level",     "label": "PPAP Level",      "type": "select",   "required": True,  "options": ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"]},
            {"key": "reason",         "label": "제출 사유",        "type": "select",   "required": True,  "options": ["신규 부품", "설계 변경", "공정 변경", "금형 수정", "소재 변경", "공급업체 변경"]},
            {"key": "due_date",       "label": "제출 기한",        "type": "text",     "required": True,  "placeholder": "2026-05-30"},
            {"key": "additional",     "label": "추가 요구사항",     "type": "textarea", "required": False, "placeholder": "고객 요청 특이사항"},
        ],
        "prompt_template": """당신은 아진산업의 PPAP 전문가입니다. PPAP 제출 커버 문서를 작성하세요.

제출처: {recipient_type}
대상 부품: {part_name} (품번: {part_number})
PPAP Level: {ppap_level}
제출 사유: {reason}
제출 기한: {due_date}
{additional_line}

작성 규칙:
- PPAP Level에 맞는 18항목 체크리스트 포함
- PSW(Part Submission Warrant) 요약
- 마감일 기준 일정표
- 톤: 공식적, 체계적
- placeholder를 절대 사용하지 마세요""",
    },
    # ── v2.5: 규제 관련 문서 5종 (기능 D 연동) ──

    "규제 변경 영향 보고서": {
        "icon": "📊",
        "description": "규제 변경이 공장/공정에 미치는 영향을 분석하는 경영진 보고서",
        "fields": [
            {"key": "regulation_name",  "label": "규제명",               "type": "text",     "required": True,  "placeholder": "EU REACH Annex XVII 개정"},
            {"key": "regulation_type",  "label": "규제 유형",            "type": "select",   "required": True,  "options": ["ISO/IATF", "EU 규제", "국내법규", "미국규제(IRA/관세)", "OEM 품질기준", "MSDS/화학물질", "ESG/탄소", "EV 배터리"]},
            {"key": "change_summary",   "label": "변경 요약",            "type": "textarea", "required": True,  "placeholder": "기존: DEHP 허용 / 개정: 2026.07부터 DEHP 전면 금지"},
            {"key": "affected_plants",  "label": "영향 사업장",           "type": "text",     "required": True,  "placeholder": "경산 본사, 경산 제2공장, AJIN USA"},
            {"key": "affected_products","label": "영향 제품",             "type": "text",     "required": True,  "placeholder": "도어실링(EPDM), 웨더스트립"},
            {"key": "risk_level",       "label": "위험 수준",             "type": "select",   "required": True,  "options": ["HIGH — 즉시 대응", "MEDIUM — 계획 대응", "LOW — 모니터링"]},
            {"key": "effective_date",   "label": "시행일",               "type": "text",     "required": True,  "placeholder": "2026-07-01"},
            {"key": "cost_impact",      "label": "예상 비용 영향 (선택)",  "type": "text",     "required": False, "placeholder": "금형 수정 약 5천만원, 원재료 변경 연 2억원 추가"},
            {"key": "action_plan",      "label": "대응 방안 / 조치 계획",  "type": "textarea", "required": True,  "placeholder": "1단계: 대체 원료 시험 / 2단계: 금형 수정 / 3단계: 고객 승인"},
        ],
        "prompt_template": """당신은 아진산업의 규제 대응 보고서 작성 전문가입니다.
경영진에게 제출할 '규제 변경 영향 보고서'를 작성하세요.

■ 규제명: {regulation_name}
■ 규제 유형: {regulation_type}
■ 변경 요약:
{change_summary}

■ 영향 사업장: {affected_plants}
■ 영향 제품: {affected_products}
■ 위험 수준: {risk_level}
■ 시행일: {effective_date}
{cost_line}

■ 대응 방안:
{action_plan}

작성 규칙:
- 보고서 구조: 1. 규제 변경 개요 → 2. 영향 분석 (사업장/제품/공정) → 3. 위험 평가 → 4. 대응 계획 (단계별 일정+담당부서) → 5. 예상 비용 → 6. 경영진 의사결정 요청사항
- Before/After 비교표 포함
- 마감 일정 타임라인 포함
- 톤: 공식적, 객관적, 데이터 기반
- placeholder를 절대 사용하지 마세요. 모든 내용을 구체적으로 작성하세요""",
    },

    "OEM 규제 대응 통보문": {
        "icon": "📮",
        "description": "현대/기아에 규제 변경 대응 현황을 통보하는 공문",
        "fields": [
            {"key": "recipient_type",   "label": "수신처",               "type": "select",   "required": True,  "options": ["현대자동차 품질팀", "기아자동차 품질팀", "HMGMA SQ"]},
            {"key": "recipient_name",   "label": "수신자명 / 직함",       "type": "text",     "required": True,  "placeholder": "현대자동차 구매품질팀 ○○○ 과장님"},
            {"key": "sender",           "label": "발신자",               "type": "text",     "required": True,  "placeholder": "아진산업 품질경영팀 ○○○"},
            {"key": "regulation_name",  "label": "규제명",               "type": "text",     "required": True,  "placeholder": "EU REACH Annex XVII 개정 (DEHP 금지)"},
            {"key": "affected_parts",   "label": "영향 부품",             "type": "text",     "required": True,  "placeholder": "도어실링 (64XXX-XXXXX), 웨더스트립 (82XXX-XXXXX)"},
            {"key": "compliance_status","label": "당사 대응 현황",         "type": "textarea", "required": True,  "placeholder": "대체 원료 시험 완료, 금형 수정 진행 중, PPAP 재제출 예정"},
            {"key": "ppap_resubmit",    "label": "PPAP 재제출 필요 여부",  "type": "select",   "required": True,  "options": ["재제출 필요", "재제출 불필요", "검토 중"]},
            {"key": "timeline",         "label": "대응 일정",             "type": "textarea", "required": True,  "placeholder": "~04/30: 시험 완료 / ~05/15: 금형 수정 / ~06/01: PPAP 제출"},
        ],
        "prompt_template": """당신은 아진산업의 OEM 대응 전문가입니다. 현대/기아 품질팀에 제출할 '규제 대응 통보문'을 작성하세요.

수신: {recipient_name} ({recipient_type})
발신: {sender}
대상 규제: {regulation_name}
영향 부품: {affected_parts}

■ 대응 현황:
{compliance_status}

■ PPAP 재제출: {ppap_resubmit}

■ 대응 일정:
{timeline}

작성 규칙:
- 구조: 1. 규제 변경 요약 → 2. 영향 부품 목록 → 3. 당사 대응 현황 → 4. PPAP 재제출 계획 → 5. 일정표 → 6. 요청사항
- SQ 포털 용어(PPAP, PSW, CSR) 사용
- 톤: 매우 정중, 격식체 (~드립니다)
- placeholder를 절대 사용하지 마세요""",
    },

    "협력사 준수 요청서": {
        "icon": "📨",
        "description": "2차 협력사에 규제 준수를 요청하는 공문",
        "fields": [
            {"key": "supplier_name",    "label": "협력사명",             "type": "text",     "required": True,  "placeholder": "○○산업(주)"},
            {"key": "supplier_contact", "label": "협력사 담당자",         "type": "text",     "required": True,  "placeholder": "품질팀 ○○○ 과장"},
            {"key": "sender",           "label": "발신자",               "type": "text",     "required": True,  "placeholder": "아진산업 구매팀 ○○○"},
            {"key": "regulation_name",  "label": "규제명",               "type": "text",     "required": True,  "placeholder": "REACH SVHC 후보물질 목록 갱신"},
            {"key": "required_actions",  "label": "협력사 요구 조치",     "type": "textarea", "required": True,  "placeholder": "1. MSDS 재제출\n2. 유해물질 불포함 확인서\n3. 대체 원료 전환 계획서"},
            {"key": "deadline",         "label": "제출 기한",             "type": "text",     "required": True,  "placeholder": "2026-05-31"},
            {"key": "penalty_note",     "label": "미준수 시 조치 (선택)",  "type": "text",     "required": False, "placeholder": "납품 중단 및 대체 업체 전환 검토"},
        ],
        "prompt_template": """당신은 아진산업의 구매/품질 담당자입니다. 2차 협력사에 보낼 '규제 준수 요청서'를 작성하세요.

수신: {supplier_name} {supplier_contact}
발신: {sender}
규제: {regulation_name}

■ 요구 조치:
{required_actions}

■ 제출 기한: {deadline}
{penalty_line}

작성 규칙:
- 구조: 1. 규제 변경 안내 → 2. 귀사 해당 사항 → 3. 요구 자료 목록 → 4. 제출 기한/방법 → 5. 미이행 시 조치
- 톤: 정중하되 명확, 의무 이행 사항 강조
- 요구 자료 각 항목에 ☐ 체크박스 포함
- placeholder를 절대 사용하지 마세요""",
    },

    "규제 시행 계획서": {
        "icon": "📅",
        "description": "규제 대응을 위한 부서별 실행 계획 문서",
        "fields": [
            {"key": "regulation_name",  "label": "규제명",               "type": "text",     "required": True,  "placeholder": "IATF 16949:2016 SI-24 개정"},
            {"key": "plan_owner",       "label": "주관 부서/담당자",       "type": "text",     "required": True,  "placeholder": "품질경영팀 ○○○ 팀장"},
            {"key": "related_depts",    "label": "관련 부서",             "type": "text",     "required": True,  "placeholder": "품질보증팀, 생산기술팀, 구매팀, 연구소"},
            {"key": "current_status",   "label": "현재 상태",             "type": "textarea", "required": True,  "placeholder": "현행 프로세스는 SI-23 기준 운영 중, SI-24 변경사항 미반영"},
            {"key": "action_items",     "label": "부서별 조치사항",        "type": "textarea", "required": True,  "placeholder": "품질: 문서 개정 / 생산기술: 공정 검증 / 구매: 협력사 통보"},
            {"key": "schedule",         "label": "일정 계획",             "type": "textarea", "required": True,  "placeholder": "Phase1(~04/30): 분석 / Phase2(~06/30): 적용 / Phase3(~07/31): 검증"},
            {"key": "budget",           "label": "소요 예산 (선택)",       "type": "text",     "required": False, "placeholder": "약 3,000만원 (교육비+컨설팅+설비)"},
        ],
        "prompt_template": """당신은 아진산업의 규제 시행 계획 수립 전문가입니다. '규제 시행 계획서'를 작성하세요.

■ 규제: {regulation_name}
■ 주관: {plan_owner}
■ 관련 부서: {related_depts}

■ 현재 상태:
{current_status}

■ 부서별 조치사항:
{action_items}

■ 일정:
{schedule}

{budget_line}

작성 규칙:
- 구조: 1. 배경 및 목적 → 2. 규제 요구사항 요약 → 3. 현황 분석 (Gap 분석) → 4. 부서별 실행 계획 (담당자/기한/산출물) → 5. 일정 마일스톤 → 6. 예산 → 7. 리스크 및 대응
- 각 부서 조치사항에 담당자/기한/산출물 명시
- Gantt 스타일 일정표 (텍스트)
- placeholder를 절대 사용하지 마세요""",
    },

    "규제 대비 체크리스트": {
        "icon": "☑️",
        "description": "규제 심사/감사 대비 자체 점검 체크리스트",
        "fields": [
            {"key": "regulation_name",  "label": "규제/인증 명",          "type": "text",     "required": True,  "placeholder": "IATF 16949:2016 정기 심사"},
            {"key": "audit_type",       "label": "심사 유형",             "type": "select",   "required": True,  "options": ["정기 심사 (Surveillance)", "갱신 심사 (Re-certification)", "특별 심사", "고객 심사 (2자 심사)", "내부 감사"]},
            {"key": "audit_date",       "label": "심사 예정일",           "type": "text",     "required": True,  "placeholder": "2026-06-15 ~ 2026-06-17"},
            {"key": "scope",            "label": "심사 범위 / 대상 부서",  "type": "textarea", "required": True,  "placeholder": "전사 (품질경영/생산기술/구매/연구소)"},
            {"key": "focus_areas",      "label": "중점 심사 항목 (선택)",  "type": "textarea", "required": False, "placeholder": "FMEA 운영 현황, MSA 주기, 내부 감사 유효성"},
            {"key": "previous_findings","label": "이전 지적사항 (선택)",   "type": "textarea", "required": False, "placeholder": "2025 심사: OFI 2건 (교정 장비 관리, 문서 버전 관리)"},
        ],
        "prompt_template": """당신은 아진산업의 품질 인증 심사 전문가입니다. '규제 대비 체크리스트'를 작성하세요.

■ 규제/인증: {regulation_name}
■ 심사 유형: {audit_type}
■ 심사 예정일: {audit_date}
■ 심사 범위: {scope}

{focus_section}
{findings_section}

작성 규칙:
- 구조: 1. 심사 개요 → 2. 사전 준비 체크리스트 (☐ 항목별) → 3. 조항별 점검 체크리스트 → 4. 증빙 서류 목록 → 5. 이전 지적사항 조치 확인 → 6. 비상 연락망
- 각 체크 항목: ☐ 항목명 | 담당부서 | 상태(완료/진행중/미착수) | 비고
- IATF/ISO 조항 번호 기반 구성
- placeholder를 절대 사용하지 마세요""",
    },

    # ── v2.6: 품질/안전 문서 ──

    "품질문제 개선대책서": {
        "icon": "🔧",
        "description": "품질 불량 원인분석 및 개선대책 보고서",
        "tone": "formal",
        "language": "ko",
        "fields": [
            {"key": "part_name",          "label": "부품명",           "type": "text",     "required": True,  "placeholder": "EWP 하우징"},
            {"key": "part_number",        "label": "품번",             "type": "text",     "required": False, "placeholder": "26410-XXXXX"},
            {"key": "plant_line",         "label": "발생 공장/라인",    "type": "text",     "required": True,  "placeholder": "경산 제1공장 프레스라인"},
            {"key": "occurrence_date",    "label": "발생일",           "type": "text",     "required": True,  "placeholder": "2026-04-01"},
            {"key": "defect_description", "label": "불량 현상",         "type": "textarea", "required": True,  "placeholder": "용접 비드 불균일, 파단 강도 미달"},
            {"key": "defect_quantity",    "label": "불량 수량/발생률",   "type": "text",     "required": False, "placeholder": "3EA / 500EA (0.6%)"},
        ],
        "prompt_template": """당신은 아진산업의 품질 개선 전문가입니다. 품질문제 개선대책서를 작성하세요.

■ 부품명: {part_name}
■ 품번: {part_number}
■ 발생 공장/라인: {plant_line}
■ 발생일: {occurrence_date}
■ 불량 현상: {defect_description}
{quantity_line}

작성 규칙:
- 구조: 1. 문제 개요 → 2. 현상 분석 → 3. 원인 분석 (Why-Why 또는 특성요인도) → 4. 개선 대책 (긴급/영구/수평전개) → 5. 효과 검증 계획 → 6. 일정 계획
- 원인 분석은 4M(Man/Machine/Material/Method) 관점으로 분석
- 긴급 조치, 영구 대책, 수평 전개를 명확히 구분
- 효과 검증: Cpk, 불량률 목표치 포함
- placeholder를 절대 사용하지 마세요""",
    },

    "안전 인시던트 리포트": {
        "icon": "🚨",
        "description": "산업 안전사고 발생 보고서 (산안법 제57조)",
        "tone": "formal",
        "language": "ko",
        "fields": [
            {"key": "incident_date",        "label": "발생 일시",    "type": "text",     "required": True,  "placeholder": "2026-04-01 14:30"},
            {"key": "incident_location",    "label": "발생 장소",    "type": "text",     "required": True,  "placeholder": "경산 본사 프레스 2라인"},
            {"key": "incident_type",        "label": "사고 유형",    "type": "text",     "required": True,  "placeholder": "끼임, 화상, 추락, 전도, 감전 등"},
            {"key": "incident_description", "label": "사고 경위",    "type": "textarea", "required": True,  "placeholder": "사고 발생 경위를 상세히 기술"},
            {"key": "victim_info",          "label": "피해자 정보",  "type": "text",     "required": False, "placeholder": "OOO (생산관리팀, 사원)"},
            {"key": "injury_severity",      "label": "피해 정도",    "type": "text",     "required": False, "placeholder": "경상 / 중상 / 무재해"},
        ],
        "prompt_template": """당신은 아진산업의 안전보건 관리자입니다. 안전 인시던트 리포트를 작성하세요.

■ 발생 일시: {incident_date}
■ 발생 장소: {incident_location}
■ 사고 유형: {incident_type}
■ 사고 경위: {incident_description}
■ 피해자: {victim_info}
■ 피해 정도: {injury_severity}

작성 규칙:
- 구조: 1. 사고 개요 → 2. 사고 경위 (시간순) → 3. 피해 현황 (인적/물적/생산/환경) → 4. 긴급 조치 → 5. 원인 분석 (직접/간접) → 6. 재발 방지 대책 → 7. 후속 조치 일정
- 산업안전보건법 제57조 기반 보고 양식 준수
- LOTO, 위험성 평가, 안전교육 관점 포함
- placeholder를 절대 사용하지 마세요""",
    },

    # ── v2.6: 생산/자재 문서 ──

    "납입용기 규격 설정서": {
        "icon": "📦",
        "description": "납입 부품 용기 규격 및 포장 사양 설정",
        "tone": "formal",
        "language": "ko",
        "fields": [
            {"key": "part_name",             "label": "부품명",            "type": "text",     "required": True,  "placeholder": "쿼터 패널 COMPL"},
            {"key": "part_number",           "label": "품번",              "type": "text",     "required": True,  "placeholder": "64XXX-XXXXX"},
            {"key": "container_dimensions",  "label": "용기 치수 (LxWxH)", "type": "text",     "required": True,  "placeholder": "1200 x 800 x 600 mm"},
            {"key": "quantity_per_container", "label": "수납 수량 (EA/용기)","type": "text",    "required": True,  "placeholder": "10"},
            {"key": "packaging_spec",        "label": "포장 사양",          "type": "textarea", "required": True,  "placeholder": "완충재, 간지 사용 여부 등"},
        ],
        "prompt_template": """당신은 아진산업의 물류/포장 전문가입니다. 납입용기 규격 설정서를 작성하세요.

■ 부품명: {part_name}
■ 품번: {part_number}
■ 용기 치수: {container_dimensions}
■ 수납 수량: {quantity_per_container}
■ 포장 사양: {packaging_spec}

작성 규칙:
- 구조: 1. 부품 정보 → 2. 용기 규격 (종류/치수/중량/수납수/적재단수) → 3. 포장 사양 (완충재/간지/고정방법) → 4. 비고
- 현대/기아 납품 기준 준수
- 부품 특성(무게, 형상, 표면 처리)에 따른 적절한 포장 방법 제안
- placeholder를 절대 사용하지 마세요""",
    },

    "사급 반출 요청서": {
        "icon": "📤",
        "description": "사급 자재 반출 요청 및 승인 문서",
        "tone": "formal",
        "language": "ko",
        "fields": [
            {"key": "material_name",   "label": "자재명",      "type": "text",     "required": True,  "placeholder": "SPCC 590 코일"},
            {"key": "material_spec",   "label": "규격/사양",    "type": "text",     "required": True,  "placeholder": "1.2t x 1219mm x C"},
            {"key": "quantity",        "label": "수량",         "type": "text",     "required": True,  "placeholder": "500 kg"},
            {"key": "to_location",     "label": "반입처",       "type": "text",     "required": True,  "placeholder": "OO산업 (2차 협력사)"},
            {"key": "dispatch_date",   "label": "반출 희망일",   "type": "text",     "required": True,  "placeholder": "2026-04-15"},
            {"key": "dispatch_reason", "label": "반출 사유",     "type": "textarea", "required": True,  "placeholder": "협력사 금형 트라이아웃용 자재 지급"},
        ],
        "prompt_template": """당신은 아진산업의 구매/자재 관리 담당자입니다. 사급 반출 요청서를 작성하세요.

■ 자재명: {material_name}
■ 규격/사양: {material_spec}
■ 수량: {quantity}
■ 반입처: {to_location}
■ 반출 희망일: {dispatch_date}
■ 반출 사유: {dispatch_reason}

작성 규칙:
- 구조: 1. 반출 대상 (자재명/코드/규격/수량) → 2. 반출 사유 → 3. 반출/반입 정보 (출발지/도착지/일정/운송방법) → 4. 비고
- 사급자재 관리 기준 준수
- 반입 예정일, 잔량 처리 계획 포함
- placeholder를 절대 사용하지 마세요""",
    },
}


# ═══════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════

def get_doc_types(context: str) -> dict:
    """context에 따른 문서 유형 딕셔너리 반환"""
    if context == "internal":
        return INTERNAL_DOC_TYPES
    return EXTERNAL_DOC_TYPES


def get_doc_type_names(context: str) -> list[str]:
    """문서 유형 이름 목록"""
    return list(get_doc_types(context).keys())


def get_doc_type_config(context: str, doc_type: str) -> dict:
    """특정 문서 유형의 설정 반환"""
    return get_doc_types(context).get(doc_type, {})


def build_prompt(context: str, doc_type: str, values: dict) -> str:
    """문서 유형 + 입력값으로 LLM 프롬프트 생성"""
    config = get_doc_type_config(context, doc_type)
    template = config.get("prompt_template", "")

    if not template:
        lines = [f"당신은 아진산업의 문서 작성 전문가입니다. {doc_type}을(를) 작성하세요.\n"]
        for k, v in values.items():
            if v:
                lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    # 선택적 라인 처리
    optional_lines = {
        "cc_line": f"CC: {values.get('cc', '')}" if values.get("cc") else "",
        "part_line": f"대상 부품: {values.get('part_info', '')}" if values.get("part_info") else "",
        "quantity_line": f"■ 발생 수량: {values.get('quantity', '')}" if values.get("quantity") else "",
        "lot_line": f"■ 로트 번호: {values.get('lot_number', '')}" if values.get("lot_number") else "",
        "impact_line": f"■ 영향 범위: {values.get('impact_scope', '')}" if values.get("impact_scope") else "",
        "related_line": f"■ 관련 문서: {values.get('related_docs', '')}" if values.get("related_docs") else "",
        "additional_line": f"■ 추가 요구사항:\n{values.get('additional', '')}" if values.get("additional") else "",
        "emergency_section": f"■ 긴급 대응 조치:\n{values.get('emergency', '')}" if values.get("emergency") else "",
        "d1_section": f"■ D1 팀 구성: {values.get('d1_team', '')}" if values.get("d1_team") else "",
        "context_section": f"■ 논의 내용/배경:\n{values.get('context_hint', '')}" if values.get("context_hint") else "",
        # v2.5: 규제 문서용 선택적 라인
        "cost_line": f"■ 예상 비용 영향: {values.get('cost_impact', '')}" if values.get("cost_impact") else "",
        "penalty_line": f"■ 미준수 시 조치: {values.get('penalty_note', '')}" if values.get("penalty_note") else "",
        "budget_line": f"■ 소요 예산: {values.get('budget', '')}" if values.get("budget") else "",
        "focus_section": f"■ 중점 심사 항목:\n{values.get('focus_areas', '')}" if values.get("focus_areas") else "",
        "findings_section": f"■ 이전 지적사항:\n{values.get('previous_findings', '')}" if values.get("previous_findings") else "",
        # Plan v1.0 — 신규 INTERNAL 5종 의 선택 섹션
        "issues_section": f"■ 이슈/지원 요청:\n{values.get('issues', '')}" if values.get("issues") else "",
        "handover_section": f"■ 업무 인수인계:\n{values.get('handover', '')}" if values.get("handover") else "",
        "validity_section": f"■ 유효기간: {values.get('validity', '')}" if values.get("validity") else "",
        "remarks_section": f"■ 특이사항:\n{values.get('remarks', '')}" if values.get("remarks") else "",
        "expense_section": f"■ 출장 경비:\n{values.get('expense', '')}" if values.get("expense") else "",
        "actions_section": f"■ 조치 / 건의 사항:\n{values.get('actions', '')}" if values.get("actions") else "",
    }

    # 언어 지시 (외부 이메일용)
    recipient_type = values.get("recipient_type", "")
    if "영문" in recipient_type or ("HMGMA" in recipient_type and "국영문" not in recipient_type):
        optional_lines["language_instruction"] = "작성 규칙:\n- Write entirely in formal business English\n- Use IATF 16949 / automotive industry terminology\n- Professional closing with Best regards"
    elif "국영문" in recipient_type:
        optional_lines["language_instruction"] = "작성 규칙:\n- 한국어 버전과 English 버전을 모두 작성\n- 영문: formal business English, IATF terminology"
    elif "해외법인" in recipient_type:
        optional_lines["language_instruction"] = "작성 규칙:\n- Write in formal English\n- Use automotive manufacturing terminology"
    else:
        optional_lines["language_instruction"] = "작성 규칙:\n- 정중한 비즈니스 한국어 사용\n- ~드립니다, ~부탁드립니다 어미\n- 마무리: 검토 부탁드립니다"

    merged = {**values, **optional_lines}

    # 템플릿에 값 대입 (누락 키는 빈 문자열)
    result = template
    for key in re.findall(r"\{(\w+)\}", template):
        result = result.replace(f"{{{key}}}", str(merged.get(key, "")))
    return result
