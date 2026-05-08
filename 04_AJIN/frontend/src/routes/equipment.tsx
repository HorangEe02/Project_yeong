// equipment.tsx — 기능 F (설비/공정 AI) 라우터.
// 8개 탭 컴포넌트로 분리된 후의 슬림 구조 — 상태/효과/핸들러/useMemo만 보유.
//
// 구조:
//   components/equipment/
//     ├── tabs/          (8 sub-tab 컴포넌트)
//     ├── types.ts       (공유 타입)
//     ├── mockData.ts    (12 mock 상수)
//     ├── markdownBuilders.ts (5 빌더)
//     └── stateMappers.ts     (백엔드→UI 매핑)

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useUIStore, type EquipmentMainTab, type EquipmentSubTab } from '@store/ui';
import { useAuthStore } from '@store/auth';
import { isMenuVisible, getLockReason } from '@lib/rbac';
import type { Data } from 'plotly.js';
import {
  fetchOverview,
  fetchMolds,
  fetchMTBF,
  fetchMLEngines,
  fetchMarkov,
  fetchErrorCategories,
  fetchSPC,
  fetchChecklist,
  searchError,
  searchManual,
  uploadSPCCsv,
  type ErrorSearchPayload,
  type ManualSearchPayload,
} from '@api/equipment';
import type {
  OverviewResponse,
  MoldsResponse,
  MTBFResponse,
  MLEnginesStatusResponse,
  MarkovResponse,
  ErrorCategoriesResponse,
  ErrorSearchResponse,
  SPCResponse,
  ManualSearchResponse,
  InspectionChecklistResponse,
  SPCUploadResponse,
} from '@/types/equipment';

import type { EquipRow } from '@components/equipment/types';
import {
  MOCK_EQUIPMENT,
  MOCK_ERR_RESULTS,
  MOCK_INSPECTIONS,
  MOCK_MAINT_COST,
  MOCK_MARKOV_CHAIN,
  MOCK_METRICS,
  MOCK_ML_ENGINES,
  MOCK_MOLDS,
  MOCK_PROCESSES5,
  MOCK_CL,
  MOCK_LCL,
  MOCK_SPC_DATA,
  MOCK_UCL,
  SYMPTOM_CATS,
} from '@components/equipment/mockData';
import { backendRiskToUI, backendStatusToUI } from '@components/equipment/stateMappers';
import { DashboardSubTab } from '@components/equipment/tabs/DashboardSubTab';
import { AlertsSubTab } from '@components/equipment/tabs/AlertsSubTab';
import { EquipmentTypeSubTab } from '@components/equipment/tabs/EquipmentTypeSubTab';
import { PredictiveSubTab } from '@components/equipment/tabs/PredictiveSubTab';
import { SPCSubTab } from '@components/equipment/tabs/SPCSubTab';
import { MLEnginesSubTab } from '@components/equipment/tabs/MLEnginesSubTab';
import { ManualErrorTab } from '@components/equipment/tabs/ManualErrorTab';
import { InspectionTab } from '@components/equipment/tabs/InspectionTab';

// ──────────────────────────────────────────────────────────────────────────
// Tabs 정의
// ──────────────────────────────────────────────────────────────────────────

const MAIN_TABS: { k: EquipmentMainTab; en: string; ko: string }[] = [
  { k: 'overview', en: 'OVERVIEW', ko: '대시보드' },
  { k: 'manual_error', en: 'MANUAL & ERROR', ko: '매뉴얼 / 에러' },
  { k: 'inspection', en: 'INSPECTION', ko: '점검 이력' },
];

const SUB_TABS: { k: EquipmentSubTab; label: string }[] = [
  { k: 'overview', label: '설비 개요' },
  { k: 'alerts', label: '긴급 조치' },
  { k: 'equipment', label: '장비 유형' },
  { k: 'predictive', label: '예측 정비' },
  { k: 'spc', label: 'SPC · Nelson 8' },
  { k: 'ml', label: 'ML 엔진' },
];

// ──────────────────────────────────────────────────────────────────────────
// Component
// ──────────────────────────────────────────────────────────────────────────

export function Equipment() {
  // ── 부서 기반 접근 제어 ──
  const user = useAuthStore((s) => s.user);
  const allowed = isMenuVisible('equipment', user);
  const lockReason = getLockReason('equipment', user);

  const tab = useUIStore((s) => s.equipmentMainTab);
  const setTab = useUIStore((s) => s.setEquipmentMainTab);
  const sub = useUIStore((s) => s.equipmentSubTab);
  const setSub = useUIStore((s) => s.setEquipmentSubTab);

  // ── API state ─────────────────────────────────────────
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [molds, setMolds] = useState<MoldsResponse | null>(null);
  const [mtbf, setMtbf] = useState<MTBFResponse | null>(null);
  const [mlEngines, setMlEngines] = useState<MLEnginesStatusResponse | null>(null);
  const [markov, setMarkov] = useState<MarkovResponse | null>(null);
  const [categories, setCategories] = useState<ErrorCategoriesResponse | null>(null);
  const [spcResp, setSpcResp] = useState<SPCResponse | null>(null);
  const [errSearchResp, setErrSearchResp] = useState<ErrorSearchResponse | null>(null);
  const [manualResp, setManualResp] = useState<ManualSearchResponse | null>(null);
  const [checklist, setChecklist] = useState<InspectionChecklistResponse | null>(null);

  const [errSearching, setErrSearching] = useState(false);
  const [manualSearching, setManualSearching] = useState(false);
  const [spcLoading, setSpcLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResp, setUploadResp] = useState<SPCUploadResponse | null>(null);
  const [globalApiError, setGlobalApiError] = useState<string | null>(null);

  // ── User input state ───────────────────────────────────
  const [errQuery, setErrQuery] = useState('프레스에서 이상한 소리');
  const [equipFilter, setEquipFilter] = useState('프레스');
  const [symptom, setSymptom] = useState('진동');
  const [ragQuery, setRagQuery] = useState('베어링 교체 절차');
  const [spcProcessId, setSpcProcessId] = useState<string>('bumper_beam');
  const [uploadProcessId, setUploadProcessId] = useState<string>('cch');

  // ── Mount load ──────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const [ov, mld, mt, ml, cat, ck] = await Promise.allSettled([
          fetchOverview(),
          fetchMolds(),
          fetchMTBF(),
          fetchMLEngines(),
          fetchErrorCategories(),
          fetchChecklist('프레스'),
        ]);
        if (ov.status === 'fulfilled') setOverview(ov.value);
        if (mld.status === 'fulfilled') setMolds(mld.value);
        if (mt.status === 'fulfilled') setMtbf(mt.value);
        if (ml.status === 'fulfilled') setMlEngines(ml.value);
        if (cat.status === 'fulfilled') setCategories(cat.value);
        if (ck.status === 'fulfilled') setChecklist(ck.value);
        const anySuccess = [ov, mld, mt, ml, cat, ck].some((r) => r.status === 'fulfilled');
        if (!anySuccess) setGlobalApiError('백엔드 연결 실패 — Mock 데이터로 시연 모드');
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setGlobalApiError(`API 로드 실패: ${msg} — Mock 데이터로 시연 모드`);
      }
    })();
  }, []);

  // ── SPC tab 진입 시 lazy load ──────────────────────────
  useEffect(() => {
    if (sub !== 'spc' || tab !== 'overview') return;
    let cancelled = false;
    (async () => {
      setSpcLoading(true);
      try {
        const res = await fetchSPC(spcProcessId);
        if (!cancelled) setSpcResp(res);
      } catch {
        if (!cancelled) setSpcResp(null);
      } finally {
        if (!cancelled) setSpcLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [sub, tab, spcProcessId]);

  // ── 매뉴얼 탭 → markov chain 자동 로드 ──
  useEffect(() => {
    if (tab !== 'manual_error') return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchMarkov('E-101', 3);
        if (!cancelled) setMarkov(res);
      } catch {
        /* ignore */
      }
    })();
    return () => { cancelled = true; };
  }, [tab]);

  // ── 핸들러 ──────────────────────────────────────────
  const onErrorSearch = useCallback(async () => {
    setErrSearching(true);
    try {
      const payload: ErrorSearchPayload = { query: errQuery, equipment_filter: equipFilter, top_k: 5 };
      const res = await searchError(payload);
      setErrSearchResp(res);
    } catch (err) {
      console.warn('[error-search]', err instanceof Error ? err.message : String(err));
      setErrSearchResp(null);
    } finally {
      setErrSearching(false);
    }
  }, [errQuery, equipFilter]);

  const onManualSearch = useCallback(async () => {
    setManualSearching(true);
    try {
      const payload: ManualSearchPayload = { query: ragQuery, equipment_type: equipFilter, n_results: 5 };
      const res = await searchManual(payload);
      setManualResp(res);
    } catch (err) {
      console.warn('[manual-search]', err instanceof Error ? err.message : String(err));
      setManualResp(null);
    } finally {
      setManualSearching(false);
    }
  }, [ragQuery, equipFilter]);

  const onSPCUpload = useCallback(async (file: File) => {
    setUploading(true);
    try {
      const res = await uploadSPCCsv(file);
      setUploadResp(res);
      if (spcProcessId === uploadProcessId) {
        const refreshed = await fetchSPC(spcProcessId);
        setSpcResp(refreshed);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`업로드 실패: ${msg}`);
    } finally {
      setUploading(false);
    }
  }, [spcProcessId, uploadProcessId]);

  // ── derive (API → mock fallback) ──────────────────────
  const metrics = useMemo(() => {
    if (!overview) return MOCK_METRICS;
    const m = overview.metrics;
    const totalAlerts = (overview.processes || []).reduce((acc, p) => acc + (p.violation_count ?? 0), 0);
    return [
      { v: '92%', en: 'UPTIME', ko: '가동률' },
      {
        v: (overview.processes.reduce((a, p) => a + p.current_cpk, 0) / Math.max(overview.processes.length, 1)).toFixed(2),
        en: 'AVG Cpk',
        ko: '평균 공정능력',
      },
      { v: String(totalAlerts), en: 'ALERTS', ko: '활성 알람' },
      { v: '720h', en: 'MTBF', ko: '평균 무고장' },
      { v: String(m.molds_warning + m.molds_critical), en: 'MAINT DUE', ko: '정비 임박' },
    ];
  }, [overview]);

  const equipment7 = useMemo<EquipRow[]>(() => {
    if (!overview || !overview.equipment_types?.length) return MOCK_EQUIPMENT;
    return overview.equipment_types.map((e) => {
      const stateColor = e.color?.toLowerCase() ?? '';
      const state: EquipRow['state'] = stateColor.includes('red')
        ? 'crit'
        : stateColor.includes('yellow')
          ? 'warn'
          : 'ok';
      return {
        type: e.type,
        en: (e.icon || e.type).toUpperCase(),
        state,
        cpk: 1.5,
        alarm: e.codes,
      };
    });
  }, [overview]);

  const processes5 = useMemo(() => {
    if (!overview?.processes?.length) return MOCK_PROCESSES5;
    return overview.processes.map((p) => ({
      name: p.process_name,
      state: backendStatusToUI(p.status),
      cpk: p.current_cpk,
      viol: p.violation_count,
      rules: p.violated_rules.map((n) => `Rule ${n}`),
    }));
  }, [overview]);

  const moldList = useMemo(() => {
    if (!molds?.items?.length) return MOCK_MOLDS;
    return molds.items.map((m) => ({
      id: m.mold_id,
      part: m.part_name || m.mold_name,
      shots: m.current_shots,
      max: m.max_shots,
      risk: backendRiskToUI(m.risk_level),
    }));
  }, [molds]);

  const maintCost = useMemo(() => {
    if (!mtbf?.top5_cost?.length) return MOCK_MAINT_COST;
    return mtbf.top5_cost.map((m, i) => {
      const item = mtbf.items.find((x) => x.machine_name === m.machine_name);
      return {
        eq: m.machine_name,
        cost: Math.round(m.total_cost / 10000),
        jobs: item?.total_repairs ?? 0,
        next: item?.next_predicted_date ? `D-${item.days_until_next}` : ['D-3', 'D-12', 'D-24', 'D-45', 'D-60'][i],
      };
    });
  }, [mtbf]);

  const mtbfBar = useMemo<Data[]>(() => {
    const src = mtbf?.items?.length ? mtbf.items : null;
    const labels = src ? src.map((m) => m.machine_name) : MOCK_MAINT_COST.map((m) => m.eq);
    const costs = src ? src.map((m) => Math.round(m.avg_repair_cost / 10000)) : MOCK_MAINT_COST.map((m) => m.cost);
    const repairs = src ? src.map((m) => m.total_repairs) : MOCK_MAINT_COST.map((m) => m.jobs);

    const maxCost = Math.max(...costs, 1);
    const colors = costs.map((c) => {
      const ratio = c / maxCost;
      if (ratio > 0.75) return '#C0392B';
      if (ratio > 0.5) return '#E8A317';
      if (ratio > 0.25) return '#FCB132';
      return '#2980B9';
    });

    return [
      {
        type: 'bar',
        x: labels,
        y: costs,
        name: '누적 비용 (만원)',
        marker: { color: colors, line: { color: '#fff', width: 1 } },
        text: costs.map((c) => `${c.toLocaleString()}만`),
        textposition: 'outside',
        textfont: { size: 11 },
        hovertemplate: '<b>%{x}</b><br>비용: %{y:,}만원<extra></extra>',
      },
      {
        type: 'scatter',
        mode: 'lines+markers',
        x: labels,
        y: repairs,
        name: '수리 건수',
        yaxis: 'y2',
        line: { color: '#FCB132', width: 2 },
        marker: { size: 8, color: '#FCB132', line: { color: '#fff', width: 1 } },
        hovertemplate: '<b>%{x}</b><br>수리: %{y}건<extra></extra>',
      },
    ] as Data[];
  }, [mtbf]);

  const mlList = useMemo(() => {
    if (!mlEngines?.engines?.length) return MOCK_ML_ENGINES;
    return mlEngines.engines.map((e) => ({
      name: e.name_en,
      p99: e.last_trained ?? '—',
      model: e.library,
      online: e.status === 'online',
    }));
  }, [mlEngines]);

  const errResults = useMemo(() => {
    if (!errSearchResp?.results?.length) return MOCK_ERR_RESULTS;
    return errSearchResp.results.map((r) => ({
      code: r.code,
      name: r.description,
      sim: r.score,
      sev: r.severity.toUpperCase(),
      count: 0,
      mttr: '—',
      cause: r.cause,
    }));
  }, [errSearchResp]);

  const markovChain = useMemo(() => {
    if (!markov?.next_predictions?.length) return MOCK_MARKOV_CHAIN;
    return markov.next_predictions.map((p) => ({ code: p.code, name: p.description, prob: p.probability }));
  }, [markov]);

  // Plotly Network 데이터 (Markov 연쇄 고장 그래프)
  const markovGraph = useMemo<Data[]>(() => {
    const cx = 0;
    const cy = 0;
    const radius = 1.0;
    const total = Math.max(markovChain.length, 1);
    const startAngle = -Math.PI / 3;
    const endAngle = Math.PI / 3;

    const branches = markovChain.map((m, i) => {
      const angle = total === 1 ? 0 : startAngle + (i * (endAngle - startAngle)) / (total - 1);
      const color = m.prob > 0.5 ? '#C0392B' : m.prob > 0.3 ? '#E8A317' : '#2980B9';
      return {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
        label: `${m.code}<br>${m.name}<br><span style="color:${color}">P=${m.prob.toFixed(2)}</span>`,
        size: 28 + m.prob * 24,
        color,
      };
    });

    const center = {
      x: cx,
      y: cy,
      label: `${markov?.current_code ?? 'E-101'}<br>${markov?.current_category ?? '베어링 마모'}`,
      size: 44,
      color: '#FCB132',
    };
    const allNodes = [center, ...branches];

    const edgeX: (number | null)[] = [];
    const edgeY: (number | null)[] = [];
    for (const b of branches) {
      edgeX.push(center.x, b.x, null);
      edgeY.push(center.y, b.y, null);
    }

    return [
      {
        type: 'scatter',
        mode: 'lines',
        x: edgeX,
        y: edgeY,
        line: { color: '#8A8276', width: 1.5 },
        hoverinfo: 'none',
        showlegend: false,
      },
      {
        type: 'scatter',
        mode: 'markers+text',
        x: allNodes.map((n) => n.x),
        y: allNodes.map((n) => n.y),
        text: allNodes.map((n) => n.label),
        textposition: 'middle right',
        textfont: { size: 11, family: 'AJIN Sans, Pretendard, sans-serif' },
        marker: {
          size: allNodes.map((n) => n.size),
          color: allNodes.map((n) => n.color),
          line: { color: '#fff', width: 1.5 },
          opacity: 0.9,
        },
        hoverinfo: 'text',
        showlegend: false,
      },
    ] as Data[];
  }, [markovChain, markov]);

  const symptomCats = useMemo<Record<string, string[]>>(() => {
    if (!categories?.groups?.length) return SYMPTOM_CATS;
    const out: Record<string, string[]> = {};
    for (const g of categories.groups) {
      out[g.equipment_type] = g.symptoms;
    }
    return Object.keys(out).length > 0 ? out : SYMPTOM_CATS;
  }, [categories]);

  const spcChart = useMemo(() => {
    if (spcResp?.data?.values?.length) {
      return {
        values: spcResp.data.values,
        cl: spcResp.data.mean,
        ucl: spcResp.data.ucl,
        lcl: spcResp.data.lcl,
        violations: spcResp.violations,
      };
    }
    return {
      values: MOCK_SPC_DATA,
      cl: MOCK_CL,
      ucl: MOCK_UCL,
      lcl: MOCK_LCL,
      violations: [],
    };
  }, [spcResp]);

  const yScale = useCallback(
    (v: number) => {
      const range = (spcChart.ucl - spcChart.lcl) * 1.5;
      const center = (spcChart.ucl + spcChart.lcl) / 2;
      const min = center - range / 2;
      return 200 - ((v - min) / range) * 180;
    },
    [spcChart.ucl, spcChart.lcl],
  );

  const inspectionRows = useMemo(() => {
    if (!checklist?.templates?.length) return MOCK_INSPECTIONS;
    return checklist.templates.map((tpl) => ({
      eq: tpl.equipment_type,
      cycle: tpl.checklist_type,
      date: '2026-04-26',
      rate: 100,
      lvl: 'ok',
      miss: '—',
    }));
  }, [checklist]);

  const alertCount = useMemo(() => {
    if (!overview?.processes?.length) return 3;
    return overview.processes.filter((p) => p.violation_count > 0).length;
  }, [overview]);

  // ── 접근 거부 가드 ───────────────────────────────────
  if (!allowed) {
    return (
      <div className="page lg-page" data-screen-label="F · Equipment AI · LOCKED">
        <section className="lg-hero">
          <div className="lg-hero-eyebrow" style={{ color: 'var(--hud-red)' }}>
            EQUIPMENT & PROCESS AI · ACCESS DENIED
          </div>
          <h1 className="lg-display">접근 권한 없음</h1>
          <p className="lg-sub">
            설비/공정 AI 모듈은 14개 허용 부서(생산기술팀·품질보증팀·정비팀·금형팀·프레스팀·용접팀·도장팀·검사팀·환경안전팀·사출팀·CNC팀·컨베이어팀·자재팀·시스템관리팀)에만 노출됩니다.
          </p>
        </section>
        <section className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-eyebrow">REASON · 사유</div>
              <h2 className="lg-h2">{lockReason ?? '권한 없음'}</h2>
            </div>
            <span className="lg-pill" style={{ color: 'var(--hud-red)' }}>LOCKED</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', lineHeight: 1.7 }}>
            현재 사용자: <b style={{ color: 'var(--hud-text)' }}>{user?.username ?? '게스트'}</b>
            {' · '}
            부서: <b style={{ color: 'var(--hud-text)' }}>{user?.department ?? '미지정'}</b>
            {' · '}
            등급: <b style={{ color: 'var(--hud-text)' }}>L{user?.role_level ?? 0}</b>
            <br />
            <br />
            ※ 관리자에게 문의하거나 대시보드로 돌아가세요.
          </div>
          <div style={{ marginTop: 18 }}>
            <button className="lg-btn" onClick={() => (window.location.href = '/')}>
              대시보드로 돌아가기
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="page lg-page" data-screen-label="F · Equipment AI">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">EQUIPMENT & PROCESS AI · MODULE F</div>
        <h1 className="lg-display">설비 / 공정 AI</h1>
        <p className="lg-sub">
          7종 ML 엔진 · 14개 부서. SPC Nelson 8 Rules · TF-IDF 에러 검색 · XGBoost 잔여수명 ·
          Markov 연쇄 고장 예측을 한 화면에서.
        </p>
        {globalApiError && (
          <div
            style={{
              marginTop: 12,
              padding: '8px 12px',
              borderRadius: 8,
              background: 'color-mix(in oklab, var(--hud-orange) 12%, transparent)',
              border: '1px solid color-mix(in oklab, var(--hud-orange) 30%, transparent)',
              fontSize: 12,
              color: 'var(--hud-orange)',
              fontFamily: 'var(--hud-font-mono)',
            }}
          >
            ⚠ {globalApiError}
          </div>
        )}
      </section>

      <div className="lg-tabs">
        {MAIN_TABS.map((t) => (
          <button
            key={t.k}
            className={'lg-tab' + (tab === t.k ? ' on' : '')}
            onClick={() => setTab(t.k)}
            type="button"
          >
            <span className="en">{t.en}</span>
            <span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="lg-subtabs">
            {SUB_TABS.map((s) => (
              <button
                key={s.k}
                className={'lg-subtab' + (sub === s.k ? ' on' : '')}
                onClick={() => setSub(s.k)}
                type="button"
              >
                {s.label}
              </button>
            ))}
          </div>

          {sub === 'overview' && (
            <DashboardSubTab metrics={metrics} equipment7={equipment7} overview={overview} />
          )}
          {sub === 'alerts' && <AlertsSubTab alertCount={alertCount} />}
          {sub === 'equipment' && <EquipmentTypeSubTab equipment7={equipment7} />}
          {sub === 'predictive' && (
            <PredictiveSubTab
              molds={molds}
              moldList={moldList}
              mtbf={mtbf}
              mtbfBar={mtbfBar}
              maintCost={maintCost}
            />
          )}
          {sub === 'spc' && (
            <SPCSubTab
              processes5={processes5}
              spcResp={spcResp}
              spcChart={spcChart}
              spcLoading={spcLoading}
              spcProcessId={spcProcessId}
              setSpcProcessId={setSpcProcessId}
              uploadProcessId={uploadProcessId}
              setUploadProcessId={setUploadProcessId}
              uploadResp={uploadResp}
              uploading={uploading}
              yScale={yScale}
              onSPCUpload={onSPCUpload}
            />
          )}
          {sub === 'ml' && <MLEnginesSubTab mlList={mlList} mlEngines={mlEngines} />}
        </>
      )}

      {tab === 'manual_error' && (
        <ManualErrorTab
          categories={categories}
          symptomCats={symptomCats}
          equipFilter={equipFilter}
          setEquipFilter={setEquipFilter}
          symptom={symptom}
          setSymptom={setSymptom}
          errQuery={errQuery}
          setErrQuery={setErrQuery}
          errSearching={errSearching}
          onErrorSearch={onErrorSearch}
          errResults={errResults}
          markov={markov}
          markovChain={markovChain}
          markovGraph={markovGraph}
          ragQuery={ragQuery}
          setRagQuery={setRagQuery}
          manualSearching={manualSearching}
          onManualSearch={onManualSearch}
          manualResp={manualResp}
        />
      )}

      {tab === 'inspection' && (
        <InspectionTab checklist={checklist} inspectionRows={inspectionRows} />
      )}
    </div>
  );
}
