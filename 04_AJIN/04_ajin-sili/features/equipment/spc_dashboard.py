"""
SPC 공정 건강 상태 대시보드 (v3.4)

5개 공정의 Nelson Rule 위반 + Cpk 예측을 통합하여
공정별 건강 상태를 한 눈에 표시하는 대시보드 데이터 제공.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class ProcessHealth:
    """단일 공정의 건강 상태"""
    process_id: str
    process_name: str
    status: str = "good"          # "good" / "warning" / "critical"
    current_cpk: float = 0.0
    cpk_trend: str = "stable"     # "improving" / "stable" / "declining" / "critical_decline"
    violation_count: int = 0
    violated_rules: List[int] = field(default_factory=list)
    risk_level: str = "normal"    # "critical" / "warning" / "normal"
    anomaly_rate: float = 0.0


class SPCDashboard:
    """SPC 공정 건강 상태 대시보드"""

    DATA_DIR = Path("data/spc_ml")

    def __init__(self):
        self._health_cache: Optional[List[ProcessHealth]] = None

    def get_all_process_health(self) -> List[ProcessHealth]:
        """5공정 전체 건강 상태를 분석하여 반환"""
        if self._health_cache is not None:
            return self._health_cache

        from features.equipment.spc_realtime import analyze_nelson_rules
        from features.equipment.spc_ml_predictor import PROCESS_SPECS, run_spc_ml_analysis

        results = []
        for process_id, spec in PROCESS_SPECS.items():
            csv_path = self.DATA_DIR / f"{process_id}.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path)
                values = df["value"].values.tolist()

                # Nelson Rules 분석
                nelson_result = analyze_nelson_rules(
                    values,
                    spec_upper=spec.get("usl"),
                    spec_lower=spec.get("lsl"),
                    process_name=spec.get("name", process_id),
                )

                violated_rules = list({v.rule_number for v in nelson_result.violations})
                violation_count = nelson_result.violation_count

                # ML 분석 (Cpk 예측)
                current_cpk = 0.0
                cpk_trend = "stable"
                anomaly_rate = 0.0
                risk_level = "normal"

                try:
                    ml_result = run_spc_ml_analysis(
                        process_id,
                        values=np.array(values),
                        usl=spec.get("usl"),
                        lsl=spec.get("lsl"),
                    )
                    if ml_result:
                        current_cpk = ml_result.cpk_prediction.current_cpk
                        cpk_trend = ml_result.cpk_prediction.trend
                        anomaly_rate = ml_result.anomaly_rate
                        risk_level = ml_result.risk_level
                except Exception:
                    # ML 분석 실패 시 기본 Cpk 계산
                    arr = np.array(values)
                    mean, std = arr.mean(), arr.std()
                    if std > 0:
                        usl = spec.get("usl", mean + 3 * std)
                        lsl = spec.get("lsl", mean - 3 * std)
                        current_cpk = min(usl - mean, mean - lsl) / (3 * std)

                # 종합 상태 판정
                has_high_violation = any(
                    v.severity == "critical" for v in nelson_result.violations
                )
                if has_high_violation or current_cpk < 1.0 or risk_level == "critical":
                    status = "critical"
                elif violation_count > 0 or current_cpk < 1.33 or risk_level == "warning":
                    status = "warning"
                else:
                    status = "good"

                results.append(ProcessHealth(
                    process_id=process_id,
                    process_name=spec.get("name", process_id),
                    status=status,
                    current_cpk=round(current_cpk, 3),
                    cpk_trend=cpk_trend,
                    violation_count=violation_count,
                    violated_rules=sorted(violated_rules),
                    risk_level=risk_level,
                    anomaly_rate=round(anomaly_rate, 1),
                ))

            except Exception:
                results.append(ProcessHealth(
                    process_id=process_id,
                    process_name=spec.get("name", process_id),
                    status="warning",
                    risk_level="warning",
                ))

        self._health_cache = results
        return results

    def get_summary(self) -> dict:
        """전체 공정 건강 요약"""
        health_list = self.get_all_process_health()
        critical = sum(1 for h in health_list if h.status == "critical")
        warning = sum(1 for h in health_list if h.status == "warning")
        good = sum(1 for h in health_list if h.status == "good")
        total_violations = sum(h.violation_count for h in health_list)

        return {
            "total_processes": len(health_list),
            "critical": critical,
            "warning": warning,
            "good": good,
            "total_violations": total_violations,
            "health_list": health_list,
        }
