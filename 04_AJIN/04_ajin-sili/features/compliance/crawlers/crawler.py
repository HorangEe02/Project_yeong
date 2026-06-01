"""Phase 3: 법규 크롤러 + 시나리오 로더

실제 운영 모드에서는 법제처 API를 크롤링하고,
데모 모드에서는 시나리오 JSON을 로드한다.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RegulationChange:
    """법규 변경 정보"""
    scenario_id: str
    title: str
    description: str
    regulation_name: str
    article: str
    authority: str
    category: str
    before_text: str
    before_date: str
    after_text: str
    after_date: str
    severity: str
    impact_areas: list[str] = field(default_factory=list)
    affected_standard_ids: list[str] = field(default_factory=list)
    affected_process_types: list[str] = field(default_factory=list)
    deadline: str = ""
    required_actions: list[str] = field(default_factory=list)
    estimated_cost: str = ""
    reference_url: str = ""


class ScenarioLoader:
    """시나리오 JSON 파일에서 법규 변경 사항을 로드한다."""

    def __init__(self, scenarios_dir: Path):
        self.scenarios_dir = scenarios_dir
        self._scenarios: dict[str, RegulationChange] = {}
        self._load_all()

    def _load_all(self):
        if not self.scenarios_dir.exists():
            return

        for json_file in self.scenarios_dir.glob("scenario_*.json"):
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            change = self._parse_scenario(data)
            self._scenarios[change.scenario_id] = change

    def _parse_scenario(self, data: dict) -> RegulationChange:
        reg = data.get("regulation", {})
        detail = data.get("change_detail", {})
        before = detail.get("before", {})
        after = detail.get("after", {})

        return RegulationChange(
            scenario_id=data["scenario_id"],
            title=data["title"],
            description=data["description"],
            regulation_name=reg.get("name", ""),
            article=reg.get("article", ""),
            authority=reg.get("authority", ""),
            category=reg.get("category", ""),
            before_text=before.get("text", ""),
            before_date=before.get("effective_date", ""),
            after_text=after.get("text", ""),
            after_date=after.get("effective_date", ""),
            severity=data.get("severity", "medium"),
            impact_areas=data.get("impact_areas", []),
            affected_standard_ids=data.get("affected_facility_ids", []),
            affected_process_types=data.get("affected_process_types", []),
            deadline=data.get("deadline", ""),
            required_actions=data.get("required_actions", []),
            estimated_cost=data.get("estimated_cost", ""),
            reference_url=data.get("reference_url", ""),
        )

    def get_scenario(self, scenario_id: str) -> RegulationChange | None:
        return self._scenarios.get(scenario_id)

    def get_all_scenarios(self) -> list[RegulationChange]:
        return list(self._scenarios.values())

    @property
    def total_scenarios(self) -> int:
        return len(self._scenarios)


class LawCrawler:
    """법제처 오픈 API 크롤러 (프로토타입)

    실제 구현 시 법제처 Open API를 사용하여
    법규 변경 사항을 실시간으로 수집한다.
    프로토타입에서는 시나리오 모드를 사용한다.
    """

    BASE_URL = "https://www.law.go.kr/DRF/lawService.do"

    def __init__(self):
        self._cached_changes: list[RegulationChange] = []

    async def fetch_recent_changes(
        self, keywords: list[str] | None = None, days: int = 30
    ) -> list[RegulationChange]:
        """최근 법규 변경 사항을 조회한다.

        프로토타입: 빈 리스트를 반환한다.
        실제 구현 시 법제처 API 호출로 교체.
        """
        # TODO: 법제처 Open API 연동
        # params = {
        #     "OC": API_KEY,
        #     "target": "law",
        #     "type": "XML",
        #     "sort": "date",
        # }
        return self._cached_changes
