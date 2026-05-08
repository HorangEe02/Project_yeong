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
    employees: list[EmployeeItem] = []


class TeamNode(BaseModel):
    name: str
    headcount: int


class DivisionNode(BaseModel):
    name: str
    headcount: int
    teams: list[TeamNode]


class OrgTreeResponse(BaseModel):
    """본부 → 팀 트리 + 헤드카운트 (활성 직원 기준)."""
    total: int
    divisions: list[DivisionNode]
