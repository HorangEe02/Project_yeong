"""
규제 리스크 정량 스코어링 엔진
- 위반 시 재무 영향 x 발생 가능성 x 시간 긴급도 = 종합 리스크 점수
- 100점 만점 기준 4단계 등급 (CRITICAL/HIGH/MEDIUM/LOW)
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Optional
import json
from pathlib import Path


@dataclass
class RiskScore:
    """리스크 평가 결과"""
    scenario_id: str
    title: str
    total_score: float          # 0~100
    grade: str                  # CRITICAL / HIGH / MEDIUM / LOW
    financial_impact: float     # 재무 영향 점수 (0~40)
    likelihood: float           # 발생 가능성 점수 (0~30)
    urgency: float              # 시간 긴급도 점수 (0~30)
    deadline: Optional[str] = None
    days_remaining: Optional[int] = None
    affected_plants: List[str] = field(default_factory=list)
    mitigation_status: str = "미착수"


# 심각도별 재무 영향 기본 점수
SEVERITY_FINANCIAL_MAP = {
    "critical": 40,
    "high": 32,
    "medium": 20,
    "low": 10,
}

# 규제 유형별 위반 시 과징금/손실 추정 (억 원)
PENALTY_ESTIMATES = {
    "EU REACH": {"min": 5, "max": 50, "type": "과징금 + 수출 금지"},
    "관세": {"min": 100, "max": 500, "type": "연간 추가 원가"},
    "IRA": {"min": 50, "max": 200, "type": "세액공제 미수령"},
    "USMCA": {"min": 30, "max": 150, "type": "관세 부과"},
    "OSHA": {"min": 1, "max": 10, "type": "과징금 + 조업중단"},
    "산안법": {"min": 1, "max": 20, "type": "과징금 + 형사처벌"},
    "소음": {"min": 0.5, "max": 5, "type": "과징금 + 개선명령"},
    "EV": {"min": 10, "max": 100, "type": "리콜 + 납품중단"},
    "CBAM": {"min": 5, "max": 30, "type": "탄소 비용"},
}


def calculate_risk_score(scenario: Dict) -> RiskScore:
    """개별 시나리오의 리스크 점수 산출"""
    scenario_id = scenario.get("scenario_id", scenario.get("id", ""))
    title = scenario.get("title", scenario.get("name", ""))
    severity = scenario.get("severity", "medium").lower()
    deadline_str = scenario.get("deadline", scenario.get("effective_date", ""))
    affected = scenario.get("affected_plants",
                scenario.get("affected_facility_ids",
                scenario.get("applicable_plants", [])))

    # 1) 재무 영향 점수 (0~40)
    financial = SEVERITY_FINANCIAL_MAP.get(severity, 15)
    for key, penalty in PENALTY_ESTIMATES.items():
        if key.lower() in title.lower():
            avg_penalty = (penalty["min"] + penalty["max"]) / 2
            if avg_penalty > 50:
                financial = min(40, financial + 8)
            elif avg_penalty > 10:
                financial = min(40, financial + 4)
            break

    # 2) 발생 가능성 점수 (0~30)
    likelihood = _estimate_likelihood(scenario)

    # 3) 시간 긴급도 점수 (0~30)
    urgency, days_remaining = _calculate_urgency(deadline_str)

    total = financial + likelihood + urgency

    if total >= 75:
        grade = "CRITICAL"
    elif total >= 55:
        grade = "HIGH"
    elif total >= 35:
        grade = "MEDIUM"
    else:
        grade = "LOW"

    return RiskScore(
        scenario_id=scenario_id,
        title=title,
        total_score=round(total, 1),
        grade=grade,
        financial_impact=round(financial, 1),
        likelihood=round(likelihood, 1),
        urgency=round(urgency, 1),
        deadline=deadline_str if deadline_str else None,
        days_remaining=days_remaining,
        affected_plants=affected if isinstance(affected, list) else [],
        mitigation_status=scenario.get("mitigation_status", "미착수"),
    )


def _estimate_likelihood(scenario: Dict) -> float:
    """발생 가능성 추정 (0~30)"""
    severity = scenario.get("severity", "medium").lower()
    base = {"critical": 25, "high": 20, "medium": 15, "low": 8}.get(severity, 12)
    status = scenario.get("status", "").lower()
    if "시행" in status or "enforced" in status or "active" in status:
        base = min(30, base + 5)
    return base


def _calculate_urgency(deadline_str: str) -> tuple:
    """시간 긴급도 산출 (0~30)"""
    if not deadline_str:
        return 10.0, None
    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        today = date.today()
        days = (deadline - today).days
        if days <= 0:
            return 30.0, days
        elif days <= 30:
            return 28.0, days
        elif days <= 90:
            return 24.0, days
        elif days <= 180:
            return 18.0, days
        elif days <= 365:
            return 12.0, days
        else:
            return 6.0, days
    except (ValueError, TypeError):
        return 10.0, None


def score_all_scenarios(scenarios_dir: str = "data/scenarios") -> List[RiskScore]:
    """전체 시나리오 리스크 스코어링"""
    scores = []
    scenarios_path = Path(scenarios_dir)
    if not scenarios_path.exists():
        return scores

    for json_file in scenarios_path.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    scores.append(calculate_risk_score(item))
            elif isinstance(data, dict):
                if "scenarios" in data:
                    for item in data["scenarios"]:
                        scores.append(calculate_risk_score(item))
                else:
                    scores.append(calculate_risk_score(data))
        except Exception:
            continue

    scores.sort(key=lambda x: x.total_score, reverse=True)
    return scores


def get_risk_summary(scores: List[RiskScore]) -> Dict:
    """리스크 요약 통계"""
    if not scores:
        return {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "avg_score": 0}

    nearest = None
    valid = [s for s in scores if s.days_remaining is not None]
    if valid:
        nearest = min(valid, key=lambda x: x.days_remaining)

    return {
        "total": len(scores),
        "critical": sum(1 for s in scores if s.grade == "CRITICAL"),
        "high": sum(1 for s in scores if s.grade == "HIGH"),
        "medium": sum(1 for s in scores if s.grade == "MEDIUM"),
        "low": sum(1 for s in scores if s.grade == "LOW"),
        "avg_score": round(sum(s.total_score for s in scores) / len(scores), 1),
        "top_risk": scores[0].title if scores else "",
        "nearest_deadline": nearest,
    }
