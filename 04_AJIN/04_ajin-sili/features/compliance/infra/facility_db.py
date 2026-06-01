"""시설/공정 데이터베이스 로더

plants.json, processes.json, chemicals.json, safety_standards.json을
로드하고, 법규 변경에 영향받는 항목을 조회한다.

JSON에 추가 필드가 있어도 에러 없이 로드한다 (미지원 필드는 무시).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Plant:
    plant_id: str
    name: str
    location: str
    established: str = ""
    main_products: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    employee_count: int = 0
    process_ids: list[str] = field(default_factory=list)
    area_sqm: int = 0
    major_customers: list[str] = field(default_factory=list)
    annual_capacity: str = ""
    # 조직 참조 문서 추가 필드
    name_short: str = ""
    is_headquarters: bool = False
    has_research_center: bool = False
    departments_onsite: list[str] = field(default_factory=list)
    ajinguard_zones: list[dict] = field(default_factory=list)
    area_land_sqm: int = 0
    area_land_pyeong: int = 0
    note: str = ""


@dataclass
class Process:
    process_id: str
    name: str
    plant_id: str
    type: str
    equipment: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)
    chemicals_used: list[str] = field(default_factory=list)
    safety_standards: list[str] = field(default_factory=list)
    workers: int = 0
    shift_pattern: str = ""
    automation_rate: float = 0.0


@dataclass
class Chemical:
    chemical_id: str
    name: str
    cas_number: str
    category: str
    hazard_class: list[str] = field(default_factory=list)
    ghs_pictograms: list[str] = field(default_factory=list)
    usage_processes: list[str] = field(default_factory=list)
    annual_usage_kg: float = 0.0
    storage_location: str = ""
    msds_version: str = ""
    regulations: list[str] = field(default_factory=list)
    reach_status: str = ""
    svhc_candidate: bool = False
    oel_ppm: float | None = None
    oel_mg_m3: float | None = None
    supplier: str = ""
    svhc_details: str = ""


@dataclass
class SafetyStandard:
    standard_id: str
    name: str
    category: str
    current_limit: str
    regulation_basis: str
    applicable_processes: list[str] = field(default_factory=list)
    last_review: str = ""
    monitoring_frequency: str = ""
    next_review: str = ""
    monitoring_method: str = ""
    ppe_required: list[str] = field(default_factory=list)
    responsible_dept: str = ""
    # 조직 참조 문서 추가 필드
    applicable_plants: list[str] = field(default_factory=list)
    alert_recipients: list[str] = field(default_factory=list)


def _safe_from_dict(cls, data: dict):
    """dataclass에 정의된 필드만 추출하여 인스턴스를 생성한다.
    JSON에 추가 필드가 있어도 무시한다."""
    import dataclasses
    valid_keys = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid_keys}
    return cls(**filtered)


class FacilityDB:
    """시설/공정 데이터베이스"""

    def __init__(self, db_dir: Path):
        self.plants: dict[str, Plant] = {}
        self.processes: dict[str, Process] = {}
        self.chemicals: dict[str, Chemical] = {}
        self.standards: dict[str, SafetyStandard] = {}
        self._load(db_dir)

    def _load(self, db_dir: Path):
        self._load_plants(db_dir / "plants.json")
        self._load_processes(db_dir / "processes.json")
        self._load_chemicals(db_dir / "chemicals.json")
        self._load_standards(db_dir / "safety_standards.json")

    def _load_plants(self, path: Path):
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # 자사 공장
        for item in data.get("plants", []):
            p = _safe_from_dict(Plant, item)
            self.plants[p.plant_id] = p
        # 국내 계열사
        for item in data.get("subsidiaries_domestic", []):
            p = _safe_from_dict(Plant, item)
            self.plants[p.plant_id] = p
        # 해외법인
        for item in data.get("subsidiaries_overseas", []):
            # 해외법인은 id → plant_id로 매핑
            mapped = {**item}
            if "id" in mapped and "plant_id" not in mapped:
                mapped["plant_id"] = mapped.pop("id")
            if "city" in mapped:
                mapped.setdefault("location", f"{mapped.get('country', '')} {mapped['city']}")
            elif "country" in mapped:
                mapped.setdefault("location", mapped["country"])
            mapped.setdefault("name", mapped.get("plant_id", ""))
            p = _safe_from_dict(Plant, mapped)
            self.plants[p.plant_id] = p

    def _load_processes(self, path: Path):
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("processes", []):
            p = _safe_from_dict(Process, item)
            self.processes[p.process_id] = p

    def _load_chemicals(self, path: Path):
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("chemicals", []):
            c = _safe_from_dict(Chemical, item)
            self.chemicals[c.chemical_id] = c

    def _load_standards(self, path: Path):
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("safety_standards", []):
            s = _safe_from_dict(SafetyStandard, item)
            self.standards[s.standard_id] = s

    def find_processes_by_type(self, process_type: str) -> list[Process]:
        """공정 유형으로 해당 공정 목록을 반환한다."""
        return [p for p in self.processes.values() if p.type == process_type]

    def find_processes_by_standard(self, standard_id: str) -> list[Process]:
        """안전기준 ID로 해당 공정 목록을 반환한다."""
        return [
            p for p in self.processes.values()
            if standard_id in p.safety_standards
        ]

    def find_processes_by_chemical(self, chemical_id: str) -> list[Process]:
        """화학물질 ID로 해당 공정 목록을 반환한다."""
        return [
            p for p in self.processes.values()
            if chemical_id in p.chemicals_used
        ]

    def find_chemicals_svhc(self) -> list[Chemical]:
        """SVHC 후보 물질 목록을 반환한다."""
        return [c for c in self.chemicals.values() if c.svhc_candidate]

    def find_plant_for_process(self, process_id: str) -> Plant | None:
        """공정 ID로 소속 공장을 반환한다."""
        proc = self.processes.get(process_id)
        if proc:
            return self.plants.get(proc.plant_id)
        return None

    def get_affected_workers(self, process_ids: list[str]) -> int:
        """영향받는 작업자 수를 합산한다."""
        return sum(
            self.processes[pid].workers
            for pid in process_ids
            if pid in self.processes
        )

    def get_impact_summary(
        self,
        standard_ids: list[str] | None = None,
        process_types: list[str] | None = None,
    ) -> dict:
        """법규 변경에 영향받는 시설 요약 정보를 반환한다."""
        affected_processes = []

        if standard_ids:
            for sid in standard_ids:
                affected_processes.extend(self.find_processes_by_standard(sid))

        if process_types:
            for ptype in process_types:
                for p in self.find_processes_by_type(ptype):
                    if p not in affected_processes:
                        affected_processes.append(p)

        affected_plant_ids = {p.plant_id for p in affected_processes}
        affected_plants = [
            self.plants[pid] for pid in affected_plant_ids if pid in self.plants
        ]
        total_workers = sum(p.workers for p in affected_processes)

        return {
            "plants": affected_plants,
            "processes": affected_processes,
            "total_workers": total_workers,
            "plant_count": len(affected_plants),
            "process_count": len(affected_processes),
        }
