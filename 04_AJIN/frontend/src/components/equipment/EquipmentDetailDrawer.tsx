// EquipmentDetailDrawer — 7대 장비 카드 클릭 시 페이지 하단 슬라이드 업.
// PR #1: 정적 3-column grid (메타 · Cpk 가우시안 곡선 · 알람 timeline + 신호등).
// PR #2 에서 우측에 ROT 식 라인 시각화 + 설비별 미니 애니메이션 추가 예정.
//
// 차트는 Plotly 가 아닌 inline SVG — 4.6MB chunk 부담 회피, 60fps 보장.

import { useMemo } from 'react';
import { Drawer } from '@/components/ui/Drawer';
import { Activity, AlertTriangle, Factory, Gauge } from 'lucide-react';
import type { EquipRow } from './types';
import { EQUIPMENT_HELP_COPY } from './EquipmentHoverCard';
import { EquipmentLineVisual } from './EquipmentLineVisual';

interface Props {
  selected: EquipRow | null;
  onClose: () => void;
}

// ─────────────────────────────────────────────────────────────
// 정규분포 곡선 생성 — Cpk → sigma
// Cpk = (USL - LSL) / (6σ)  →  σ = (USL - LSL) / (6 * Cpk)
// LSL = -3, USL = +3 (정규화 단위) 기준
// ─────────────────────────────────────────────────────────────
function generateGaussianPoints(cpk: number, width = 320, height = 100): {
  d: string;
  fillD: string;
  meanX: number;
  uslX: number;
  lslX: number;
} {
  const safeCpk = Math.max(0.4, cpk);
  const sigma = 1 / safeCpk; // 정규화 (USL-LSL=2, mean=0)
  const xMin = -3.5;
  const xMax = 3.5;
  const usl = 1; // 정규화 1 = USL (스펙 상한)
  const lsl = -1;
  const N = 80;
  const pts: { x: number; y: number }[] = [];
  let maxY = 0;
  for (let i = 0; i <= N; i++) {
    const x = xMin + ((xMax - xMin) * i) / N;
    const y = Math.exp(-(x * x) / (2 * sigma * sigma)) / (sigma * Math.sqrt(2 * Math.PI));
    pts.push({ x, y });
    if (y > maxY) maxY = y;
  }
  const toX = (x: number) => ((x - xMin) / (xMax - xMin)) * width;
  const toY = (y: number) => height - (y / maxY) * (height - 10) - 4;

  const pathD = pts
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(p.x).toFixed(2)} ${toY(p.y).toFixed(2)}`)
    .join(' ');

  // 스펙 안쪽 (LSL ~ USL) fill path
  const insidePts = pts.filter((p) => p.x >= lsl && p.x <= usl);
  const fillD = insidePts.length
    ? `M ${toX(insidePts[0].x).toFixed(2)} ${height} ` +
      insidePts.map((p) => `L ${toX(p.x).toFixed(2)} ${toY(p.y).toFixed(2)}`).join(' ') +
      ` L ${toX(insidePts[insidePts.length - 1].x).toFixed(2)} ${height} Z`
    : '';

  return {
    d: pathD,
    fillD,
    meanX: toX(0),
    uslX: toX(usl),
    lslX: toX(lsl),
  };
}

// ─────────────────────────────────────────────────────────────
// 알람 timeline mock — 시연용 (실제 API 연결 시 교체).
// row.alarm 카운트를 24h 12개 bin 에 자연스럽게 분배.
// ─────────────────────────────────────────────────────────────
function generateAlarmBins(totalAlarm: number, seed: number): { hour: number; count: number; severity: 'critical' | 'high' | 'medium' | 'low' }[] {
  // 결정적 pseudo-random (seed 기반)
  let s = seed;
  const rng = () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
  const bins: { hour: number; count: number; severity: 'critical' | 'high' | 'medium' | 'low' }[] = [];
  let remaining = totalAlarm;
  for (let i = 0; i < 12; i++) {
    const portion = i === 11 ? remaining : Math.floor(remaining * rng() * 0.4);
    remaining -= portion;
    const r = rng();
    const severity: 'critical' | 'high' | 'medium' | 'low' =
      r < 0.08 ? 'critical' : r < 0.25 ? 'high' : r < 0.55 ? 'medium' : 'low';
    bins.push({ hour: i * 2, count: portion, severity });
  }
  return bins;
}

const SEVERITY_COLOR: Record<'critical' | 'high' | 'medium' | 'low', string> = {
  critical: '#e24b4a',
  high: '#ef9f27',
  medium: '#eab308',
  low: '#94a3b8',
};

function cpkGrade(cpk: number): { label: string; color: string } {
  if (cpk >= 1.33) return { label: '우수', color: '#639922' };
  if (cpk >= 1.0)  return { label: '양호', color: '#97c459' };
  if (cpk >= 0.67) return { label: '주의', color: '#ef9f27' };
  return { label: '개선 필요', color: '#e24b4a' };
}

// ─────────────────────────────────────────────────────────────
// 본체 컴포넌트
// ─────────────────────────────────────────────────────────────

export function EquipmentDetailDrawer({ selected, onClose }: Props) {
  const copy = selected ? EQUIPMENT_HELP_COPY[selected.type] : null;
  const grade = selected ? cpkGrade(selected.cpk) : null;

  const gaussian = useMemo(
    () => (selected ? generateGaussianPoints(selected.cpk) : null),
    [selected?.cpk, selected?.type],
  );

  const alarmBins = useMemo(
    () =>
      selected
        ? generateAlarmBins(
            selected.alarm,
            selected.type.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0),
          )
        : [],
    [selected?.alarm, selected?.type],
  );

  const severityCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    alarmBins.forEach((b) => {
      counts[b.severity] += b.count;
    });
    return counts;
  }, [alarmBins]);

  if (!selected) return null;

  return (
    <Drawer
      isOpen={!!selected}
      onClose={onClose}
      side="bottom"
      height={640}
      title={`${selected.type} · ${selected.en} — 상세 학습 패널`}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: 16,
          padding: '4px 4px 14px',
          fontFamily: 'var(--hud-font-sans)',
        }}
      >
        {/* ── 좌: 설비 메타 ────────────────────────── */}
        <section style={{ background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)', borderRadius: 10, padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8, fontFamily: 'var(--hud-font-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            <Factory size={12} strokeWidth={1.5} />
            EQUIPMENT META
          </div>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{selected.type}</h3>
          <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--hud-text-dim)', marginBottom: 12 }}>
            {copy?.description ?? '설비 정보가 등록되지 않았습니다.'}
          </p>

          <dl style={{ display: 'grid', gap: 8, fontSize: 12 }}>
            <div>
              <dt style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginBottom: 2 }}>핵심 모니터링 지표</dt>
              <dd style={{ fontWeight: 500 }}>{copy?.key_metric ?? '—'}</dd>
            </div>
            <div>
              <dt style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginBottom: 2 }}>알람 발생 기준</dt>
              <dd style={{ fontWeight: 500 }}>{copy?.alarm_basis ?? '—'}</dd>
            </div>
            <div>
              <dt style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginBottom: 2 }}>데이터 소스</dt>
              <dd style={{ fontWeight: 500, fontSize: 11, fontFamily: 'var(--hud-font-mono)' }}>
                {selected.dataClass ?? 'synthetic'} · {selected.sourceSystem ?? 'seed_equipment'}
              </dd>
            </div>
          </dl>
        </section>

        {/* ── 중: Cpk 가우시안 곡선 ────────────────────────── */}
        <section style={{ background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)', borderRadius: 10, padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8, fontFamily: 'var(--hud-font-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            <Gauge size={12} strokeWidth={1.5} />
            CPK · 공정능력지수
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: grade?.color }}>{selected.cpk.toFixed(2)}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: grade?.color }}>{grade?.label}</span>
          </div>

          {gaussian && (
            <svg viewBox="0 0 320 120" style={{ width: '100%', height: 130, display: 'block' }}>
              {/* baseline */}
              <line x1="0" y1="100" x2="320" y2="100" stroke="color-mix(in oklab, var(--hud-text) 18%, transparent)" strokeWidth="0.5" />
              {/* LSL/USL 수직선 */}
              <line x1={gaussian.lslX} y1="6" x2={gaussian.lslX} y2="100" stroke="#e24b4a" strokeWidth="1" strokeDasharray="3 3" />
              <line x1={gaussian.uslX} y1="6" x2={gaussian.uslX} y2="100" stroke="#e24b4a" strokeWidth="1" strokeDasharray="3 3" />
              {/* mean 수직선 */}
              <line x1={gaussian.meanX} y1="6" x2={gaussian.meanX} y2="100" stroke="var(--hud-text-dim)" strokeWidth="0.5" strokeDasharray="2 2" />
              {/* 스펙 안쪽 fill (yellow) */}
              <path d={gaussian.fillD} fill="var(--hud-primary, #FBBF24)" fillOpacity="0.22" />
              {/* 곡선 */}
              <path d={gaussian.d} fill="none" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1.5" />
              {/* 라벨 */}
              <text x={gaussian.lslX} y="115" fontSize="9" textAnchor="middle" fill="#e24b4a">LSL</text>
              <text x={gaussian.uslX} y="115" fontSize="9" textAnchor="middle" fill="#e24b4a">USL</text>
              <text x={gaussian.meanX} y="115" fontSize="9" textAnchor="middle" fill="var(--hud-text-dim)">μ</text>
            </svg>
          )}

          <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', lineHeight: 1.6, marginTop: 6 }}>
            <strong style={{ color: 'var(--hud-text)' }}>1.33↑</strong> 우수 ·
            <strong style={{ color: 'var(--hud-text)', marginLeft: 4 }}>1.0~1.33</strong> 양호 ·
            <strong style={{ color: 'var(--hud-text)', marginLeft: 4 }}>&lt;1.0</strong> 개선 필요
          </div>
          <div style={{ fontSize: 10, color: 'var(--hud-text-muted, var(--hud-text-dim))', marginTop: 4 }}>
            노란색 영역 = 스펙(LSL~USL) 안에 분포한 비율. 좁고 높을수록 공정 안정.
          </div>
        </section>

        {/* ── 우: 알람 timeline + 신호등 ────────────────────────── */}
        <section style={{ background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)', borderRadius: 10, padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8, fontFamily: 'var(--hud-font-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            <AlertTriangle size={12} strokeWidth={1.5} />
            ALARMS · 24h timeline
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--hud-text)' }}>{selected.alarm}</span>
            <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>건 / 24h</span>
          </div>

          {/* timeline bars */}
          <svg viewBox="0 0 240 64" style={{ width: '100%', height: 64, display: 'block' }}>
            {alarmBins.map((bin, i) => {
              const maxBin = Math.max(...alarmBins.map((b) => b.count), 1);
              const h = (bin.count / maxBin) * 50;
              const x = i * 20 + 2;
              return (
                <rect
                  key={i}
                  x={x}
                  y={60 - h}
                  width="16"
                  height={h}
                  fill={SEVERITY_COLOR[bin.severity]}
                  fillOpacity={bin.count === 0 ? 0.15 : 0.85}
                  rx="1.5"
                />
              );
            })}
            <line x1="0" y1="60" x2="240" y2="60" stroke="color-mix(in oklab, var(--hud-text) 18%, transparent)" strokeWidth="0.5" />
            <text x="2" y="74" fontSize="8" fill="var(--hud-text-dim)">-24h</text>
            <text x="238" y="74" fontSize="8" textAnchor="end" fill="var(--hud-text-dim)">now</text>
          </svg>

          {/* severity 신호등 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 6, marginTop: 10 }}>
            {(['critical', 'high', 'medium', 'low'] as const).map((sev) => (
              <div
                key={sev}
                style={{
                  padding: '6px 4px',
                  borderRadius: 6,
                  background: `color-mix(in oklab, ${SEVERITY_COLOR[sev]} 14%, transparent)`,
                  border: `1px solid color-mix(in oklab, ${SEVERITY_COLOR[sev]} 30%, transparent)`,
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: 9, color: SEVERITY_COLOR[sev], textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600 }}>
                  {sev === 'critical' ? '치명' : sev === 'high' ? '높음' : sev === 'medium' ? '중간' : '낮음'}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, marginTop: 2 }}>{severityCounts[sev]}</div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: 10, color: 'var(--hud-text-muted, var(--hud-text-dim))', marginTop: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Activity size={10} strokeWidth={1.5} />
            <span>알람 = Nelson Rule 위반 + ML 이상감지 + 임계치 초과의 합산</span>
          </div>
        </section>
      </div>

      {/* ── 하단 row: 설비 동작 + 라인 시뮬레이션 (PR #2) ────────────────────── */}
      <div style={{ padding: '0 4px 20px', fontFamily: 'var(--hud-font-sans)' }}>
        <EquipmentLineVisual row={selected} />
      </div>
    </Drawer>
  );
}
