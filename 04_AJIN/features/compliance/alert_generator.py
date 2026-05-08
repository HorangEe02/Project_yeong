"""Phase 6: 알림 생성기

영향 분석 결과를 바탕으로 심각도별 알림을 생성한다.
"""

from dataclasses import dataclass
from datetime import datetime

from features.compliance.impact_analyzer import ImpactReport


SEVERITY_ICONS = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}

SEVERITY_LABELS = {
    "high": "긴급",
    "medium": "주의",
    "low": "참고",
}


@dataclass
class Alert:
    """법규 변경 알림"""
    alert_id: str
    severity: str
    icon: str
    label: str
    title: str
    summary: str
    detail: str
    affected_info: str
    actions: str
    deadline: str
    created_at: str


class AlertGenerator:
    """영향 분석 결과를 알림으로 변환한다."""

    def __init__(self):
        self._alert_counter = 0

    def generate(self, report: ImpactReport) -> Alert:
        """ImpactReport로부터 Alert를 생성한다."""
        self._alert_counter += 1
        alert_id = f"ALT-{self._alert_counter:04d}"

        icon = SEVERITY_ICONS.get(report.severity, "⚪")
        label = SEVERITY_LABELS.get(report.severity, "정보")

        summary = self._build_summary(report)
        detail = self._build_detail(report)
        affected_info = self._build_affected_info(report)
        actions = self._build_actions(report)

        return Alert(
            alert_id=alert_id,
            severity=report.severity,
            icon=icon,
            label=label,
            title=report.title,
            summary=summary,
            detail=detail,
            affected_info=affected_info,
            actions=actions,
            deadline=report.deadline,
            created_at=datetime.now().isoformat(),
        )

    def _build_summary(self, report: ImpactReport) -> str:
        icon = SEVERITY_ICONS.get(report.severity, "⚪")
        label = SEVERITY_LABELS.get(report.severity, "정보")
        return (
            f"{icon} [{label}] {report.title}\n"
            f"영향: {len(report.affected_plants)}개 공장, "
            f"{len(report.affected_processes)}개 공정, "
            f"{report.affected_workers}명 작업자"
        )

    def _build_detail(self, report: ImpactReport) -> str:
        lines = [
            f"■ 변경 개요: {report.change_summary}",
            f"■ 심각도: {report.severity.upper()} (위험점수: {report.risk_score:.0f}/100)",
            f"■ 시행일: {report.deadline}",
            f"■ 예상 비용: {report.estimated_cost}",
        ]
        if report.llm_analysis:
            lines.append(f"\n■ AI 분석:\n{report.llm_analysis}")
        return "\n".join(lines)

    def _build_affected_info(self, report: ImpactReport) -> str:
        lines = []
        if report.affected_plants:
            lines.append(f"공장: {', '.join(report.affected_plants)}")
        if report.affected_processes:
            lines.append(f"공정: {', '.join(report.affected_processes)}")
        if report.affected_chemicals:
            lines.append(f"화학물질: {', '.join(report.affected_chemicals)}")
        if report.affected_standards:
            lines.append(f"안전기준: {', '.join(report.affected_standards)}")
        lines.append(f"작업자: {report.affected_workers}명")
        return "\n".join(lines)

    def _build_actions(self, report: ImpactReport) -> str:
        if not report.required_actions:
            return "필요 조치 사항 없음"
        lines = []
        for i, action in enumerate(report.required_actions, 1):
            lines.append(f"{i}. {action}")
        return "\n".join(lines)

    def format_alert_text(self, alert: Alert) -> str:
        """알림을 텍스트 형식으로 포맷한다."""
        border = "=" * 60
        return (
            f"\n{border}\n"
            f"{alert.summary}\n"
            f"{border}\n\n"
            f"{alert.detail}\n\n"
            f"[영향 범위]\n{alert.affected_info}\n\n"
            f"[필요 조치]\n{alert.actions}\n"
            f"{border}\n"
        )
