// MVP — 임원용 KPI 1페이지.
// 4 stat cards + 30일 등급별 trend mini chart (inline SVG, recharts 의존성 없음).
//
// `/compliance` 페이지 상단에 배치 — RBAC role_level >= 4 (본부장+) 만 노출.

import { useEffect, useState } from 'react';
import {
 fetchChangeKpi,
 fetchExtendedTrend,
 downloadExecReport,
 type ChangeKpiResponse,
 type ChangeKpiTrendPoint,
 type ExecReportFormat,
 type ExtendedTrendResponse } from '@api/compliance';
import { useToastStore } from '@store/toast';
import { WhatIfModal } from './WhatIfModal';
import { COMPLIANCE_GRADE_META } from '@lib/complianceSeverity';

const GRADE_COLORS: Record<string, string> = {
 CRITICAL: COMPLIANCE_GRADE_META.CRITICAL.color,
 HIGH: COMPLIANCE_GRADE_META.HIGH.color,
 MEDIUM: COMPLIANCE_GRADE_META.MEDIUM.color,
 LOW: COMPLIANCE_GRADE_META.LOW.color };

interface Props {
 /** 트렌드 chart 윈도우 초기값 (default 30일) */
 initialWindowDays?: number;
}

export function ExecKPICards({ initialWindowDays = 30 }: Props) {
 const [windowDays, setWindowDays] = useState(initialWindowDays);
 const [kpi, setKpi] = useState<ChangeKpiResponse | null>(null);
 const [error, setError] = useState<string | null>(null);
 const [loading, setLoading] = useState(true);

 // P3 D13 — 확장 트렌드 lazy
 const [extended, setExtended] = useState<ExtendedTrendResponse | null>(null);
 const [extendedLoading, setExtendedLoading] = useState(false);

 // P3 D10 — What-if 모달
 const [whatIfOpen, setWhatIfOpen] = useState(false);

 useEffect(() => {
 let cancelled = false;
 setLoading(true);
 fetchChangeKpi(windowDays)
 .then((data) => {
 if (!cancelled) setKpi(data);
 })
 .catch((e) => {
 if (!cancelled) setError(e instanceof Error ? e.message : String(e));
 })
 .finally(() => {
 if (!cancelled) setLoading(false);
 });
 return () => { cancelled = true; };
 }, [windowDays]);

 const loadExtended = async () => {
 if (extended !== null) {
 setExtended(null);
 return;
 }
 setExtendedLoading(true);
 try {
 const r = await fetchExtendedTrend(180);
 setExtended(r);
 } catch {
 setExtended(null);
 } finally {
 setExtendedLoading(false);
 }
 };

 if (loading) {
 return (
 <section className="lg-card" style={{ marginBottom: 16 }}>
 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}> KPI 로딩 중…</p>
 </section>
 );
 }

 if (error || !kpi) {
 return (
 <section className="lg-card" style={{ marginBottom: 16 }}>
 <p style={{ fontSize: 12, color: 'var(--hud-red, #f33)' }}>
 KPI 로드 실패: {error}
 </p>
 </section>
 );
 }

 return (
 <section className="lg-card" style={{ marginBottom: 16 }}>
 <div className="lg-card-h">
 <div>
 <div className="lg-eyebrow">EXEC KPI · 임원 대시보드</div>
 <h2 className="lg-h2">규제 변경 처리 현황</h2>
 </div>
 <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
 <ReportDownload windowDays={windowDays} />
 <button
 className="lg-btn sm"
 onClick={() => setWhatIfOpen(true)}
 title="What-if 시뮬레이션 (관세/환율/화학/노동/탄소)"
 >
 What-if
 </button>
 <select
 className="lg-select sm"
 value={windowDays}
 onChange={(e) => setWindowDays(Number(e.target.value))}
 aria-label="트렌드 윈도우"
 >
 <option value={30}>최근 30일</option>
 <option value={90}>최근 90일</option>
 <option value={180}>최근 180일</option>
 </select>
 <button
 className="lg-btn sm ghost"
 onClick={() => void loadExtended()}
 disabled={extendedLoading}
 title="6개월 월별 트렌드 + 부서별 처리시간"
 >
 {extendedLoading ? '' : extended !== null ? '확장 닫기' : '확장 트렌드'}
 </button>
 </div>
 </div>

 <WhatIfModal isOpen={whatIfOpen} onClose={() => setWhatIfOpen(false)} />

 {/* 4 stat cards */}
 <div
 style={{
 display: 'grid',
 gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
 gap: 12,
 marginBottom: 16 }}
 >
 <StatCard
 label="이번달 CRITICAL"
 value={kpi.month_critical}
 accent={GRADE_COLORS.CRITICAL}
 sub={`HIGH ${kpi.month_high}건 · MEDIUM ${kpi.month_medium}건`}
 />
 <StatCard
 label="미해결 누적"
 value={kpi.open_count}
 accent={kpi.open_count > 10 ? GRADE_COLORS.HIGH : GRADE_COLORS.MEDIUM}
 sub="status ≠ done/filtered"
 />
 <StatCard
 label="평균 처리시간"
 value={kpi.avg_hours_to_done}
 unit="시간"
 accent="#26A69A"
 sub="감지→완료 평균"
 />
 <StatCard
 label="오늘 신규 변경"
 value={kpi.today_new}
 accent={kpi.today_new > 0 ? GRADE_COLORS.HIGH : GRADE_COLORS.LOW}
 sub="자정 기준"
 />
 </div>

 {/* 30일 trend chart */}
 {kpi.trend.length > 0 && <TrendChart trend={kpi.trend} />}

 {/* P3 D13 — 확장 트렌드 (lazy) */}
 {extended !== null && <ExtendedTrendPanel data={extended} />}

 <p style={{ marginTop: 12, fontSize: 11, color: 'var(--hud-text-dim)' }}>
 ※ AI 자동 분류 결과 기반. CRITICAL 등급은 SMS·DM 직보 (P1 후속 작업).
 </p>
 </section>
 );
}

// ─────────────────────────────────────────────────────────────
// StatCard
// ─────────────────────────────────────────────────────────────

interface StatCardProps {
 label: string;
 value: number;
 unit?: string;
 accent: string;
 sub?: string;
}

function StatCard({ label, value, unit, accent, sub }: StatCardProps) {
 return (
 <div
 style={{
 border: '1px solid var(--hud-border, #2a2a2a)',
 borderLeft: `3px solid ${accent}`,
 borderRadius: 2,
 padding: '10px 14px',
 background: 'var(--hud-card-bg, rgba(255,255,255,0.02))' }}
 >
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 4 }}>
 {label}
 </div>
 <div style={{ fontSize: 28, fontWeight: 700, color: accent, lineHeight: 1.2 }}>
 {value}
 {unit && (
 <span style={{ fontSize: 14, fontWeight: 500, marginLeft: 4, color: 'var(--hud-text)' }}>
 {unit}
 </span>
 )}
 </div>
 {sub && <div style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginTop: 2 }}>{sub}</div>}
 </div>
 );
}

// ─────────────────────────────────────────────────────────────
// TrendChart — SVG 누적 막대 (recharts 미사용)
// ─────────────────────────────────────────────────────────────

function TrendChart({ trend }: { trend: ChangeKpiTrendPoint[] }) {
 // 최근 N일 누적 합계 — y 스케일 결정
 const maxTotal = Math.max(
 1,
 ...trend.map((d) => d.CRITICAL + d.HIGH + d.MEDIUM + d.LOW),
 );

 const chartHeight = 80;

 return (
 <div>
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 6 }}>
 등급별 일자 trend (최근 {trend.length}일, max {maxTotal}건/일)
 </div>
 <div
 style={{
 position: 'relative',
 height: chartHeight,
 width: '100%',
 background: 'rgba(0,0,0,0.15)',
 padding: '4px 0',
 display: 'flex',
 alignItems: 'flex-end',
 gap: 1 }}
 role="img"
 aria-label={`${trend.length}일 trend chart`}
 >
 {trend.map((d) => {
 const total = d.CRITICAL + d.HIGH + d.MEDIUM + d.LOW;
 if (total === 0) {
 return (
 <div
 key={d.day}
 style={{ flex: 1, minWidth: 2, height: 2, background: 'var(--hud-text-dim)', opacity: 0.3 }}
 title={`${d.day} · 0건`}
 />
 );
 }
 const ph = (n: number) => (n / maxTotal) * (chartHeight - 8);
 return (
 <div
 key={d.day}
 style={{
 flex: 1,
 minWidth: 2,
 display: 'flex',
 flexDirection: 'column-reverse',
 height: '100%' }}
 title={`${d.day} · CRITICAL ${d.CRITICAL} · HIGH ${d.HIGH} · MEDIUM ${d.MEDIUM} · LOW ${d.LOW}`}
 >
 {d.LOW > 0 && <div style={{ height: ph(d.LOW), background: GRADE_COLORS.LOW }} />}
 {d.MEDIUM > 0 && <div style={{ height: ph(d.MEDIUM), background: GRADE_COLORS.MEDIUM }} />}
 {d.HIGH > 0 && <div style={{ height: ph(d.HIGH), background: GRADE_COLORS.HIGH }} />}
 {d.CRITICAL > 0 && <div style={{ height: ph(d.CRITICAL), background: GRADE_COLORS.CRITICAL }} />}
 </div>
 );
 })}
 </div>
 <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 10, color: 'var(--hud-text-dim)' }}>
 {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((g) => (
 <span key={g} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
 <span style={{ width: 8, height: 8, background: GRADE_COLORS[g], display: 'inline-block' }} />
 {g}
 </span>
 ))}
 </div>
 </div>
 );
}

// ─────────────────────────────────────────────────────────────
// ReportDownload — P1 D2 보고서 다운로드 드롭다운
// ─────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────
// P3 D13 — ExtendedTrendPanel
// ─────────────────────────────────────────────────────────────

function ExtendedTrendPanel({ data }: { data: ExtendedTrendResponse }) {
 const months = data.monthly_grade_trend;
 const maxMonth = Math.max(
 1,
 ...months.map((m) => m.CRITICAL + m.HIGH + m.MEDIUM + m.LOW),
 );

 return (
 <div
 style={{
 marginTop: 16,
 padding: 12,
 background: 'rgba(123,31,162,0.06)',
 border: '1px solid #7B1FA2' }}
 >
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8 }}>
 확장 트렌드 — 최근 {data.window_days}일 (총 {data.total}건)
 </div>

 {/* 월별 등급 trend */}
 {months.length > 0 ? (
 <div style={{ marginBottom: 12 }}>
 <div style={{ fontSize: 11, marginBottom: 4 }}>월별 등급별 변경 (max {maxMonth}건/월)</div>
 <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, minHeight: 60 }}>
 {months.map((m) => {
 const total = m.CRITICAL + m.HIGH + m.MEDIUM + m.LOW;
 const ph = (n: number) => (n / maxMonth) * 50;
 return (
 <div
 key={m.month}
 title={`${m.month} · CRITICAL ${m.CRITICAL} · HIGH ${m.HIGH} · MEDIUM ${m.MEDIUM} · LOW ${m.LOW}`}
 style={{
 flex: 1,
 minWidth: 16,
 display: 'flex',
 flexDirection: 'column',
 alignItems: 'center' }}
 >
 <div
 style={{
 width: '100%',
 height: 50,
 display: 'flex',
 flexDirection: 'column-reverse',
 background: 'rgba(0,0,0,0.15)' }}
 >
 {m.LOW > 0 && <div style={{ height: ph(m.LOW), background: GRADE_COLORS.LOW }} />}
 {m.MEDIUM > 0 && <div style={{ height: ph(m.MEDIUM), background: GRADE_COLORS.MEDIUM }} />}
 {m.HIGH > 0 && <div style={{ height: ph(m.HIGH), background: GRADE_COLORS.HIGH }} />}
 {m.CRITICAL > 0 && <div style={{ height: ph(m.CRITICAL), background: GRADE_COLORS.CRITICAL }} />}
 </div>
 <span style={{ fontSize: 9, marginTop: 2, color: 'var(--hud-text-dim)' }}>
 {m.month.slice(5)}
 </span>
 {total > 0 && <span style={{ fontSize: 9 }}>{total}</span>}
 </div>
 );
 })}
 </div>
 </div>
 ) : (
 <p style={{ fontSize: 11, color: 'var(--hud-text-dim)', margin: 0 }}>
 6개월 누적 데이터 수집 중 (월별 트렌드 차트는 데이터 누적 후 표시)
 </p>
 )}

 {/* 부서별 처리시간 */}
 {data.by_dept_handling_hours.length > 0 && (
 <div style={{ marginBottom: 12 }}>
 <div style={{ fontSize: 11, marginBottom: 4 }}>
 부서별 평균 처리시간 (top {data.by_dept_handling_hours.length})
 </div>
 <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 11 }}>
 {data.by_dept_handling_hours.map((d) => {
 const maxAvg = Math.max(...data.by_dept_handling_hours.map((x) => x.avg_hours), 1);
 const pct = (d.avg_hours / maxAvg) * 100;
 return (
 <li key={d.department} style={{ marginBottom: 4 }}>
 <div style={{ display: 'flex', justifyContent: 'space-between' }}>
 <span>{d.department}</span>
 <span style={{ color: 'var(--hud-text-dim)' }}>
 {d.avg_hours}시간 ({d.count}건)
 </span>
 </div>
 <div style={{ background: 'rgba(0,0,0,0.15)', height: 4 }}>
 <div style={{ width: `${pct}%`, background: '#7B1FA2', height: 4 }} />
 </div>
 </li>
 );
 })}
 </ul>
 </div>
 )}

 {/* 법무 5분류 분포 */}
 {Object.keys(data.by_legal_class).length > 0 && (
 <div>
 <div style={{ fontSize: 11, marginBottom: 4 }}>법무 분류 분포</div>
 <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
 {Object.entries(data.by_legal_class).map(([cls, count]) => (
 <span key={cls} className="lg-pill" style={{ fontSize: 10 }}>
 {cls}: {count}
 </span>
 ))}
 </div>
 </div>
 )}
 </div>
 );
}


function ReportDownload({ windowDays }: { windowDays: number }) {
 const [busy, setBusy] = useState<ExecReportFormat | null>(null);
 const addToast = useToastStore.getState().addToast;

 const handleDownload = async (format: ExecReportFormat) => {
 setBusy(format);
 try {
 // 기간: 최근 windowDays 일 (오늘 기준 역산)
 const today = new Date();
 const since = new Date(today.getTime() - windowDays * 24 * 3600 * 1000);
 const sinceStr = since.toISOString().slice(0, 10);
 const untilStr = today.toISOString().slice(0, 10);

 const { blob, filename } = await downloadExecReport({
 format,
 since: sinceStr,
 until: untilStr });

 // Trigger browser download
 const url = URL.createObjectURL(blob);
 const a = document.createElement('a');
 a.href = url;
 a.download = filename;
 document.body.appendChild(a);
 a.click();
 a.remove();
 URL.revokeObjectURL(url);

 addToast({ type: 'success', message: `${filename} 다운로드 완료` });
 } catch (e) {
 addToast({
 type: 'error',
 message: '보고서 생성 실패: ' + (e instanceof Error ? e.message : String(e)) });
 } finally {
 setBusy(null);
 }
 };

 return (
 <div style={{ display: 'flex', gap: 4 }}>
 <button
 className="lg-btn sm"
 onClick={() => void handleDownload('markdown')}
 disabled={!!busy}
 title="markdown 보고서 다운로드"
 >
 {busy === 'markdown' ? '' : ' .md'}
 </button>
 <button
 className="lg-btn sm"
 onClick={() => void handleDownload('docx_boon_bujang')}
 disabled={!!busy}
 title="본부장 보고서 (Word) 다운로드"
 >
 {busy === 'docx_boon_bujang' ? '' : '본부장 .docx'}
 </button>
 </div>
 );
}
