// management.ts — v4.8 F 트랙. Management 콘솔 API 클라이언트.
// backend/routers/directory.py + backend/routers/admin.py 의 신규 endpoint 와 1:1 매핑.

import { api } from './client';

// ─────────────────────────────────────────────────────────────
// 부서 트리 (/directory/tree)
// ─────────────────────────────────────────────────────────────

export interface DirectoryNode {
  id: string;
  name: string;
  parent_id: string | null;
  level: number;
  user_count: number;
}

export interface DirectoryTreeResponse {
  nodes: DirectoryNode[];
  total_users: number;
}

export async function fetchDirectoryTree(): Promise<DirectoryTreeResponse> {
  const { data } = await api.get<DirectoryTreeResponse>('/directory/tree');
  return data;
}

// ─────────────────────────────────────────────────────────────
// CSV 일괄 사용자 생성 (/admin/users/bulk)
// ─────────────────────────────────────────────────────────────

export interface BulkIngestErrorRow {
  row_index: number;
  error_code: string;
  error_msg: string;
  raw_payload: Record<string, unknown>;
}

export interface BulkIngestResult {
  rows_total: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped: number;
  rows_error: number;
  dry_run: boolean;
  source: string;
  started_at: string;
  finished_at: string;
  error_payload: BulkIngestErrorRow[];
  ingest_log_id?: number | null;
}

export async function bulkUploadUsers(file: File, dryRun: boolean): Promise<BulkIngestResult> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<BulkIngestResult>(
    `/admin/users/bulk?dry_run=${dryRun}`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// 권한 일괄 변경 (/admin/users/bulk-role)
// ─────────────────────────────────────────────────────────────

export interface BulkRoleChangeResult {
  changed_count: number;
  not_found: string[];
  changes: Array<{
    employee_id: string;
    username: string;
    before_role: string;
    before_level: number;
    after_role: string;
    after_level: number;
  }>;
  target_role: string;
  target_role_level: number;
}

export async function bulkChangeRoles(
  userIds: string[],
  targetRole: number,
  reason: string,
): Promise<BulkRoleChangeResult> {
  const { data } = await api.post<BulkRoleChangeResult>('/admin/users/bulk-role', {
    user_ids: userIds,
    target_role: targetRole,
    reason,
  });
  return data;
}

// ─────────────────────────────────────────────────────────────
// 단일 사용자 수정 (/admin/users/{employee_id}) — v4.8 F-Users bulk modal 확장
//   backend/routers/admin.py L383 PUT /admin/users/{employee_id}
//   - username, department, position, email, phone, is_active, role_name
//   - 본인 자신 / 본인보다 같거나 높은 권한 계정은 수정 차단 (백엔드)
// ─────────────────────────────────────────────────────────────

export interface UpdateUserPayload {
  username?: string;
  department?: string;
  position?: string;
  email?: string;
  phone?: string;
  is_active?: boolean;
  role_name?: string;
}

export interface UpdateUserResult {
  updated: number;
  employee_id?: string;
}

export async function updateUser(
  employeeId: string,
  payload: UpdateUserPayload,
): Promise<UpdateUserResult> {
  const { data } = await api.put<UpdateUserResult>(
    `/admin/users/${encodeURIComponent(employeeId)}`,
    payload,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// 비밀번호 초기화 (/admin/users/{employee_id}/reset-password)
//   backend/routers/admin.py L458, _require_hr_admin (L4+)
// ─────────────────────────────────────────────────────────────

export interface ResetPasswordResult {
  employee_id: string;
  initial_password?: string;
  password_shown: boolean;
  next_action: string;
}

export async function resetUserPassword(
  employeeId: string,
): Promise<ResetPasswordResult> {
  const { data } = await api.post<ResetPasswordResult>(
    `/admin/users/${encodeURIComponent(employeeId)}/reset-password`,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// 인원 삭제 (soft delete: /admin/users/{employee_id}/retire)
//   backend/routers/admin.py L560, _require_hr_admin (L4+)
//   본인보다 같거나 높은 권한 계정 삭제 차단 (백엔드)
//   마지막 SYS_ADMIN 차단 (백엔드 L596)
// ─────────────────────────────────────────────────────────────

export interface RetireUserResult {
  retired: boolean;
  employee_id: string;
  before_role: string;
}

export async function retireUser(
  employeeId: string,
  reason: string,
): Promise<RetireUserResult> {
  const { data } = await api.delete<RetireUserResult>(
    `/admin/users/${encodeURIComponent(employeeId)}/retire`,
    { data: { reason } },
  );
  return data;
}

// ─────────────────────────────────────────────────────────────
// 감사 타임라인 (/admin/audit/timeline)
// ─────────────────────────────────────────────────────────────

export interface AuditTimelineRow {
  id: number | string;
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

export interface AuditTimelineFilters {
  actor?: string;
  action?: string;
  target?: string;
  result?: 'all' | 'success' | 'fail';
  period_days?: number;
  page?: number;
  page_size?: number;
}

export interface AuditTimelineResponse {
  total: number;
  page: number;
  page_size: number;
  rows: AuditTimelineRow[];
  filters: Record<string, string | number>;
}

export async function fetchAuditTimeline(filters: AuditTimelineFilters = {}): Promise<AuditTimelineResponse> {
  const { data } = await api.get<AuditTimelineResponse>('/admin/audit/timeline', { params: filters });
  return data;
}

// ─────────────────────────────────────────────────────────────
// 확장 시스템 헬스 (/admin/system/health-extended)
// ─────────────────────────────────────────────────────────────

export interface SystemHealthSection {
  status: string;
  [key: string]: unknown;
}

export interface SystemHealthExtended {
  timestamp: string;
  sections: {
    celery_beat?: SystemHealthSection;
    redis?: SystemHealthSection;
    postgresql?: SystemHealthSection;
    supabase?: SystemHealthSection;
    vector_store?: SystemHealthSection;
    sqlite?: SystemHealthSection;
    chromadb?: SystemHealthSection;
    disk?: SystemHealthSection;
    external?: SystemHealthSection;
  };
}

export async function fetchSystemHealthExtended(): Promise<SystemHealthExtended> {
  const { data } = await api.get<SystemHealthExtended>('/admin/system/health-extended');
  return data;
}

// ─────────────────────────────────────────────────────────────
// 사용 통계 히트맵 (/admin/stats/feature-heatmap)
// ─────────────────────────────────────────────────────────────

export interface FeatureHeatmapBucket {
  label: string;
  key: string;
}

export interface FeatureHeatmapResponse {
  period: 'day' | 'week' | 'month';
  buckets: FeatureHeatmapBucket[];
  features: string[];
  matrix: Record<string, Record<string, number>>;
}

export async function fetchFeatureHeatmap(
  period: 'day' | 'week' | 'month' = 'day',
  periodDays = 7,
): Promise<FeatureHeatmapResponse> {
  const { data } = await api.get<FeatureHeatmapResponse>('/admin/stats/feature-heatmap', {
    params: { period, period_days: periodDays },
  });
  return data;
}
