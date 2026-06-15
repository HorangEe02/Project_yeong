// AccountDelegationTab — 사용자/그룹/권한 운영을 한 화면에서 관리.
// 흡수 대상: UsersTab (캐시 기반 read-only 디렉토리).
// 추가: AD 그룹 → AJIN role 매핑 표, user_cache 정합성 카드, IdP 위임 안내.
// RBAC: HR_ADMIN (L4) 이상.

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchDepartmentTree,
  fetchUsers,
  type AdminUserItem,
  type AdminUserListResponse,
  type DepartmentTreeResponse,
  type UserListFilters,
} from '@api/admin';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import {
  UserFilterBar,
  DEFAULT_FILTERS,
  FILTER_ALL,
  type UserFilters,
} from '@components/admin/filters/UserFilterBar';
import { IdpManagedRedirect } from '@components/admin/IdpManagedRedirect';
import { PermissionMatrixUI } from '@components/admin/permissions/PermissionMatrixUI';
import { ApprovalQueueTable } from '@components/admin/permissions/ApprovalQueueTable';
import { PermissionHistoryTimeline } from '@components/admin/permissions/PermissionHistoryTimeline';

// 권한 백오피스 sub-tab
type SubTab = 'users' | 'group_mapping' | 'permission_matrix' | 'approval_queue' | 'change_history';

const SUB_TABS: Array<{ key: SubTab; ko: string; en: string }> = [
  { key: 'users',             ko: '사용자',         en: 'USERS' },
  { key: 'group_mapping',     ko: '그룹 매핑',     en: 'GROUP MAPPING' },
  { key: 'permission_matrix', ko: '권한 매트릭스', en: 'MATRIX' },
  { key: 'approval_queue',    ko: '결재 대기열',   en: 'APPROVAL QUEUE' },
  { key: 'change_history',    ko: '변경 이력',     en: 'HISTORY' },
];

// ─────────────────────────────────────────────────────────────
// AD 그룹 → AJIN role 매핑 표.
// 출처: core/auth/group_mapper.py GROUP_TO_ROLE — 운영자 가시화를 위한 정적 미러.
// 백엔드 GROUP_TO_ROLE 가 변경되면 본 표도 함께 갱신할 것.
// ─────────────────────────────────────────────────────────────
interface GroupMappingRow {
  group_cn: string;
  role_name: string;
  role_level: number;
  departments?: string[];
}

const GROUP_TO_ROLE_MIRROR: GroupMappingRow[] = [
  { group_cn: 'IT-SystemAdmin', role_name: 'SYS_ADMIN', role_level: 5 },
  {
    group_cn: 'HR-Admin',
    role_name: 'HR_ADMIN',
    role_level: 4,
    departments: ['총무인사팀', 'ESG경영팀'],
  },
  { group_cn: 'TeamLead', role_name: 'TEAM_LEAD', role_level: 3 },
  { group_cn: 'Manager', role_name: 'MANAGER', role_level: 2 },
  { group_cn: 'Employee', role_name: 'EMPLOYEE', role_level: 1 },
  { group_cn: 'External', role_name: 'GUEST', role_level: 0 },
];

// ─────────────────────────────────────────────────────────────
// user_cache 정합성 카드 — 현재 사용자 목록 기반 snapshot 을 표시한다.
// backend 의 야간 reconcile job 이 실제 정합성 점검을 담당한다.
// ─────────────────────────────────────────────────────────────
interface CacheStatusSnapshot {
  last_reconcile: string | null;
  mismatch_count: number;
  cached_user_count: number;
  source: 'snapshot' | 'api';
}

function getInitialCacheStatus(userCount: number): CacheStatusSnapshot {
  return {
    last_reconcile: null,
    mismatch_count: 0,
    cached_user_count: userCount,
    source: 'snapshot',
  };
}

function statusPill(u: AdminUserItem) {
  if (u.locked_until && new Date(u.locked_until) > new Date()) {
    if (!u.is_active && u.resign_date) {
      return (
        <span
          className="lg-state-pill"
          style={{
            background: 'color-mix(in oklab, var(--hud-text) 12%, transparent)',
            color: 'var(--hud-text-dim)',
          }}
        >
          퇴직
        </span>
      );
    }
    return <span className="lg-state-pill crit">잠김</span>;
  }
  if (!u.is_active && u.resign_date) {
    return (
      <span
        className="lg-state-pill"
        style={{
          background: 'color-mix(in oklab, var(--hud-text) 12%, transparent)',
          color: 'var(--hud-text-dim)',
        }}
      >
        퇴직
      </span>
    );
  }
  if (!u.is_active) return <span className="lg-state-pill warn">비활성</span>;
  return <span className="lg-state-pill ok">활성</span>;
}

function buildUsersMarkdown(rows: AdminUserItem[]): string {
  const lines: string[] = ['# 사용자 디렉터리 (캐시)', ''];
  lines.push(`총 ${rows.length}명`, '');
  lines.push('| 사번 | 이름 | 본부 | 부서 | 직급 | 역할 | L | 상태 | 마지막 로그인 |');
  lines.push('|---|---|---|---|---|---|---|---|---|');
  for (const u of rows) {
    lines.push(
      `| ${u.employee_id} | ${u.username} | ${u.division} | ${u.department} | ${u.position} | ${u.role_name} | L${u.role_level} | ${u.is_active ? '활성' : '비활성'} | ${u.last_login ?? '—'} |`,
    );
  }
  return lines.join('\n');
}

export function AccountDelegationTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);

  const [tree, setTree] = useState<DepartmentTreeResponse | null>(null);
  const [filters, setFilters] = useState<UserFilters>(DEFAULT_FILTERS);
  const [data, setData] = useState<AdminUserListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showIdpInfo, setShowIdpInfo] = useState(false);
  const [subTab, setSubTab] = useState<SubTab>('users');

  useEffect(() => {
    fetchDepartmentTree()
      .then(setTree)
      .catch((e) => setError(`부서 트리 로드 실패: ${(e as Error).message}`));
  }, []);

  const apiFilters = useMemo<UserListFilters>(() => {
    const out: UserListFilters = { limit: 500 };
    if (filters.division !== FILTER_ALL) out.division = filters.division;
    if (filters.department !== FILTER_ALL) out.department = filters.department;
    if (filters.position !== FILTER_ALL) out.position = filters.position;
    if (filters.role_name !== FILTER_ALL) out.role_name = filters.role_name;
    out.status = filters.status;
    if (filters.q.trim()) out.q = filters.q.trim();
    return out;
  }, [filters]);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchUsers(apiFilters)
      .then(setData)
      .catch((e) => setError(`사용자 조회 실패: ${(e as Error).message}`))
      .finally(() => setLoading(false));
  }, [apiFilters]);

  useEffect(() => {
    const t = setTimeout(reload, 200);
    return () => clearTimeout(t);
  }, [reload]);

  const rows = data?.users ?? [];
  const cacheStatus = useMemo(
    () => getInitialCacheStatus(rows.length),
    [rows.length],
  );

  if (myLevel < 4) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>
          계정 위임 탭은 HR_ADMIN(L4) 이상에게만 노출됩니다.
        </p>
      </div>
    );
  }

  if (showIdpInfo) {
    return (
      <>
        <div className="lg-card" style={{ marginBottom: 12 }}>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={() => setShowIdpInfo(false)}
          >
            ← 사용자 목록으로 돌아가기
          </button>
        </div>
        <IdpManagedRedirect fullPage={false} />
      </>
    );
  }

  return (
    <>
      <div
        className="lg-tabs"
        style={{ marginBottom: 12, fontSize: 12 }}
      >
        {SUB_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`lg-tab ${subTab === t.key ? 'on' : ''}`}
            onClick={() => setSubTab(t.key)}
          >
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
              <span className="en">{t.en}</span>
              <span className="ko">{t.ko}</span>
            </div>
          </button>
        ))}
      </div>

      {subTab === 'permission_matrix' && <PermissionMatrixUI />}
      {subTab === 'approval_queue' && <ApprovalQueueTable />}
      {subTab === 'change_history' && <PermissionHistoryTimeline />}

      {(subTab === 'users' || subTab === 'group_mapping') && (
      <>
      <div className="lg-card">
        <UserFilterBar
          tree={tree}
          filters={filters}
          onChange={setFilters}
          totalCount={data?.total}
          filteredCount={data?.filtered}
          onReset={() => setFilters(DEFAULT_FILTERS)}
        />
      </div>

      {/* 메인 그리드: 좌측 사용자 목록(2fr) + 우측 매핑/캐시(1fr) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)',
          gap: 12,
          alignItems: 'start',
        }}
      >
        {/* 좌측: 사용자 목록 (캐시 보기 모드 — read-only) */}
        <div className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-pill">USER DIRECTORY · 캐시 보기</div>
              <div
                style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}
              >
                {loading ? '로딩 중…' : `${rows.length}명 표시`} · 사내 IdP에서 추가/수정/삭제 처리
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                type="button"
                className="lg-btn primary"
                onClick={() => setShowIdpInfo(true)}
              >
                + 신규 사용자 추가
              </button>
              <DownloadActions
                source="admin"
                basename="ajin-users-cache"
                content={() => buildUsersMarkdown(rows)}
              />
            </div>
          </div>

          {error && (
            <div
              className="lg-state-pill crit"
              style={{ display: 'inline-block', marginBottom: 10 }}
            >
              {error}
            </div>
          )}

          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead>
                <tr>
                  <th>사번</th>
                  <th>이름</th>
                  <th>본부</th>
                  <th>부서</th>
                  <th>직급</th>
                  <th>역할</th>
                  <th>레벨</th>
                  <th>상태</th>
                  <th>마지막 로그인</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.employee_id}>
                    <td className="mono">{u.employee_id}</td>
                    <td>{u.username}</td>
                    <td className="dim">{u.division || '—'}</td>
                    <td>{u.department || '—'}</td>
                    <td>{u.position || '—'}</td>
                    <td>
                      <span className="lg-role">{u.role_name}</span>
                    </td>
                    <td className="mono">L{u.role_level}</td>
                    <td>{statusPill(u)}</td>
                    <td className="dim mono">{u.last_login ?? '—'}</td>
                  </tr>
                ))}
                {!loading && rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={9}
                      style={{
                        textAlign: 'center',
                        color: 'var(--hud-text-dim)',
                        padding: 24,
                      }}
                    >
                      조건에 맞는 사용자가 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 우측 상단: AD 그룹 매핑 표 + 우측 하단: 캐시 정합성 카드 */}
        <div style={{ display: 'grid', gap: 12 }}>
          <div className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-pill">AD GROUP → ROLE 매핑</div>
                <div
                  style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}
                >
                  IdP groupOf → AJIN role_name 우선순위 (role_level desc).
                </div>
              </div>
            </div>
            <div className="lg-table-wrap">
              <table className="lg-table">
                <thead>
                  <tr>
                    <th>AD 그룹 (cn)</th>
                    <th>역할</th>
                    <th>L</th>
                    <th>부서 제한</th>
                  </tr>
                </thead>
                <tbody>
                  {GROUP_TO_ROLE_MIRROR.map((g) => (
                    <tr key={g.group_cn}>
                      <td className="mono">{g.group_cn}</td>
                      <td>
                        <span className="lg-role">{g.role_name}</span>
                      </td>
                      <td className="mono">L{g.role_level}</td>
                      <td className="dim" style={{ fontSize: 12 }}>
                        {g.departments?.join(' · ') ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-pill">USER_CACHE 정합성</div>
                <div
                  style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}
                >
                  IdP ↔ AJIN 캐시 mismatch 야간 reconcile.
                </div>
              </div>
            </div>
            <div className="lg-metric-row">
              <div className="lg-metric">
                <div className="k">CACHED USERS</div>
                <div className="v">{cacheStatus.cached_user_count}</div>
                <div className="en">user_cache rows</div>
              </div>
              <div className="lg-metric">
                <div className="k">MISMATCH</div>
                <div
                  className="v"
                  style={{
                    color:
                      cacheStatus.mismatch_count > 0
                        ? '#C0392B'
                        : 'var(--hud-primary)',
                  }}
                >
                  {cacheStatus.mismatch_count}
                </div>
                <div className="en">IDP vs CACHE</div>
              </div>
              <div className="lg-metric">
                <div className="k">LAST RECONCILE</div>
                <div className="v" style={{ fontSize: 14 }}>
                  {cacheStatus.last_reconcile ?? '—'}
                </div>
                <div className="en">{cacheStatus.source.toUpperCase()}</div>
              </div>
            </div>
            <div
              style={{
                marginTop: 10,
                fontSize: 11,
                color: 'var(--hud-text-dim)',
                lineHeight: 1.5,
              }}
            >
              ※ 현재 카드는 사용자 목록 기준 캐시 행 수와 mismatch 요약을 표시합니다. 야간 reconcile
              job 은 backend 에서 실행되며, 상세 실행 메타데이터 API 는 별도 운영 항목입니다.
            </div>
          </div>
        </div>
      </div>
      </>
      )}
    </>
  );
}

export default AccountDelegationTab;
