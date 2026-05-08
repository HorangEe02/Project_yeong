// search.tsx — Module A · 조직도/인원 검색 (lg-* canonical 양식 재구성).
// 캐노니컬 uiux/web_app/Search.jsx 1:1 매핑 + 기존 RBAC 가시성 마스킹 + DownloadActions 보존.

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { useToast } from '@store/toast';
import { DownloadActions } from '@components/common/DownloadActions';
import { MapView, type MapMarker } from '@components/chart/MapView';
import { EmployeeDetailDrawer } from '@components/employee/EmployeeDetailDrawer';
import {
  EMPLOYEES,
  ORG,
  PLANTS,
  POSITIONS,
  TOTAL_HEADCOUNT,
  type MockEmployee,
} from '@api/mock/seed/employees';
import { PLANTS_COORDS } from '@api/mock/seed/plants';
import { applyVisibility, type FilteredEmployee } from '@lib/visibility';
import {
  fetchByDepartment,
  fetchByDivision,
  fetchEmployeeList,
  fetchOrgTree,
  type BackendEmployee,
  type DivisionNode,
} from '@api/employee';
import { fetchFacilities, type FacilityItem } from '@api/compliance';
import { sortEmployees, SORT_OPTIONS, type EmployeeSortKey } from '@lib/employeeSort';

const ALL = '전체';

// 백엔드 응답 → MockEmployee 형태로 어댑트 (RBAC 마스킹은 백엔드가 이미 적용했음)
function adaptBackend(b: BackendEmployee, idx: number): MockEmployee {
  return {
    id: `${b.department || 'DEPT'}-${String(idx + 1).padStart(3, '0')}`,
    name: b.name || '—',
    gender: '남' as const,  // 백엔드 미반환 → UI 표시용 기본값
    hq: b.division || '—',
    team: b.department || '—',
    position: b.position || '—',
    ext: b.extension || '',
    mobile: b.phone || '',
    email: b.email || '',
    plant: b.plant || '—',
  };
}

export function Search() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const { addToast } = useToast();

  const [hq, setHq] = useState<string>(ALL);
  const [team, setTeam] = useState<string>(ALL);
  const [position, setPosition] = useState<string>(ALL);
  const [gender, setGender] = useState<string>(ALL);
  const [plant, setPlant] = useState<string>(ALL);
  const [query, setQuery] = useState('');
  const [selectedHq, setSelectedHq] = useState<string | null>(null);

  // v3.6 — 정렬 (기본: 직급 내림차순). localStorage 영속.
  const [sortKey, setSortKey] = useState<EmployeeSortKey>(() => {
    if (typeof window === 'undefined') return 'rank-desc';
    const saved = localStorage.getItem('ajin-search-sort') as EmployeeSortKey | null;
    return saved && SORT_OPTIONS.some((o) => o.key === saved) ? saved : 'rank-desc';
  });
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('ajin-search-sort', sortKey);
    }
  }, [sortKey]);

  // v3.6 — 상세 Drawer state
  const [selectedEmployee, setSelectedEmployee] = useState<FilteredEmployee | null>(null);
  // v3.6 — 컬럼 가시성 토글 (관리자급 사용자 대상 "전체 보기" 옵션)
  const [showAllColumns, setShowAllColumns] = useState<boolean>(false);

  // 백엔드 fetch — hq 또는 team 선택 시 실 DB의 전체 인원 조회
  const [backendEmployees, setBackendEmployees] = useState<MockEmployee[] | null>(null);
  const [backendMeta, setBackendMeta] = useState<{ total: number; masked: number; excluded: number; scope: string; name: string } | null>(null);
  const [backendBusy, setBackendBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setBackendBusy(true);
    // v3.6 — 필터 없음(첫 마운트) → 전체 페이지네이션 24명, 필터 있음 → 부서/본부 단위 전체
    let fetcher: Promise<{ employees: BackendEmployee[]; total: number; masked: number; excluded: number; scope: string; name: string }>;
    if (team !== ALL) {
      fetcher = fetchByDepartment(team);
    } else if (hq !== ALL) {
      fetcher = fetchByDivision(hq);
    } else {
      // 필터 없음 — 실 DB 첫 24명 (이전 mock seed 24명 가상 인물 대체)
      fetcher = fetchEmployeeList(24, 0);
    }
    fetcher
      .then((d) => {
        if (cancelled) return;
        const adapted = d.employees.map((e, i) => adaptBackend(e, i));
        setBackendEmployees(adapted);
        setBackendMeta({
          total: d.total,
          masked: d.masked,
          excluded: d.excluded,
          scope: d.scope,
          name: d.name,
        });
      })
      .catch(() => {
        if (cancelled) return;
        // 백엔드 실패 → mock seed 폴백 (오프라인 데모 시연 안전망)
        setBackendEmployees(null);
        setBackendMeta(null);
      })
      .finally(() => {
        if (!cancelled) setBackendBusy(false);
      });
    return () => { cancelled = true; };
  }, [hq, team]);

  // 가시성 마스킹 — 백엔드 모드는 이미 백엔드가 마스킹 적용 완료, 단 프론트의 FilteredEmployee shape 으로 재포장
  const visibleEmployees = useMemo(
    () => applyVisibility(backendEmployees ?? EMPLOYEES, user),
    [backendEmployees, user],
  );

  // 백엔드 org-tree (본부 → 팀) — 첫 마운트 시 1회 fetch, 실패 시 mock ORG 사용
  const [backendOrg, setBackendOrg] = useState<DivisionNode[] | null>(null);
  const [backendTotal, setBackendTotal] = useState<number | null>(null);
  useEffect(() => {
    fetchOrgTree()
      .then((d) => {
        setBackendOrg(d.divisions);
        setBackendTotal(d.total);
      })
      .catch(() => {
        setBackendOrg(null);
        setBackendTotal(null);
      });
  }, []);

  // mock ORG 의 color 정보를 보존하면서 backend 트리로 대체
  const effectiveOrg = useMemo(() => {
    if (!backendOrg) return ORG;
    return backendOrg.map((d) => {
      const mockHQ = ORG.find((o) => o.hq === d.name);
      return {
        hq: d.name,
        n: d.headcount,
        color: mockHQ?.color ?? 'var(--hud-primary)',
        teams: d.teams.map((t) => ({ team: t.name, n: t.headcount })),
      };
    });
  }, [backendOrg]);

  const effectiveTotalHeadcount = backendTotal ?? TOTAL_HEADCOUNT;

  // 필터링
  const filteredUnsorted = useMemo(() => {
    return visibleEmployees.filter((p) => {
      if (hq !== ALL && p.hq !== hq) return false;
      if (team !== ALL && p.team !== team) return false;
      if (position !== ALL && p.position !== position) return false;
      if (gender !== ALL && p.gender !== gender) return false;
      if (plant !== ALL && p.plant !== plant) return false;
      if (query.trim()) {
        const q = query.toLowerCase();
        const haystack = [p.name, p.id, p.email, p.team, p.hq].join(' ').toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [visibleEmployees, hq, team, position, gender, plant, query]);

  // v3.6 — 정렬 적용 (직급 내림차순 기본)
  const filtered = useMemo(
    () => sortEmployees(filteredUnsorted, sortKey),
    [filteredUnsorted, sortKey],
  );

  const teamsForHq = useMemo(
    () => (hq === ALL ? [] : effectiveOrg.find((o) => o.hq === hq)?.teams ?? []),
    [hq, effectiveOrg],
  );

  const handleReset = () => {
    setHq(ALL);
    setTeam(ALL);
    setPosition(ALL);
    setGender(ALL);
    setPlant(ALL);
    setQuery('');
    setSelectedHq(null);
  };

  const handleQuickAction = (emp: FilteredEmployee) => {
    if (emp.visibility !== 'FULL') {
      addToast({ type: 'warning', message: '타 부서 사원 정보는 권한이 제한됩니다.' });
      return;
    }
    addToast({
      type: 'info',
      title: '문서 작성으로 이동',
      message: `${emp.name} ${emp.position} — 요청 내용에 자동 입력됩니다`,
      action: {
        label: '이동',
        onClick: () =>
          navigate('/draft', {
            state: {
              prefillRecipient: emp.name,
              prefillPosition: emp.position,
              prefillTeam: emp.team,
              prefillEmail: emp.email,
            },
          }),
      },
    });
  };

  // 백엔드 facilities (19개소, lat/lng 포함) — 첫 로드 시 한 번만 조회
  const [facilities, setFacilities] = useState<FacilityItem[]>([]);
  useEffect(() => {
    fetchFacilities()
      .then((d) => setFacilities(d.facilities))
      .catch(() => {
        // 백엔드 실패 시 mock fallback (오프라인 데모용)
        const fallback: FacilityItem[] = PLANTS_COORDS.map((p) => ({
          plant_id: p.id ?? p.name,
          name: p.name,
          location: '',
          address: '',
          certifications: p.certifications ?? [],
          processes: p.processes ?? [],
          kind: p.region === 'domestic' ? 'subsidiary_domestic' : 'subsidiary_overseas',
          country: p.region === 'domestic' ? 'KR' : '',
          lat: p.lat,
          lng: p.lng,
        }));
        setFacilities(fallback);
      });
  }, []);

  // 사업장 지도 — 19개소 모두 항상 표시. 검색 결과와 매칭되는 사업장은 description 에 표시.
  // mock 직원의 plant 필드(예: '본사 (대구)')와 backend facility name(예: '경산 본사 (제1공장)') 이
  // 1:1 매칭되지 않으므로 substring 으로 느슨하게 비교.
  const usedPlantTokens = useMemo(() => {
    const tokens = new Set<string>();
    for (const f of filtered) {
      if (!f.plant) continue;
      tokens.add(f.plant);
      // '본사 (대구)' → '본사', '경산' 같은 토큰 추출
      f.plant.split(/[()\s]+/).filter((t) => t.length >= 2).forEach((t) => tokens.add(t));
    }
    return tokens;
  }, [filtered]);

  const filteredPlants = facilities;

  const mapMarkers: MapMarker[] = filteredPlants
    .filter((p) => typeof p.lat === 'number' && typeof p.lng === 'number')
    .map((p) => {
      const isMatched =
        usedPlantTokens.size > 0 &&
        Array.from(usedPlantTokens).some(
          (t) => p.name.includes(t) || p.plant_id.includes(t),
        );
      const kindLabel =
        p.kind === 'plant'
          ? '자사'
          : p.kind === 'subsidiary_domestic'
            ? '국내계열사'
            : '해외법인';
      return {
        id: p.plant_id || p.name,
        name: p.name,
        lat: p.lat as number,
        lng: p.lng as number,
        description: `${p.country === 'KR' ? '국내' : '해외'} · ${kindLabel}${isMatched ? ' · ★ 검색 매칭' : ''}`,
      };
    });

  const matchedCount = mapMarkers.filter((m) => m.description?.includes('★')).length;

  // ──────────────────────────────────────────────────────────────────
  // Render
  // ──────────────────────────────────────────────────────────────────

  return (
    <div className="page lg-page" data-screen-label="A · Org & Directory">
      {/* HERO */}
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">EMPLOYEE DIRECTORY · MODULE A</div>
        <h1 className="lg-display">조직도 / 인원 검색</h1>
        <p className="lg-sub">
          아진산업 {effectiveOrg.length}개 본부 · {effectiveOrg.reduce((acc, o) => acc + o.teams.length, 0)}개 팀 · {effectiveTotalHeadcount}명. 본부와 팀을 선택해 부서별 체계와 인원
          정보를 한눈에 확인하세요.
        </p>
      </section>

      {/* ORG CHART */}
      <section className="lg-card lg-orgchart">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">ORG CHART · 조직도</div>
            <h2 className="lg-h2">본부 → 팀 구조</h2>
          </div>
          <div className="lg-pill">총 {effectiveTotalHeadcount}명 · {effectiveOrg.length} HQ · {effectiveOrg.reduce((acc, o) => acc + o.teams.length, 0)} TEAMS</div>
        </div>

        <div className="org-diagram">
          <div className="org-ceo">
            <div className="org-node-glass ceo">
              <div className="org-node-eyebrow">CEO · 대표이사</div>
              <div className="org-node-title">AJIN INDUSTRY</div>
              <div className="org-node-sub">아진산업 주식회사 · {effectiveTotalHeadcount}명</div>
            </div>
          </div>
          <svg className="org-connectors" viewBox="0 0 1200 60" preserveAspectRatio="none">
            <path
              d="M600,0 V20 M100,60 V40 H1100 V40 M100,40 V60 M300,40 V60 M500,40 V60 M700,40 V60 M900,40 V60 M1100,40 V60 M600,20 V40"
              stroke="oklch(70% 0.02 80 / 0.4)"
              strokeWidth="1"
              fill="none"
            />
          </svg>
          <div className="org-hq-row">
            {effectiveOrg.map((b) => (
              <button
                key={b.hq}
                className={
                  'org-node-glass hq' +
                  (selectedHq === b.hq ? ' active' : '') +
                  (hq === b.hq ? ' selected' : '')
                }
                onClick={() => {
                  setSelectedHq(selectedHq === b.hq ? null : b.hq);
                  setHq(b.hq);
                  setTeam(ALL);
                }}
              >
                <span
                  className="org-accent"
                  style={{ background: b.color ?? 'var(--hud-primary)' }}
                />
                <div className="org-node-eyebrow">{b.teams.length} TEAMS</div>
                <div className="org-node-title">{b.hq}</div>
                <div className="org-node-sub">{b.n ?? '—'}명</div>
              </button>
            ))}
          </div>
          {selectedHq && (
            <div className="org-team-row">
              <div className="org-team-label">└ {selectedHq} 산하 팀</div>
              <div className="org-team-chips">
                {effectiveOrg.find((o) => o.hq === selectedHq)?.teams.map((t) => (
                  <button
                    key={t.team}
                    className={'org-team-chip' + (team === t.team ? ' on' : '')}
                    onClick={() => setTeam(t.team)}
                  >
                    <span className="t-name">{t.team}</span>
                    <span className="t-count">{t.n ?? '—'}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* FILTERS */}
      <section className="lg-card lg-filters">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">FILTERS · 분류 검색</div>
            <h2 className="lg-h2">부서 / 직급별 필터</h2>
          </div>
          <button className="lg-btn ghost" onClick={handleReset}>
            초기화
          </button>
        </div>
        <div className="lg-filter-grid">
          <div className="lg-field">
            <label>본부</label>
            <select
              value={hq}
              onChange={(e) => {
                setHq(e.target.value);
                setTeam(ALL);
                setSelectedHq(e.target.value === ALL ? null : e.target.value);
              }}
            >
              <option>{ALL}</option>
              {effectiveOrg.map((o) => (
                <option key={o.hq}>{o.hq}</option>
              ))}
            </select>
          </div>
          <div className="lg-field">
            <label>팀</label>
            <select
              value={team}
              onChange={(e) => setTeam(e.target.value)}
              disabled={hq === ALL}
            >
              <option>{ALL}</option>
              {teamsForHq.map((t) => (
                <option key={t.team}>{t.team}</option>
              ))}
            </select>
          </div>
          <div className="lg-field">
            <label>직급</label>
            <select value={position} onChange={(e) => setPosition(e.target.value)}>
              <option>{ALL}</option>
              {POSITIONS.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="lg-field">
            <label>성별</label>
            <select value={gender} onChange={(e) => setGender(e.target.value)}>
              <option>{ALL}</option>
              <option>남</option>
              <option>여</option>
            </select>
          </div>
          <div className="lg-field">
            <label>사업장</label>
            <select value={plant} onChange={(e) => setPlant(e.target.value)}>
              <option>{ALL}</option>
              {PLANTS.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="lg-field grow">
            <label>이름 / 사번 / 이메일</label>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="검색어 입력..."
            />
          </div>
        </div>
        {/* v3.6 — 정렬 드롭다운 + 컬럼 가시성 토글 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginTop: 12,
            paddingTop: 12,
            borderTop: '1px dashed var(--hud-border, #2A2520)',
          }}
        >
          <div className="lg-field" style={{ minWidth: 240 }}>
            <label className="label-en" style={{ fontSize: 10, letterSpacing: '0.1em' }}>
              SORT · 정렬
            </label>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as EmployeeSortKey)}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: 'var(--hud-text-dim)',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <input
              type="checkbox"
              checked={showAllColumns}
              onChange={(e) => setShowAllColumns(e.target.checked)}
              style={{ accentColor: 'var(--hud-primary)' }}
            />
            전체 컬럼 보기 (사번 · 성별 · 내선 · 사업장)
          </label>
        </div>
      </section>

      {/* DIRECTORY TABLE */}
      <section className="lg-card lg-table-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">DIRECTORY · 인원 정보</div>
            <h2 className="lg-h2">
              {filtered.length}명 검색됨{' '}
              <span className="lg-h2-sub">
                {backendMeta ? (
                  <>
                    / {backendMeta.scope === 'department' ? '부서' : '본부'}{' '}
                    <b>{backendMeta.name}</b> 전체 {backendMeta.total}명
                    {backendMeta.masked > 0 && ` · 마스킹 ${backendMeta.masked}명`}
                    {backendMeta.excluded > 0 && ` · 비공개 ${backendMeta.excluded}명`}
                  </>
                ) : (
                  <>/ 가시 {visibleEmployees.length}명 · 전체 {EMPLOYEES.length}명</>
                )}
                {backendBusy && ' · 불러오는 중…'}
              </span>
            </h2>
          </div>
          <DownloadActions
            content={() => {
              const headers = ['사번', '이름', '본부', '팀', '직급', '내선', '이메일', '사업장'];
              const lines = [
                `# 인원 검색 결과 (${filtered.length}명)`,
                '',
                `검색 조건 — 가시 ${visibleEmployees.length}명 중 ${filtered.length}명 매칭`,
                '',
                `| ${headers.join(' | ')} |`,
                `| ${headers.map(() => '---').join(' | ')} |`,
                ...filtered.map(
                  (e) =>
                    `| ${e.id} | ${e.name} | ${e.hq} | ${e.team} | ${e.position} | ${e.extMasked} | ${e.emailMasked} | ${e.plant} |`,
                ),
              ];
              return lines.join('\n');
            }}
            basename={`ajin-employees-${filtered.length}_${new Date().toISOString().slice(0, 10)}`}
            source="search"
            metadata={{
              title: `인원 검색 결과 ${filtered.length}명`,
              doc_type: 'employee_search',
            }}
          />
        </div>

        {/* v3.6 — 기본 5컬럼 (이름·본부/팀·직급·휴대전화·이메일).
            "전체 컬럼 보기" 토글 시 사번/성별/내선/사업장 추가 노출.
            행 클릭 → 우측 상세 Drawer 열림. 표는 그대로 유지되어 비교 가능. */}
        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                {showAllColumns && <th>사번</th>}
                <th>이름</th>
                {showAllColumns && <th>성별</th>}
                <th>본부 / 팀</th>
                <th>직급</th>
                {showAllColumns && <th>내선</th>}
                <th>휴대전화</th>
                <th>이메일</th>
                {showAllColumns && <th>사업장</th>}
                <th aria-label="액션"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={showAllColumns ? 10 : 6} className="lg-empty">
                    조건에 맞는 인원이 없습니다. 필터를 조정해 보세요.
                  </td>
                </tr>
              ) : (
                filtered.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => setSelectedEmployee(p)}
                    style={{ cursor: 'pointer' }}
                    title={`${p.name} ${p.position} 상세 보기 (${p.id} · ${p.plant})`}
                  >
                    {showAllColumns && <td className="mono dim">{p.id}</td>}
                    <td>
                      <div className="lg-person">
                        <span className="lg-avatar">{p.name.slice(-2)}</span>
                        <span className="lg-name">{p.name}</span>
                      </div>
                    </td>
                    {showAllColumns && (
                      <td>
                        <span className={'lg-gender g-' + (p.gender === '남' ? 'm' : 'f')}>
                          {p.gender}
                        </span>
                      </td>
                    )}
                    <td>
                      <div className="lg-deptcol">
                        <span className="hq-tag">{p.hq.replace('본부', '')}</span>
                        <span className="team-tag">{p.team}</span>
                      </div>
                    </td>
                    <td>
                      <span className="lg-pos">{p.position}</span>
                    </td>
                    {showAllColumns && <td className="mono">{p.extMasked}</td>}
                    <td className="mono dim">{p.phoneMasked || '—'}</td>
                    <td
                      className="lg-email"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {p.visibility === 'FULL' ? (
                        <a href={`mailto:${p.email}`}>{p.email}</a>
                      ) : (
                        <span className="dim">{p.emailMasked}</span>
                      )}
                    </td>
                    {showAllColumns && <td className="dim">{p.plant}</td>}
                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        className="lg-btn ghost sm"
                        onClick={() => handleQuickAction(p)}
                        title="문서 작성/메일"
                      >
                        ↗
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* PLANTS MAP */}
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">PLANTS · {facilities.length || 19} LOCATIONS</div>
            <h2 className="lg-h2">
              사업장 분포{' '}
              <span className="lg-h2-sub">
                국내 {facilities.filter((p) => p.country === 'KR').length || 12}{' '}
                · 해외 {facilities.filter((p) => p.country && p.country !== 'KR').length || 7}
              </span>
            </h2>
          </div>
          <span className="lg-pill">
            {mapMarkers.length}개소
            {matchedCount > 0 && ` · ★ ${matchedCount}`}
          </span>
        </div>
        <div style={{ width: '100%', height: 420, borderRadius: 12, overflow: 'hidden' }}>
          <MapView markers={mapMarkers} zoom={3} height={420} />
        </div>
      </section>

      {/* v3.6 — 인원 상세 Drawer (행 클릭 시 우측 슬라이드, ESC/외부클릭 닫힘) */}
      <EmployeeDetailDrawer
        employee={selectedEmployee}
        isOpen={selectedEmployee !== null}
        onClose={() => setSelectedEmployee(null)}
        onMail={(e) => {
          if (e.email) window.location.href = `mailto:${e.email}`;
        }}
        onDraft={(e) => {
          handleQuickAction(e);
          setSelectedEmployee(null);
        }}
        onPrev={
          selectedEmployee
            ? () => {
                const idx = filtered.findIndex((p) => p.id === selectedEmployee.id);
                if (idx > 0) setSelectedEmployee(filtered[idx - 1]);
              }
            : undefined
        }
        onNext={
          selectedEmployee
            ? () => {
                const idx = filtered.findIndex((p) => p.id === selectedEmployee.id);
                if (idx >= 0 && idx < filtered.length - 1) {
                  setSelectedEmployee(filtered[idx + 1]);
                }
              }
            : undefined
        }
      />
    </div>
  );
}
