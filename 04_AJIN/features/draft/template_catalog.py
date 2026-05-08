"""
양식 템플릿 카탈로그
- 내부용/외부용 양식의 카테고리, 필드 정의, 파일 경로를 중앙 관리
- doc_search_panel.py와 page_draft.py에서 공통 참조
"""

from pathlib import Path

# 템플릿 디렉토리 경로
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "data" / "templates"

# ═══════════════════════════════════════════════════════
# 내부용 양식 카탈로그
# ═══════════════════════════════════════════════════════
INTERNAL_TEMPLATES = {
    "이메일 양식": [
        {
            "id": "internal_email",
            "name": "사내 이메일",
            "file": "email/to_internal.j2",
            "description": "사내 부서 간 업무 이메일 양식",
            "fields": [
                {"key": "recipient",   "label": "수신자 (부서/이름)",  "type": "text",     "placeholder": "품질관리팀 홍길동 과장님"},
                {"key": "subject",     "label": "제목",               "type": "text",     "placeholder": "○○ 관련 협조 요청의 건"},
                {"key": "sender",      "label": "발신자",             "type": "text",     "placeholder": "생산기술팀 김철수"},
                {"key": "cc",          "label": "CC (선택)",          "type": "text",     "placeholder": "관련 부서/담당자", "required": False},
                {"key": "body",        "label": "본문 내용 / 요청사항", "type": "textarea", "placeholder": "요청 사항을 간략히 입력하세요"},
            ],
        },
    ],
    "회의 양식": [
        {
            "id": "meeting_note",
            "name": "회의록",
            "file": "report/meeting_note.j2",
            "description": "사내 회의록 표준 양식",
            "fields": [
                {"key": "meeting_title", "label": "회의명",       "type": "text",     "placeholder": "2026년 Q2 품질 검토 회의"},
                {"key": "date",          "label": "일시",         "type": "text",     "placeholder": "2026-04-15 14:00"},
                {"key": "location",      "label": "장소",         "type": "text",     "placeholder": "본사 3층 대회의실"},
                {"key": "attendees",     "label": "참석자",       "type": "textarea", "placeholder": "홍길동(품질), 김영희(생산), ..."},
                {"key": "agenda",        "label": "안건",         "type": "textarea", "placeholder": "1. Q1 품질 실적 검토\n2. Q2 개선 계획"},
                {"key": "decisions",     "label": "결정사항",     "type": "textarea", "placeholder": "결정된 사항을 기입", "required": False},
                {"key": "action_items",  "label": "후속 조치",    "type": "textarea", "placeholder": "담당자별 조치 사항", "required": False},
            ],
        },
    ],
}

# ═══════════════════════════════════════════════════════
# 외부용 양식 카탈로그
# ═══════════════════════════════════════════════════════
EXTERNAL_TEMPLATES = {
    "이메일 양식": [
        {
            "id": "email_oem",
            "name": "OEM 이메일 (현대/기아)",
            "file": "email/to_oem.j2",
            "description": "현대·기아 완성차 업체 대상 공식 이메일",
            "fields": [
                {"key": "recipient",   "label": "수신자",         "type": "text",     "placeholder": "현대자동차 구매팀 ○○○ 과장님"},
                {"key": "subject",     "label": "제목",           "type": "text",     "placeholder": "[아진산업] ○○ 관련 회신의 건"},
                {"key": "sender",      "label": "발신자",         "type": "text",     "placeholder": "아진산업 ○○팀 ○○○"},
                {"key": "part_name",   "label": "부품명",         "type": "text",     "placeholder": "A-Panel", "required": False},
                {"key": "part_number", "label": "품번",           "type": "text",     "placeholder": "XXXX-XXXXX", "required": False},
                {"key": "body",        "label": "본문 내용",       "type": "textarea", "placeholder": "요청/회신 내용"},
            ],
        },
        {
            "id": "email_supplier",
            "name": "협력사 이메일",
            "file": "email/to_supplier.j2",
            "description": "2차 협력사 대상 이메일",
            "fields": [
                {"key": "recipient",   "label": "수신 업체/담당자", "type": "text",     "placeholder": "○○산업 ○○○ 대리님"},
                {"key": "subject",     "label": "제목",            "type": "text",     "placeholder": "○○ 부품 납기 확인 요청"},
                {"key": "sender",      "label": "발신자",          "type": "text",     "placeholder": "아진산업 구매팀 ○○○"},
                {"key": "body",        "label": "본문 내용",        "type": "textarea", "placeholder": "요청 내용"},
            ],
        },
        {
            "id": "email_overseas",
            "name": "해외법인 이메일 (영문)",
            "file": "email/to_overseas.j2",
            "description": "JOON INC, AJIN USA 등 해외법인 대상 영문 이메일",
            "fields": [
                {"key": "recipient",   "label": "To",              "type": "text",     "placeholder": "JOON INC Quality Team"},
                {"key": "subject",     "label": "Subject",         "type": "text",     "placeholder": "RE: EWP Assembly Quality Report"},
                {"key": "sender",      "label": "From",            "type": "text",     "placeholder": "AJIN HQ Quality Dept."},
                {"key": "body",        "label": "Body",            "type": "textarea", "placeholder": "Email content in English"},
            ],
        },
    ],
    "품질 문서": [
        {
            "id": "8d_report",
            "name": "8D Report (클레임 대응)",
            "file": "report/8d_report.j2",
            "description": "고객 클레임 원인분석 및 시정조치 보고서",
            "fields": [
                {"key": "customer",      "label": "고객사",           "type": "text",     "placeholder": "현대자동차 울산공장"},
                {"key": "part_name",     "label": "부품명",           "type": "text",     "placeholder": "EWP (전동식 워터펌프)"},
                {"key": "part_number",   "label": "품번",             "type": "text",     "placeholder": "26410-XXXXX"},
                {"key": "defect_desc",   "label": "불량 현상",         "type": "textarea", "placeholder": "조립 후 누수 발생, 시동 후 30분 내 냉각수 누출"},
                {"key": "plant_line",    "label": "발생 공장/라인",    "type": "text",     "placeholder": "경산 제1공장 EWP 조립라인 #2"},
                {"key": "quantity",      "label": "불량 수량",         "type": "text",     "placeholder": "5EA / 1,000EA (불량률 0.5%)", "required": False},
                {"key": "lot_number",    "label": "로트 번호",         "type": "text",     "placeholder": "LOT-2026-0401-A", "required": False},
                {"key": "emergency",     "label": "긴급 대응 조치",    "type": "textarea", "placeholder": "전수 검사 실시, 의심 로트 출하 보류", "required": False},
            ],
        },
        {
            "id": "ppap_checklist",
            "name": "PPAP 체크리스트",
            "file": "report/ppap_checklist_template.j2",
            "description": "생산부품승인절차 18항목 체크리스트",
            "fields": [
                {"key": "part_name",     "label": "부품명",       "type": "text",     "placeholder": "CCH (전동식 냉난방 장치)"},
                {"key": "part_number",   "label": "품번",         "type": "text",     "placeholder": "97XXX-XXXXX"},
                {"key": "ppap_level",    "label": "PPAP Level",  "type": "select",   "options": ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"]},
                {"key": "customer",      "label": "제출처",       "type": "text",     "placeholder": "현대자동차 SQ"},
                {"key": "due_date",      "label": "제출 기한",    "type": "text",     "placeholder": "2026-05-30"},
            ],
        },
        {
            "id": "fmea",
            "name": "공정 FMEA",
            "file": "report/fmea_process_template.j2",
            "description": "공정별 잠재 고장모드 영향분석",
            "fields": [
                {"key": "process_name",  "label": "공정명",       "type": "text",     "placeholder": "EWP 하우징 가공 공정"},
                {"key": "part_name",     "label": "대상 부품",    "type": "text",     "placeholder": "EWP 하우징 (AL Die Casting)"},
                {"key": "team",          "label": "작성 팀",      "type": "text",     "placeholder": "생산기술팀 + 품질관리팀"},
            ],
        },
    ],
    "품질/안전 문서": [
        {
            "id": "quality_improvement",
            "name": "품질문제 개선대책서",
            "file": "report/quality_improvement.j2",
            "description": "품질 불량 원인분석 및 개선대책 보고서 (8D와 별개 양식)",
            "fields": [
                {"key": "part_name",           "label": "부품명",           "type": "text",     "placeholder": "EWP 하우징"},
                {"key": "part_number",         "label": "품번",             "type": "text",     "placeholder": "26410-XXXXX", "required": False},
                {"key": "plant_line",          "label": "발생 공장/라인",    "type": "text",     "placeholder": "경산 제1공장 프레스라인"},
                {"key": "occurrence_date",     "label": "발생일",           "type": "text",     "placeholder": "2026-04-01"},
                {"key": "defect_description",  "label": "불량 현상",         "type": "textarea", "placeholder": "용접 비드 불균일, 파단 강도 미달"},
                {"key": "defect_quantity",     "label": "불량 수량/발생률",   "type": "text",     "placeholder": "3EA / 500EA (0.6%)", "required": False},
            ],
        },
        {
            "id": "incident_report",
            "name": "안전 인시던트 리포트",
            "file": "report/incident_report.j2",
            "description": "산업 안전사고 발생 보고서 (산안법 제57조 기반)",
            "fields": [
                {"key": "incident_date",       "label": "발생 일시",         "type": "text",     "placeholder": "2026-04-01 14:30"},
                {"key": "incident_location",   "label": "발생 장소",         "type": "text",     "placeholder": "경산 본사 프레스 2라인"},
                {"key": "incident_type",       "label": "사고 유형",         "type": "text",     "placeholder": "끼임, 화상, 추락, 전도, 감전 등"},
                {"key": "incident_description","label": "사고 경위",         "type": "textarea", "placeholder": "사고 발생 경위를 상세히 기술"},
                {"key": "victim_info",         "label": "피해자 정보",       "type": "text",     "placeholder": "OOO (생산관리팀, 사원)", "required": False},
                {"key": "injury_severity",     "label": "피해 정도",         "type": "text",     "placeholder": "경상 / 중상 / 무재해", "required": False},
            ],
        },
    ],
    "생산/자재 문서": [
        {
            "id": "container_spec",
            "name": "납입용기 규격 설정서",
            "file": "report/container_spec.j2",
            "description": "납입 부품 용기 규격 및 포장 사양 설정",
            "fields": [
                {"key": "part_name",              "label": "부품명",           "type": "text",     "placeholder": "쿼터 패널 COMPL"},
                {"key": "part_number",            "label": "품번",             "type": "text",     "placeholder": "64XXX-XXXXX"},
                {"key": "container_dimensions",   "label": "용기 치수 (LxWxH)", "type": "text",    "placeholder": "1200 x 800 x 600 mm"},
                {"key": "quantity_per_container",  "label": "수납 수량 (EA/용기)","type": "text",   "placeholder": "10"},
                {"key": "packaging_spec",         "label": "포장 사양",         "type": "textarea", "placeholder": "완충재, 간지 사용 여부 등"},
            ],
        },
        {
            "id": "supply_dispatch",
            "name": "사급 반출 요청서",
            "file": "report/supply_dispatch.j2",
            "description": "사급 자재 반출 요청 및 승인 문서",
            "fields": [
                {"key": "material_name",   "label": "자재명",           "type": "text",     "placeholder": "SPCC 590 코일"},
                {"key": "material_spec",   "label": "규격/사양",         "type": "text",     "placeholder": "1.2t x 1219mm x C"},
                {"key": "quantity",        "label": "수량",              "type": "text",     "placeholder": "500 kg"},
                {"key": "to_location",     "label": "반입처",            "type": "text",     "placeholder": "OO산업 (2차 협력사)"},
                {"key": "dispatch_date",   "label": "반출 희망일",        "type": "text",     "placeholder": "2026-04-15"},
                {"key": "dispatch_reason", "label": "반출 사유",          "type": "textarea", "placeholder": "협력사 금형 트라이아웃용 자재 지급"},
            ],
        },
    ],
    "변경 통보": [
        {
            "id": "ecn_notice",
            "name": "ECN 변경통보",
            "file": "report/ecn_notice.j2",
            "description": "승인된 설계변경 통보 문서",
            "fields": [
                {"key": "ecn_number",    "label": "ECN 번호",     "type": "text",     "placeholder": "ECN-2026-0078"},
                {"key": "part_name",     "label": "부품명",       "type": "text",     "placeholder": "A-Panel Reinforce"},
                {"key": "part_number",   "label": "품번",         "type": "text",     "placeholder": "64XXX-XXXXX"},
                {"key": "before_spec",   "label": "변경 전 사양", "type": "textarea", "placeholder": "두께 1.2mm / SPCC 440"},
                {"key": "after_spec",    "label": "변경 후 사양", "type": "textarea", "placeholder": "두께 1.4mm / SPCC 590"},
                {"key": "reason",        "label": "변경 사유",    "type": "textarea", "placeholder": "충돌 시험 결과 보강 필요"},
                {"key": "effective_date","label": "적용 시점",    "type": "text",     "placeholder": "2026-06-01 (LOT-2026-0601부터)"},
                {"key": "impact_scope",  "label": "영향 범위",    "type": "text",     "placeholder": "경산 제1공장 프레스라인, 금형 2종 수정", "required": False},
            ],
        },
    ],
}


def get_template_path(filename: str) -> Path:
    """템플릿 파일의 절대 경로 반환"""
    return TEMPLATE_DIR / filename


def get_catalog(context: str) -> dict:
    """context에 따라 양식 카탈로그 반환"""
    if context == "internal":
        return INTERNAL_TEMPLATES
    return EXTERNAL_TEMPLATES


def get_all_template_ids(context: str) -> list[str]:
    """특정 context의 모든 양식 ID 목록"""
    catalog = get_catalog(context)
    ids = []
    for templates in catalog.values():
        for t in templates:
            ids.append(t["id"])
    return ids


def find_template_by_id(template_id: str) -> dict | None:
    """ID로 양식 메타데이터 검색 (내부/외부 모두 탐색)"""
    for catalog in [INTERNAL_TEMPLATES, EXTERNAL_TEMPLATES]:
        for templates in catalog.values():
            for t in templates:
                if t["id"] == template_id:
                    return t
    return None
