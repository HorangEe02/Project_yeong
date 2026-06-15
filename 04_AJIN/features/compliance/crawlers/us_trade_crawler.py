"""v1.6: 미국 무역/통상 규제 크롤러 — IRA, 관세, USMCA 등"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class USTradeRegulationChange:
    """미국 무역 규제 변경 사항"""
    id: str
    title: str
    regulation_name: str
    authority: str
    status: str
    effective_date: str | None
    severity: str
    summary: str
    impact_on_ajin: dict = field(default_factory=dict)
    monitoring_urls: list[str] = field(default_factory=list)
    applicable_plants: list[str] = field(default_factory=list)


class USTradeRegulationCrawler:
    """미국 무역 규제 크롤러

    현재: data/scenarios/us_trade_regulations.json에서 시나리오 로드
    향후: USTR, Federal Register, IRS API 연동 예정
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            from config import DATA_DIR
            data_dir = DATA_DIR
        self._scenarios_path = data_dir / "scenarios" / "us_trade_regulations.json"
        self._scenarios: list[USTradeRegulationChange] = []

    def crawl(self) -> dict:
        """규제 데이터를 로드하고 결과를 반환한다."""
        try:
            if not self._scenarios_path.exists():
                return {"status": "failed", "error": "us_trade_regulations.json not found", "total_count": 0}

            with open(self._scenarios_path, encoding="utf-8") as f:
                data = json.load(f)

            scenarios = data.get("scenarios", [])
            self._scenarios = [
                USTradeRegulationChange(
                    id=s["id"],
                    title=s["title"],
                    regulation_name=s.get("regulation_name", ""),
                    authority=s.get("authority", ""),
                    status=s.get("status", ""),
                    effective_date=s.get("effective_date"),
                    severity=s.get("severity", "medium"),
                    summary=s.get("summary", ""),
                    impact_on_ajin=s.get("impact_on_ajin", {}),
                    monitoring_urls=s.get("monitoring_urls", []),
                    applicable_plants=s.get("applicable_plants", []),
                )
                for s in scenarios
            ]

            return {
                "status": "success",
                "total_count": len(self._scenarios),
                "errors": [],
            }

        except Exception as e:
            return {"status": "failed", "error": str(e), "total_count": 0}

    def get_all_scenarios(self) -> list[USTradeRegulationChange]:
        """로드된 전체 시나리오 반환"""
        return self._scenarios

    def get_scenario(self, scenario_id: str) -> USTradeRegulationChange | None:
        """ID로 시나리오 조회"""
        return next((s for s in self._scenarios if s.id == scenario_id), None)

    def get_high_severity(self) -> list[USTradeRegulationChange]:
        """심각도 HIGH인 시나리오만 반환"""
        return [s for s in self._scenarios if s.severity == "high"]

    def estimate_tariff_impact(self) -> dict:
        """관세 영향 시뮬레이션 (US-TRADE-001 기반)"""
        tariff_items = [
            {"item": "금형 (한국 수입)", "annual_import_usd": 5_000_000, "tariff_rate": 0.25},
            {"item": "한국산 소재 (강판/알루미늄)", "annual_import_usd": 10_000_000, "tariff_rate": 0.25},
            {"item": "전자 서브어셈블리", "annual_import_usd": 3_000_000, "tariff_rate": 0.25},
        ]
        for item in tariff_items:
            item["estimated_tariff_usd"] = int(item["annual_import_usd"] * item["tariff_rate"])

        total_tariff = sum(i["estimated_tariff_usd"] for i in tariff_items)
        krw_rate = 1350  # approximate
        return {
            "items": tariff_items,
            "total_tariff_usd": total_tariff,
            "total_tariff_krw": total_tariff * krw_rate,
            "note": "25% 관세 시뮬레이션 (추정치)",
        }
