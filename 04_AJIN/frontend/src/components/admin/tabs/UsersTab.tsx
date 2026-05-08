// UsersTab — 사용자 디렉토리 (캐스케이드 드롭다운 + 표 + 편집 드로어).

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
import { UserEditDrawer } from '@components/admin/widgets/UserEditDrawer';

function buildUsersMarkdown(rows: AdminUserItem[]): string {
  const lines: string[] = ['# 사용자 디렉터리', ''];
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

function statusPill(u: AdminUserItem) {
  // 우선순위: 잠김 > 퇴직 > 비활성 > 활성
  if (u.locked_until && new Date(u.locked_until) > new Date()) {
    // 영구 잠금(50년)은 퇴직으로 간주 — resign_date 가 있으면 "퇴직" 우선
    if (!u.is_active && u.resign_date) {
      return <span className="lg-state-pill" style={{ background: 'color-mix(in oklab, var(--hud-text) 12%, transparent)', color: 'var(--hud-text-dim)' }}>퇴직</span>;
    }
    return <span className="lg-state-pill crit">잠김</span>;
  }
  if (!u.is_active && u.resign_date) {
    return <span className="lg-state-pill" style={{ background: 'color-mix(in oklab, var(--hud-text) 12%, transparent)', color: 'var(--hud-text-dim)' }}>퇴직</span>;
  }
  if (!u.is_active) return <span className="lg-state-pill warn">비활성</span>;
  return <span className="lg-state-pill ok">활성</span>;
}

export function UsersTab() {
  const auth = useAuthStore((s) => s.user);
  const myLevel = auth?.role_level ?? 1;
  const myId = auth?.employee_id ?? '';

  const [tree, setTree] = useState<DepartmentTreeResponse | null>(null);
  const [filters, setFilters] = useState<UserFilters>(DEFAULT_FILTERS);
  const [data, setData] = useState<AdminUserListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AdminUserItem | null>(null);

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

  if (myLevel < 4) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>이 화면은 HR_ADMIN(L4) 이상에게만 노출됩니다.</p>
      </div>
    );
  }

  return (
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

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">USER DIRECTORY</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              {loading ? '로딩 중…' : `${rows.length}명 표시`}
            </div>
          </div>
          <DownloadActions source="admin" basename="ajin-users" content={() => buildUsersMarkdown(rows)} />
        </div>

        {error && (
          <div className="lg-state-pill crit" style={{ display: 'inline-block', marginBottom: 10 }}>
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
                <th>액션</th>
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
                  <td>
                    <button className="lg-btn ghost sm" onClick={() => setSelected(u)} type="button">
                      편집
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}>
                    조건에 맞는 사용자가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <UserEditDrawer
          user={selected}
          tree={tree}
          currentUserLevel={myLevel}
          currentUserId={myId}
          onClose={() => setSelected(null)}
          onChanged={() => {
            reload();
            setSelected(null);
          }}
        />
      )}
    </>
  );
}
