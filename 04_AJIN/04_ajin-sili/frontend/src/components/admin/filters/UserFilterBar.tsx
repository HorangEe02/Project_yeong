// UserFilterBar — Feature A search.tsx 의 캐스케이드 드롭다운 패턴 답습.
// 본부 → 부서 캐스케이드 + 직급/역할/상태 + 자유 검색.

import { useMemo } from 'react';
import type { DepartmentTreeResponse } from '@api/admin';

const ALL = '전체';

export interface UserFilters {
  division: string;
  department: string;
  position: string;
  role_name: string;
  status: 'active' | 'inactive' | 'locked' | 'retired' | 'all';
  q: string;
}

export const DEFAULT_FILTERS: UserFilters = {
  division: ALL,
  department: ALL,
  position: ALL,
  role_name: ALL,
  status: 'active',
  q: '',
};

interface Props {
  tree: DepartmentTreeResponse | null;
  filters: UserFilters;
  onChange: (next: UserFilters) => void;
  totalCount?: number;
  filteredCount?: number;
  onReset?: () => void;
}

export function UserFilterBar({ tree, filters, onChange, totalCount, filteredCount, onReset }: Props) {
  const divisions = useMemo(() => tree?.divisions.map((d) => d.division) ?? [], [tree]);
  const departments = useMemo(() => {
    if (!tree) return [];
    if (filters.division === ALL) {
      return tree.divisions.flatMap((d) => d.departments.map((x) => x.name));
    }
    const found = tree.divisions.find((d) => d.division === filters.division);
    return found ? found.departments.map((x) => x.name) : [];
  }, [tree, filters.division]);
  const positions = tree?.positions ?? [];
  const roles = tree?.roles ?? [];

  const update = (patch: Partial<UserFilters>) => onChange({ ...filters, ...patch });

  return (
    <div>
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">사용자 필터</div>
          {typeof filteredCount === 'number' && (
            <span style={{ marginLeft: 12, fontFamily: 'var(--hud-font-mono)', fontSize: 11, color: 'var(--hud-text-dim)' }}>
              {filteredCount.toLocaleString()} / {(totalCount ?? 0).toLocaleString()} 건 일치
            </span>
          )}
        </div>
        <button className="lg-btn ghost" onClick={onReset} type="button">
          초기화
        </button>
      </div>

      <div className="lg-filter-grid">
        <div className="lg-field">
          <label>본부</label>
          <select
            value={filters.division}
            onChange={(e) => update({ division: e.target.value, department: ALL })}
          >
            <option>{ALL}</option>
            {divisions.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </div>

        <div className="lg-field">
          <label>부서</label>
          <select
            value={filters.department}
            onChange={(e) => update({ department: e.target.value })}
            disabled={filters.division === ALL && departments.length > 30}
          >
            <option>{ALL}</option>
            {departments.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </div>

        <div className="lg-field">
          <label>직급</label>
          <select value={filters.position} onChange={(e) => update({ position: e.target.value })}>
            <option>{ALL}</option>
            {positions.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>

        <div className="lg-field">
          <label>역할</label>
          <select value={filters.role_name} onChange={(e) => update({ role_name: e.target.value })}>
            <option>{ALL}</option>
            {roles.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>

        <div className="lg-field">
          <label>상태</label>
          <select
            value={filters.status}
            onChange={(e) => update({ status: e.target.value as UserFilters['status'] })}
          >
            <option value="active">활성</option>
            <option value="inactive">비활성</option>
            <option value="locked">잠금</option>
            <option value="retired">퇴직</option>
            <option value="all">전체</option>
          </select>
        </div>

        <div className="lg-field grow">
          <label>이름 / 사번 / 이메일</label>
          <input
            type="search"
            value={filters.q}
            onChange={(e) => update({ q: e.target.value })}
            placeholder="검색어 입력..."
          />
        </div>
      </div>
    </div>
  );
}

export { ALL as FILTER_ALL };
