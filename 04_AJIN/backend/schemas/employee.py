"""직원 검색 관련 Pydantic 스키마."""

from pydantic import BaseModel


class EmployeeSearchRequest(BaseModel):
    query: str


class EmployeeItem(BaseModel):
    name: str = ""
    department: str = ""
    division: str = ""
    position: str = ""
    email: str = ""
    phone: str = ""
    extension: str = ""
    plant: str = ""
    # Sprint 1 P0 (Feature A §4.4) — 합성 데이터 시각 구분.
    # 1 = seed/시연 / 0 = ERP·LDAP 실데이터 / None = 미정 (마이그레이션 전 row)
    is_synthetic: int | None = None
    data_class: str = "unknown"
    source_system: str = "unknown"
    source_label: str = ""


class EmployeeSearchResponse(BaseModel):
    mode: str = ""  # "person" | "department" | "position" | "stats"
    results: list[EmployeeItem] = []
    message: str = ""
    formatted_markdown: str = ""
    total: int = 0


class EmployeeListResponse(BaseModel):
    """부서/본부 단위 전체 인원 목록."""
    scope: str = ""        # "department" | "division"
    name: str = ""          # 부서명 또는 본부명
    total: int = 0          # 가시성 필터 후 반환된 인원 수
    masked: int = 0         # PARTIAL (필드 마스킹) 처리 인원
    excluded: int = 0       # HIDDEN 처리되어 제외된 인원
    real_count: int = 0
    synthetic_count: int = 0
    system_count: int = 0
    employees: list[EmployeeItem] = []


class TeamNode(BaseModel):
    name: str
    headcount: int
    real_count: int = 0
    synthetic_count: int = 0


class DivisionNode(BaseModel):
    name: str
    headcount: int
    real_count: int = 0
    synthetic_count: int = 0
    teams: list[TeamNode]


class OrgTreeResponse(BaseModel):
    """본부 → 팀 트리 + 헤드카운트 (활성 직원 기준)."""
    total: int
    real_count: int = 0
    synthetic_count: int = 0
    system_count: int = 0
    divisions: list[DivisionNode]
