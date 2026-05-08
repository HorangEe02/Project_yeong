"""
SILI 데모용 시나리오 시뮬레이션 엔진 (v3.4)

실제 크롤러 대신 사전 준비된 Before/After JSON으로
법규 변경 감지 -> 리스크 스코어링 -> 시설 영향 매핑 파이프라인을 실행한다.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path


DATA_DIR = Path("data/demo_scenarios")


@dataclass
class DemoScenario:
    """데모 시나리오 정의"""
    id: str
    title: str
    category: str
    severity: str                    # CRITICAL / HIGH / MEDIUM
    summary: str
    description: str
    change_details: Dict[str, str]
    effective_date: str
    affected_plants: List[str]
    affected_departments: List[str]
    affected_products: List[str]
    required_actions: List[str]
    cost_impact: str = ""
    risk_score: int = 0
    days_until_effective: int = 0


DEMO_SCENARIOS: List[DemoScenario] = [
    DemoScenario(
        id="safety_distance",
        title="산업안전보건법 프레스 안전거리 기준 강화",
        category="산안법",
        severity="CRITICAL",
        summary="프레스 작업 시 안전거리 기준 300mm -> 400mm 강화",
        description=(
            "산업안전보건법 시행규칙 개정으로 프레스 작업 시 작업자와 위험 구역 간 "
            "최소 안전거리가 기존 300mm에서 400mm로 강화됩니다. "
            "최근 프레스 사고 증가에 따른 조치로, 기준 미달 라인은 "
            "안전장치를 보완하거나 라인 레이아웃을 변경해야 합니다."
        ),
        change_details={
            "법령": "산업안전보건법 시행규칙",
            "변경 전": "최소 안전거리 300mm",
            "변경 후": "최소 안전거리 400mm",
            "변경 유형": "기준 강화",
            "과태료": "500만 원 -> 1,000만 원 (상향)",
            "시행 유예": "6개월",
        },
        effective_date="2026-10-01",
        affected_plants=["경산 본사 제1공장", "경산 본사 제2공장", "경주 구어공장"],
        affected_departments=["안전보건팀", "생산관리팀", "생산기술팀"],
        affected_products=["DASH COMPL", "루프 패널", "플로어 패널"],
        required_actions=[
            "현행 프레스 라인 안전거리 전수 측정 (3개 공장 x 전 라인)",
            "기준 미달 라인 식별 및 안전장치 보완 계획 수립",
            "광커튼/양수조작식 안전장치 설치 또는 교체",
            "변경 후 작업자 안전 교육 실시 (전 프레스 작업자 대상)",
            "Control Plan 및 작업표준서에 변경 내용 반영",
        ],
        cost_impact="안전장치 교체 예상: 라인당 500~1,500만 원 x 해당 라인 수",
        risk_score=85,
    ),
    DemoScenario(
        id="us_tariff_25",
        title="미국 자동차 부품 관세 25% 부과",
        category="관세",
        severity="HIGH",
        summary="트럼프 행정부 자동차 부품 관세 25% -- HMGMA 공급 원가 직격",
        description=(
            "미국 통상 정책에 따라 자동차 및 자동차 부품에 25% 관세가 부과됩니다. "
            "아진산업은 조지아 공장(JOON INC)을 통해 HMGMA에 EWP, CCH 등을 공급하고 있으며, "
            "한국에서 미국으로 수출하는 부품에 직접적인 원가 영향이 발생합니다."
        ),
        change_details={
            "규제": "미국 자동차 관세",
            "변경 전": "관세율 0%",
            "변경 후": "관세율 25%",
            "적용 범위": "자동차 부품 (HS 8708)",
            "아진산업 영향": "한국->미국 수출 부품 전량 대상",
        },
        effective_date="2026-07-01",
        affected_plants=["JOON INC (Georgia)", "경산 본사 제1공장"],
        affected_departments=["기술영업팀", "해외지원팀", "원가기획팀", "구매팀"],
        affected_products=["EWP (전동 워터 펌프)", "CCH (냉각수 히터)", "OBC 케이스", "범퍼빔"],
        required_actions=[
            "한국->미국 수출 부품 목록 및 금액 산정 (원가기획팀)",
            "조지아 현지 생산 전환 가능 품목 검토 (생산기술팀+해외지원팀)",
            "현지 조달률(Local Content) 향상 방안 수립",
            "HMGMA와 원가 협의 일정 조율 (기술영업팀)",
            "IRA 보조금 적용 가능 품목 확인 (해외지원팀)",
        ],
        cost_impact="관세 25% 적용 시 연간 원가 영향 약 400억 원 (6품목 기준)",
        risk_score=78,
    ),
    DemoScenario(
        id="reach_svhc_update",
        title="EU REACH SVHC 후보 목록 신규 등재 (크롬산)",
        category="EU_REACH",
        severity="MEDIUM",
        summary="크롬산(CAS: 7738-94-5) SVHC 후보 목록 신규 등재 -- 도금 공정 영향",
        description=(
            "EU ECHA에서 크롬산(Chromic acid)을 SVHC 후보 목록에 신규 등재. "
            "현재는 후보 등재 단계로 즉시 금지는 아니지만, 향후 인가 대상(Annex XIV) 지정 시 사용 제한. "
            "경산 공장 도금 공정에서 해당 물질 사용 중으로 대체 약품 검토 필요."
        ),
        change_details={
            "규제": "EU REACH SVHC 후보 목록",
            "물질": "크롬산 (Chromic acid, CAS: 7738-94-5)",
            "변경 전": "SVHC 후보 목록 235종",
            "변경 후": "SVHC 후보 목록 237종 (+2종 신규)",
            "현재 단계": "후보 목록 등재 (즉시 규제 아님)",
            "향후 전망": "인가 대상 지정 시 사용 제한 가능",
        },
        effective_date="2027-01-01",
        affected_plants=["경산 본사 제1공장"],
        affected_departments=["ESG경영팀", "구매팀", "품질경영팀"],
        affected_products=["도금 처리 부품 전반"],
        required_actions=[
            "경산 공장 도금 공정 크롬산 사용량 확인",
            "대체 약품 후보 조사 및 공급업체 협의",
            "MSDS(물질안전보건자료) 업데이트",
            "EU 수출 부품 REACH 적합성 선언서 재검토",
        ],
        cost_impact="대체 약품 전환 비용 + 공정 검증 비용 (추정 필요)",
        risk_score=52,
    ),
]


class DemoScenarioEngine:
    """데모 시나리오 시뮬레이션 엔진"""

    def __init__(self):
        self.scenarios = {s.id: s for s in DEMO_SCENARIOS}
        self._update_days()
        self._ensure_demo_data()

    def _update_days(self):
        today = datetime.now().date()
        for s in self.scenarios.values():
            try:
                eff = datetime.strptime(s.effective_date, "%Y-%m-%d").date()
                s.days_until_effective = max(0, (eff - today).days)
            except ValueError:
                s.days_until_effective = 0

    def _ensure_demo_data(self):
        """JSON 데이터 파일이 없으면 자동 생성"""
        if DATA_DIR.exists() and len(list(DATA_DIR.glob("*.json"))) >= 6:
            return
        generate_demo_data()

    def get_all_scenarios(self) -> List[DemoScenario]:
        return sorted(self.scenarios.values(), key=lambda s: s.risk_score, reverse=True)

    def get_scenario(self, scenario_id: str) -> Optional[DemoScenario]:
        return self.scenarios.get(scenario_id)

    def run_simulation(self, scenario_id: str) -> Dict:
        start = time.time()
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return {"error": f"시나리오 '{scenario_id}'를 찾을 수 없습니다."}

        result: Dict = {
            "scenario": scenario,
            "diff_result": None,
            "risk_result": None,
            "plant_mapping": None,
            "execution_time_ms": 0,
        }

        # 1) Before/After diff (JSON 파일 또는 내장 데이터)
        before_path = DATA_DIR / f"before_{scenario_id}.json"
        after_path = DATA_DIR / f"after_{scenario_id}.json"
        if before_path.exists() and after_path.exists():
            try:
                with open(before_path, encoding="utf-8") as f:
                    before = json.load(f)
                with open(after_path, encoding="utf-8") as f:
                    after = json.load(f)
                from features.compliance.change_detector import detect_changes
                diff = detect_changes(
                    scenario.category,
                    before.get("items", [before]),
                    after.get("items", [after]),
                )
                result["diff_result"] = {"changes": diff, "source": "json_diff"}
            except Exception:
                result["diff_result"] = {"changes": scenario.change_details, "source": "builtin"}
        else:
            result["diff_result"] = {"changes": scenario.change_details, "source": "builtin"}

        # 2) 리스크 스코어
        result["risk_result"] = {
            "score": scenario.risk_score,
            "severity": scenario.severity,
            "cost_impact": scenario.cost_impact,
            "days_remaining": scenario.days_until_effective,
        }

        # 3) 시설 매핑
        result["plant_mapping"] = {
            "affected_plants": scenario.affected_plants,
            "affected_count": len(scenario.affected_plants),
            "affected_departments": scenario.affected_departments,
            "affected_products": scenario.affected_products,
        }

        result["execution_time_ms"] = int((time.time() - start) * 1000)
        return result

    def get_summary_for_dashboard(self) -> Dict:
        scenarios = self.get_all_scenarios()
        critical = sum(1 for s in scenarios if s.severity == "CRITICAL")
        high = sum(1 for s in scenarios if s.severity == "HIGH")
        medium = sum(1 for s in scenarios if s.severity == "MEDIUM")

        most_urgent = min(scenarios, key=lambda s: s.days_until_effective) if scenarios else None
        highest_risk = scenarios[0] if scenarios else None

        return {
            "total_scenarios": len(scenarios),
            "critical_count": critical,
            "high_count": high,
            "medium_count": medium,
            "most_urgent": most_urgent,
            "highest_risk": highest_risk,
            "scenarios": scenarios,
        }


def generate_demo_data():
    """Before/After JSON 데이터 파일 생성"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 산안법 안전거리
    _write(DATA_DIR / "before_safety_distance.json", {
        "regulation_type": "domestic_safety", "title": "산업안전보건법 시행규칙",
        "items": [{"id": "KOSHA-PRESS-001", "subject": "프레스 작업 안전거리",
                   "current_standard": "300mm", "penalty": "과태료 500만 원 이하",
                   "last_updated": "2024-01-01"}],
        "crawled_at": "2026-03-01T09:00:00",
    })
    _write(DATA_DIR / "after_safety_distance.json", {
        "regulation_type": "domestic_safety", "title": "산업안전보건법 시행규칙 (개정)",
        "items": [{"id": "KOSHA-PRESS-001", "subject": "프레스 작업 안전거리",
                   "current_standard": "400mm", "penalty": "과태료 1,000만 원 이하 (상향)",
                   "effective_date": "2026-10-01",
                   "change_reason": "프레스 작업 중 사고 증가에 따른 안전 기준 강화"}],
        "crawled_at": "2026-04-01T09:00:00",
    })

    # 미국 관세
    _write(DATA_DIR / "before_us_tariff.json", {
        "regulation_type": "trade", "title": "미국 자동차 부품 관세",
        "items": [{"id": "US-TARIFF-AUTO", "subject": "자동차 부품 관세 (HS 8708)",
                   "current_rate": "0%", "status": "면제 적용 중"}],
        "crawled_at": "2026-03-01T09:00:00",
    })
    _write(DATA_DIR / "after_us_tariff.json", {
        "regulation_type": "trade", "title": "미국 자동차 부품 관세 (변경)",
        "items": [{"id": "US-TARIFF-AUTO", "subject": "자동차 부품 관세 (HS 8708)",
                   "current_rate": "25%", "effective_date": "2026-07-01",
                   "estimated_annual_impact": "약 400억 원 (아진산업 기준)"}],
        "crawled_at": "2026-04-01T09:00:00",
    })

    # EU REACH SVHC
    _write(DATA_DIR / "before_reach_svhc.json", {
        "regulation_type": "eu_reach", "title": "EU REACH SVHC 후보 목록",
        "items": [{"id": "ECHA-SVHC-LIST", "subject": "SVHC 후보 물질 목록",
                   "total_substances": 235, "last_updated": "2025-12-01"}],
        "crawled_at": "2026-03-01T09:00:00",
    })
    _write(DATA_DIR / "after_reach_svhc.json", {
        "regulation_type": "eu_reach", "title": "EU REACH SVHC 후보 목록 (갱신)",
        "items": [{"id": "ECHA-SVHC-LIST", "subject": "SVHC 후보 물질 목록",
                   "total_substances": 237,
                   "new_additions": ["크롬산 (CAS: 7738-94-5)", "크롬산 나트륨 (CAS: 7775-11-3)"],
                   "effective_date": "2027-01-01"}],
        "crawled_at": "2026-04-01T09:00:00",
    })


def _write(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
