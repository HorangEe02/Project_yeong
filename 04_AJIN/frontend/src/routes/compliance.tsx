// compliance.tsx — Module D 백엔드 연동 버전.
// 모든 데이터(Scenarios / Crawlers / Changes / Tariff / Facilities)를
// /api/compliance/* 에서 fetch. 다운로드는 fetch 결과 기반 Markdown 빌드.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import { ScenarioSimulationModal } from '@components/compliance/ScenarioSimulationModal';
import { ScenarioDetailModal } from '@components/compliance/ScenarioDetailModal';
import { CrawlResultsDrawer } from '@components/compliance/CrawlResultsDrawer';
import { BulkReportModal } from '@components/compliance/BulkReportModal';
import { SearchBar } from '@components/compliance/SearchBar';
import {
  acknowledgeChange,
  fetchChanges,
  fetchFacilities,
  fetchRiskScores,
  fetchScenarios,
  runAllCrawlers,
  simulateTariff,
  type ChangeItem,
  type CrawlRunResult,
  type CrawlerName,
  type FacilityItem,
  type RiskScoreItem,
  type ScenarioRaw,
  type TariffSimItem,
} from '@api/compliance';

// ──────────────────────────────────────────────────────────────────
// Type aliases (UI)
// ──────────────────────────────────────────────────────────────────

type CatLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

interface ScenarioCard {
  id: string;
  title: string;
  en: string;
  score: number;
  cat: CatLevel;
  dday: number;
  desc: string;
  risk: { fin: number; pos: number; urg: number };
  sites: string[];
  depts: string[];
}

interface CrawlerCard {
  id: number;
  key: CrawlerName;
  name: string;
  target: string;
  last: string;
  changes: number;
  status: 'ok' | 'err' | 'idle';
}

interface PlantCard {
  plant_id: string;
  name: string;
  type: string;
  certs: string[];
  domestic: boolean;
}

// ──────────────────────────────────────────────────────────────────
// Adapters: backend → UI
// ──────────────────────────────────────────────────────────────────

const SCN_EN_MAP: Record<string, string> = {
  'SCN-001': 'KOSHA SAFETY DISTANCE',
  'SCN-002': 'EU REACH AUTHORIZATION',
  'SCN-003': 'EV BATTERY HV SAFETY',
  'SCN-004': 'WORKPLACE NOISE LIMIT',
  'US-TRADE-001': 'US TARIFF 25%',
  'US-TRADE-002': 'US TARIFF SIMULATION',
};

function gradeToCat(grade: string): CatLevel {
  const g = grade.toUpperCase();
  if (g === 'CRITICAL' || g === 'HIGH' || g === 'MEDIUM' || g === 'LOW') return g;
  return 'MEDIUM';
}

function toScenarioCard(
  s: RiskScoreItem,
  scn?: ScenarioRaw,
  classified?: { departments: string[] },
): ScenarioCard {
  return {
    id: s.scenario_id,
    title: s.title,
    en: SCN_EN_MAP[s.scenario_id] ?? s.scenario_id,
    score: Math.round(s.total_score),
    cat: gradeToCat(s.grade),
    dday: s.days_remaining ?? 0,
    desc: scn?.description ?? scn?.regulation?.article ?? '',
    risk: {
      fin: Math.round(s.financial_impact),
      pos: Math.round(s.likelihood),
      urg: Math.round(s.urgency),
    },
    sites: s.affected_plants.length ? s.affected_plants : ['—'],
    depts: classified?.departments ?? [],
  };
}

const CRAWLER_META: { key: CrawlerName; id: number; name: string; target: string }[] = [
  { id: 1, key: 'iso', name: 'ISO Crawler', target: 'ISO 14001 / 45001' },
  { id: 2, key: 'msds', name: 'MSDS Crawler', target: '화학물질안전보건자료' },
  { id: 3, key: 'eu_regulation', name: 'EU Regulation', target: 'REACH · RoHS · ELV' },
  { id: 4, key: 'domestic_law', name: 'Domestic Law', target: '산안법 · 화관법 · 환경법' },
  { id: 5, key: 'oem_quality', name: 'OEM Quality', target: 'IATF 16949 · PPAP · FMEA' },
  { id: 6, key: 'apqp', name: 'APQP Crawler', target: 'APQP 단계별 요구사항' },
  { id: 7, key: 'carbon_esg', name: 'Carbon ESG', target: '탄소 배출 / ESG 지표' },
  { id: 8, key: 'ev_battery', name: 'EV Battery', target: 'EV 배터리 (UN R100)' },
  { id: 9, key: 'global_trade', name: 'Global Trade', target: '관세 · FTA · 무역 규제' },
];

function toCrawlerCard(meta: typeof CRAWLER_META[number], r?: CrawlRunResult): CrawlerCard {
  const last = r?.crawled_at
    ? new Date(r.crawled_at).toISOString().slice(5, 16).replace('T', ' ')
    : '—';
  return {
    id: meta.id,
    key: meta.key,
    name: meta.name,
    target: meta.target,
    last,
    changes: r?.updates_found ?? 0,
    status: r ? (r.errors?.length ? 'err' : 'ok') : 'idle',
  };
}

function toPlantCard(f: FacilityItem): PlantCard {
  const isDomestic = f.country === 'KR' || !f.country;
  // 첫 번째 process or kind를 type 으로
  const type =
    f.processes?.[0] ??
    (f.kind === 'subsidiary_overseas' ? f.country : f.kind === 'plant' ? 'HQ' : 'Subsidiary');
  return {
    plant_id: f.plant_id,
    name: f.name,
    type: type || '—',
    certs: f.certifications ?? [],
    domestic: isDomestic,
  };
}

// ──────────────────────────────────────────────────────────────────
// Markdown builders (다운로드용)
// ──────────────────────────────────────────────────────────────────

function buildScenariosMarkdown(s: ScenarioCard[]): string {
  const lines: string[] = ['# 규제 현황 시나리오 TOP', ''];
  for (const x of s) {
    lines.push(`## ${x.title} (${x.en})`, '');
    lines.push(`- 카테고리: **${x.cat}**`);
    lines.push(`- 위험도 점수: **${x.score}/100**`);
    lines.push(`- 대응 마감: D-${x.dday}`);
    lines.push(`- 설명: ${x.desc || '—'}`);
    lines.push(`- 영향 시설: ${x.sites.join(', ')}`);
    lines.push(`- 리스크 — 재무 ${x.risk.fin}/40 · 가능성 ${x.risk.pos}/30 · 긴급 ${x.risk.urg}/30`, '');
  }
  return lines.join('\n');
}

function buildChangesMarkdown(items: ChangeItem[], total: number): string {
  const lines: string[] = ['# 법규 변경 감지 보고서', ''];
  lines.push(`총 변경 건수: **${total}건**`, '');
  lines.push('| 유형 | 규제 | 항목 | 일자 | 상태 |');
  lines.push('|---|---|---|---|---|');
  for (const it of items) {
    const date = (it.detected_at || '').slice(0, 10);
    const status = it.acknowledged ? '처리됨' : '미확인';
    lines.push(`| ${it.change_type} | ${it.regulation_type} | ${it.title || it.item_id} | ${date} | ${status} |`);
  }
  return lines.join('\n');
}

function buildTariffMarkdown(items: TariffSimItem[], rate: number, totalKrwBillion: number): string {
  const lines: string[] = ['# 美 관세 영향 시뮬레이션', ''];
  lines.push(`적용 관세율: **${rate}%**`);
  lines.push(`연 추가 부담: **${totalKrwBillion.toFixed(1)}억원**`, '');
  lines.push('| 품목 | 관세율 | 단가 추가관세 (USD) | 연간 추가 비용 (억원) |');
  lines.push('|---|---:|---:|---:|');
  for (const it of items) {
    const krwBn = it.annual_tariff_krw / 1e8;
    lines.push(`| ${it.product} | ${it.tariff_rate}% | ${it.unit_tariff.toFixed(2)} | ${krwBn.toFixed(2)} |`);
  }
  return lines.join('\n');
}

function buildPlantsMarkdown(plants: PlantCard[]): string {
  const lines: string[] = ['# 글로벌 사업장', ''];
  const dom = plants.filter((p) => p.domestic).length;
  const ovs = plants.length - dom;
  lines.push(`국내 ${dom}개 + 해외 ${ovs}개 (총 ${plants.length}개소)`, '');
  lines.push('| 사업장 | 구분 | 유형 | 인증 |');
  lines.push('|---|---|---|---|');
  for (const p of plants) {
    lines.push(`| ${p.name} | ${p.domestic ? '국내' : '해외'} | ${p.type} | ${p.certs.join(', ') || '—'} |`);
  }
  return lines.join('\n');
}

const DOCS = [
  { name: '산안법 시행규칙 개정안', source: '고용노동부', version: '2026.04', doc_type: 'kosha_amend' },
  { name: 'REACH SVHC 등재 후보 리스트 v28', source: 'ECHA', version: '2026.04', doc_type: 'reach_svhc' },
  { name: '美 자동차부품 232조 관세 검토안', source: 'USTR', version: '2026.03', doc_type: 'ustr_232' },
  { name: 'IATF 16949 Sanctioned Interpretations', source: 'IATF', version: '2026.01', doc_type: 'iatf_si' },
];

function buildSingleDocMarkdown(doc: typeof DOCS[number]): string {
  return [
    `# ${doc.name}`,
    '',
    `- 출처: ${doc.source}`,
    `- 버전: ${doc.version}`,
    `- 문서 유형: ${doc.doc_type}`,
    '',
    '※ 원문은 각 출처 공식 사이트에서 확인 후 본 보고서에 첨부 바람.',
  ].join('\n');
}

// ──────────────────────────────────────────────────────────────────
// Component
// ──────────────────────────────────────────────────────────────────

type ComplianceTab = 'updates' | 'monitor' | 'sites' | 'docs';

const TABS: { k: ComplianceTab; en: string; ko: string }[] = [
  { k: 'updates', en: 'UPDATES', ko: '법규 업데이트' },
  { k: 'monitor', en: 'MONITOR', ko: '영향 분석' },
  { k: 'sites', en: 'SITES', ko: '사업장' },
  { k: 'docs', en: 'DOCS', ko: '법규 문서' },
];

export function Compliance() {
  const nav = useNavigate();
  const [tab, setTab] = useState<ComplianceTab>('updates');
  const [tariff, setTariff] = useState(25);

  // v3.6 — 사용자 사업장 정보 (Item 2: 본인 사업장 영향 시나리오 우선 노출)
  const user = useAuthStore((s) => s.user);
  const userPlant: string =
    (user as { plant?: string; current_plant?: string; site?: string } | null)?.plant
      ?? (user as { current_plant?: string } | null)?.current_plant
      ?? (user as { site?: string } | null)?.site
      ?? '';
  // 필터 모드: 'mine' = 본인 사업장 영향만, 'all' = 전체 (기본 본인 사업장 정보가 있을 때 mine)
  const [scenarioFilter, setScenarioFilter] = useState<'mine' | 'all'>(
    userPlant ? 'mine' : 'all',
  );

  // v3.6 Phase 2 — 시뮬레이션 Modal + 크롤링 결과 Drawer + 영향 분석 동적 필터
  const [selectedSimScenario, setSelectedSimScenario] = useState<{
    id: string;
    title: string;
    cat: string;
  } | null>(null);
  const [selectedCrawler, setSelectedCrawler] = useState<{
    name: string;
    label?: string;
  } | null>(null);
  const [, setSelectedScenarioId] = useState<string | null>(null);

  // v3.6 Phase 3 — 시나리오 원문 상세 Modal (시뮬레이션과 분리)
  const [selectedDetailScenario, setSelectedDetailScenario] = useState<{
    id: string;
    title: string;
  } | null>(null);

  // v3.6 Phase 4 — 9개 통합 보고서 다운로드 모달
  const [bulkModalOpen, setBulkModalOpen] = useState(false);

  // ── server state ──
  const [scenarios, setScenarios] = useState<ScenarioCard[]>([]);
  const [crawlers, setCrawlers] = useState<CrawlerCard[]>(
    CRAWLER_META.map((m) => toCrawlerCard(m, undefined)),
  );
  const [changes, setChanges] = useState<ChangeItem[]>([]);
  const [changeStats, setChangeStats] = useState<ChangeListResponseStats>({});
  const [plants, setPlants] = useState<PlantCard[]>([]);
  const [tariffItems, setTariffItems] = useState<TariffSimItem[]>([]);
  const [tariffTotalKrwBn, setTariffTotalKrwBn] = useState(0);
  const [crawlBusy, setCrawlBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ── 초기 로드 ──
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [scnRes, riskRes, chRes, faRes] = await Promise.all([
          fetchScenarios(),
          fetchRiskScores(),
          fetchChanges(20, false),
          fetchFacilities(),
        ]);
        if (cancelled) return;

        const scnById = new Map<string, ScenarioRaw>();
        for (const s of scnRes.scenarios) {
          const k = s.scenario_id ?? s.id;
          if (k) scnById.set(k, s);
        }
        // v3.6 — 전체 시나리오 저장. 사용자 사업장 필터는 displayedScenarios useMemo 에서 적용.
        const cards = riskRes.scores.map((s) =>
          toScenarioCard(s, scnById.get(s.scenario_id)),
        );
        setScenarios(cards);

        setChanges(chRes.changes);
        setChangeStats(chRes.stats ?? {});
        setPlants(faRes.facilities.map(toPlantCard));
      } catch (e) {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : String(e));
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // v3.6 — 표시할 시나리오 (사업장 필터 + 상위 N 컷)
  // mine: user.plant 가 sites 에 포함된 시나리오 + 그 외에서 상위 점수 보충 (최대 6)
  // all : 전체 위험도 순 (최대 6)
  const displayedScenarios = useMemo(() => {
    if (scenarios.length === 0) return [];
    if (scenarioFilter === 'all' || !userPlant) {
      return scenarios.slice(0, 6);
    }
    const matched = scenarios.filter((s) =>
      s.sites.some((site) => site && site !== '—' && site.includes(userPlant)),
    );
    // 매칭 결과가 6개 미만이면 상위 점수에서 보충 (사용자가 전체 흐름도 파악 가능하도록)
    if (matched.length < 6) {
      const fillers = scenarios
        .filter((s) => !matched.find((m) => m.id === s.id))
        .slice(0, 6 - matched.length);
      return [...matched, ...fillers];
    }
    return matched.slice(0, 6);
  }, [scenarios, scenarioFilter, userPlant]);

  const matchedCount = useMemo(() => {
    if (!userPlant) return 0;
    return scenarios.filter((s) =>
      s.sites.some((site) => site && site !== '—' && site.includes(userPlant)),
    ).length;
  }, [scenarios, userPlant]);

  // ── 관세 슬라이더 → 백엔드 호출 (디바운스 250ms) ──
  const tariffTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (tariffTimer.current) clearTimeout(tariffTimer.current);
    tariffTimer.current = setTimeout(async () => {
      try {
        const r = await simulateTariff(tariff);
        setTariffItems(r.results);
        setTariffTotalKrwBn(r.total_annual_krw_billion);
      } catch {
        // 401/네트워크 실패 시 조용히 skip — 로컬 state 유지
      }
    }, 250);
    return () => {
      if (tariffTimer.current) clearTimeout(tariffTimer.current);
    };
  }, [tariff]);

  // ── RUN ALL 크롤러 ──
  const handleRunAll = useCallback(async () => {
    if (crawlBusy) return;
    setCrawlBusy(true);
    try {
      const out = await runAllCrawlers();
      setCrawlers(CRAWLER_META.map((m) => toCrawlerCard(m, out.crawlers[m.key])));
      // 변경 이력 갱신
      const ch = await fetchChanges(20, false);
      setChanges(ch.changes);
      setChangeStats(ch.stats ?? {});
    } catch (e) {
      alert(`크롤러 실행 실패: ${e instanceof Error ? e.message : e}`);
    } finally {
      setCrawlBusy(false);
    }
  }, [crawlBusy]);

  // ── 변경 확인 ──
  const handleAck = useCallback(async (id: number) => {
    try {
      await acknowledgeChange(id);
      const ch = await fetchChanges(20, false);
      setChanges(ch.changes);
      setChangeStats(ch.stats ?? {});
    } catch (e) {
      alert(`확인 처리 실패: ${e instanceof Error ? e.message : e}`);
    }
  }, []);

  // ── derived ──
  const totalChanges = changeStats.total ?? changes.length;
  const newCount = changeStats.added ?? 0;
  const modCount = changeStats.modified ?? 0;
  const unackCount = changeStats.unacknowledged ?? 0;

  const totalImpact = tariffTotalKrwBn;

  return (
    <div className="page lg-page" data-screen-label="D · Compliance">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">COMPLIANCE MONITORING · MODULE D</div>
        <h1 className="lg-display">법규 / 규정 모니터링</h1>
        <p className="lg-sub">
          산업안전법·REACH·관세·IATF 등 국내외 법규 변경을 매일 자동 수집해, 우리 회사 사업장({plants.length || 19}개)에 미치는 영향을 한눈에 보여드립니다. 기한이 임박한 규제를 우선 표시하고, 영향받는 부서·시설을 자동으로 연결해 대응 일정을 세울 수 있습니다.
        </p>
        <div className="lg-hero-search">
          <SearchBar
            onSelect={(hit) => {
              if (hit.index === 'scenarios') {
                const id = String(hit.id || hit.payload?.scenario_id || '');
                if (id) {
                  setSelectedDetailScenario({ id, title: hit.title });
                }
              } else if (hit.index === 'regulations') {
                // F5 — regulations 단일 상세 페이지로 이동.
                // 시나리오 카드와 정확히 매칭되면 시나리오 모달을 우선.
                const matched = scenarios.find(
                  (s) => s.title === hit.title || hit.title.includes(s.title),
                );
                if (matched) {
                  setSelectedDetailScenario({ id: matched.id, title: matched.title });
                } else {
                  nav(`/compliance/reg/${encodeURIComponent(hit.id)}`);
                }
              } else {
                // G7: glossary 페이지로 이동 (검색어로 자동 필터)
                nav(`/compliance/glossary?q=${encodeURIComponent(hit.title)}`);
              }
            }}
            onSeeAll={(q) => nav(`/compliance/search?q=${encodeURIComponent(q)}`)}
          />
        </div>
        {loadError && (
          <p className="lg-sub" style={{ color: 'var(--hud-red, #f33)' }}>
            ⚠ 백엔드 연결 실패: {loadError}
          </p>
        )}
      </section>

      <div className="lg-tabs">
        {TABS.map((t) => (
          <button
            key={t.k}
            className={'lg-tab' + (tab === t.k ? ' on' : '')}
            onClick={() => setTab(t.k)}
          >
            <span className="en">{t.en}</span>
            <span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {/* ───────── UPDATES ───────── */}
      {tab === 'updates' && (
        <>
          {/* SCENARIOS */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">
                  SCENARIOS · {scenarioFilter === 'mine' && userPlant ? `${userPlant} 영향` : `전체 ${scenarios.length}건`}
                </div>
                <h2 className="lg-h2">
                  규제 현황 시나리오
                  {scenarioFilter === 'mine' && userPlant && (
                    <span className="lg-h2-sub">
                      · 본인 사업장 매칭 {matchedCount}건
                    </span>
                  )}
                </h2>
              </div>
              <span className="lg-pill">위험도 점수 100점 기준</span>
            </div>

            {/* v3.6 — 사용자 사업장 필터 토글 (Item 2) */}
            {userPlant && (
              <div
                style={{
                  display: 'flex',
                  gap: 8,
                  marginBottom: 14,
                  padding: '8px 0',
                }}
              >
                <button
                  className={'lg-btn ' + (scenarioFilter === 'mine' ? '' : 'ghost') + ' sm'}
                  onClick={() => setScenarioFilter('mine')}
                  title={`${userPlant} 사업장 영향 시나리오 우선 표시`}
                >
                  내 사업장 ({userPlant}) {matchedCount > 0 && `· ${matchedCount}건`}
                </button>
                <button
                  className={'lg-btn ' + (scenarioFilter === 'all' ? '' : 'ghost') + ' sm'}
                  onClick={() => setScenarioFilter('all')}
                  title="전체 사업장 시나리오 (위험도순)"
                >
                  전체 보기
                </button>
              </div>
            )}

            <div className="lg-scen-grid">
              {displayedScenarios.length === 0 && (
                <div className="lg-sub">
                  {scenarios.length === 0
                    ? '불러오는 중…'
                    : scenarioFilter === 'mine'
                      ? `${userPlant} 영향 시나리오가 없습니다. '전체 보기'로 전환해 보세요.`
                      : '표시할 시나리오가 없습니다.'}
                </div>
              )}
              {displayedScenarios.map((s) => (
                <div key={s.id} className={'lg-scen cat-' + s.cat.toLowerCase()}>
                  <div className="lg-scen-top">
                    <span className="cat">{s.cat}</span>
                    <span className="dday">D-{s.dday}</span>
                  </div>
                  <div className="lg-scen-score">
                    {s.score}<span>/100</span>
                  </div>
                  <div className="lg-scen-title">{s.title}</div>
                  <div className="lg-scen-en">{s.en}</div>
                  <div className="lg-scen-desc">{s.desc}</div>
                  <div className="lg-scen-risk">
                    <span><i>재무</i><b>{s.risk.fin}</b><u>/40</u></span>
                    <span><i>가능성</i><b>{s.risk.pos}</b><u>/30</u></span>
                    <span><i>긴급</i><b>{s.risk.urg}</b><u>/30</u></span>
                  </div>
                  <div className="lg-scen-meta">
                    <div><span className="ko">영향</span> {s.sites.join(', ')}</div>
                  </div>
                  {/* v3.6 Phase 2 — 시뮬레이션 + Phase 3 상세 버튼.
                      두 버튼 동일 라인에 배치 (margin-top:auto 로 카드 푸터에 정렬). */}
                  <div
                    style={{
                      display: 'flex',
                      gap: 6,
                      marginTop: 'auto',
                    }}
                  >
                    <button
                      className="lg-btn ghost"
                      style={{ flex: 1 }}
                      onClick={() =>
                        setSelectedDetailScenario({ id: s.id, title: s.title })
                      }
                      title="법규 원문·변경 내역·체크리스트 보기"
                    >
                      📋 상세
                    </button>
                    <button
                      className="lg-btn"
                      style={{ flex: 1 }}
                      onClick={() =>
                        setSelectedSimScenario({ id: s.id, title: s.title, cat: s.cat })
                      }
                      title="위험도·영향·비용 시뮬레이션 보기"
                    >
                      시뮬레이션 ▶
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <DownloadActions
              content={() => buildScenariosMarkdown(displayedScenarios)}
              basename={`compliance_scenarios_${scenarioFilter === 'mine' && userPlant ? `${userPlant}_` : ''}${new Date().toISOString().slice(0, 10)}`}
              source="compliance"
              metadata={{
                title:
                  scenarioFilter === 'mine' && userPlant
                    ? `규제 현황 시나리오 — ${userPlant} 영향`
                    : '규제 현황 시나리오 (전체)',
                doc_type: 'compliance_scenarios',
              }}
            />
          </section>

          {/* CRAWLERS */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">CRAWLERS · 9개</div>
                <h2 className="lg-h2">크롤러 실행 현황</h2>
              </div>
              <div className="lg-actions" style={{ display: 'flex', gap: 8 }}>
                {/* v3.6 Phase 4 — 9개 전체 통합 보고서 다운로드 (모달 띄움) */}
                <button
                  className="lg-btn ghost"
                  onClick={() => setBulkModalOpen(true)}
                  title="9개 크롤러 결과를 단일 파일로 통합 다운로드"
                >
                  📦 전체 통합 보고서
                </button>
                <button className="lg-btn" onClick={handleRunAll} disabled={crawlBusy}>
                  {crawlBusy ? '실행 중…' : 'RUN ALL'}
                </button>
              </div>
            </div>
            <div className="lg-crawl-grid">
              {crawlers.map((c) => (
                <div
                  key={c.id}
                  className="lg-crawl"
                  onClick={() => setSelectedCrawler({ name: c.key, label: c.name })}
                  style={{ cursor: 'pointer' }}
                  title={`${c.name} 크롤링 결과 상세 보기`}
                >
                  <div className="lg-crawl-h">
                    <span className="num">{String(c.id).padStart(2, '0')}</span>
                    <span className={'lg-dot ' + (c.status === 'ok' ? 'ok' : c.status === 'err' ? 'err' : '')} />
                  </div>
                  <div className="lg-crawl-name">{c.name}</div>
                  <div className="lg-crawl-target">{c.target}</div>
                  <div className="lg-crawl-foot">
                    <span className="mono dim">{c.last}</span>
                    {c.changes ? <span className="lg-chg">{c.changes}건</span> : <span className="dim">—</span>}
                  </div>
                  {/* v3.6 Phase 2 — 크롤링 결과 Drawer 트리거 */}
                  <button
                    className="lg-btn ghost sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedCrawler({ name: c.key, label: c.name });
                    }}
                    style={{ marginTop: 8, fontSize: 11, padding: '4px 10px' }}
                  >
                    📄 상세 보기
                  </button>
                </div>
              ))}
            </div>
          </section>

          {/* CHANGE DETECTOR */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">CHANGE DETECTOR · 변경 감지</div>
                <h2 className="lg-h2">신규·수정 사항</h2>
              </div>
              <div className="lg-actions">
                <span className="lg-pill">총 {totalChanges}건</span>
              </div>
            </div>
            <div className="lg-metric-row">
              <div className="lg-metric"><span className="k">총 변경</span><span className="v">{totalChanges}</span></div>
              <div className="lg-metric"><span className="k">신규</span><span className="v">{newCount}</span></div>
              <div className="lg-metric"><span className="k">수정</span><span className="v">{modCount}</span></div>
              <div className="lg-metric warn"><span className="k">미확인</span><span className="v">{unackCount}</span></div>
            </div>
            <div className="lg-table-wrap">
              <table className="lg-table">
                <thead>
                  <tr>
                    <th>유형</th>
                    <th>규제 / 항목</th>
                    <th>일자</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {changes.length === 0 && (
                    <tr><td colSpan={4} className="dim">불러오는 중…</td></tr>
                  )}
                  {changes.map((it) => (
                    <tr key={it.id}>
                      <td>
                        <span className={'lg-tag ' + (it.change_type === 'added' ? 'new' : 'mod')}>
                          {it.change_type === 'added' ? '신규' : it.change_type === 'modified' ? '수정' : '삭제'}
                        </span>
                      </td>
                      <td>{it.regulation_type} / {it.title || it.item_id}</td>
                      <td className="mono dim">{(it.detected_at || '').slice(0, 10)}</td>
                      <td>
                        {!it.acknowledged ? (
                          <button className="lg-btn ghost sm" onClick={() => void handleAck(it.id)}>확인</button>
                        ) : (
                          <span className="lg-ok">✓ 처리됨</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <DownloadActions
              content={() => buildChangesMarkdown(changes, totalChanges)}
              basename={`compliance_changes_${new Date().toISOString().slice(0, 10)}`}
              source="compliance"
              metadata={{ title: '법규 변경 감지 보고서', doc_type: 'compliance_changes' }}
            />
          </section>

          {/* TARIFF SIMULATOR */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">TARIFF SIMULATOR · 관세</div>
                <h2 className="lg-h2">美 관세율 시나리오</h2>
              </div>
              <span className="lg-pill">JOON INC · 북미 공급분</span>
            </div>
            <div className="lg-tariff-control">
              <div>
                <div className="lg-eyebrow">관세율 조정</div>
                <div className="lg-tariff-val">
                  {tariff}<i>%</i>
                </div>
              </div>
              <input
                className="lg-range"
                type="range"
                min={0}
                max={50}
                step={1}
                value={tariff}
                onChange={(e) => setTariff(+e.target.value)}
              />
              <div>
                <div className="lg-eyebrow">연 추가 부담 추정</div>
                <div className="lg-tariff-val accent">
                  {totalImpact.toFixed(1)}<i>억</i>
                </div>
              </div>
            </div>
            <div className="lg-tariff-bars">
              {tariffItems.length === 0 && (
                <div className="lg-sub">시뮬레이션 중…</div>
              )}
              {tariffItems.map((it) => {
                const bn = it.annual_tariff_krw / 1e8;
                const maxBn = Math.max(...tariffItems.map((x) => x.annual_tariff_krw / 1e8), 1);
                return (
                  <div key={it.product} className="lg-tariff-row">
                    <span className="lbl">{it.product}</span>
                    <div className="lg-tariff-bar">
                      <span className="add" style={{ width: `${(bn / maxBn) * 70}%` }} />
                    </div>
                    <span className="val mono">
                      +{bn.toFixed(2)}억원/년
                    </span>
                  </div>
                );
              })}
            </div>
            <DownloadActions
              content={() => buildTariffMarkdown(tariffItems, tariff, totalImpact)}
              basename={`compliance_tariff_${tariff}pct_${new Date().toISOString().slice(0, 10)}`}
              source="compliance"
              metadata={{ title: `美 관세 ${tariff}% 영향 시뮬레이션`, doc_type: 'compliance_tariff' }}
            />
          </section>
        </>
      )}

      {/* ───────── MONITOR ───────── */}
      {tab === 'monitor' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">DEADLINE TIMELINE · D-DAY</div>
                <h2 className="lg-h2">대응 마감 타임라인</h2>
              </div>
            </div>
            <div className="lg-timeline">
              {scenarios.map((s) => (
                <div key={s.id} className={'lg-tl-row cat-' + s.cat.toLowerCase()}>
                  <span className="lg-tl-name">{s.title}</span>
                  <div className="lg-tl-bar">
                    <span className="lg-tl-fill" style={{ width: Math.max(5, 100 - Math.abs(s.dday) / 2) + '%' }} />
                    <span className="lg-tl-d">D-{s.dday}</span>
                  </div>
                  <span className="lg-tl-cat">{s.cat}</span>
                </div>
              ))}
              {scenarios.length === 0 && <div className="lg-sub">불러오는 중…</div>}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">IMPACT NETWORK · 영향 관계도</div>
                <h2 className="lg-h2">규제 → 시설 → 부서</h2>
              </div>
              <div className="lg-net-legend">
                <span><i className="d-reg" />규제 {scenarios.length}</span>
                <span><i className="d-site" />시설 {plants.length}</span>
              </div>
            </div>
            <div className="lg-impact-net">
              <svg viewBox="0 0 800 320" preserveAspectRatio="xMidYMid meet">
                {scenarios.slice(0, 3).map((s, i) => {
                  const y = 60 + i * 100;
                  return (
                    <g key={s.id} className="reg">
                      <circle cx="120" cy={y} r="26" />
                      <text x="120" y={y + 5} textAnchor="middle">{s.title.slice(0, 4)}</text>
                      {s.sites.slice(0, 2).map((site, j) => {
                        const sy = y + (j - 0.5) * 30;
                        return (
                          <line key={site}
                            x1="146" y1={y}
                            x2="354" y2={sy}
                            stroke="var(--hud-primary, #6FB1FC)" strokeWidth="1.5" opacity="0.5" />
                        );
                      })}
                    </g>
                  );
                })}
                {plants.slice(0, 6).map((p, i) => {
                  const y = 50 + i * 40;
                  return (
                    <g key={p.plant_id} className="site">
                      <rect x="350" y={y} width="80" height="32" rx="10" />
                      <text x="390" y={y + 20} textAnchor="middle">{p.name.slice(0, 6)}</text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <DownloadActions
              content={() => buildScenariosMarkdown(scenarios)}
              basename={`compliance_impact_${new Date().toISOString().slice(0, 10)}`}
              source="compliance"
              metadata={{ title: '규제 영향 관계도 보고서', doc_type: 'compliance_impact' }}
            />
          </section>
        </>
      )}

      {/* ───────── SITES ───────── */}
      {tab === 'sites' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-eyebrow">SITES · {plants.length} LOCATIONS</div>
              <h2 className="lg-h2">
                국내 {plants.filter((p) => p.domestic).length} + 해외 {plants.filter((p) => !p.domestic).length}
              </h2>
            </div>
            <div className="lg-actions">
              <span className="lg-pill">전체</span>
            </div>
          </div>
          <div className="lg-sites-grid">
            {plants.length === 0 && <div className="lg-sub">불러오는 중…</div>}
            {plants.map((p) => (
              <div key={p.plant_id} className={'lg-site ' + (p.domestic ? 'dom' : 'ovs')}>
                <div className="lg-site-h">
                  <span className="flag">{p.domestic ? '국내' : '해외'}</span>
                  <span className="type">{p.type}</span>
                </div>
                <div className="lg-site-name">{p.name}</div>
                <div className="lg-site-certs">
                  {p.certs.length ? (
                    p.certs.map((c) => <span key={c} className="cert">{c}</span>)
                  ) : (
                    <span className="cert ghost">—</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          <DownloadActions
            content={() => buildPlantsMarkdown(plants)}
            basename={`compliance_sites_${plants.length}`}
            source="compliance"
            metadata={{ title: `글로벌 사업장 ${plants.length}개소`, doc_type: 'compliance_sites' }}
          />
        </section>
      )}

      {/* ───────── DOCS ───────── */}
      {tab === 'docs' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-eyebrow">DOCS · 법규 문서 라이브러리</div>
              <h2 className="lg-h2">출처별 원문 / 개정안</h2>
            </div>
          </div>
          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead>
                <tr>
                  <th>문서</th>
                  <th>출처</th>
                  <th>버전</th>
                  <th style={{ minWidth: 380 }}>다운로드</th>
                </tr>
              </thead>
              <tbody>
                {DOCS.map((d) => (
                  <tr key={d.doc_type}>
                    <td>{d.name}</td>
                    <td className="dim">{d.source}</td>
                    <td className="mono">{d.version}</td>
                    <td>
                      <DownloadActions
                        content={() => buildSingleDocMarkdown(d)}
                        basename={`${d.doc_type}_${d.version.replace(/\./g, '')}`}
                        formats={['docx', 'pdf', 'hwp', 'hwpx']}
                        source="compliance"
                        metadata={{ title: d.name, doc_type: d.doc_type }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* v3.6 Phase 3 — 시나리오 원문 상세 Modal */}
      <ScenarioDetailModal
        scenarioId={selectedDetailScenario?.id ?? null}
        fallbackTitle={selectedDetailScenario?.title}
        fallbackScenario={
          selectedDetailScenario
            ? scenarios.find((s) => s.id === selectedDetailScenario.id)
            : undefined
        }
        isOpen={selectedDetailScenario !== null}
        onClose={() => setSelectedDetailScenario(null)}
        onShowSimulation={(id) => {
          // 상세 → 시뮬레이션 전환: 동일 시나리오 데이터로 시뮬 Modal 열기
          const card = scenarios.find((s) => s.id === id);
          if (card) {
            setSelectedSimScenario({ id: card.id, title: card.title, cat: card.cat });
          } else {
            setSelectedSimScenario({
              id,
              title: selectedDetailScenario?.title ?? id,
              cat: 'MEDIUM',
            });
          }
        }}
      />

      {/* v3.6 Phase 2 — 시뮬레이션 결과 Modal */}
      <ScenarioSimulationModal
        scenarioId={selectedSimScenario?.id ?? null}
        fallbackTitle={selectedSimScenario?.title}
        fallbackCategory={selectedSimScenario?.cat}
        fallbackScenario={
          selectedSimScenario
            ? scenarios.find((s) => s.id === selectedSimScenario.id)
            : undefined
        }
        userPlant={userPlant || undefined}
        isOpen={selectedSimScenario !== null}
        onClose={() => setSelectedSimScenario(null)}
        onShowImpact={(id) => {
          setSelectedScenarioId(id);
          setTab('monitor');
        }}
      />

      {/* v3.6 Phase 2 — 크롤러 결과 Drawer */}
      <CrawlResultsDrawer
        crawlerName={selectedCrawler?.name ?? null}
        displayName={selectedCrawler?.label}
        isOpen={selectedCrawler !== null}
        onClose={() => setSelectedCrawler(null)}
      />

      {/* v3.6 Phase 4 — 9개 통합 보고서 다운로드 Modal */}
      <BulkReportModal isOpen={bulkModalOpen} onClose={() => setBulkModalOpen(false)} />
    </div>
  );
}

// 보조 타입 — fetchChanges().stats 의 부분 타입
type ChangeListResponseStats = {
  total?: number;
  unacknowledged?: number;
  added?: number;
  modified?: number;
  removed?: number;
};

// useMemo 추후 활용을 위한 stub (eslint-no-unused-imports 회피)
void useMemo;
