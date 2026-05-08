"""기능 D: 법규/규정 업데이트 모니터링

시나리오 모드(데모)와 실시간 모드(운영)를 지원하는
법규 변경 감지 → 영향 분석 → 알림 생성 파이프라인.

크롤러 목록:
- ISO 국제규격 표준 크롤러
- APQP 연구개발 프로세스 크롤러
- MSDS 유해물질 크롤러
- 국내법규 통합 크롤러 (산안법, 중대재해, 환경법 등)
- EU 규제 통합 크롤러 (RoHS, ELV, 배터리규정, CBAM 등)
- OEM 품질기준 크롤러 (SQ, CQI, BIQS, Formel-Q)
- 탄소/ESG 크롤러 (CBAM, CSRD, 탄소중립)
- EV 배터리 안전 크롤러 (UN GTR 20, R100, IEC)
- 미국/중국 규제 크롤러 (IRA, TSCA, 중국REACH)
"""

from pathlib import Path

from features.compliance.crawler import ScenarioLoader, LawCrawler, RegulationChange
from features.compliance.facility_db import FacilityDB
from features.compliance.text_change_detector import ChangeDetector
from features.compliance.impact_analyzer import ImpactAnalyzer, ImpactReport
from features.compliance.alert_generator import AlertGenerator, Alert
from features.compliance.compliance_checker import ComplianceChecker
from features.compliance.iso_crawler import ISOCrawler
from features.compliance.apqp_crawler import APQPCrawler
from features.compliance.msds_crawler import MSDSCrawler
from features.compliance.domestic_law_crawler import DomesticLawCrawler
from features.compliance.eu_regulation_crawler import EURegulationCrawler
from features.compliance.oem_quality_crawler import OEMQualityCrawler
from features.compliance.carbon_esg_crawler import CarbonESGCrawler
from features.compliance.ev_battery_crawler import EVBatteryCrawler
from features.compliance.global_trade_crawler import GlobalTradeCrawler


class CompliancePipeline:
    """법규/규정 모니터링 통합 파이프라인"""

    def __init__(
        self,
        facility_db_dir: Path | None = None,
        scenarios_dir: Path | None = None,
    ):
        base = Path(__file__).parent.parent.parent
        if facility_db_dir is None:
            facility_db_dir = base / "data" / "facility_db"
        if scenarios_dir is None:
            scenarios_dir = base / "data" / "scenarios"

        self.db = FacilityDB(facility_db_dir)
        self.scenario_loader = ScenarioLoader(scenarios_dir)
        self.crawler = LawCrawler()
        self.detector = ChangeDetector()
        self.analyzer = ImpactAnalyzer(self.db)
        self.alert_gen = AlertGenerator()
        self.checker = ComplianceChecker(self.db, self.scenario_loader)

        # 추가 크롤러
        crawled_dir = base / "data" / "crawled"
        self.iso_crawler = ISOCrawler(crawled_dir)
        self.apqp_crawler = APQPCrawler(crawled_dir)
        self.msds_crawler = MSDSCrawler(crawled_dir)
        self.domestic_law_crawler = DomesticLawCrawler(crawled_dir)
        self.eu_regulation_crawler = EURegulationCrawler(crawled_dir)
        self.oem_quality_crawler = OEMQualityCrawler(crawled_dir)
        self.carbon_esg_crawler = CarbonESGCrawler(crawled_dir)
        self.ev_battery_crawler = EVBatteryCrawler(crawled_dir)
        self.global_trade_crawler = GlobalTradeCrawler(crawled_dir)

    def run_scenario(self, scenario_id: str) -> dict:
        """시나리오 모드: 특정 시나리오를 실행하고 결과를 반환한다."""
        change = self.scenario_loader.get_scenario(scenario_id)
        if not change:
            return {"error": f"시나리오 {scenario_id}를 찾을 수 없습니다."}

        # 변경 감지
        change_analysis = self.detector.detect(
            change.before_text, change.after_text
        )

        # 영향 분석
        report = self.analyzer.analyze(change)

        # 알림 생성
        alert = self.alert_gen.generate(report)

        return {
            "scenario_id": scenario_id,
            "change_analysis": change_analysis,
            "impact_report": report,
            "alert": alert,
            "alert_text": self.alert_gen.format_alert_text(alert),
        }

    async def run_scenario_with_llm(self, scenario_id: str) -> dict:
        """시나리오 모드 + LLM 분석."""
        change = self.scenario_loader.get_scenario(scenario_id)
        if not change:
            return {"error": f"시나리오 {scenario_id}를 찾을 수 없습니다."}

        change_analysis = self.detector.detect(
            change.before_text, change.after_text
        )

        report = await self.analyzer.analyze_with_llm(change)
        alert = self.alert_gen.generate(report)

        return {
            "scenario_id": scenario_id,
            "change_analysis": change_analysis,
            "impact_report": report,
            "alert": alert,
            "alert_text": self.alert_gen.format_alert_text(alert),
        }

    def run_all_scenarios(self) -> list[dict]:
        """모든 시나리오를 실행하고 결과 목록을 반환한다."""
        results = []
        for scenario in self.scenario_loader.get_all_scenarios():
            result = self.run_scenario(scenario.scenario_id)
            results.append(result)
        return results

    def check_compliance(self, query: str) -> dict:
        """규정 준수 확인 (규칙 기반)."""
        result = self.checker.check(query)
        return {
            "query": result.query,
            "answer": result.answer,
            "status": result.compliance_status,
            "standards": result.relevant_standards,
            "chemicals": result.relevant_chemicals,
            "source": result.source,
        }

    async def check_compliance_with_llm(self, query: str) -> dict:
        """규정 준수 확인 (LLM 포함)."""
        result = await self.checker.check_with_llm(query)
        return {
            "query": result.query,
            "answer": result.answer,
            "status": result.compliance_status,
            "standards": result.relevant_standards,
            "chemicals": result.relevant_chemicals,
            "source": result.source,
        }

    def get_facility_overview(self) -> dict:
        """시설 현황 요약을 반환한다."""
        return {
            "plants": len(self.db.plants),
            "processes": len(self.db.processes),
            "chemicals": len(self.db.chemicals),
            "standards": len(self.db.standards),
            "scenarios": self.scenario_loader.total_scenarios,
            "svhc_chemicals": [
                c.name for c in self.db.find_chemicals_svhc()
            ],
        }

    # ── ISO 국제규격 표준 ──

    def crawl_iso_standards(self) -> dict:
        """ISO 국제규격 표준 데이터를 수집한다."""
        result = self.iso_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "updates_found": result.updates_found,
            "standards": [
                {
                    "id": s.standard_id,
                    "title_ko": s.title_ko,
                    "status": s.status,
                    "category": s.category,
                    "latest_amendment": s.latest_amendment,
                    "transition_deadline": s.transition_deadline,
                    "changes_summary": s.changes_summary,
                }
                for s in result.standards
            ],
            "errors": result.errors,
        }

    def check_iso_certification_gaps(self) -> list[dict]:
        """공장 인증과 최신 ISO 표준을 비교하여 갭을 분석한다."""
        all_gaps = []
        for plant in self.db.plants.values():
            gaps = self.iso_crawler.check_certification_gaps(plant.certifications)
            for gap in gaps:
                gap["plant_id"] = plant.plant_id
                gap["plant_name"] = plant.name
            all_gaps.extend(gaps)
        return all_gaps

    # ── APQP 연구개발 프로세스 ──

    def crawl_apqp_process(self) -> dict:
        """APQP 프로세스 데이터를 수집한다."""
        result = self.apqp_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_phases": result.total_phases,
            "total_checklist_items": result.total_checklist_items,
            "total_updates": result.total_updates,
            "phases": [
                {
                    "phase_id": p.phase_id,
                    "name_ko": p.name_ko,
                    "deliverables_ko": p.deliverables_ko,
                    "responsible_dept": p.responsible_dept,
                }
                for p in result.phases
            ],
            "updates": [
                {
                    "update_id": u.update_id,
                    "source": u.source,
                    "title": u.title,
                    "severity": u.severity,
                    "effective_date": u.effective_date,
                    "required_actions": u.required_actions,
                }
                for u in result.updates
            ],
            "summary": self.apqp_crawler.get_summary(),
            "errors": result.errors,
        }

    def get_apqp_incomplete_items(self) -> list[dict]:
        """APQP 미완료 체크리스트 항목을 반환한다."""
        items = self.apqp_crawler.get_incomplete_items()
        return [
            {
                "item_id": c.item_id,
                "phase_id": c.phase_id,
                "name_ko": c.name_ko,
                "criticality": c.criticality,
                "status": c.ajin_status,
                "responsible_dept": c.responsible_dept,
            }
            for c in items
        ]

    # ── MSDS 유해물질 ──

    def crawl_msds_data(self) -> dict:
        """MSDS 유해물질 데이터를 수집한다."""
        result = self.msds_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_records": result.total_records,
            "updates_needed": result.updates_needed,
            "svhc_alerts": result.svhc_alerts,
            "chemicals_needing_update": [
                {
                    "chemical_id": r.chemical_id,
                    "name_ko": r.substance_name_ko,
                    "current_version": r.msds_version,
                    "latest_version": r.msds_latest_version,
                    "supplier": r.supplier,
                }
                for r in result.records if r.msds_update_needed
            ],
            "svhc_affected": [
                {
                    "substance": s.substance_name,
                    "cas_number": s.cas_number,
                    "reason": s.reason_for_inclusion,
                    "sunset_date": s.sunset_date,
                    "affected_chemicals": s.affected_chemicals,
                    "required_actions": s.required_actions,
                }
                for s in result.svhc_updates if s.ajin_affected
            ],
            "summary": self.msds_crawler.get_summary(),
            "errors": result.errors,
        }

    def get_msds_cmr_chemicals(self) -> list[dict]:
        """CMR 분류 화학물질 목록을 반환한다."""
        records = self.msds_crawler.get_cmr_chemicals()
        return [
            {
                "chemical_id": r.chemical_id,
                "name_ko": r.substance_name_ko,
                "cas_number": r.cas_number,
                "cmr_classification": r.cmr_classification,
                "oel_twa_mg_m3": r.oel_twa_mg_m3,
                "regulations_kr": r.regulations_kr,
            }
            for r in records
        ]

    # ── 국내법규 ──

    def crawl_domestic_laws(self) -> dict:
        """국내 법규 데이터를 수집한다."""
        result = self.domestic_law_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "action_needed": result.action_needed,
            "laws": [
                {
                    "law_id": law.law_id,
                    "name": law.name,
                    "category": law.category,
                    "authority": law.authority,
                    "compliance_status": law.compliance_status,
                    "amendment_summary": law.amendment_summary,
                }
                for law in result.laws
            ],
            "summary": self.domestic_law_crawler.get_summary(),
            "errors": result.errors,
        }

    def get_domestic_law_actions(self) -> list[dict]:
        """조치가 필요한 국내 법규 목록을 반환한다."""
        laws = self.domestic_law_crawler.get_action_needed()
        return [
            {
                "law_id": law.law_id,
                "name": law.name,
                "category": law.category,
                "compliance_status": law.compliance_status,
                "penalties": law.penalties,
            }
            for law in laws
        ]

    # ── EU 규제 ──

    def crawl_eu_regulations(self) -> dict:
        """EU 규제 데이터를 수집한다."""
        result = self.eu_regulation_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "regulations": [
                {
                    "reg_id": r.reg_id,
                    "name": r.name,
                    "name_ko": r.name_ko,
                    "category": r.category,
                    "compliance_status": r.compliance_status,
                    "effective_date": r.effective_date,
                }
                for r in result.regulations
            ],
            "upcoming_deadlines": self.eu_regulation_crawler.get_upcoming_deadlines(),
            "summary": self.eu_regulation_crawler.get_summary(),
            "errors": result.errors,
        }

    def get_eu_regulation_actions(self) -> list[dict]:
        """조치가 필요한 EU 규제 목록을 반환한다."""
        regs = self.eu_regulation_crawler.get_action_needed()
        return [
            {
                "reg_id": r.reg_id,
                "name": r.name,
                "name_ko": r.name_ko,
                "compliance_status": r.compliance_status,
            }
            for r in regs
        ]

    # ── OEM 품질기준 ──

    def crawl_oem_quality(self) -> dict:
        """OEM 품질기준 데이터를 수집한다."""
        result = self.oem_quality_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "standards": [
                {
                    "standard_id": s.standard_id,
                    "name": s.name,
                    "name_ko": s.name_ko,
                    "category": s.category,
                    "ajin_relevance": s.ajin_relevance,
                }
                for s in result.standards
            ],
            "summary": self.oem_quality_crawler.get_summary(),
            "errors": result.errors,
        }

    def get_oem_standards_by_oem(self, oem: str) -> list[dict]:
        """특정 OEM의 품질기준 목록을 반환한다."""
        standards = self.oem_quality_crawler.get_by_oem(oem)
        return [
            {
                "standard_id": s.standard_id,
                "name": s.name,
                "name_ko": s.name_ko,
                "category": s.category,
            }
            for s in standards
        ]

    # ── 탄소/ESG ──

    def crawl_carbon_esg(self) -> dict:
        """탄소/ESG 규제 데이터를 수집한다."""
        result = self.carbon_esg_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "regulations": [
                {
                    "regulation_id": r.regulation_id,
                    "name": r.name,
                    "name_ko": r.name_ko,
                    "category": r.category,
                    "ajin_readiness": r.ajin_readiness,
                }
                for r in result.regulations
            ],
            "upcoming_deadlines": self.carbon_esg_crawler.get_upcoming_deadlines(),
            "summary": self.carbon_esg_crawler.get_summary(),
            "errors": result.errors,
        }

    # ── EV 배터리 안전 ──

    def crawl_ev_battery(self) -> dict:
        """EV 배터리 안전 규격 데이터를 수집한다."""
        result = self.ev_battery_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "action_needed": result.action_needed,
            "standards": [
                {
                    "standard_id": s.standard_id,
                    "name": s.name,
                    "name_ko": s.name_ko,
                    "category": s.category,
                    "ajin_compliance_status": s.ajin_compliance_status,
                    "transition_deadline": s.transition_deadline,
                }
                for s in result.standards
            ],
            "upcoming_deadlines": self.ev_battery_crawler.get_upcoming_deadlines(),
            "summary": self.ev_battery_crawler.get_summary(),
            "errors": result.errors,
        }

    def get_ev_battery_actions(self) -> list[dict]:
        """조치가 필요한 EV 배터리 규격 목록을 반환한다."""
        standards = self.ev_battery_crawler.get_action_needed()
        return [
            {
                "standard_id": s.standard_id,
                "name": s.name,
                "name_ko": s.name_ko,
                "ajin_compliance_status": s.ajin_compliance_status,
                "action_items": s.action_items_ko,
            }
            for s in standards
        ]

    # ── 미국/중국 규제 ──

    def crawl_global_trade(self) -> dict:
        """미국/중국 글로벌 무역 규제 데이터를 수집한다."""
        result = self.global_trade_crawler.crawl()
        return {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "action_needed": result.action_needed,
            "regulations": [
                {
                    "regulation_id": r.regulation_id,
                    "name": r.name,
                    "name_ko": r.name_ko,
                    "country": r.country,
                    "category": r.category,
                    "ajin_compliance_status": r.ajin_compliance_status,
                }
                for r in result.regulations
            ],
            "summary": self.global_trade_crawler.get_summary(),
            "errors": result.errors,
        }

    def get_global_trade_by_country(self, country: str) -> list[dict]:
        """특정 국가의 무역 규제 목록을 반환한다."""
        regs = self.global_trade_crawler.get_by_country(country)
        return [
            {
                "regulation_id": r.regulation_id,
                "name": r.name,
                "name_ko": r.name_ko,
                "ajin_compliance_status": r.ajin_compliance_status,
            }
            for r in regs
        ]

    # ── 통합 크롤링 ──

    def crawl_all(self) -> dict:
        """전체 크롤러를 실행한다 (9개 크롤러)."""
        return {
            "iso": self.crawl_iso_standards(),
            "apqp": self.crawl_apqp_process(),
            "msds": self.crawl_msds_data(),
            "domestic_law": self.crawl_domestic_laws(),
            "eu_regulation": self.crawl_eu_regulations(),
            "oem_quality": self.crawl_oem_quality(),
            "carbon_esg": self.crawl_carbon_esg(),
            "ev_battery": self.crawl_ev_battery(),
            "global_trade": self.crawl_global_trade(),
        }
