"""Phase 5: 영향도 분석기

법규 변경 사항과 시설 DB를 매칭하여 영향도를 분석하고,
LLM을 사용하여 상세 영향 분석 보고서를 생성한다.
"""

from dataclasses import dataclass, field
from pathlib import Path

from features.compliance.crawler import RegulationChange
from features.compliance.facility_db import FacilityDB
from features.compliance.text_change_detector import ChangeDetector, ChangeAnalysis
from core.llm_client import get_llm


@dataclass
class ImpactReport:
    """영향 분석 보고서"""
    scenario_id: str
    title: str
    severity: str
    change_summary: str
    affected_plants: list[str]
    affected_processes: list[str]
    affected_workers: int
    affected_chemicals: list[str]
    affected_standards: list[str]
    required_actions: list[str]
    deadline: str
    estimated_cost: str
    llm_analysis: str = ""
    risk_score: float = 0.0


class ImpactAnalyzer:
    """법규 변경 영향도 분석기"""

    def __init__(self, facility_db: FacilityDB, prompts_dir: Path | None = None):
        self.db = facility_db
        self.detector = ChangeDetector()

        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "prompts"
        self._prompt_template = (prompts_dir / "impact_analysis.txt").read_text(
            encoding="utf-8"
        )

    def analyze(self, change: RegulationChange) -> ImpactReport:
        """법규 변경에 대한 영향도 분석 (규칙 기반)."""
        # 텍스트 변경 분석
        change_analysis = self.detector.detect(
            change.before_text, change.after_text
        )

        # 시설 DB에서 영향받는 항목 조회
        impact = self.db.get_impact_summary(
            standard_ids=change.affected_standard_ids,
            process_types=change.affected_process_types,
        )

        affected_plant_names = [p.name for p in impact["plants"]]
        affected_process_names = [p.name for p in impact["processes"]]

        # 영향받는 화학물질 조회
        affected_chemicals = []
        for proc in impact["processes"]:
            for chem_id in proc.chemicals_used:
                chem = self.db.chemicals.get(chem_id)
                if chem and chem.name not in affected_chemicals:
                    affected_chemicals.append(chem.name)

        # 영향받는 안전 기준
        affected_stds = []
        for sid in change.affected_standard_ids:
            std = self.db.standards.get(sid)
            if std:
                affected_stds.append(f"{std.name} ({std.current_limit})")

        # 위험 점수 계산
        risk_score = self._calculate_risk_score(
            change, impact, change_analysis
        )

        return ImpactReport(
            scenario_id=change.scenario_id,
            title=change.title,
            severity=change.severity,
            change_summary=change_analysis.summary,
            affected_plants=affected_plant_names,
            affected_processes=affected_process_names,
            affected_workers=impact["total_workers"],
            affected_chemicals=affected_chemicals,
            affected_standards=affected_stds,
            required_actions=change.required_actions,
            deadline=change.deadline,
            estimated_cost=change.estimated_cost,
            risk_score=risk_score,
        )

    async def analyze_with_llm(self, change: RegulationChange) -> ImpactReport:
        """LLM을 사용한 상세 영향 분석."""
        report = self.analyze(change)

        # LLM 프롬프트 구성
        facility_info = self._format_facility_info(report)
        change_detail = self._format_change_detail(change)

        prompt = (
            self._prompt_template
            .replace("{regulation_title}", change.title)
            .replace("{regulation_detail}", change_detail)
            .replace("{facility_info}", facility_info)
            .replace("{severity}", change.severity)
            .replace("{deadline}", change.deadline)
        )

        llm = get_llm(temperature=0.2)
        response = await llm.ainvoke(prompt)
        report.llm_analysis = response.content

        return report

    def _calculate_risk_score(
        self,
        change: RegulationChange,
        impact: dict,
        change_analysis: ChangeAnalysis,
    ) -> float:
        """위험 점수를 0~100 스케일로 계산한다."""
        score = 0.0

        # 심각도 기반 (40점)
        severity_scores = {"high": 40, "medium": 25, "low": 10}
        score += severity_scores.get(change.severity, 15)

        # 영향 범위 (30점)
        plant_score = min(impact["plant_count"] * 10, 15)
        worker_score = min(impact["total_workers"] / 50, 15)
        score += plant_score + worker_score

        # 변경 규모 (20점)
        change_score = min(change_analysis.total_changes * 5, 10)
        number_score = min(len(change_analysis.key_numbers_changed) * 5, 10)
        score += change_score + number_score

        # 시한 긴급성 (10점)
        if change.deadline:
            score += 10

        return min(score, 100)

    def _format_facility_info(self, report: ImpactReport) -> str:
        lines = []
        lines.append(f"영향 공장: {', '.join(report.affected_plants)}")
        lines.append(f"영향 공정: {', '.join(report.affected_processes)}")
        lines.append(f"영향 작업자: {report.affected_workers}명")
        if report.affected_chemicals:
            lines.append(f"관련 화학물질: {', '.join(report.affected_chemicals)}")
        if report.affected_standards:
            lines.append(f"관련 안전기준: {', '.join(report.affected_standards)}")
        return "\n".join(lines)

    def _format_change_detail(self, change: RegulationChange) -> str:
        lines = [
            f"법규: {change.regulation_name}",
            f"조항: {change.article}",
            f"관할: {change.authority}",
            f"분류: {change.category}",
            "",
            "[구법 내용]",
            change.before_text[:500],
            "",
            "[신법 내용]",
            change.after_text[:500],
            "",
            f"시행일: {change.after_date}",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────
# v1.6: 미국 무역 규제 영향 분석 함수
# ─────────────────────────────────────────────

def estimate_tariff_impact(tariff_rate: float = 0.25) -> dict:
    """25% 관세 적용 시 JOON INC / AJIN USA의 연간 추정 영향을 계산한다."""
    import_items = [
        {"item": "금형 (한국 수입)", "annual_import_usd": 5_000_000},
        {"item": "한국산 소재 (강판/알루미늄)", "annual_import_usd": 10_000_000},
        {"item": "전자 서브어셈블리", "annual_import_usd": 3_000_000},
    ]
    for item in import_items:
        item["tariff_rate"] = tariff_rate
        item["estimated_tariff_usd"] = int(item["annual_import_usd"] * tariff_rate)

    total_tariff_usd = sum(i["estimated_tariff_usd"] for i in import_items)
    return {
        "items": import_items,
        "total_tariff_usd": total_tariff_usd,
        "total_tariff_krw": total_tariff_usd * 1350,
        "tariff_rate": tariff_rate,
    }


def check_origin_compliance(part_data: dict | None = None) -> dict:
    """USMCA 역내가치 비율(RVC 75%) 준수 여부를 평가한다."""
    if part_data is None:
        # 기본 예시 데이터
        part_data = {
            "part_name": "EWP Assembly",
            "total_value_usd": 150,
            "us_content_usd": 90,
            "korea_content_usd": 45,
            "other_content_usd": 15,
        }
    total = part_data.get("total_value_usd", 1)
    us_content = part_data.get("us_content_usd", 0)
    rvc = (us_content / total) * 100 if total > 0 else 0
    threshold = 75.0

    return {
        "part_name": part_data.get("part_name", "Unknown"),
        "rvc_percent": round(rvc, 1),
        "threshold": threshold,
        "compliant": rvc >= threshold,
        "gap_percent": round(max(0, threshold - rvc), 1),
        "recommendation": "USMCA 기준 충족" if rvc >= threshold else f"역내가치 비율 {round(threshold - rvc, 1)}%p 부족 — 미국/캐나다/멕시코산 소재 비율 확대 필요",
    }


def generate_us_timeline(effective_date_str: str | None = None) -> dict:
    """미국 규제 시행일 기준 타임라인을 생성한다."""
    from datetime import date, datetime

    today = date.today()

    if effective_date_str:
        try:
            eff_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
        except ValueError:
            eff_date = today
    else:
        eff_date = today

    days_diff = (eff_date - today).days

    milestones = []
    if days_diff > 0:
        milestones.append({"event": "규제 시행일", "date": effective_date_str, "days": f"D-{days_diff}"})
        if days_diff > 90:
            milestones.append({"event": "대응 계획 수립 마감", "date": "", "days": f"D-{days_diff - 30}"})
        if days_diff > 30:
            milestones.append({"event": "현장 적용 완료 목표", "date": "", "days": "D-14"})
    else:
        milestones.append({"event": "규제 시행 완료", "date": effective_date_str, "days": f"D+{abs(days_diff)}"})

    return {
        "effective_date": effective_date_str,
        "days_until": days_diff,
        "status": "upcoming" if days_diff > 0 else "active",
        "milestones": milestones,
    }
