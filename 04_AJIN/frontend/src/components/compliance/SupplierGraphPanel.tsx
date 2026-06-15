// P4 D16 — 공급망 다중 tier 그래프 panel.
// supplierId 기준 down(자식) / up(부모) 트리 노출 + cycle 경고.
// 디스클레이머: AI 자문은 참고용 — 최종 판단은 담당자.

import { useEffect, useState } from 'react';
import {
 fetchSupplierGraph,
 type SupplierGraphNode,
 type SupplierGraphResponse } from '@api/compliance';

interface Props {
 supplierId: string;
 initialDirection?: 'down' | 'up';
 initialMaxDepth?: number;
}

const DEPTH_COLORS = ['#1976d2', '#43a047', '#fb8c00', '#8e24aa', '#c62828', '#5d4037'];

export function SupplierGraphPanel({
 supplierId,
 initialDirection = 'down',
 initialMaxDepth = 3 }: Props) {
 const [direction, setDirection] = useState<'down' | 'up'>(initialDirection);
 const [maxDepth, setMaxDepth] = useState<number>(initialMaxDepth);
 const [data, setData] = useState<SupplierGraphResponse | null>(null);
 const [busy, setBusy] = useState(false);
 const [error, setError] = useState<string | null>(null);

 useEffect(() => {
 if (!supplierId) return;
 setBusy(true);
 setError(null);
 fetchSupplierGraph(supplierId, direction, maxDepth)
 .then(setData)
 .catch((e) => setError((e as Error).message))
 .finally(() => setBusy(false));
 }, [supplierId, direction, maxDepth]);

 return (
 <div className="lg-card">
 <div className="lg-card-h">
 <div>
 <div className="lg-pill">P4 D16 · SUPPLIER GRAPH</div>
 <strong>공급망 다중 tier — origin {supplierId}</strong>
 </div>
 <div style={{ display: 'flex', gap: 8 }}>
 <select
 className="lg-input"
 value={direction}
 onChange={(e) => setDirection(e.target.value as 'down' | 'up')}
 >
 <option value="down">자식 (down)</option>
 <option value="up">부모 체인 (up)</option>
 </select>
 <select
 className="lg-input"
 value={maxDepth}
 onChange={(e) => setMaxDepth(Number(e.target.value))}
 >
 {[1, 2, 3, 4, 5].map((d) => (
 <option key={d} value={d}>
 depth {d}
 </option>
 ))}
 </select>
 </div>
 </div>

 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
 AI 자문은 참고용 — 최종 판단은 담당자입니다.
 </p>

 {error && (
 <div className="lg-state-pill crit" style={{ marginTop: 8 }}>
 {error}
 </div>
 )}

 {busy && <p>불러오는 중…</p>}

 {data && (
 <>
 {data.cycles_detected.length > 0 && (
 <div className="lg-state-pill crit" style={{ marginBottom: 8 }}>
 Cycle {data.cycles_detected.length}개 감지 — parent_supplier_id 매핑 검증 필요
 </div>
 )}
 {data.nodes.length === 0 ? (
 <p style={{ color: 'var(--hud-text-dim)' }}>
 {direction === 'down' ? '자식' : '부모'} 협력사 데이터 미수집 — CSV 임포트 필요
 </p>
 ) : (
 <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
 {data.nodes.map((n) => (
 <li
 key={`${n.supplier_id}-${n.depth_from_origin}`}
 style={{
 padding: '6px 8px',
 marginBottom: 2,
 borderLeft: `4px solid ${
 DEPTH_COLORS[n.depth_from_origin % DEPTH_COLORS.length]
 }`,
 background: 'var(--hud-surface)' }}
 >
 <span style={{ paddingLeft: n.depth_from_origin * 14 }}>
 {n.supplier_id} · {n.name || '-'}{' '}
 {n.relation_type && n.relation_type !== 'direct' && (
 <span
 style={{
 padding: '1px 5px',
 marginLeft: 4,
 borderRadius: 3,
 background: 'rgba(123,31,162,0.15)',
 fontSize: 10,
 color: '#9C27B0' }}
 >
 {n.relation_type}
 </span>
 )}
 <small style={{ color: 'var(--hud-text-dim)', marginLeft: 4 }}>
 tier {n.tier_depth} · {n.country} · 점수 {n.compliance_score}
 </small>
 </span>
 </li>
 ))}
 </ul>
 )}
 </>
 )}
 </div>
 );
}

function _suppress<T>(node: SupplierGraphNode): T {
 return node as unknown as T;
}
void _suppress;
