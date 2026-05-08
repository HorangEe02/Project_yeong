"""APQP 연구개발 프로세스 크롤러

APQP(Advanced Product Quality Planning) 5단계 프로세스의
최신 요구사항, OEM별 가이드라인, 산출물 체크리스트를 수집한다.

데이터 소스:
- AIAG APQP 매뉴얼 (3rd Edition)
- 현대/기아 SQ 포털 협력사 가이드
- VDA MLA (Maturity Level Assurance)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class APQPPhase:
    """APQP 단계 정보"""
    phase_id: str               # e.g., "APQP-P1"
    phase_number: int
    name: str
    name_ko: str
    description: str
    key_activities: list[str]
    deliverables: list[str]     # 산출물 목록
    deliverables_ko: list[str]
    gate_review_criteria: list[str]  # 게이트 리뷰 기준
    responsible_dept: list[str]
    typical_duration: str
    oem_requirements: dict      # OEM별 추가 요구사항


@dataclass
class APQPChecklist:
    """APQP 산출물 체크리스트 항목"""
    item_id: str
    phase_id: str
    name: str
    name_ko: str
    description: str
    required_by: list[str]      # ["AIAG", "현대/기아", "GM", "VW"]
    template_available: bool
    responsible_dept: str
    criticality: str            # critical, major, minor
    ajin_status: str            # completed, in_progress, not_started, not_applicable


@dataclass
class APQPUpdate:
    """APQP 관련 업데이트/변경사항"""
    update_id: str
    source: str                 # "AIAG", "현대/기아_SQ", "VDA_MLA"
    title: str
    description: str
    affected_phases: list[str]
    effective_date: str
    severity: str
    required_actions: list[str]
    reference_url: str = ""
    crawled_at: str = ""


@dataclass
class APQPCrawlResult:
    """크롤링 결과"""
    phases: list[APQPPhase]
    checklists: list[APQPChecklist]
    updates: list[APQPUpdate]
    crawled_at: str
    source: str
    total_phases: int
    total_checklist_items: int
    total_updates: int
    errors: list[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        """v2.6: UI 호환 — 전체 수집 건수 (phases + checklists + updates)."""
        return self.total_phases + self.total_checklist_items + self.total_updates


# ─────────────────────────────────────────────
# APQP 5단계 마스터 데이터
# ─────────────────────────────────────────────

_APQP_PHASES = [
    {
        "phase_id": "APQP-P1",
        "phase_number": 1,
        "name": "Plan and Define Program",
        "name_ko": "프로그램 기획 및 정의",
        "description": "고객의 소리(VOC)를 통해 고객 요구사항을 명확히 하고, 프로그램 목표와 범위를 정의한다.",
        "key_activities": [
            "고객 요구사항 분석 (VOC)",
            "벤치마킹 조사",
            "제품/공정 가정 수립",
            "제품 신뢰성 목표 설정",
            "예비 자재 목록(BOM) 작성",
            "예비 공정 흐름도 작성",
            "특별 특성(SC/CC) 사전 목록 작성",
        ],
        "deliverables": [
            "Design Goals", "Reliability Goals", "Preliminary BOM",
            "Preliminary Process Flow", "Product Assurance Plan",
            "Management Support & Sign-off",
        ],
        "deliverables_ko": [
            "설계 목표", "신뢰성 목표", "예비 BOM",
            "예비 공정 흐름도", "제품 보증 계획서",
            "경영진 승인",
        ],
        "gate_review_criteria": [
            "고객 요구사항 완전성 확인",
            "벤치마킹 결과 문서화",
            "타당성 검토 완료",
            "일정 및 자원 배분 승인",
        ],
        "responsible_dept": ["연구소", "품질관리팀", "영업팀"],
        "typical_duration": "RFQ 접수 후 4~8주",
        "oem_requirements": {
            "현대/기아": "SQ 포털에 VOC 분석서 및 타당성 검토서 제출. 사전 DFMEA 필수.",
            "GM": "GQTS(Global Quality Tracking System) 등록. 프로그램 마일스톤 입력.",
            "VW": "VDA MLA Level 0 (RFQ Analysis) 완료. 프로젝트 계약서 체결.",
        },
    },
    {
        "phase_id": "APQP-P2",
        "phase_number": 2,
        "name": "Product Design and Development",
        "name_ko": "제품 설계 및 개발",
        "description": "설계 사양을 구체화하고, DFMEA를 통해 설계 리스크를 평가하며, 시작품(Prototype)을 제작/검증한다.",
        "key_activities": [
            "설계 FMEA (DFMEA) 작성",
            "DFM/DFA (제조/조립 용이성 설계) 검토",
            "설계 검증 계획 및 보고 (DVP&R)",
            "시작품 금형/치공구 제작",
            "시작품 제작 및 시험",
            "도면 및 사양서 확정",
            "특별 특성 확정",
            "소재 사양 결정",
        ],
        "deliverables": [
            "DFMEA", "DFM/DFA Review", "DVP&R",
            "Prototype Build", "Engineering Drawings",
            "Material Specifications", "Special Characteristics",
        ],
        "deliverables_ko": [
            "설계 FMEA", "DFM/DFA 검토", "DVP&R",
            "시작품 제작", "엔지니어링 도면",
            "소재 사양서", "특별 특성 목록",
        ],
        "gate_review_criteria": [
            "DFMEA 완료 및 리스크 조치 계획 수립",
            "시작품 시험 결과 목표 충족",
            "도면/사양서 OEM 승인",
            "소재 선정 및 시험 완료",
        ],
        "responsible_dept": ["연구소", "품질관리팀"],
        "typical_duration": "8~16주",
        "oem_requirements": {
            "현대/기아": "SQ 포털 DFMEA 등록. 현대 연구소 설계 리뷰 참석. IMDS 자재 등록.",
            "GM": "DFMEA AIAG-VDA 통합 양식 사용. GM Drawing Standards 준수.",
            "VW": "VDA MLA Level 1-3. VDA Volume 4 (FMEA) 준수. IMDS 등록.",
        },
    },
    {
        "phase_id": "APQP-P3",
        "phase_number": 3,
        "name": "Process Design and Development",
        "name_ko": "공정 설계 및 개발",
        "description": "양산 공정을 설계하고, PFMEA를 통해 공정 리스크를 평가하며, 관리 계획서를 작성한다.",
        "key_activities": [
            "공정 흐름도(PFD) 작성",
            "배치도(Floor Plan Layout) 작성",
            "공정 FMEA (PFMEA) 작성",
            "양산 선행 관리 계획서(Pre-Launch CP) 작성",
            "공정 지시서/작업 표준서 작성",
            "MSA(측정시스템분석) 계획",
            "Cp/Cpk 목표 설정",
            "포장 사양 결정",
        ],
        "deliverables": [
            "Process Flow Diagram", "Floor Plan Layout",
            "PFMEA", "Pre-Launch Control Plan",
            "Work Instructions", "MSA Plan",
            "Packaging Specifications",
        ],
        "deliverables_ko": [
            "공정 흐름도", "배치도",
            "공정 FMEA", "양산 선행 관리 계획서",
            "작업 표준서", "MSA 계획",
            "포장 사양서",
        ],
        "gate_review_criteria": [
            "PFMEA 완료 및 고위험 항목 대책 수립",
            "설비/치공구 발주 완료",
            "관리 계획서 OEM 승인",
            "작업자 교육 계획 수립",
        ],
        "responsible_dept": ["생산기술팀", "품질관리팀", "연구소"],
        "typical_duration": "8~12주",
        "oem_requirements": {
            "현대/기아": "SQ 포털 PFMEA/CP 등록. 현대 SQ 심사 대응. 특별 특성 관리 방안 제출.",
            "GM": "GM PFMEA 양식. GP-12 Early Production Containment 준비.",
            "VW": "VDA MLA Level 4-5. VDA 6.3 공정 심사 준비. 특별 특성 D/TLD 관리.",
        },
    },
    {
        "phase_id": "APQP-P4",
        "phase_number": 4,
        "name": "Product and Process Validation",
        "name_ko": "제품 및 공정 유효성 확인",
        "description": "시험 생산(Trial Run)을 통해 공정 능력을 검증하고, PPAP 서류를 제출하여 양산 승인을 획득한다.",
        "key_activities": [
            "시험 생산(Significant Production Run)",
            "MSA(측정시스템분석) 실시",
            "초기 공정능력 조사 (Ppk/Cpk)",
            "제품 치수 검사 (Layout Inspection)",
            "재료/성능 시험",
            "양산 관리 계획서(Production CP) 확정",
            "PPAP 서류 작성 및 제출",
            "고객 승인 (PSW: Part Submission Warrant)",
        ],
        "deliverables": [
            "Trial Run Results", "MSA Results",
            "Initial Process Capability Study",
            "PPAP Package (Level 3)",
            "Production Control Plan",
            "PSW Approval",
        ],
        "deliverables_ko": [
            "시험 생산 결과", "MSA 결과",
            "초기 공정능력 조사",
            "PPAP 패키지 (Level 3)",
            "양산 관리 계획서",
            "PSW 승인",
        ],
        "gate_review_criteria": [
            "Ppk ≥ 1.67 달성 (특별 특성)",
            "MSA 합격 (GR&R < 10% 허용)",
            "PPAP 18개 항목 완비",
            "OEM PSW 승인 획득",
        ],
        "responsible_dept": ["품질관리팀", "생산기술팀"],
        "typical_duration": "4~8주",
        "oem_requirements": {
            "현대/기아": "PPAP Level 3 제출 (SQ 포털). 초물 100% 전수검사 3 lot. 라인 정지 시 즉시 보고.",
            "GM": "PPAP Level 3 + Run@Rate. GP-12 90일 강화관리. GSIP 등록.",
            "VW": "VDA MLA Level 6-7. VDA 2 (PPAP 대응). BMG 승인 절차.",
        },
    },
    {
        "phase_id": "APQP-P5",
        "phase_number": 5,
        "name": "Feedback, Assessment, and Corrective Action",
        "name_ko": "양산 및 피드백/시정조치",
        "description": "양산 개시 후 공정 안정화, 변동 축소, 고객 만족도 향상을 지속적으로 관리한다.",
        "key_activities": [
            "양산 초기 관리 (Run@Rate)",
            "산포 축소 활동 (Cpk 향상)",
            "고객 불만/클레임 분석 및 대응",
            "양산 관리 계획서 업데이트",
            "Lessons Learned 문서화",
            "SPC 관리도 운영",
            "연간 레이아웃 검사 (Annual Layout)",
            "지속적 개선 (CI) 활동",
        ],
        "deliverables": [
            "SPC Charts", "Customer Satisfaction Data",
            "Lessons Learned", "Updated Control Plan",
            "Annual Layout Inspection Results",
            "Corrective Action Reports (8D)",
        ],
        "deliverables_ko": [
            "SPC 관리도", "고객 만족도 데이터",
            "교훈 문서", "관리 계획서 업데이트",
            "연간 레이아웃 검사 결과",
            "시정조치 보고서 (8D)",
        ],
        "gate_review_criteria": [
            "양산 초기 3개월 Cpk ≥ 1.33 유지",
            "고객 클레임 0건 목표",
            "SPC 관리도 안정 상태 확인",
            "Lessons Learned 데이터베이스 등록",
        ],
        "responsible_dept": ["품질관리팀", "생산기술팀"],
        "typical_duration": "양산 개시 후 지속",
        "oem_requirements": {
            "현대/기아": "초물 3 lot 전수검사 후 정규 관리 전환. 클레임 발생 시 24h 내 D3 등록. SQ 월간 품질 회의.",
            "GM": "GP-12 해제 심사. CQI 특수공정 심사 (용접 CQI-15, 도장 CQI-12). 연간 레이아웃.",
            "VW": "VDA MLA Level 7 유지. VDA 6.3 정기 공정 심사. Formel-Q 등급 관리.",
        },
    },
]

# ─────────────────────────────────────────────
# APQP 산출물 체크리스트 (핵심 항목)
# ─────────────────────────────────────────────

_APQP_CHECKLIST = [
    {"item_id": "CK-001", "phase_id": "APQP-P1", "name": "Product Assurance Plan", "name_ko": "제품 보증 계획서", "description": "APQP 전체 일정, 마일스톤, 책임자, 리스크를 정의", "required_by": ["AIAG", "현대/기아"], "template_available": True, "responsible_dept": "품질관리팀", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-002", "phase_id": "APQP-P2", "name": "DFMEA", "name_ko": "설계 FMEA", "description": "설계 잠재 고장모드 분석. AIAG-VDA 통합 양식 사용", "required_by": ["AIAG", "현대/기아", "GM", "VW"], "template_available": True, "responsible_dept": "연구소", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-003", "phase_id": "APQP-P2", "name": "DVP&R", "name_ko": "설계 검증 계획 및 보고", "description": "설계 검증/타당성 확인 시험 계획 및 결과", "required_by": ["AIAG", "현대/기아", "GM"], "template_available": True, "responsible_dept": "연구소", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-004", "phase_id": "APQP-P3", "name": "PFMEA", "name_ko": "공정 FMEA", "description": "공정 잠재 고장모드 분석. Action Priority 기반 리스크 관리", "required_by": ["AIAG", "현대/기아", "GM", "VW"], "template_available": True, "responsible_dept": "생산기술팀", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-005", "phase_id": "APQP-P3", "name": "Control Plan", "name_ko": "관리 계획서", "description": "양산 공정의 관리 항목, 방법, 빈도, 대응 계획", "required_by": ["AIAG", "현대/기아", "GM", "VW"], "template_available": True, "responsible_dept": "품질관리팀", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-006", "phase_id": "APQP-P3", "name": "Process Flow Diagram", "name_ko": "공정 흐름도", "description": "전체 제조 공정의 순서도. 특별 특성 표시 포함", "required_by": ["AIAG", "현대/기아", "GM", "VW"], "template_available": True, "responsible_dept": "생산기술팀", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-007", "phase_id": "APQP-P4", "name": "MSA Study", "name_ko": "측정시스템분석", "description": "GR&R, 편의, 안정성, 선형성 분석", "required_by": ["AIAG", "현대/기아", "GM"], "template_available": True, "responsible_dept": "품질관리팀", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-008", "phase_id": "APQP-P4", "name": "Ppk/Cpk Study", "name_ko": "초기 공정능력 조사", "description": "특별 특성 기준 Ppk ≥ 1.67 / 일반 특성 Cpk ≥ 1.33", "required_by": ["AIAG", "현대/기아", "GM", "VW"], "template_available": True, "responsible_dept": "품질관리팀", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-009", "phase_id": "APQP-P4", "name": "PPAP Package", "name_ko": "PPAP 패키지", "description": "18개 항목 (Level 3 기준). PSW 포함", "required_by": ["AIAG", "현대/기아", "GM"], "template_available": True, "responsible_dept": "품질관리팀", "criticality": "critical", "ajin_status": "completed"},
    {"item_id": "CK-010", "phase_id": "APQP-P4", "name": "IMDS Registration", "name_ko": "IMDS 재료 등록", "description": "International Material Data System 소재 정보 등록", "required_by": ["현대/기아", "GM", "VW"], "template_available": False, "responsible_dept": "연구소", "criticality": "major", "ajin_status": "completed"},
    {"item_id": "CK-011", "phase_id": "APQP-P5", "name": "SPC Management", "name_ko": "SPC 관리도 운영", "description": "양산 중 특별 특성에 대한 통계적 공정 관리", "required_by": ["AIAG", "현대/기아", "GM"], "template_available": True, "responsible_dept": "품질관리팀", "criticality": "critical", "ajin_status": "in_progress"},
    {"item_id": "CK-012", "phase_id": "APQP-P5", "name": "Lessons Learned DB", "name_ko": "교훈 데이터베이스", "description": "프로젝트 종료 후 교훈 문서화 및 차기 프로젝트 반영", "required_by": ["AIAG", "현대/기아"], "template_available": True, "responsible_dept": "품질관리팀", "criticality": "minor", "ajin_status": "in_progress"},
]

# ─────────────────────────────────────────────
# APQP 관련 최근 업데이트
# ─────────────────────────────────────────────

_APQP_UPDATES = [
    {
        "update_id": "APQP-UPD-001",
        "source": "AIAG",
        "title": "AIAG APQP 3rd Edition 발행 (2024)",
        "description": "APQP 매뉴얼 3판 발행. AIAG-VDA FMEA 통합 양식 공식 채택, DFSS(Design for Six Sigma) 연계 강화, EV/전동화 부품 특별 요구사항 추가.",
        "affected_phases": ["APQP-P1", "APQP-P2", "APQP-P3"],
        "effective_date": "2024-06-01",
        "severity": "high",
        "required_actions": [
            "APQP 매뉴얼 3판 구매 및 관련 부서 배포",
            "DFMEA/PFMEA 양식을 AIAG-VDA 통합 양식으로 전환",
            "EV 배터리 케이스 APQP에 전동화 특별 요구사항 반영",
            "교육 계획 수립 (연구소, 품질관리팀, 생산기술팀)",
        ],
        "reference_url": "https://www.aiag.org/quality/automotive-core-tools/apqp",
    },
    {
        "update_id": "APQP-UPD-002",
        "source": "현대/기아_SQ",
        "title": "현대/기아 SQ 전동화 부품 APQP 가이드라인 신설 (2025)",
        "description": "EV 배터리 케이스, 모터 하우징 등 전동화 부품에 대한 별도 APQP 가이드라인 신설. 고전압 안전성, 방수성, EMC 특별 관리 요구.",
        "affected_phases": ["APQP-P2", "APQP-P3", "APQP-P4"],
        "effective_date": "2025-01-01",
        "severity": "high",
        "required_actions": [
            "전동화 부품 DFMEA에 고전압 안전성 항목 추가",
            "공정 흐름도에 절연 검사, 방수 시험 공정 반영",
            "PPAP에 EMC 시험 성적서 추가 제출",
            "경산 제2공장 EV 라인 APQP 문서 업데이트",
        ],
        "reference_url": "https://suppliers.hyundai.com/",
    },
    {
        "update_id": "APQP-UPD-003",
        "source": "VDA_MLA",
        "title": "VDA MLA (Maturity Level Assurance) 3rd Edition 개정 (2024)",
        "description": "VDA MLA 3판 개정. 소프트웨어 내장 부품의 성숙도 관리 요구사항 강화. Cybersecurity TARA 분석 연계.",
        "affected_phases": ["APQP-P1", "APQP-P2", "APQP-P3", "APQP-P4"],
        "effective_date": "2024-09-01",
        "severity": "medium",
        "required_actions": [
            "VDA MLA 3판 매뉴얼 구매",
            "소프트웨어 포함 부품 대상 MLA 체크리스트 업데이트",
            "VW향 프로젝트 MLA 보고서 양식 갱신",
        ],
        "reference_url": "https://webshop.vda.de/QMC/en/mla",
    },
    {
        "update_id": "APQP-UPD-004",
        "source": "AIAG",
        "title": "AIAG CQI-15 용접 공정 심사 개정 (2025)",
        "description": "CQI-15 특수공정 심사(용접) 5판 개정. 레이저 용접 관련 요구사항 대폭 추가. 아크 용접 AI 기반 모니터링 요구 신설.",
        "affected_phases": ["APQP-P3", "APQP-P4"],
        "effective_date": "2025-03-01",
        "severity": "medium",
        "required_actions": [
            "CQI-15 5판 기반 용접 공정 심사 체크리스트 갱신",
            "레이저 용접 라인(경산 제2공장) 공정 파라미터 검증",
            "용접 SPC 모니터링 시스템 업그레이드 검토",
        ],
        "reference_url": "https://www.aiag.org/quality/automotive-core-tools/cqi",
    },
]


class APQPCrawler:
    """APQP 연구개발 프로세스 크롤러

    APQP 5단계 프로세스의 최신 요구사항, OEM별 가이드라인,
    산출물 체크리스트, 최근 업데이트를 수집하고 관리한다.
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.data_dir / "apqp_process.json"

        self._phases: list[APQPPhase] = []
        self._checklists: list[APQPChecklist] = []
        self._updates: list[APQPUpdate] = []

    def crawl(self) -> APQPCrawlResult:
        """APQP 데이터를 수집한다.

        AIAG, 현대/기아 SQ, VDA 포털 등에서 최신 정보를 수집한다.
        현재는 마스터 데이터 + 최근 업데이트를 구축한다.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors = []

        # 단계 데이터
        phases = []
        for item in _APQP_PHASES:
            try:
                phases.append(APQPPhase(**item))
            except Exception as e:
                errors.append(f"Phase 파싱 오류: {e}")

        # 체크리스트 데이터
        checklists = []
        for item in _APQP_CHECKLIST:
            try:
                checklists.append(APQPChecklist(**item))
            except Exception as e:
                errors.append(f"Checklist 파싱 오류: {e}")

        # 업데이트 데이터
        updates = []
        for item in _APQP_UPDATES:
            try:
                updates.append(APQPUpdate(**item, crawled_at=now))
            except Exception as e:
                errors.append(f"Update 파싱 오류: {e}")

        self._phases = phases
        self._checklists = checklists
        self._updates = updates

        result = APQPCrawlResult(
            phases=phases,
            checklists=checklists,
            updates=updates,
            crawled_at=now,
            source="aiag_apqp_3rd + hyundai_sq + vda_mla",
            total_phases=len(phases),
            total_checklist_items=len(checklists),
            total_updates=len(updates),
            errors=errors,
        )

        self._save(result)
        return result

    def _save(self, result: APQPCrawlResult):
        """크롤링 결과를 JSON으로 저장한다."""
        data = {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_phases": result.total_phases,
            "total_checklist_items": result.total_checklist_items,
            "total_updates": result.total_updates,
            "phases": [asdict(p) for p in result.phases],
            "checklists": [asdict(c) for c in result.checklists],
            "updates": [asdict(u) for u in result.updates],
            "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"APQP 데이터 저장: {self.output_path}")

    def load(self) -> dict:
        """저장된 APQP 데이터를 로드한다."""
        if not self.output_path.exists():
            return {"phases": [], "checklists": [], "updates": []}
        with open(self.output_path, encoding="utf-8") as f:
            return json.load(f)

    def get_phase(self, phase_number: int) -> APQPPhase | None:
        """특정 단계 정보를 반환한다."""
        if not self._phases:
            self.crawl()
        for p in self._phases:
            if p.phase_number == phase_number:
                return p
        return None

    def get_checklist_by_phase(self, phase_id: str) -> list[APQPChecklist]:
        """특정 단계의 체크리스트를 반환한다."""
        if not self._checklists:
            self.crawl()
        return [c for c in self._checklists if c.phase_id == phase_id]

    def get_incomplete_items(self) -> list[APQPChecklist]:
        """미완료 체크리스트 항목을 반환한다."""
        if not self._checklists:
            self.crawl()
        return [c for c in self._checklists if c.ajin_status not in ("completed", "not_applicable")]

    def get_high_severity_updates(self) -> list[APQPUpdate]:
        """고위험 업데이트를 반환한다."""
        if not self._updates:
            self.crawl()
        return [u for u in self._updates if u.severity == "high"]

    def get_summary(self) -> dict:
        """APQP 현황 요약을 반환한다."""
        if not self._phases:
            self.crawl()
        return {
            "total_phases": len(self._phases),
            "total_checklist_items": len(self._checklists),
            "completed_items": len([c for c in self._checklists if c.ajin_status == "completed"]),
            "in_progress_items": len([c for c in self._checklists if c.ajin_status == "in_progress"]),
            "total_updates": len(self._updates),
            "high_severity_updates": len([u for u in self._updates if u.severity == "high"]),
        }
