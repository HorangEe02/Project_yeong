"""기능 E (인사 관리) Pydantic 스키마.

backend/routers/admin.py 와 1:1 매핑.
React 프론트엔드(/admin/*) 가 소비하는 응답 형태를 정의한다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ───────────────────────────────────────────────────────────────
# 부서 트리
# ───────────────────────────────────────────────────────────────

class DepartmentNode(BaseModel):
    name: str
    prefix: str
    description: str = ""


class DivisionGroup(BaseModel):
    division: str
    departments: list[DepartmentNode]


class DepartmentTreeResponse(BaseModel):
    divisions: list[DivisionGroup]
    positions: list[str]
    roles: list[str]


# ───────────────────────────────────────────────────────────────
# 사용자 (목록/상세)
# ───────────────────────────────────────────────────────────────

class AdminUserItem(BaseModel):
    employee_id: str
    username: str
    department: str = ""
    division: str = ""
    position: str = ""
    role_name: str
    role_level: int
    email: str = ""
    phone: str = ""
    is_active: bool
    must_change_pw: bool = False
    last_login: str | None = None
    locked_until: str | None = None
    failed_attempts: int = 0
    hire_date: str = ""
    resign_date: str = ""


class AdminUserListResponse(BaseModel):
    total: int
    filtered: int
    users: list[AdminUserItem]


class LoginHistoryEntry(BaseModel):
    timestamp: str
    employee_id: str
    username: str = ""
    action: str = "login"
    success: bool
    ip_address: str = ""
    flag: str | None = None


class AdminUserDetailResponse(BaseModel):
    user: AdminUserItem
    recent_logins: list[LoginHistoryEntry] = Field(default_factory=list)


# ───────────────────────────────────────────────────────────────
# 계정 생성 / 수정
# ───────────────────────────────────────────────────────────────

class CreateEmployeeRequest(BaseModel):
    division: str
    department: str
    username: str = Field(min_length=1, max_length=40)
    position: str
    email: str = ""
    phone: str = ""
    hire_date: str = ""
    role_name: str = "EMPLOYEE"
    is_active: bool = True
    must_change_pw: bool = True


class CreateEmployeeResponse(BaseModel):
    employee_id: str
    username: str
    department: str
    role_name: str
    role_level: int
    initial_password: str
    must_change_pw: bool = True
    issuance_note: str = ""
    instructions_markdown: str


class UpdateUserRequest(BaseModel):
    username: str | None = None
    department: str | None = None
    position: str | None = None
    email: str | None = None
    phone: str | None = None
    role_name: str | None = None
    is_active: bool | None = None


class ResetPasswordResponse(BaseModel):
    employee_id: str
    initial_password: str
    must_change_pw: bool = True


class LockUserRequest(BaseModel):
    minutes: int = Field(default=30, ge=1, le=10_000)


# ───────────────────────────────────────────────────────────────
# 삭제 (Soft retire / Hard delete)
# ───────────────────────────────────────────────────────────────

class RetireResponse(BaseModel):
    retired: bool
    employee_id: str
    resign_date: str


class HardDeleteRequest(BaseModel):
    confirm_employee_id: str
    reason: str = ""


class HardDeleteResponse(BaseModel):
    deleted: bool
    employee_id: str
    cascaded: dict[str, int]


class EmployeeIDPreviewRequest(BaseModel):
    department: str


class EmployeeIDPreviewResponse(BaseModel):
    department: str
    prefix: str
    next_id: str
    sequence: int
    suggested_email: str
    suggested_initial_password: str


# ───────────────────────────────────────────────────────────────
# 보안 감사
# ───────────────────────────────────────────────────────────────

class SecurityAlertItem(BaseModel):
    alert_type: str  # brute_force / unusual_hour / inactive_access
    severity: str    # critical / warning / info
    title: str
    description: str
    employee_id: str = ""
    timestamp: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class SecurityAlertsResponse(BaseModel):
    period_hours: int
    alerts: list[SecurityAlertItem]
    summary: dict[str, int]  # {brute_force: 1, unusual_hour: 3, inactive_access: 0}


class LoginStatsResponse(BaseModel):
    days: int
    total_logins: int
    successful: int
    failed: int
    success_rate: float
    unique_users: int
    locked_accounts: int
    hour_distribution: list[dict[str, Any]]
    failed_trend: list[dict[str, Any]]


class LoginHistoryResponse(BaseModel):
    total: int
    history: list[LoginHistoryEntry]


# ───────────────────────────────────────────────────────────────
# AI 활용 분석
# ───────────────────────────────────────────────────────────────

class FeatureUsageRow(BaseModel):
    feature: str
    name: str
    count: int
    color: str = ""


class DepartmentUsageRow(BaseModel):
    department: str
    count: int


class HourlyUsageRow(BaseModel):
    hour: int
    count: int


class AnalyticsUsageResponse(BaseModel):
    days: int
    by_feature: list[FeatureUsageRow]
    by_department: list[DepartmentUsageRow]
    by_hour: list[HourlyUsageRow]


class HeatmapResponse(BaseModel):
    days: int
    departments: list[str]
    features: list[str]
    matrix: dict[str, dict[str, int]]


class DauResponse(BaseModel):
    days: int
    series: list[dict[str, Any]]  # [{date, dau}]


class RoiPerFeature(BaseModel):
    name: str
    count: int
    saved_min: int


class RoiResponse(BaseModel):
    period_days: int
    total_uses: int
    total_saved_minutes: int
    total_saved_hours: float
    saved_cost_krw: float
    saved_cost_display: str
    per_feature: dict[str, RoiPerFeature]


# ───────────────────────────────────────────────────────────────
# 인사 통계
# ───────────────────────────────────────────────────────────────

class HRSummaryResponse(BaseModel):
    total: int
    departments: int
    divisions: int
    plants: int
    leaders: int


class HeadcountRow(BaseModel):
    label: str
    count: int
    division: str | None = None
    dept_count: int | None = None


class HeadcountResponse(BaseModel):
    by: str  # division / department / position / plant
    rows: list[HeadcountRow]


class GenderResponse(BaseModel):
    distribution: dict[str, int]


class TenureRow(BaseModel):
    range: str
    count: int


class TenureResponse(BaseModel):
    rows: list[TenureRow]


class DivisionPositionMatrixResponse(BaseModel):
    divisions: list[str]
    positions: list[str]
    matrix: dict[str, dict[str, int]]


class OverseasStaffRow(BaseModel):
    name: str
    position: str
    department: str
    overseas_assignment: str


class OverseasResponse(BaseModel):
    rows: list[OverseasStaffRow]


# ───────────────────────────────────────────────────────────────
# 시스템 도구
# ───────────────────────────────────────────────────────────────

class AuditLogRow(BaseModel):
    timestamp: str
    employee_id: str = ""
    name: str = ""
    department: str = ""
    role: str = ""
    endpoint: str
    method: str = "GET"
    status_code: int = 200
    detail: str = ""
    ip_address: str = ""


class AuditLogResponse(BaseModel):
    total: int
    rows: list[AuditLogRow]


class SystemHealthResponse(BaseModel):
    auth_db_ok: bool
    employees_db_ok: bool
    audit_db_ok: bool
    seed_users: int
    active_sessions: int
