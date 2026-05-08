"""EU 규제 통합 크롤러

EU RoHS, ELV, 배터리 규정, CBAM, CLP 등
유럽 수출 관련 핵심 규제를 통합 관리한다.

데이터 소스:
- EUR-Lex (EU 관보)
- ECHA (유럽화학물질청)
- European Commission 공식 사이트
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EURegulation:
    """EU 규제 정보"""
    reg_id: str
    name: str
    name_ko: str
    category: str               # rohs, elv, battery, cbam, clp, csrd
    authority: str
    regulation_number: str      # e.g., "(EC) No 1907/2006"
    status: str                 # active, proposed, transitioning
    effective_date: str
    last_amended: str
    key_requirements: list[dict]
    penalties: str
    ajin_relevance: str
    affected_chemicals: list[str]
    affected_processes: list[str]
    compliance_status: str
    transition_deadlines: list[dict]  # [{date, requirement, status}]
    reference_url: str = ""
    crawled_at: str = ""


@dataclass
class EURegulationCrawlResult:
    """크롤링 결과"""
    regulations: list[EURegulation]
    crawled_at: str
    source: str
    total_count: int
    action_needed: int
    upcoming_deadlines: int
    errors: list[str] = field(default_factory=list)


_EU_REGULATIONS = [
    # ── RoHS ──
    {
        "reg_id": "EU-ROHS-001",
        "name": "Restriction of Hazardous Substances Directive",
        "name_ko": "유해물질 사용 제한 지침 (RoHS)",
        "category": "rohs",
        "authority": "European Commission",
        "regulation_number": "Directive 2011/65/EU (RoHS 2) + Delegated Directives",
        "status": "active",
        "effective_date": "2011-07-21",
        "last_amended": "2024-10-01",
        "key_requirements": [
            {"requirement": "6대 유해물질 사용 제한", "detail": "납(Pb) 1000ppm, 수은(Hg) 1000ppm, 카드뮴(Cd) 100ppm, 6가크롬(Cr6+) 1000ppm, PBB 1000ppm, PBDE 1000ppm + DEHP/BBP/DBP/DIBP(4P) 각 1000ppm", "ajin_impact": "CHEM-006 (6가 크롬) 직접 해당. 도금/표면처리 공정 소재 성분 관리."},
            {"requirement": "면제(Exemption) 조항 관리", "detail": "Annex III/IV 면제 항목별 유효기간 모니터링. Pack 23 재검토 진행 중 (2024~2025)", "ajin_impact": "자동차 부품 납 면제(Exemption 3) 연장 여부 모니터링. 만료 시 대체소재 전환 필요."},
            {"requirement": "기술문서 보관", "detail": "CE 적합성 선언, 기술문서 10년 보관 의무", "ajin_impact": "OEM 요청 시 RoHS 적합성 증빙 제출."},
        ],
        "penalties": "EU 각 회원국 자체 벌칙 적용. 독일: 최대 10만 유로 과태료. 시장 출시 금지/회수 명령.",
        "ajin_relevance": "유럽 수출 차량용 부품 전체 적용. 특히 표면처리 공정(6가 크롬), 전자부품 접합(납) 관련. IMDS 데이터 RoHS 준수 입증.",
        "affected_chemicals": ["CHEM-006"],
        "affected_processes": ["PRC-PAINT-01", "PRC-WELD-01", "PRC-WELD-02", "PRC-WELD-03"],
        "compliance_status": "action_needed",
        "transition_deadlines": [
            {"date": "2025-07-21", "requirement": "Pack 23 면제 재검토 결과 반영", "status": "monitoring"},
            {"date": "2025-12-31", "requirement": "Exemption 3(납) 연장 여부 확정 예정", "status": "monitoring"},
        ],
        "reference_url": "https://environment.ec.europa.eu/topics/waste-and-recycling/rohs-directive_en",
    },
    # ── ELV ──
    {
        "reg_id": "EU-ELV-001",
        "name": "End-of-Life Vehicles Regulation",
        "name_ko": "폐차 처리 규정 (ELV)",
        "category": "elv",
        "authority": "European Commission",
        "regulation_number": "Directive 2000/53/EC → Regulation (proposed 2023)",
        "status": "transitioning",
        "effective_date": "2000-10-21",
        "last_amended": "2023-07-13",
        "key_requirements": [
            {"requirement": "4대 유해물질 사용 금지", "detail": "납(Pb), 수은(Hg), 카드뮴(Cd), 6가크롬(Cr6+) — 농도 기준 초과 시 사용 금지 (면제 조항 있음)", "ajin_impact": "6가 크롬(CHEM-006) 직접 해당. Annex II 면제 조항 모니터링."},
            {"requirement": "재활용률 의무", "detail": "차량 중량 기준 재사용/재활용 85%, 회수 95% 달성", "ajin_impact": "차체 구조물 소재 선택 시 재활용성 고려. 복합소재 사용 제한 가능."},
            {"requirement": "디지털 제품 여권 (DPP)", "detail": "신규 규정안: 차량/부품별 소재 성분, 재활용 정보 디지털 제공 의무", "ajin_impact": "부품별 소재 성분 디지털 데이터 준비 필요. IMDS → DPP 전환 대비."},
            {"requirement": "재활용 소재 최소 함량", "detail": "신규 규정안: 철강 25%, 알루미늄 25%, 플라스틱 25% 재활용 소재 의무", "ajin_impact": "프레스 소재(SABC 강판) 재활용 철강 비율 증빙 필요."},
        ],
        "penalties": "EU 각 회원국 자체 벌칙. 시장 출시 금지, 형식 승인 취소 가능.",
        "ajin_relevance": "차체 구조물/서브프레임 직접 해당. 소재 성분 관리, 재활용성 설계(DfR) 반영 필요.",
        "affected_chemicals": ["CHEM-006"],
        "affected_processes": ["PRC-STAMP-01", "PRC-STAMP-02", "PRC-STAMP-03", "PRC-PAINT-01"],
        "compliance_status": "monitoring",
        "transition_deadlines": [
            {"date": "2025-Q4", "requirement": "신규 ELV Regulation 최종 채택 예정", "status": "monitoring"},
            {"date": "2028-01-01", "requirement": "디지털 제품 여권(DPP) 의무화 예상", "status": "pending"},
            {"date": "2030-01-01", "requirement": "재활용 소재 최소 함량 의무 시행 예상", "status": "pending"},
        ],
        "reference_url": "https://environment.ec.europa.eu/topics/waste-and-recycling/end-life-vehicles_en",
    },
    # ── 배터리 규정 ──
    {
        "reg_id": "EU-BATT-001",
        "name": "EU Battery Regulation",
        "name_ko": "EU 배터리 규정",
        "category": "battery",
        "authority": "European Commission",
        "regulation_number": "Regulation (EU) 2023/1542",
        "status": "active",
        "effective_date": "2023-08-17",
        "last_amended": "2023-08-17",
        "key_requirements": [
            {"requirement": "탄소 발자국 신고", "detail": "EV 배터리 탄소 발자국(Carbon Footprint) 신고 의무 (2025-02부터 단계 시행)", "ajin_impact": "배터리 케이스 제조 공정의 탄소 배출량 데이터 제공 필요."},
            {"requirement": "재활용 소재 최소 함량", "detail": "코발트 16%(2031), 납 85%(2031), 리튬 6%(2031), 니켈 6%(2031)", "ajin_impact": "배터리 케이스 소재(알루미늄/강판) 재활용 소재 비율 증빙."},
            {"requirement": "배터리 여권 (Battery Passport)", "detail": "2027년 2월부터 배터리별 디지털 여권 의무. QR코드 기반 정보 제공.", "ajin_impact": "배터리 케이스의 소재, 제조 이력, 탄소 발자국 정보 디지털 제공."},
            {"requirement": "공급망 실사 (Due Diligence)", "detail": "배터리 원자재 공급망 인권/환경 실사 의무", "ajin_impact": "철강/알루미늄 원자재 공급망 추적성 확보 필요."},
            {"requirement": "성능/내구성 기준", "detail": "배터리 최소 성능/수명 기준 설정", "ajin_impact": "케이스 구조 강도, 방수 성능이 배터리 수명에 영향."},
        ],
        "penalties": "회원국별 벌칙. 시장 출시 금지, 리콜 명령. 과태료 최대 매출액 비례.",
        "ajin_relevance": "경산 제2공장 EV 배터리 케이스 직접 해당. 탄소 발자국 데이터, 배터리 여권 정보 제공 의무.",
        "affected_chemicals": [],
        "affected_processes": ["PRC-STAMP-02", "PRC-LASER-01", "PRC-ASSY-02"],
        "compliance_status": "action_needed",
        "transition_deadlines": [
            {"date": "2025-02-18", "requirement": "탄소 발자국 신고 의무 시작 (EV 배터리)", "status": "action_needed"},
            {"date": "2025-08-18", "requirement": "배터리 내구성/성능 기준 적용", "status": "monitoring"},
            {"date": "2026-02-18", "requirement": "탄소 발자국 성능등급 표시 의무", "status": "pending"},
            {"date": "2027-02-18", "requirement": "배터리 여권(Battery Passport) 의무화", "status": "pending"},
            {"date": "2028-08-18", "requirement": "탄소 발자국 상한값 적용", "status": "pending"},
            {"date": "2031-08-18", "requirement": "재활용 소재 최소 함량 의무 적용", "status": "pending"},
        ],
        "reference_url": "https://eur-lex.europa.eu/eli/reg/2023/1542/oj",
    },
    # ── CBAM ──
    {
        "reg_id": "EU-CBAM-001",
        "name": "Carbon Border Adjustment Mechanism",
        "name_ko": "탄소국경조정메커니즘 (CBAM)",
        "category": "cbam",
        "authority": "European Commission",
        "regulation_number": "Regulation (EU) 2023/956",
        "status": "transitioning",
        "effective_date": "2023-10-01",
        "last_amended": "2023-10-01",
        "key_requirements": [
            {"requirement": "전환기간 보고 의무", "detail": "2023.10~2025.12 전환기간: 철강/알루미늄 등 수입 시 내재 탄소 배출량 분기별 보고", "ajin_impact": "유럽 수출 차량용 철강 부품에 간접 영향. OEM/무역상의 데이터 요청 대응."},
            {"requirement": "본격 시행 (CBAM 인증서 구매)", "detail": "2026년부터: 수입품의 내재 탄소 배출량에 대해 CBAM 인증서 구매 의무", "ajin_impact": "유럽 수출 물량에 대한 탄소 비용 추가 가능. 제조 공정 탄소 배출량 저감 인센티브."},
        ],
        "penalties": "미보고: CBAM 인증서 가격×3배 과태료. 인증서 미구매: 시장 접근 제한.",
        "ajin_relevance": "직접 수출 아닌 OEM 납품이므로 간접 영향. 그러나 OEM이 Scope 3 데이터 요구 시 대응 필요.",
        "affected_chemicals": [],
        "affected_processes": ["PRC-STAMP-01", "PRC-STAMP-02", "PRC-STAMP-03", "PRC-HOTSTAMP-01"],
        "compliance_status": "monitoring",
        "transition_deadlines": [
            {"date": "2025-12-31", "requirement": "전환기간 종료 (보고 의무만)", "status": "monitoring"},
            {"date": "2026-01-01", "requirement": "본격 시행 — CBAM 인증서 구매 의무", "status": "pending"},
        ],
        "reference_url": "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en",
    },
    # ── CLP ──
    {
        "reg_id": "EU-CLP-001",
        "name": "Classification, Labelling and Packaging Regulation",
        "name_ko": "분류·표시·포장 규정 (CLP)",
        "category": "clp",
        "authority": "ECHA",
        "regulation_number": "Regulation (EC) No 1272/2008",
        "status": "active",
        "effective_date": "2009-01-20",
        "last_amended": "2024-05-01",
        "key_requirements": [
            {"requirement": "화학물질 위험성 분류", "detail": "GHS 기반 위험성 분류, 경고표지, 안전보건자료(SDS) 작성 의무", "ajin_impact": "수출 제품에 사용된 화학물질의 EU CLP 분류 확인. MSDS 양식 EU 버전 관리."},
            {"requirement": "신규 위험성 분류 도입", "detail": "2024년 개정: 내분비계교란물질(ED), PBT/vPvB 분류 신설. Delegated Act 2024 적용.", "ajin_impact": "사용 화학물질 중 ED/PBT 해당 여부 확인 필요. 신규 분류 적용 유예기간 모니터링."},
        ],
        "penalties": "미분류/미표시: 회원국별 과태료. 시장 출시 제한.",
        "ajin_relevance": "EU 수출 시 화학물질 관련 서류 EU CLP 기준 준수. SDS(Safety Data Sheet) EU 양식 유지.",
        "affected_chemicals": ["CHEM-006", "CHEM-004", "CHEM-005", "CHEM-009"],
        "affected_processes": ["PRC-PAINT-01", "PRC-ASSY-02"],
        "compliance_status": "monitoring",
        "transition_deadlines": [
            {"date": "2026-05-01", "requirement": "신규 위험성 분류(ED, PMT 등) 물질/혼합물 적용", "status": "monitoring"},
        ],
        "reference_url": "https://echa.europa.eu/regulations/clp/understanding-clp",
    },
    # ── SCIP Database ──
    {
        "reg_id": "EU-SCIP-001",
        "name": "SCIP Database (Substances of Concern In articles as such or in complex objects Products)",
        "name_ko": "SCIP 데이터베이스 (완제품 내 유해물질 신고)",
        "category": "rohs",
        "authority": "ECHA",
        "regulation_number": "Waste Framework Directive (EU) 2018/851, Article 9(1)(i)",
        "status": "active",
        "effective_date": "2021-01-05",
        "last_amended": "2024-01-01",
        "key_requirements": [
            {"requirement": "SVHC 함유 완제품 SCIP 신고", "detail": "SVHC 0.1%(w/w) 초과 함유 완제품을 EU 시장에 출시 시 ECHA SCIP Database에 신고 의무", "ajin_impact": "6가 크롬(CHEM-006) 사용 부품의 SCIP 신고 해당 여부 확인. 현재 OEM이 신고 주체이나 데이터 제공 필요."},
        ],
        "penalties": "미신고: 회원국별 과태료.",
        "ajin_relevance": "CHEM-006(6가 크롬) 함유 표면처리 부품 대상. OEM에 SVHC 함유 정보 및 SCIP 데이터 제공.",
        "affected_chemicals": ["CHEM-006"],
        "affected_processes": ["PRC-PAINT-01"],
        "compliance_status": "action_needed",
        "transition_deadlines": [],
        "reference_url": "https://echa.europa.eu/scip-database",
    },
]


class EURegulationCrawler:
    """EU 규제 통합 크롤러"""

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.data_dir / "eu_regulations.json"
        self._regulations: list[EURegulation] = []

    def crawl(self) -> EURegulationCrawlResult:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors = []
        regulations = []
        for item in _EU_REGULATIONS:
            try:
                regulations.append(EURegulation(**item, crawled_at=now))
            except Exception as e:
                errors.append(f"파싱 오류 ({item.get('reg_id', '?')}): {e}")
        self._regulations = regulations

        all_deadlines = []
        for r in regulations:
            for d in r.transition_deadlines:
                if d["status"] in ("action_needed", "monitoring"):
                    all_deadlines.append(d)

        result = EURegulationCrawlResult(
            regulations=regulations, crawled_at=now,
            source="eur-lex.europa.eu + echa.europa.eu + ec.europa.eu",
            total_count=len(regulations),
            action_needed=sum(1 for r in regulations if r.compliance_status == "action_needed"),
            upcoming_deadlines=len(all_deadlines),
            errors=errors,
        )
        self._save(result)
        return result

    def _save(self, result: EURegulationCrawlResult):
        data = {
            "crawled_at": result.crawled_at, "source": result.source,
            "total_count": result.total_count, "action_needed": result.action_needed,
            "upcoming_deadlines": result.upcoming_deadlines,
            "regulations": [asdict(r) for r in result.regulations], "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> list[EURegulation]:
        if not self.output_path.exists():
            return []
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)
        return [EURegulation(**item) for item in data.get("regulations", [])]

    def get_action_needed(self) -> list[EURegulation]:
        if not self._regulations: self.crawl()
        return [r for r in self._regulations if r.compliance_status == "action_needed"]

    def get_upcoming_deadlines(self) -> list[dict]:
        if not self._regulations: self.crawl()
        deadlines = []
        for r in self._regulations:
            for d in r.transition_deadlines:
                deadlines.append({"regulation": r.name_ko, "reg_id": r.reg_id, **d})
        return sorted(deadlines, key=lambda x: x.get("date", "9999"))

    def get_summary(self) -> dict:
        if not self._regulations: self.crawl()
        return {
            "total": len(self._regulations),
            "by_category": {cat: len([r for r in self._regulations if r.category == cat])
                           for cat in set(r.category for r in self._regulations)},
            "action_needed": len([r for r in self._regulations if r.compliance_status == "action_needed"]),
            "monitoring": len([r for r in self._regulations if r.compliance_status == "monitoring"]),
        }
