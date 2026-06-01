// search.tsx — Module A · 조직도/인원 검색 (lg-* canonical 양식 재구성).
// 캐노니컬 uiux/web_app/Search.jsx 1:1 매핑 + 기존 RBAC 가시성 마스킹 + DownloadActions 보존.

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import { MapView, type MapMarker } from '@components/chart/MapView';
import { EmployeeDetailDrawer } from '@components/employee/EmployeeDetailDrawer';
import { DocumentSearchPanel } from '@components/search/DocumentSearchPanel';
import { DrawingsPanel } from '@components/search/DrawingsPanel';
import { UnifiedSearchPanel } from '@components/search/UnifiedSearchPanel';
import { HistoryFavoritesPanel } from '@components/search/HistoryFavoritesPanel';
import { OnboardingSidePanel } from '@components/search/OnboardingSidePanel';
import { Tabs } from '@components/ui/Tabs';
import { usePersonActions } from '@hooks/usePersonActions';
import { pushViewedPerson } from '@lib/searchHistory';
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
  searchEmployees,
  type BackendEmployee,
  type DivisionNode,
} from '@api/employee';
import { fetchFacilities, type FacilityItem } from '@api/compliance';
import { useIsMobile } from '@hooks/useBreakpoint';
import { AJINMobileSearch } from '@components/uikit/AJINMobileSearch';
import { sortEmployees, SORT_OPTIONS, type EmployeeSortKey } from '@lib/employeeSort';

const ALL = '전체';

// 본부 이름 → 결정적(deterministic) OKLCH 색상.
// mock ORG 에 등록된 6 본부는 명시 색상을 사용하고, 그 외 본부에는 이름 해시로
// hue 를 분배해 카드 vertical bar 가 일관되게 다양해지도록 한다.
function hueForHqName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
  const hue = Math.abs(hash) % 360;
  return `oklch(72% 0.13 ${hue})`;
}

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
  const user = useAuthStore((s) => s.user);
  const personActions = usePersonActions();
  const [searchParams] = useSearchParams();

  // W4 — HistoryFavoritesPanel → UnifiedSearchPanel 쿼리 주입 채널
  const [pickedQuery, setPickedQuery] = useState<string | undefined>(undefined);
  const [pickedNonce, setPickedNonce] = useState<number>(0);

  // W1·W2 — 검색 탭 (통합 / 인사 / 문서 / 도면). localStorage 영속. 기본값은 통합.
  type TabId = 'unified' | 'people' | 'documents' | 'drawings';
  const [tab, setTab] = useState<TabId>(() => {
    if (typeof window === 'undefined') return 'unified';
    const saved = localStorage.getItem('ajin-search-tab');
    return saved === 'people' || saved === 'documents' || saved === 'drawings'
      ? (saved as TabId)
      : 'unified';
  });
  useEffect(() => {
    if (typeof window !== 'undefined') localStorage.setItem('ajin-search-tab', tab);
  }, [tab]);

  // W5 — URL 의 ?tab= 파라미터로 진입 시 우선 적용 (CommandPalette 의 페이지 점프).
  useEffect(() => {
    const t = searchParams.get('tab');
    if (t === 'people' || t === 'documents' || t === 'unified') {
      setTab(t);
    }
  }, [searchParams]);

  // v3.9 — 디지털 사원증 QR 클릭 진입 (/search?empId=...) — 자동 인원 선택.
  // filtered 가 로드된 후 매칭. 매칭되면 setSelectedEmployee + 최근 본 사람 기록.
  // 한 번만 실행하기 위해 sessionStorage 가드 (URL 의 empId 가 그대로면 재진입 방지).
  // 주의: filtered 는 아래에서 정의되므로 hoist 의존성 — 별도 useEffect 로 분리.

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

  // F3 — query 입력 시 백엔드 자연어 검색(/employee/search) 우선 호출, 250ms 디바운스.
  //       query 비어있으면 기존 본부/팀/list 분기 유지.
  useEffect(() => {
    let cancelled = false;
    const q = query.trim();
    setBackendBusy(true);

    const run = async () => {
      try {
        if (q.length >= 1) {
          // 자연어 인사 검색 — 부서 약어/직급 동의어 등 백엔드 인덱서가 처리
          const d = await searchEmployees(q);
          if (cancelled) return;
          const adapted = d.results.map((e, i) => adaptBackend(e, i));
          setBackendEmployees(adapted);
          setBackendMeta({
            total: d.total,
            masked: 0,
            excluded: 0,
            scope: 'query',
            name: q,
          });
          return;
        }

        // query 비어있음 → 기존 본부/팀/list 분기
        let fetcher: Promise<{
          employees: BackendEmployee[];
          total: number;
          masked: number;
          excluded: number;
          scope: string;
          name: string;
        }>;
        if (team !== ALL) {
          fetcher = fetchByDepartment(team);
        } else if (hq !== ALL) {
          fetcher = fetchByDivision(hq);
        } else {
          fetcher = fetchEmployeeList(24, 0);
        }
        const d = await fetcher;
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
      } catch {
        if (cancelled) return;
        // 백엔드 실패 → mock seed 폴백 (오프라인 데모 시연 안전망)
        setBackendEmployees(null);
        setBackendMeta(null);
      } finally {
        if (!cancelled) setBackendBusy(false);
      }
    };

    // query 입력 시는 디바운스, 아니면 즉시
    const delay = q.length >= 1 ? 250 : 0;
    const timer = setTimeout(run, delay);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [hq, team, query]);

  // 가시성 마스킹 — 백엔드 모드는 이미 백엔드가 마스킹 적용 완료, 단 프론트의 FilteredEmployee shape 으로 재포장
  const visibleEmployees = useMemo(
    () => applyVisibility(backendEmployees ?? EMPLOYEES, user),
    [backendEmployees, user],
  );

  // 백엔드 org-tree (본부 → 팀) — 첫 마운트 시 1회 fetch, 실패 시 mock ORG 사용
  const [backendOrg, setBackendOrg] = useState<DivisionNode[] | null>(null);
  const [backendTotal, setBackendTotal] = useState<number | null>(null);
  // 첫 fetch 완료 여부 — true 가 되기 전에는 mock 대신 로딩 placeholder 노출.
  // 강제 새로고침 (Cmd+Shift+R) 시 mock(427명/19팀)이 잠시 보이는 문제 방지.
  const [orgLoaded, setOrgLoaded] = useState(false);
  useEffect(() => {
    fetchOrgTree()
      .then((d) => {
        setBackendOrg(d.divisions);
        setBackendTotal(d.total);
      })
      .catch(() => {
        setBackendOrg(null);
        setBackendTotal(null);
      })
      .finally(() => {
        setOrgLoaded(true);
      });
  }, []);

  // mock ORG 의 color 정보를 보존하면서 backend 트리로 대체.
  // 첫 fetch 전에는 빈 배열 → 헤더/카드의 숫자가 mock 으로 표시되지 않도록 함.
  const effectiveOrg = useMemo(() => {
    if (!orgLoaded) return [];
    if (!backendOrg) return ORG;
    return backendOrg.map((d) => {
      const mockHQ = ORG.find((o) => o.hq === d.name);
      return {
        hq: d.name,
        n: d.headcount,
        color: mockHQ?.color ?? hueForHqName(d.name),
        teams: d.teams.map((t) => ({ team: t.name, n: t.headcount })),
      };
    });
  }, [backendOrg, orgLoaded]);

  // 첫 fetch 전에는 null → 카운트 표시 자리에 "—" 또는 placeholder.
  const effectiveTotalHeadcount = orgLoaded ? (backendTotal ?? TOTAL_HEADCOUNT) : null;

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

  // v3.9 — 디지털 사원증 QR 클릭 진입 (/search?empId=...) — 자동 인원 선택.
  // filtered 가 비어있지 않을 때 매칭. 처음 1회만 실행 (sessionStorage 가드).
  useEffect(() => {
    const empId = searchParams.get('empId');
    if (!empId || filtered.length === 0) return;
    const guardKey = `__qr_empId_consumed:${empId}`;
    if (typeof window !== 'undefined' && window.sessionStorage.getItem(guardKey) === '1') return;
    const target = filtered.find((p) => p.id === empId);
    if (target) {
      setSelectedEmployee(target);
      pushViewedPerson({
        id: target.id,
        name: target.name,
        team: target.team,
        position: target.position,
      });
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(guardKey, '1');
      }
    }
  }, [filtered, searchParams]);

  const teamsForHq = useMemo(
    () => (hq === ALL ? [] : effectiveOrg.find((o) => o.hq === hq)?.teams ?? []),
    [hq, effectiveOrg],
  );

  // F4 — 팀명 → 본부 역매핑 (자동 동기화 + 자동완성용)
  const teamToHqMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const o of effectiveOrg) {
      for (const t of o.teams) {
        if (!map.has(t.team)) map.set(t.team, o.hq);
      }
    }
    return map;
  }, [effectiveOrg]);

  // F4 — 팀 선택 시 본부 자동 동기화
  const handleTeamChange = (value: string) => {
    setTeam(value);
    if (value === ALL) return;
    const ownerHq = teamToHqMap.get(value);
    if (ownerHq && ownerHq !== hq) {
      setHq(ownerHq);
      setSelectedHq(ownerHq);
    }
  };

  const handleReset = () => {
    setHq(ALL);
    setTeam(ALL);
    setPosition(ALL);
    setGender(ALL);
    setPlant(ALL);
    setQuery('');
    setSelectedHq(null);
  };

  // W3 — 4종 액션 훅에 위임. 행의 단축 버튼은 초안 작성 액션으로 라우팅.
  const handleQuickAction = (emp: FilteredEmployee) => {
    personActions.draft(emp);
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

  // v3.5 모바일 — uiux MobSearch 패턴 풀스크린.
  const isMobileSearch = useIsMobile();
  if (isMobileSearch) {
    return <AJINMobileSearch />;
  }

  return (
    <div className="page lg-page" data-screen-label="A · Org & Directory">
      {/* HERO */}
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">DIRECTORY & DOCUMENT SEARCH · MODULE A</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div className="ne-orb sm" aria-hidden style={{ flexShrink: 0 }} />
          <h1 className="lg-display" style={{ margin: 0 }}>조직도 · 인원 / 문서 검색</h1>
        </div>
        <p className="lg-sub">
          {tab === 'unified'
            ? '한 번 입력으로 사람 · 문서 · SOP 를 동시에 검색합니다. 의도가 모호해도 자동으로 관련 항목을 분할 표시합니다.'
            : tab === 'people'
              ? orgLoaded
                ? `아진산업 ${effectiveOrg.length}개 본부 · ${effectiveOrg.reduce((acc, o) => acc + o.teams.length, 0)}개 팀 · ${effectiveTotalHeadcount}명. 본부와 팀을 선택해 부서별 체계와 인원 정보를 한눈에 확인하세요.`
                : '조직도 데이터를 불러오는 중입니다…'
              : '8D 보고서 · ECN · 이메일 · 회의록 · PPAP 등 사내 문서를 BM25 + Vector 하이브리드 검색으로 찾아보세요.'}
        </p>
      </section>

      {/* W1·W2 — TABS (통합 / 인사 / 문서 / 도면) */}
      <section style={{ marginTop: -8, marginBottom: 8 }}>
        <Tabs
          items={[
            { id: 'unified', labelEn: 'UNIFIED', labelKo: '통합' },
            { id: 'people', labelEn: 'PEOPLE', labelKo: '인사' },
            { id: 'documents', labelEn: 'DOCUMENTS', labelKo: '문서' },
            { id: 'drawings', labelEn: 'DRAWINGS', labelKo: '도면' },
          ]}
          active={tab}
          onChange={(id) => setTab(id as TabId)}
        />
      </section>

      {tab === 'unified' && (
        <>
          <UnifiedSearchPanel
            onSwitchTab={(t) => setTab(t)}
            initialQuery={pickedQuery}
            triggerNonce={pickedNonce}
          />
          {/* W6 — 신입(role_level<=2)에게만 노출 */}
          <OnboardingSidePanel />
          <HistoryFavoritesPanel
            onPickQuery={(q) => {
              setPickedQuery(q);
              setPickedNonce((n) => n + 1);
            }}
            onPickPerson={(_id, name) => {
              setQuery(name);
              setTab('people');
            }}
            onPickDoc={() => {
              setTab('documents');
            }}
          />
        </>
      )}

      {tab === 'documents' && <DocumentSearchPanel />}

      {tab === 'drawings' && <DrawingsPanel />}

      {tab === 'people' && (
        <>
      {/* ORG CHART */}
      <section className="lg-card lg-orgchart">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">ORG CHART · 조직도</div>
            <h2 className="lg-h2">본부 → 팀 구조</h2>
          </div>
          <div className="lg-pill">
            {orgLoaded
              ? `총 ${effectiveTotalHeadcount}명 · ${effectiveOrg.length} HQ · ${effectiveOrg.reduce((acc, o) => acc + o.teams.length, 0)} TEAMS`
              : '로딩 중…'}
          </div>
        </div>

        <div className="org-diagram">
          <div className="org-ceo">
            <div className="org-node-glass ceo">
              <div className="org-node-eyebrow">CEO · 대표이사</div>
              <div className="org-node-title">AJIN INDUSTRY</div>
              <div className="org-node-sub">
                아진산업 주식회사 · {orgLoaded ? `${effectiveTotalHeadcount}명` : '— 명'}
              </div>
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
          <div
            className="org-hq-row"
            style={{ ['--hq-count' as 'gridColumn']: String(effectiveOrg.length || 6) }}
          >
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
            {/* F4 — 본부 미선택 시도 활성. 본부 미선택이면 30개 팀 본부별 optgroup. */}
            <select
              value={team}
              onChange={(e) => handleTeamChange(e.target.value)}
            >
              <option>{ALL}</option>
              {hq === ALL
                ? effectiveOrg.map((o) => (
                    <optgroup key={o.hq} label={o.hq}>
                      {o.teams.map((t) => (
                        <option key={`${o.hq}-${t.team}`}>{t.team}</option>
                      ))}
                    </optgroup>
                  ))
                : teamsForHq.map((t) => (
                    <option key={t.team}>{t.team}</option>
                  ))}
            </select>
          </div>
          {/* F4 — 팀명 직접 입력 자동완성 (datalist). 팀 선택 시 본부 자동 동기화 */}
          <div className="lg-field">
            <label>팀 빠른 검색</label>
            <input
              type="search"
              list="ajin-team-options"
              placeholder="팀명 직접 입력..."
              onChange={(e) => {
                const v = e.target.value.trim();
                if (!v) return;
                if (teamToHqMap.has(v)) {
                  handleTeamChange(v);
                }
              }}
            />
            <datalist id="ajin-team-options">
              {effectiveOrg.flatMap((o) =>
                o.teams.map((t) => (
                  <option
                    key={`opt-${o.hq}-${t.team}`}
                    value={t.team}
                    label={o.hq}
                  />
                )),
              )}
            </datalist>
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
                    onClick={() => {
                      setSelectedEmployee(p);
                      // W4 — 최근 본 사람 기록
                      pushViewedPerson({
                        id: p.id,
                        name: p.name,
                        team: p.team,
                        position: p.position,
                      });
                    }}
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
                      {/* F5 — 사내 이메일은 PARTIAL/FULL 모두 공개 (HIDDEN 만 빈값) */}
                      {p.email ? (
                        <a href={`mailto:${p.email}`}>{p.email}</a>
                      ) : (
                        <span className="dim">—</span>
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
      {/* W3 — 4종 액션(메일/멘션/초안/챗봇) personActions 훅 위임 */}
      <EmployeeDetailDrawer
        employee={selectedEmployee}
        isOpen={selectedEmployee !== null}
        onClose={() => setSelectedEmployee(null)}
        onMail={(e) => personActions.mail(e)}
        onMention={(e) => personActions.copyMention(e)}
        onAskChat={(e) => {
          personActions.askChat(e);
          setSelectedEmployee(null);
        }}
        onDraft={(e) => {
          personActions.draft(e);
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
        </>
      )}
    </div>
  );
}
