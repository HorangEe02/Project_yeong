// CascadeFailureSimulation — F · 설비 / 연쇄 고장 예측 인터랙티브 시뮬레이션.
//
// 참조 패턴: EquipmentDetailDrawer 의 정적 3-column grid (메타·Cpk gaussian SVG·알람 timeline).
// 사용자 요청: MATLAB Simulink 스타일 (다이어그램 + fault toggle + 시계열) 으로 확장.
//
// 구조:
//   ┌ 좌: Markov network (기존 markovGraph Plotly 보강) ─────────┐
//   ├ 중: Fault toggle row (각 next_prediction 활성/severity) ──┤
//   └ 우: Time-series (시간별 cascade 확률, 토글 영향 반영) ────┘
//
// 데이터:
//   - markov / markovChain: 부모 (ManualErrorTab) 에서 fetchMarkov('E-101', 3) 결과
//   - faultToggles / severityMul: 컴포넌트 내 local state (frontend mock)
//   - time-series: useMemo — t∈[0..30] 분, 각 branch 의 P(t)=1-exp(-λt) 누적 곡선

import { useMemo, useState } from 'react';
import { Activity, AlertOctagon, Cpu, GitBranch } from 'lucide-react';
import { PlotlyChart } from '@components/chart/PlotlyChart';
import type { Data, Layout } from 'plotly.js';
import type { MarkovResponse } from '@/types/equipment';
import type { MarkovBranchDisplay } from './types';

interface Props {
  markov: MarkovResponse | null;
  markovChain: MarkovBranchDisplay[];
  markovGraph: Data[];
}

// branch 별 fault 활성 + severity multiplier (시뮬레이션 sliders)
interface BranchToggle {
  enabled: boolean;
  severity: number; // 0.5 ~ 1.5 (1.0 = base)
}

const TIME_STEPS = 31; // 0~30 분
const TIME_MIN = 0;
const TIME_MAX = 30;

// branch.prob (P0) 를 도달률 λ 로 환산 — 30분 시점에 P=P0 가 되도록 λ 결정.
// P(t) = 1 - exp(-λ * t) → λ = -ln(1 - P0) / T
function probToLambda(p0: number, T: number): number {
  const clamped = Math.min(0.999, Math.max(0.001, p0));
  return -Math.log(1 - clamped) / T;
}

export function CascadeFailureSimulation({ markov, markovChain, markovGraph }: Props) {
  // 각 branch 의 fault toggle state (default: enabled, severity 1.0)
  const [toggles, setToggles] = useState<Record<string, BranchToggle>>(() =>
    Object.fromEntries(markovChain.map((m) => [m.code, { enabled: true, severity: 1.0 }])),
  );

  // markovChain 이 변경되면 (새 fetch) 누락된 code 의 default toggle 추가.
  // 기존 toggle 은 보존하여 사용자 설정 유지.
  const branchToggles = useMemo<Record<string, BranchToggle>>(() => {
    const out: Record<string, BranchToggle> = {};
    for (const b of markovChain) {
      out[b.code] = toggles[b.code] ?? { enabled: true, severity: 1.0 };
    }
    return out;
  }, [markovChain, toggles]);

  // 시계열 데이터 — 각 branch 의 누적 확률 곡선 + 합산 (any cascade)
  const timeSeries = useMemo<Data[]>(() => {
    const t = Array.from({ length: TIME_STEPS }, (_, i) => TIME_MIN + (i * (TIME_MAX - TIME_MIN)) / (TIME_STEPS - 1));

    // 각 branch 별 시간별 P
    const perBranchSeries: Data[] = markovChain.map((b) => {
      const tog = branchToggles[b.code];
      const effectiveP = tog.enabled ? Math.min(0.999, b.prob * tog.severity) : 0;
      const lambda = probToLambda(effectiveP, TIME_MAX);
      const y = t.map((ti) => (lambda > 0 ? 1 - Math.exp(-lambda * ti) : 0));
      const color = b.prob > 0.5 ? '#C0392B' : b.prob > 0.3 ? '#E8A317' : '#2980B9';
      return {
        type: 'scatter',
        mode: 'lines',
        x: t,
        y,
        name: `${b.code} ${b.name}`,
        line: { color, width: 1.6 },
        hovertemplate: '%{x}분: %{y:.1%}<extra>%{fullData.name}</extra>',
      } as Data;
    });

    // any-cascade (1 - Π(1 - P_i))
    const anyY = t.map((ti) => {
      let prodNotFail = 1;
      for (const b of markovChain) {
        const tog = branchToggles[b.code];
        if (!tog.enabled) continue;
        const effectiveP = Math.min(0.999, b.prob * tog.severity);
        const lambda = probToLambda(effectiveP, TIME_MAX);
        const P = lambda > 0 ? 1 - Math.exp(-lambda * ti) : 0;
        prodNotFail *= 1 - P;
      }
      return 1 - prodNotFail;
    });

    const anyTrace: Data = {
      type: 'scatter',
      mode: 'lines',
      x: t,
      y: anyY,
      name: 'ANY 연쇄 고장',
      line: { color: '#FCB132', width: 2.4, dash: 'solid' },
      fill: 'tozeroy',
      fillcolor: 'rgba(252, 177, 50, 0.10)',
      hovertemplate: '%{x}분: %{y:.1%}<extra>ANY</extra>',
    };

    return [anyTrace, ...perBranchSeries];
  }, [markovChain, branchToggles]);

  const timeSeriesLayout = useMemo<Partial<Layout>>(
    () => ({
      margin: { l: 40, r: 10, t: 10, b: 32 },
      xaxis: { title: { text: '경과 (분)', font: { size: 10 } }, fixedrange: true, gridcolor: 'rgba(127,127,127,0.15)' },
      yaxis: { title: { text: '누적 확률', font: { size: 10 } }, range: [0, 1], tickformat: '.0%', fixedrange: true, gridcolor: 'rgba(127,127,127,0.15)' },
      hovermode: 'x unified',
      legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'left', x: 0, font: { size: 10 } },
      showlegend: true,
    }),
    [],
  );

  const markovGraphLayout = useMemo<Partial<Layout>>(
    () => ({
      margin: { l: 10, r: 10, t: 10, b: 10 },
      xaxis: { visible: false, range: [-0.5, 2.0] },
      yaxis: { visible: false, range: [-1.2, 1.2], scaleanchor: 'x', scaleratio: 1 },
      hovermode: 'closest',
    }),
    [],
  );

  const updateToggle = (code: string, patch: Partial<BranchToggle>) => {
    setToggles((prev) => ({
      ...prev,
      [code]: { ...(prev[code] ?? { enabled: true, severity: 1.0 }), ...patch },
    }));
  };

  const enabledCount = Object.values(branchToggles).filter((t) => t.enabled).length;
  const anyAt30 = useMemo(() => {
    const anyTrace = timeSeries[0];
    const yArr = (anyTrace as { y?: number[] }).y;
    return yArr ? yArr[yArr.length - 1] : 0;
  }, [timeSeries]);

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">MARKOV CHAIN · DFS depth=3 · INTERACTIVE SIMULATION</div>
          <h2 className="lg-h2">연쇄 고장 예측 시뮬레이션</h2>
        </div>
        {markov?.risk_level && (
          <span className={'lg-pill ' + (markov.risk_level === 'critical' ? 'warn' : '')}>
            {markov.risk_level.toUpperCase()}
          </span>
        )}
      </div>

      {/* 3-column grid (EquipmentDetailDrawer 패턴 차용) — 좁은 화면에서는 1col stack */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.85fr) minmax(0, 1.15fr)',
          gap: 14,
          marginTop: 8,
          alignItems: 'stretch',
        }}
        className="cascade-sim-grid"
      >
        {/* ── 좌: Markov 네트워크 다이어그램 ───────────────── */}
        <div
          style={{
            background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
            borderRadius: 10,
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 320,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 11,
              color: 'var(--hud-text-dim)',
              marginBottom: 8,
              fontFamily: 'var(--hud-font-mono)',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}
          >
            <GitBranch size={12} strokeWidth={1.5} />
            FAULT NETWORK
          </div>
          <div style={{ flex: 1, minHeight: 260 }}>
            <PlotlyChart
              data={markovGraph}
              layout={markovGraphLayout}
              config={{ displayModeBar: false }}
              style={{ width: '100%', height: '100%' }}
            />
          </div>
          <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginTop: 4 }}>
            중심 = 현재 {markov?.current_code ?? 'E-101'} ({markov?.current_category ?? '베어링 마모'}),
            분기 = depth-3 후보 ({markovChain.length}개)
          </div>
        </div>

        {/* ── 중: Fault toggle / severity ─────────────────── */}
        <div
          style={{
            background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
            borderRadius: 10,
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            minHeight: 320,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 11,
              color: 'var(--hud-text-dim)',
              marginBottom: 4,
              fontFamily: 'var(--hud-font-mono)',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}
          >
            <Cpu size={12} strokeWidth={1.5} />
            SET FAULTS · {enabledCount}/{markovChain.length} 활성
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, overflowY: 'auto' }}>
            {markovChain.length === 0 && (
              <div style={{ fontSize: 12, opacity: 0.6, padding: 8 }}>다음 단계 후보 없음 — 시뮬레이션 불가.</div>
            )}
            {markovChain.map((b) => {
              const tog = branchToggles[b.code];
              const sevPct = Math.round(tog.severity * 100);
              return (
                <div
                  key={b.code}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: 'color-mix(in oklab, var(--hud-text) 3%, transparent)',
                    border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
                    opacity: tog.enabled ? 1 : 0.55,
                  }}
                >
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={tog.enabled}
                      onChange={(e) => updateToggle(b.code, { enabled: e.target.checked })}
                    />
                    <span style={{ fontSize: 11, fontFamily: 'var(--hud-font-mono)', fontWeight: 600, color: '#FCB132' }}>
                      {b.code}
                    </span>
                    <span style={{ fontSize: 12, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {b.name}
                    </span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--hud-font-mono)', color: 'var(--hud-text-dim)' }}>
                      P₀ {b.prob.toFixed(2)}
                    </span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                    <span style={{ fontSize: 10, color: 'var(--hud-text-dim)', minWidth: 38 }}>심도</span>
                    <input
                      type="range"
                      min={50}
                      max={150}
                      step={5}
                      value={sevPct}
                      onChange={(e) => updateToggle(b.code, { severity: Number(e.target.value) / 100 })}
                      disabled={!tog.enabled}
                      style={{ flex: 1, minWidth: 0 }}
                    />
                    <span style={{ fontSize: 10, fontFamily: 'var(--hud-font-mono)', minWidth: 38, textAlign: 'right' }}>
                      {sevPct}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── 우: Time-series ───────────────────────────────── */}
        <div
          style={{
            background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
            borderRadius: 10,
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 320,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 11,
              color: 'var(--hud-text-dim)',
              marginBottom: 8,
              fontFamily: 'var(--hud-font-mono)',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}
          >
            <Activity size={12} strokeWidth={1.5} />
            P(t) · 누적 확률 30분
          </div>
          <div style={{ flex: 1, minHeight: 240 }}>
            <PlotlyChart
              data={timeSeries}
              layout={timeSeriesLayout}
              config={{ displayModeBar: false }}
              style={{ width: '100%', height: '100%' }}
            />
          </div>
          <div
            style={{
              marginTop: 6,
              padding: '6px 10px',
              borderRadius: 8,
              background: 'rgba(252,177,50,0.10)',
              borderLeft: '2px solid #FCB132',
              fontSize: 11,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <AlertOctagon size={12} strokeWidth={1.5} color="#FCB132" />
            <span>
              30분 후 ANY 연쇄 고장 확률 = <b style={{ fontFamily: 'var(--hud-font-mono)' }}>{(anyAt30 * 100).toFixed(1)}%</b>
            </span>
          </div>
        </div>
      </div>

      <div className="lg-markov-foot" style={{ marginTop: 12 }}>
        {markov?.prevention_message ?? '권장 사전 조치: 윤활 점검 → 베어링 교체 → 모터 온도 모니터링'}
      </div>
    </section>
  );
}
