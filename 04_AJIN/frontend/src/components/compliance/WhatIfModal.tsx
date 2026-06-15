// P3 D10 — What-if 시뮬레이션 모달.
// 자연어 입력 또는 5 시나리오 선택 → 시뮬레이션 결과.

import { useState } from 'react';
import {
 simulateWhatIf,
 type WhatIfResponse,
 type WhatIfScenarioType } from '@api/compliance';
import { useToastStore } from '@store/toast';

interface Props {
 isOpen: boolean;
 onClose: () => void;
}

const SCENARIO_LABELS: Record<WhatIfScenarioType, string> = {
 natural_language: '자연어 입력',
 tariff: '관세 변동',
 fx: '환율 변동',
 chemical: '화학물질 제한',
 labor: '노동 비용 (최저시급)',
 carbon: '탄소세 도입' };

export function WhatIfModal({ isOpen, onClose }: Props) {
 const addToast = useToastStore.getState().addToast;
 const [scenario, setScenario] = useState<WhatIfScenarioType>('natural_language');
 const [query, setQuery] = useState('');
 const [params, setParams] = useState<Record<string, string>>({});
 const [result, setResult] = useState<WhatIfResponse | null>(null);
 const [loading, setLoading] = useState(false);

 if (!isOpen) return null;

 const handleSubmit = async () => {
 setLoading(true);
 try {
 let payload: Record<string, unknown>;
 if (scenario === 'natural_language') {
 payload = { query };
 } else {
 // string params → number 변환
 payload = Object.fromEntries(
 Object.entries(params).map(([k, v]) => [k, isNaN(Number(v)) ? v : Number(v)]),
 );
 }
 const r = await simulateWhatIf(scenario, payload);
 setResult(r);
 } catch (e) {
 addToast({
 type: 'error',
 message: '시뮬레이션 실패: ' + (e instanceof Error ? e.message : String(e)) });
 } finally {
 setLoading(false);
 }
 };

 const handleClose = () => {
 setResult(null);
 setQuery('');
 setParams({});
 onClose();
 };

 return (
 <div
 role="dialog"
 style={{
 position: 'fixed',
 inset: 0,
 background: 'rgba(0,0,0,0.6)',
 display: 'flex',
 alignItems: 'center',
 justifyContent: 'center',
 zIndex: 1000 }}
 onClick={handleClose}
 >
 <div
 onClick={(e) => e.stopPropagation()}
 style={{
 background: 'var(--hud-card-bg, #1a1a1a)',
 color: 'var(--hud-text)',
 padding: 20,
 width: '90%',
 maxWidth: 700,
 maxHeight: '85vh',
 overflow: 'auto',
 border: '1px solid #7B1FA2' }}
 >
 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
 <h2 className="lg-h2" style={{ margin: 0 }}> What-if 분석</h2>
 <button className="lg-btn sm ghost" onClick={handleClose}>✕</button>
 </div>

 {/* 시나리오 선택 */}
 <div style={{ marginBottom: 16 }}>
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 6 }}>시나리오</div>
 <select
 className="lg-select sm"
 value={scenario}
 onChange={(e) => {
 setScenario(e.target.value as WhatIfScenarioType);
 setResult(null);
 }}
 style={{ width: '100%' }}
 >
 {Object.entries(SCENARIO_LABELS).map(([k, v]) => (
 <option key={k} value={k}>{v}</option>
 ))}
 </select>
 </div>

 {/* 입력 영역 */}
 {scenario === 'natural_language' && (
 <div style={{ marginBottom: 16 }}>
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 6 }}>
 자연어 질문 (예: "관세 50% 추가시?", "탄소세 톤당 5만원 도입시?")
 </div>
 <input
 className="lg-input sm"
 type="text"
 value={query}
 onChange={(e) => setQuery(e.target.value)}
 placeholder="질문을 입력하세요"
 style={{ width: '100%' }}
 />
 </div>
 )}

 {scenario === 'tariff' && (
 <ParamInput label="관세율 (%)" k="rate_pct" value={params.rate_pct ?? '25'} onChange={setParams} />
 )}
 {scenario === 'fx' && (
 <ParamInput label="KRW/USD 변동률 (%, 음수=원화 강세)" k="krw_usd_change_pct" value={params.krw_usd_change_pct ?? '-10'} onChange={setParams} />
 )}
 {scenario === 'chemical' && (
 <ParamInput label="화학물질명 (예: 6가 크롬, 납)" k="substance" value={params.substance ?? '6가 크롬'} onChange={setParams} type="text" />
 )}
 {scenario === 'labor' && (
 <ParamInput label="최저시급 인상률 (%)" k="min_wage_increase_pct" value={params.min_wage_increase_pct ?? '5'} onChange={setParams} />
 )}
 {scenario === 'carbon' && (
 <>
 <ParamInput label="톤당 KRW" k="krw_per_ton" value={params.krw_per_ton ?? '30000'} onChange={setParams} />
 <ParamInput label="연간 배출량 (tCO2)" k="annual_tons" value={params.annual_tons ?? '50000'} onChange={setParams} />
 </>
 )}

 <button
 className="lg-btn sm"
 onClick={() => void handleSubmit()}
 disabled={loading || (scenario === 'natural_language' && !query.trim())}
 style={{ marginBottom: 16 }}
 >
 {loading ? '시뮬레이션 중...' : '시뮬레이션 실행'}
 </button>

 {/* 결과 */}
 {result && <ResultPanel result={result} />}

 <p style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginTop: 12 }}>
 ※ 추정치 — 실제 회계 영향은 재무팀 검토 후 확정. 산업 평균 가정 사용.
 </p>
 </div>
 </div>
 );
}

function ParamInput({
 label, k, value, onChange, type = 'number' }: {
 label: string;
 k: string;
 value: string;
 onChange: (fn: (prev: Record<string, string>) => Record<string, string>) => void;
 type?: string;
}) {
 return (
 <div style={{ marginBottom: 12 }}>
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 4 }}>{label}</div>
 <input
 className="lg-input sm"
 type={type}
 value={value}
 onChange={(e) => onChange((prev) => ({ ...prev, [k]: e.target.value }))}
 style={{ width: '100%' }}
 />
 </div>
 );
}

function ResultPanel({ result }: { result: WhatIfResponse }) {
 const fmt = (n: number) => `${n.toLocaleString()}`;
 const baseRev = (result.baseline_kpi.revenue_krw_mn ?? 0) as number;
 const newRev = (result.new_kpi.revenue_krw_mn ?? 0) as number;
 const baseCogs = (result.baseline_kpi.cogs_krw_mn ?? 0) as number;
 const newCogs = (result.new_kpi.cogs_krw_mn ?? 0) as number;
 const baseOp = (result.baseline_kpi.operating_profit_krw_mn ?? 0) as number;
 const newOp = (result.new_kpi.operating_profit_krw_mn ?? 0) as number;
 const baseRisk = (result.baseline_kpi.risk_score ?? 0) as number;
 const newRisk = (result.new_kpi.risk_score ?? 0) as number;

 if (result.scenario_type === 'natural_language') {
 return (
 <div style={{ padding: 12, background: 'rgba(245,124,0,0.1)', border: '1px solid #F57C00' }}>
 <p style={{ margin: 0, fontSize: 12 }}>{result.note}</p>
 </div>
 );
 }

 const meta = result.meta ?? {};
 const conf = meta.confidence ?? 0;
 const confLabel = conf >= 0.8 ? '높음' : conf >= 0.5 ? '중간' : '낮음';
 const confColor = conf >= 0.8 ? '#388E3C' : conf >= 0.5 ? '#F57C00' : '#D32F2F';
 const sourceLabel: Record<string, string> = {
 erp: '내부 ERP',
 dart: 'DART 재무제표',
 industry_avg: '산업 평균',
 hardcoded: '하드코딩 (산업 가정)',
 none: '데이터 없음' };

 return (
 <div style={{ padding: 12, background: 'rgba(123,31,162,0.1)', border: '1px solid #7B1FA2' }}>
 <div
 style={{
 display: 'flex',
 gap: 8,
 alignItems: 'center',
 marginBottom: 8,
 fontSize: 11 }}
 >
 <span
 style={{
 padding: '2px 6px',
 borderRadius: 3,
 background: confColor,
 color: '#fff',
 fontWeight: 600 }}
 >
 confidence {confLabel} ({(conf * 100).toFixed(0)}%)
 </span>
 <span style={{ color: 'var(--hud-text-dim)' }}>
 {sourceLabel[meta.data_source ?? 'none'] ?? meta.data_source ?? '미상'}
 {meta.as_of ? ` · ${meta.as_of}` : ''}
 {meta.corp_code ? ` · corp ${meta.corp_code}` : ''}
 </span>
 </div>
 <p
 style={{
 margin: '0 0 8px 0',
 fontSize: 11,
 color: 'var(--hud-text-dim)',
 fontStyle: 'italic' }}
 >
 AI 자문은 참고용 — 최종 회계 영향은 재무팀 검토 필수.
 </p>
 <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>

 <thead>
 <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
 <th style={{ textAlign: 'left', padding: 4 }}>지표</th>
 <th style={{ textAlign: 'right', padding: 4 }}>baseline</th>
 <th style={{ textAlign: 'right', padding: 4 }}>new</th>
 <th style={{ textAlign: 'right', padding: 4 }}>변화</th>
 </tr>
 </thead>
 <tbody>
 <tr>
 <td style={{ padding: 4 }}>매출 (백만원)</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{fmt(baseRev)}</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{fmt(newRev)}</td>
 <td style={{ textAlign: 'right', padding: 4, color: newRev < baseRev ? '#F57C00' : '#388E3C' }}>
 {newRev - baseRev >= 0 ? '+' : ''}{fmt(newRev - baseRev)}
 </td>
 </tr>
 <tr>
 <td style={{ padding: 4 }}>원가 (백만원)</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{fmt(baseCogs)}</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{fmt(newCogs)}</td>
 <td style={{ textAlign: 'right', padding: 4, color: newCogs > baseCogs ? '#F57C00' : '#388E3C' }}>
 {newCogs - baseCogs >= 0 ? '+' : ''}{fmt(newCogs - baseCogs)}
 </td>
 </tr>
 <tr style={{ fontWeight: 600 }}>
 <td style={{ padding: 4 }}>영업이익 (백만원)</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{fmt(baseOp)}</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{fmt(newOp)}</td>
 <td style={{ textAlign: 'right', padding: 4, color: newOp < baseOp ? '#D32F2F' : '#388E3C' }}>
 {newOp - baseOp >= 0 ? '+' : ''}{fmt(newOp - baseOp)}
 </td>
 </tr>
 <tr>
 <td style={{ padding: 4 }}>위험도 점수</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{baseRisk}</td>
 <td style={{ textAlign: 'right', padding: 4 }}>{newRisk}</td>
 <td style={{ textAlign: 'right', padding: 4, color: newRisk > baseRisk ? '#D32F2F' : '#388E3C' }}>
 {newRisk - baseRisk >= 0 ? '+' : ''}{newRisk - baseRisk}
 </td>
 </tr>
 </tbody>
 </table>
 {result.note && (
 <p style={{ marginTop: 8, fontSize: 11, color: 'var(--hud-text-dim)' }}>{result.note}</p>
 )}
 </div>
 );
}
