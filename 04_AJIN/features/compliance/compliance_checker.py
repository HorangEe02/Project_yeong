"""Phase 7: 규정 준수 확인기

사용자 질의에 대해 현행 규정 준수 상태를 확인하고,
LLM을 사용하여 맞춤형 답변을 생성한다.
"""

from dataclasses import dataclass
from pathlib import Path

from features.compliance.facility_db import FacilityDB
from features.compliance.crawler import ScenarioLoader
from core.llm_client import get_llm


@dataclass
class ComplianceResult:
    """규정 준수 확인 결과"""
    query: str
    answer: str
    relevant_standards: list[str]
    relevant_chemicals: list[str]
    compliance_status: str  # "compliant", "at_risk", "non_compliant", "unknown"
    source: str  # "facility_db", "llm", "both"


class ComplianceChecker:
    """규정 준수 확인기"""

    def __init__(
        self,
        facility_db: FacilityDB,
        scenario_loader: ScenarioLoader | None = None,
        prompts_dir: Path | None = None,
    ):
        self.db = facility_db
        self.scenarios = scenario_loader

        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "prompts"
        self._prompt_template = (prompts_dir / "compliance_check.txt").read_text(
            encoding="utf-8"
        )

    def check(self, query: str) -> ComplianceResult:
        """규칙 기반 규정 준수 확인."""
        query_lower = query.lower()

        # 관련 안전기준 검색
        relevant_stds = []
        for std in self.db.standards.values():
            if (std.category in query_lower
                or std.name in query
                or any(kw in query_lower for kw in self._get_keywords(std.category))):
                relevant_stds.append(std)

        # 관련 화학물질 검색
        relevant_chems = []
        for chem in self.db.chemicals.values():
            if chem.name in query or chem.chemical_id in query:
                relevant_chems.append(chem)
            elif any(kw in query_lower for kw in self._chem_keywords(chem)):
                relevant_chems.append(chem)

        # 기본 답변 구성
        answer_parts = []
        status = "unknown"

        if relevant_stds:
            for std in relevant_stds:
                procs = self.db.find_processes_by_standard(std.standard_id)
                proc_names = [p.name for p in procs]
                answer_parts.append(
                    f"[{std.name}]\n"
                    f"- 현행 기준: {std.current_limit}\n"
                    f"- 법적 근거: {std.regulation_basis}\n"
                    f"- 적용 공정: {', '.join(proc_names)}\n"
                    f"- 모니터링: {std.monitoring_frequency}"
                )
            status = "compliant"

        if relevant_chems:
            for chem in relevant_chems:
                procs = self.db.find_processes_by_chemical(chem.chemical_id)
                proc_names = [p.name for p in procs]
                svhc_note = " ⚠️ SVHC 후보물질" if chem.svhc_candidate else ""
                answer_parts.append(
                    f"[{chem.name}]{svhc_note}\n"
                    f"- CAS: {chem.cas_number}\n"
                    f"- REACH 상태: {chem.reach_status}\n"
                    f"- 사용 공정: {', '.join(proc_names)}\n"
                    f"- 연간 사용량: {chem.annual_usage_kg:,.0f}kg\n"
                    f"- 관련 규정: {', '.join(chem.regulations)}"
                )
                if chem.svhc_candidate:
                    status = "at_risk"

        answer = "\n\n".join(answer_parts) if answer_parts else ""

        return ComplianceResult(
            query=query,
            answer=answer,
            relevant_standards=[s.name for s in relevant_stds],
            relevant_chemicals=[c.name for c in relevant_chems],
            compliance_status=status,
            source="facility_db" if answer else "unknown",
        )

    async def check_with_llm(self, query: str) -> ComplianceResult:
        """LLM을 사용한 상세 규정 준수 확인."""
        base_result = self.check(query)

        # 시설 현황 정보
        facility_summary = self._build_facility_summary()

        # 최근 법규 변경 정보
        scenario_info = ""
        if self.scenarios:
            scenarios = self.scenarios.get_all_scenarios()
            if scenarios:
                parts = []
                for s in scenarios:
                    parts.append(f"- {s.title} (심각도: {s.severity}, 시행일: {s.deadline})")
                scenario_info = "\n".join(parts)

        prompt = (
            self._prompt_template
            .replace("{user_query}", query)
            .replace("{facility_summary}", facility_summary)
            .replace("{current_standards}", base_result.answer or "(관련 기준 없음)")
            .replace("{recent_changes}", scenario_info or "(최근 변경 없음)")
        )

        llm = get_llm(temperature=0.2)
        response = await llm.ainvoke(prompt)

        return ComplianceResult(
            query=query,
            answer=response.content,
            relevant_standards=base_result.relevant_standards,
            relevant_chemicals=base_result.relevant_chemicals,
            compliance_status=base_result.compliance_status,
            source="both" if base_result.answer else "llm",
        )

    def _build_facility_summary(self) -> str:
        lines = []
        lines.append(f"공장: {len(self.db.plants)}개")
        for p in self.db.plants.values():
            lines.append(f"  - {p.name} ({p.location}): {p.employee_count}명")
        lines.append(f"공정: {len(self.db.processes)}개")
        lines.append(f"화학물질: {len(self.db.chemicals)}개")
        svhc = self.db.find_chemicals_svhc()
        if svhc:
            lines.append(f"  ⚠️ SVHC 후보물질: {', '.join(c.name for c in svhc)}")
        lines.append(f"안전기준: {len(self.db.standards)}개")
        return "\n".join(lines)

    def _get_keywords(self, category: str) -> list[str]:
        keyword_map = {
            "noise": ["소음", "데시벨", "dB", "청력"],
            "press_safety": ["프레스", "안전거리", "방호장치", "끼임"],
            "welding_safety": ["용접", "흄", "아크", "감전"],
            "chemical": ["화학물질", "MSDS", "GHS", "유해물질"],
            "electrical": ["고전압", "감전", "절연", "배터리", "전기"],
            "fire": ["소방", "화재", "소화", "피난"],
            "painting": ["도장", "VOC", "환기", "유기용제"],
            "ergonomics": ["인체공학", "근골격", "작업자세", "중량물"],
        }
        return keyword_map.get(category, [])

    def _chem_keywords(self, chem) -> list[str]:
        keywords = []
        if "크롬" in chem.name:
            keywords.extend(["크롬", "chromium", "6가", "도금"])
        if "도장" in chem.name:
            keywords.extend(["도장", "도료", "페인트", "코팅"])
        if "가공유" in chem.name:
            keywords.extend(["가공유", "절삭유", "윤활유"])
        if "세정" in chem.name:
            keywords.extend(["세정", "세척", "탈지"])
        return keywords
