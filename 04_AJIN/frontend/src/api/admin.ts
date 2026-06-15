// admin.ts — 기능 E (인사 관리) API 클라이언트.
// backend/routers/admin.py 와 1:1 매핑. JWT 자동 주입은 client.ts 인터셉터.

import { api } from './client';

// ─────────────────────────────────────────────────────────────
// 부서 트리
// ─────────────────────────────────────────────────────────────

export interface DepartmentNode {
  name: string;
  prefix: string;
  description: string;
}

export interface DivisionGroup {
  division: string;
  departments: DepartmentNode[];
}

export interface DepartmentTreeResponse {
  divisions: DivisionGroup[];
  positions: string[];
  roles: string[];
}

export async function fetchDepartmentTree(): Promise<DepartmentTreeResponse> {
  const { data } = await api.get<DepartmentTreeResponse>('/admin/departments');
  return data;
}

// ─────────────────────────────────────────────────────────────
// 사용자 목록 / 상세
// ─────────────────────────────────────────────────────────────

export interface AdminUserItem {
  employee_id: string;
  username: string;
  department: string;
  division: string;
  position: string;
  role_name: string;
  role_level: number;
  email: string;
  phone: string;
  is_active: boolean;
  must_change_pw: boolean;
  last_login: string | null;
  locked_until: string | null;
  failed_attempts: number;
  hire_date: string;
  resign_date: string;
}

export interface AdminUserListResponse {
  total: number;
  filtered: number;
  users: AdminUserItem[];
}

export interface UserListFilters {
  division?: string;
  department?: string;
  position?: string;
  role_name?: string;
  status?: 'active' | 'inactive' | 'locked' | 'retired' | 'all';
  q?: string;
  limit?: number;
  offset?: number;
}

export async function fetchUsers(filters: UserListFilters = {}): Promise<AdminUserListResponse> {
  const { data } = await api.get<AdminUserListResponse>('/admin/users', { params: filters });
  return data;
}

export interface LoginHistoryEntry {
  timestamp: string;
  employee_id: string;
  username: string;
  action: string;
  success: boolean;
  ip_address: string;
  flag?: string | null;
  // v4.9 — 선택 필드 (backend 확장 시 활성). 미응답 시 SecurityTab 부서·역할 필터 미노출.
  department?: string | null;
  role_name?: string | null;
}

export interface AdminUserDetailResponse {
  user: AdminUserItem;
  recent_logins: LoginHistoryEntry[];
}

export async function fetchUserDetail(employeeId: string): Promise<AdminUserDetailResponse> {
  const { data } = await api.get<AdminUserDetailResponse>(`/admin/users/${encodeURIComponent(employeeId)}`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// 사용자 수정 / 잠금 / 비밀번호 재설정
// ─────────────────────────────────────────────────────────────

export interface UpdateUserRequest {
  username?: string;
  department?: string;
  position?: string;
  email?: string;
  phone?: string;
  role_name?: string;
  is_active?: boolean;
}

export async function updateUser(employeeId: string, req: UpdateUserRequest): Promise<{ updated: number }> {
  const { data } = await api.put(`/admin/users/${encodeURIComponent(employeeId)}`, req);
  return data;
}

export interface ResetPasswordResponse {
  employee_id: string;
  initial_password: string;
  must_change_pw: boolean;
  credential_delivery?: 'local_plaintext' | 'idp_invite_required' | string;
  issuance_note?: string;
}

export async function resetPassword(employeeId: string): Promise<ResetPasswordResponse> {
  const { data } = await api.post<ResetPasswordResponse>(
    `/admin/users/${encodeURIComponent(employeeId)}/reset-password`,
  );
  return data;
}

export async function lockUser(employeeId: string, minutes = 30): Promise<{ locked: boolean; locked_until: string }> {
  const { data } = await api.post(`/admin/users/${encodeURIComponent(employeeId)}/lock`, { minutes });
  return data;
}

export async function unlockUser(employeeId: string): Promise<{ unlocked: boolean }> {
  const { data } = await api.post(`/admin/users/${encodeURIComponent(employeeId)}/unlock`);
  return data;
}

// ─────────────────────────────────────────────────────────────
// 삭제 (Soft retire / Hard delete)
// ─────────────────────────────────────────────────────────────

export interface RetireResponse {
  retired: boolean;
  employee_id: string;
  resign_date: string;
}

export async function retireUser(employeeId: string): Promise<RetireResponse> {
  const { data } = await api.delete<RetireResponse>(
    `/admin/users/${encodeURIComponent(employeeId)}/retire`,
  );
  return data;
}

export interface HardDeleteResponse {
  deleted: boolean;
  employee_id: string;
  cascaded: { login_history: number; password_history: number };
}

export async function hardDeleteUser(employeeId: string, reason = ''): Promise<HardDeleteResponse> {
  const { data } = await api.delete<HardDeleteResponse>(
    `/admin/users/${encodeURIComponent(employeeId)}`,
    { data: { confirm_employee_id: employeeId, reason } },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// 사번 미리보기 + 계정 생성
// ─────────────────────────────────────────────────────────────

export interface EmployeeIDPreviewResponse {
  department: string;
  prefix: string;
  next_id: string;
  sequence: number;
  suggested_email: string;
  suggested_initial_password: string;
}

export async function previewEmployeeId(department: string): Promise<EmployeeIDPreviewResponse> {
  const { data } = await api.post<EmployeeIDPreviewResponse>('/admin/employee-id/preview', { department });
  return data;
}

export interface CreateEmployeeRequest {
  division: string;
  department: string;
  username: string;
  position: string;
  email?: string;
  phone?: string;
  hire_date?: string;
  role_name: string;
  is_active?: boolean;
  must_change_pw?: boolean;
}

export interface CreateEmployeeResponse {
  employee_id: string;
  username: string;
  department: string;
  role_name: string;
  role_level: number;
  initial_password: string;
  must_change_pw: boolean;
  issuance_note: string;
  credential_delivery?: 'local_plaintext' | 'idp_invite_required' | string;
  instructions_markdown: string;
}

export async function createEmployee(req: CreateEmployeeRequest): Promise<CreateEmployeeResponse> {
  const { data } = await api.post<CreateEmployeeResponse>('/admin/users', req);
  return data;
}

// ─────────────────────────────────────────────────────────────
// 보안 감사
// ─────────────────────────────────────────────────────────────

export interface SecurityAlertItem {
  alert_type: 'brute_force' | 'unusual_hour' | 'inactive_access' | string;
  severity: 'critical' | 'warning' | 'info' | string;
  title: string;
  description: string;
  employee_id: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface SecurityAlertsResponse {
  period_hours: number;
  alerts: SecurityAlertItem[];
  summary: { brute_force: number; unusual_hour: number; inactive_access: number };
}

export async function fetchSecurityAlerts(hours = 24): Promise<SecurityAlertsResponse> {
  const { data } = await api.get<SecurityAlertsResponse>('/admin/security/alerts', { params: { hours } });
  return data;
}

export interface DailyCount {
  date: string;   // YYYY-MM-DD
  count: number;
  failed: number;
}

export interface LoginStatsResponse {
  days: number;
  total_logins: number;
  successful: number;
  failed: number;
  success_rate: number;
  unique_users: number;
  locked_accounts: number;
  hour_distribution: { hour: number; count: number; failed: number }[];
  failed_trend: { date: string; success: number; failed: number }[];
  daily_counts: DailyCount[];   // v4.9 — 달력 히트맵
}

export async function fetchLoginStats(days = 30): Promise<LoginStatsResponse> {
  const { data } = await api.get<LoginStatsResponse>('/admin/security/login-stats', { params: { days } });
  return data;
}

export interface LoginHistoryResponse {
  total: number;
  history: LoginHistoryEntry[];
}

// v4.9.2 — 90일 초과 archived 로그인 이력 (BigQuery audit)
export interface ArchivedLoginHistoryResponse {
  total: number;
  history: LoginHistoryEntry[];
  source: 'bigquery';
  available: boolean;
}

export async function fetchArchivedLogins(date: string, limit = 500): Promise<ArchivedLoginHistoryResponse> {
  const { data } = await api.get<ArchivedLoginHistoryResponse>('/admin/security/login-history-archived', {
    params: { date, limit },
  });
  return data;
}

export async function fetchLoginHistory(limit = 50): Promise<LoginHistoryResponse> {
  const { data } = await api.get<LoginHistoryResponse>('/admin/security/login-history', { params: { limit } });
  return data;
}

// ─────────────────────────────────────────────────────────────
// PR-E5 — Audit Dashboard (5-dim) + 7-pattern anomaly feed
// ─────────────────────────────────────────────────────────────

export type AnomalySeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type AnomalyPattern =
  | 'brute_force'
  | 'unusual_hour'
  | 'inactive_access'
  | 'privilege_escalation'
  | 'mass_export'
  | 'off_hours_export'
  | 'deprecated_account_active';

export interface AnomalyFeedItem {
  pattern: AnomalyPattern;
  severity: AnomalySeverity;
  title: string;
  description: string;
  employee_id: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface AnomalyFeedResponse {
  window_hours: number;
  total: number;
  items: AnomalyFeedItem[];
}

export async function fetchAuditAnomalyFeed(window_hours = 24): Promise<AnomalyFeedResponse> {
  const { data } = await api.get<AnomalyFeedResponse>('/admin/audit/anomaly/feed', {
    params: { window_hours },
  });
  return data;
}

export interface TimePatternBucket {
  hour: number;     // 0-23
  weekday: number;  // 0=Mon ~ 6=Sun
  department: string;
  count: number;
}

export interface PermissionViolationRow {
  timestamp: string;
  employee_id: string;
  name: string;
  department: string;
  role: string;
  endpoint: string;
  method: string;
  status_code: number;
  detail: string;
  ip_address: string;
}

export interface FeatureUsageSummaryRow {
  feature: string;
  name: string;
  count: number;
  avg_rating: number;
  feedback_count: number;
}

export interface ChangeAuditRow {
  timestamp: string;
  actor: string;
  actor_name: string;
  actor_role: string;
  action: string;
  endpoint: string;
  method: string;
  status_code: number;
  detail: string;
}

export interface AuditDashboardResponse {
  period: 'day' | 'week' | 'month';
  time_pattern: TimePatternBucket[];
  anomalies: AnomalyFeedItem[];
  permission_violations: PermissionViolationRow[];
  feature_usage: FeatureUsageSummaryRow[];
  change_audit: ChangeAuditRow[];
}

export async function fetchAuditDashboard(
  period: 'day' | 'week' | 'month' = 'week',
): Promise<AuditDashboardResponse> {
  const { data } = await api.get<AuditDashboardResponse>('/admin/audit/dashboard', {
    params: { period },
  });
  return data;
}

// ─────────────────────────────────────────────────────────────
// AI 활용 분석
// ─────────────────────────────────────────────────────────────

export interface FeatureUsageRow {
  feature: string;
  name: string;
  count: number;
  color: string;
}

export interface AnalyticsUsageResponse {
  days: number;
  by_feature: FeatureUsageRow[];
  by_department: { department: string; count: number }[];
  by_hour: { hour: number; count: number }[];
}

export async function fetchAnalyticsUsage(days = 30): Promise<AnalyticsUsageResponse> {
  const { data } = await api.get<AnalyticsUsageResponse>('/admin/analytics/usage', { params: { days } });
  return data;
}

export interface HeatmapResponse {
  days: number;
  departments: string[];
  features: string[];
  matrix: Record<string, Record<string, number>>;
}

export async function fetchAnalyticsHeatmap(days = 30): Promise<HeatmapResponse> {
  const { data } = await api.get<HeatmapResponse>('/admin/analytics/heatmap', { params: { days } });
  return data;
}

export interface DauResponse {
  days: number;
  series: { date: string; dau: number }[];
}

export async function fetchAnalyticsDau(days = 30): Promise<DauResponse> {
  const { data } = await api.get<DauResponse>('/admin/analytics/dau', { params: { days } });
  return data;
}

export interface RoiPerFeature {
  name: string;
  count: number;
  saved_min: number;
}

export interface RoiResponse {
  period_days: number;
  total_uses: number;
  total_saved_minutes: number;
  total_saved_hours: number;
  saved_cost_krw: number;
  saved_cost_display: string;
  per_feature: Record<string, RoiPerFeature>;
}

export async function fetchAnalyticsRoi(days = 30): Promise<RoiResponse> {
  const { data } = await api.get<RoiResponse>('/admin/analytics/roi', { params: { days } });
  return data;
}

// ─────────────────────────────────────────────────────────────
// 인사 통계
// ─────────────────────────────────────────────────────────────

export interface HRSummaryResponse {
  total: number;
  departments: number;
  divisions: number;
  plants: number;
  leaders: number;
}

export async function fetchHrSummary(): Promise<HRSummaryResponse> {
  const { data } = await api.get<HRSummaryResponse>('/admin/hr/summary');
  return data;
}

export interface HeadcountRow {
  label: string;
  count: number;
  division?: string | null;
  dept_count?: number | null;
}

export interface HeadcountResponse {
  by: 'division' | 'department' | 'position' | 'plant';
  rows: HeadcountRow[];
}

export async function fetchHrHeadcount(by: HeadcountResponse['by'] = 'division'): Promise<HeadcountResponse> {
  const { data } = await api.get<HeadcountResponse>('/admin/hr/headcount', { params: { by } });
  return data;
}

export async function fetchHrGender(): Promise<{ distribution: Record<string, number> }> {
  const { data } = await api.get<{ distribution: Record<string, number> }>('/admin/hr/gender');
  return data;
}

export async function fetchHrTenure(): Promise<{ rows: { range: string; count: number }[] }> {
  const { data } = await api.get<{ rows: { range: string; count: number }[] }>('/admin/hr/tenure');
  return data;
}

export interface DivisionPositionMatrixResponse {
  divisions: string[];
  positions: string[];
  matrix: Record<string, Record<string, number>>;
}

export async function fetchHrMatrix(): Promise<DivisionPositionMatrixResponse> {
  const { data } = await api.get<DivisionPositionMatrixResponse>('/admin/hr/matrix');
  return data;
}

export interface OverseasResponse {
  rows: { name: string; position: string; department: string; overseas_assignment: string }[];
}

export async function fetchHrOverseas(): Promise<OverseasResponse> {
  const { data } = await api.get<OverseasResponse>('/admin/hr/overseas');
  return data;
}

// ─────────────────────────────────────────────────────────────
// 시스템 도구
// ─────────────────────────────────────────────────────────────

export interface AuditLogRow {
  timestamp: string;
  employee_id: string;
  name: string;
  department: string;
  role: string;
  endpoint: string;
  method: string;
  status_code: number;
  detail: string;
  ip_address: string;
}

export interface AuditLogResponse {
  total: number;
  rows: AuditLogRow[];
}

export async function fetchAuditLog(params: { employee_id?: string; endpoint?: string; limit?: number } = {}): Promise<AuditLogResponse> {
  const { data } = await api.get<AuditLogResponse>('/admin/system/audit-log', { params });
  return data;
}

export interface SystemHealthResponse {
  auth_db_ok: boolean;
  employees_db_ok: boolean;
  audit_db_ok: boolean;
  seed_users: number;
  active_sessions: number;
}

export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  const { data } = await api.get<SystemHealthResponse>('/admin/system/health');
  return data;
}

export async function downloadSystemBackup(): Promise<Blob> {
  const { data } = await api.post('/admin/system/backup', undefined, { responseType: 'blob' });
  return data as Blob;
}

// ─────────────────────────────────────────────────────────────
// PR-E8 — Permission 매트릭스 + 결재 워크플로우
// backend/routers/admin.py PR-E7~E8 endpoints 와 1:1 매핑.
// ─────────────────────────────────────────────────────────────

export interface PermissionItem {
  key: string;
  description: string;
  min_role: string;
  departments: string[] | null;
  allow_same_division: boolean;
  min_position_level: number;
  created_at?: string;
  updated_at?: string;
  updated_by?: string;
}

export interface PermissionListResponse {
  total: number;
  items: PermissionItem[];
}

export async function fetchPermissionsList(): Promise<PermissionListResponse> {
  const { data } = await api.get<PermissionListResponse>('/admin/permissions/list');
  return data;
}

export async function fetchPermission(key: string): Promise<PermissionItem> {
  const { data } = await api.get<PermissionItem>(`/admin/permissions/${encodeURIComponent(key)}`);
  return data;
}

export interface PermissionChangeRequestBody {
  permission_key: string;
  new_value: {
    description?: string;
    min_role?: string;
    departments?: string[] | null;
    allow_same_division?: boolean;
    min_position_level?: number;
    [k: string]: unknown;
  };
  reason: string;
}

export interface PermissionPreviewResponse {
  permission_key: string;
  before: PermissionItem | null;
  after: PermissionChangeRequestBody['new_value'];
  is_new: boolean;
  reason: string;
}

export async function previewPermissionChange(
  body: PermissionChangeRequestBody,
): Promise<PermissionPreviewResponse> {
  const { data } = await api.post<PermissionPreviewResponse>(
    '/admin/permissions/preview', body,
  );
  return data;
}

export interface PermissionRequestCreated {
  request_id: number;
  status: string;
}

export async function requestPermissionChange(
  body: PermissionChangeRequestBody,
): Promise<PermissionRequestCreated> {
  const { data } = await api.post<PermissionRequestCreated>(
    '/admin/permissions/request', body,
  );
  return data;
}

export type PermissionRequestStatus =
  | 'pending'
  | 'security_approved'
  | 'executive_approved'
  | 'applied'
  | 'rejected';

export interface PermissionChangeRequestRow {
  request_id: number;
  permission_key: string;
  requested_by: string;
  old_value: PermissionItem | null;
  new_value: PermissionChangeRequestBody['new_value'];
  status: PermissionRequestStatus;
  security_approver: string | null;
  executive_approver: string | null;
  requested_at: string;
  applied_at: string | null;
  reason: string;
}

export async function approvePermissionSecurity(
  requestId: number,
): Promise<PermissionChangeRequestRow> {
  const { data } = await api.post<PermissionChangeRequestRow>(
    `/admin/permissions/approve/security/${requestId}`,
  );
  return data;
}

export async function approvePermissionExecutive(
  requestId: number,
): Promise<PermissionChangeRequestRow> {
  const { data } = await api.post<PermissionChangeRequestRow>(
    `/admin/permissions/approve/executive/${requestId}`,
  );
  return data;
}

export async function rejectPermissionRequest(
  requestId: number, reason: string,
): Promise<PermissionChangeRequestRow> {
  const { data } = await api.post<PermissionChangeRequestRow>(
    `/admin/permissions/reject/${requestId}`, { reason },
  );
  return data;
}

export interface PermissionQueueResponse {
  status: string;
  items: PermissionChangeRequestRow[];
}

export async function fetchPermissionQueue(
  status: 'pending' | 'security_approved' = 'pending',
): Promise<PermissionQueueResponse> {
  const { data } = await api.get<PermissionQueueResponse>(
    '/admin/permissions/queue', { params: { status } },
  );
  return data;
}

export interface PermissionHistoryResponse {
  limit: number;
  items: PermissionChangeRequestRow[];
}

export async function fetchPermissionHistory(
  limit: number = 50,
): Promise<PermissionHistoryResponse> {
  const { data } = await api.get<PermissionHistoryResponse>(
    '/admin/permissions/history', { params: { limit } },
  );
  return data;
}
