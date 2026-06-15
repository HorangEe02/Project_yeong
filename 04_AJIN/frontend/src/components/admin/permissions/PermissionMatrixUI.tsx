// PermissionMatrixUI — PR-E8 핵심 컴포넌트.
// 27 부서 × 5 역할 권한 매트릭스 — 부서별 default + 예외 셀 강조.
// 셀 클릭 시 PermissionChangeRequestModal 호출.
// RBAC: HR_ADMIN (L4) 이상.

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchPermissionsList,
  type PermissionItem,
} from '@api/admin';
import { PermissionChangeRequestModal } from './PermissionChangeRequestModal';

// 5 역할 — rbac.ROLE_LEVELS 미러
const ROLES: Array<{ name: string; level: number }> = [
  { name: 'EMPLOYEE', level: 1 },
  { name: 'MANAGER', level: 2 },
  { name: 'TEAM_LEAD', level: 3 },
  { name: 'HR_ADMIN', level: 4 },
  { name: 'SYS_ADMIN', level: 5 },
];

// core/auth/department_config.py DEPARTMENT_CATEGORIES 의 27 부서 미러
const DEPARTMENTS: string[] = [
  // 재경본부
  'IT전략팀', '재무팀', '회계팀', '원가기획팀',
  // 관리본부
  '총무인사팀', '품질경영팀', 'ESG경영팀', '기술교육원',
  // 구매본부
  '구매팀', '해외지원팀', '상생협력팀',
  // 생산본부
  '품질보증팀', '안전보건팀', '생산관리팀', '영업팀', '자재관리팀',
  // 개발본부
  '기술영업팀', '부품개발팀', '금형생산팀',
  // 생산기술본부
  '생산기술팀', '자동화기술팀', '비전연구팀', 'FA사업팀',
  '플랜트사업팀', '제품설계팀', '공법계획팀', '용기운영팀',
];

interface CellCheck {
  allowed: boolean;
  isException: boolean;
  perms: PermissionItem[];
}

function getRoleLevel(role: string): number {
  return ROLES.find((r) => r.name === role)?.level ?? 1;
}

// 단일 (dept, role) 셀에서 허용된 권한 개수 + 예외 여부 계산.
function checkCell(
  perms: PermissionItem[], dept: string, role: string,
): CellCheck {
  const userLevel = getRoleLevel(role);
  const allowed: PermissionItem[] = [];
  let hasException = false;
  for (const p of perms) {
    const minLevel = getRoleLevel(p.min_role);
    if (userLevel < minLevel) continue;
    if (p.departments && p.departments.length > 0) {
      if (!p.departments.includes(dept)) continue;
      hasException = true;
    }
    allowed.push(p);
  }
  return { allowed: allowed.length > 0, isException: hasException, perms: allowed };
}

function permCountLabel(perms: PermissionItem[]): string {
  if (perms.length === 0) return '—';
  if (perms.length <= 3) return perms.map((p) => p.key).join(', ');
  return `${perms.length}개 권한`;
}

export function PermissionMatrixUI() {
  const [perms, setPerms] = useState<PermissionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [deptFilter, setDeptFilter] = useState<string>('ALL');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [selectedCell, setSelectedCell] = useState<{
    dept: string; role: string; existing: PermissionItem | null;
  } | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchPermissionsList()
      .then((r) => setPerms(r.items))
      .catch((e) => setError(`권한 매트릭스 로드 실패: ${(e as Error).message}`))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const filteredDepts = useMemo(() => {
    if (deptFilter !== 'ALL') return [deptFilter];
    if (!query.trim()) return DEPARTMENTS;
    const q = query.trim().toLowerCase();
    return DEPARTMENTS.filter((d) => d.toLowerCase().includes(q));
  }, [deptFilter, query]);

  const visibleRoles = useMemo(() => {
    if (roleFilter === 'ALL') return ROLES;
    return ROLES.filter((r) => r.name === roleFilter);
  }, [roleFilter]);

  return (
    <>
      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">PERMISSION MATRIX</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              {loading
                ? '로딩 중…'
                : `${perms.length} 권한 / ${filteredDepts.length} 부서 × ${visibleRoles.length} 역할`}
              {' '}— 셀 클릭 → 변경 요청
            </div>
          </div>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={reload}
            disabled={loading}
          >
            새로고침
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <input
            type="text"
            className="lg-input"
            placeholder="부서명 검색…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: '1 1 200px', minWidth: 160 }}
          />
          <select
            className="lg-input"
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
            style={{ minWidth: 160 }}
          >
            <option value="ALL">전체 부서</option>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
          <select
            className="lg-input"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            style={{ minWidth: 140 }}
          >
            <option value="ALL">전체 역할</option>
            {ROLES.map((r) => (
              <option key={r.name} value={r.name}>{r.name} (L{r.level})</option>
            ))}
          </select>
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
                <th style={{ position: 'sticky', left: 0, background: 'var(--hud-bg)' }}>
                  부서
                </th>
                {visibleRoles.map((r) => (
                  <th key={r.name} style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span>{r.name}</span>
                      <span className="mono dim" style={{ fontSize: 11 }}>L{r.level}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredDepts.map((dept) => (
                <tr key={dept}>
                  <td style={{
                    position: 'sticky', left: 0, background: 'var(--hud-bg)',
                    fontWeight: 600,
                  }}>{dept}</td>
                  {visibleRoles.map((role) => {
                    const cell = checkCell(perms, dept, role.name);
                    const bg = cell.isException
                      ? 'color-mix(in oklab, #F39C12 18%, transparent)'
                      : cell.allowed
                        ? 'color-mix(in oklab, var(--hud-primary) 10%, transparent)'
                        : 'transparent';
                    return (
                      <td
                        key={role.name}
                        onClick={() => {
                          // 가장 먼저 일치하는 권한(예외 우선) 을 변경 대상으로 제시
                          const target =
                            cell.perms.find((p) => p.departments?.includes(dept)) ??
                            cell.perms[0] ?? null;
                          setSelectedCell({
                            dept,
                            role: role.name,
                            existing: target,
                          });
                        }}
                        style={{
                          textAlign: 'center', cursor: 'pointer', background: bg,
                          fontSize: 12,
                        }}
                        title={`클릭하여 ${dept} · ${role.name} 권한 변경 요청`}
                      >
                        {permCountLabel(cell.perms)}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {!loading && filteredDepts.length === 0 && (
                <tr>
                  <td
                    colSpan={visibleRoles.length + 1}
                    style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}
                  >
                    조건에 맞는 부서가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--hud-text-dim)' }}>
          ※ 주황 배경 = 부서 예외 권한 (departments 화이트리스트 적용). 파란 배경 = 기본 허용.
        </div>
      </div>

      {selectedCell && (
        <PermissionChangeRequestModal
          dept={selectedCell.dept}
          role={selectedCell.role}
          existing={selectedCell.existing}
          onClose={() => setSelectedCell(null)}
          onSubmitted={() => { setSelectedCell(null); reload(); }}
        />
      )}
    </>
  );
}

export default PermissionMatrixUI;
