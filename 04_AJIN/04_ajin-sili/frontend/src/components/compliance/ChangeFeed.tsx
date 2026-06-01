// MVP — 변경 피드 카드 리스트 (Stage 7 결과 view).
// 필터: grade / status / dept / 노이즈 archive 포함 여부
// 카드: grade 배지 · 1줄 요약 · 영향 부서 칩 · diff 펼치기 · 상태 전환 · 확인
//
// 디자인 시스템: Liquid Glass v3.5 (lg-card / lg-pill / lg-btn).

import { useEffect, useState, useCallback, useRef } from 'react';
import {
 fetchChangeFeed,
 acknowledgeChange,
 transitionChangeStatus,
 correctChange,
 fetchSimilarCases,
 fetchAffectedContracts,
 fetchAffectedSuppliers,
 fetchCostSimulation,
 sendSupplierAssessment,
 createCollabTicket,
 fetchIndustryContext,
 type ChangeFeedItem,
 type ChangeGrade,
 type ChangeStatus,
 type LegalClass,
 type CorrectableField,
 type CaseLawItem,
 type AffectedContractItem,
 type AffectedSupplierItem,
 type CostSimulationResponse,
 type IndustryContextResponse } from '@api/compliance';
import { useToastStore } from '@store/toast';
import { getComplianceGradeMeta } from '@lib/complianceSeverity';

const STATUS_LABEL: Record<ChangeStatus, string> = {
 pending: '대기',
 reviewing: '검토중',
 planning: '계획수립',
 announced: '공지발송',
 done: '완료',
 filtered: '자동 archive' };

const TYPE_LABEL: Record<string, string> = {
 added: '신설',
 modified: '개정',
 removed: '폐지' };

const LEGAL_LABEL: Record<LegalClass, { ko: string; color: string }> = {
 criminal: { ko: '형사', color: '#D32F2F' },
 administrative: { ko: '행정', color: '#F57C00' },
 civil: { ko: '민사', color: '#7B1FA2' },
 contract: { ko: '계약', color: '#1976D2' },
 standardization: { ko: '표준', color: '#388E3C' } };

interface Props {
 /** 페이지네이션 크기 (default 30) */
 pageSize?: number;
 /** v4.2 M3 — D 알람 deep-link 대상 regulation_id. 진입 시 해당 row 확장·스크롤·하이라이트. */
 focusId?: string | null;
}

export function ChangeFeed({ pageSize = 30, focusId = null }: Props) {
 const [items, setItems] = useState<ChangeFeedItem[]>([]);
 const [total, setTotal] = useState(0);
 const [hasMore, setHasMore] = useState(false);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string | null>(null);

 // 필터
 const [grade, setGrade] = useState<ChangeGrade | ''>('');
 const [status, setStatus] = useState<ChangeStatus | ''>('');
 const [dept, setDept] = useState('');
 const [legalClass, setLegalClass] = useState<LegalClass | ''>('');
 const [includeFiltered, setIncludeFiltered] = useState(false);
 const [expandedId, setExpandedId] = useState<number | null>(null);
 // v4.2 M3 — focusId 진입 시 임시 하이라이트 (3초 후 자동 해제)
 const [highlightedId, setHighlightedId] = useState<number | null>(null);
 const listRef = useRef<HTMLUListElement | null>(null);

 const addToast = useToastStore.getState().addToast;

 const load = useCallback(async (offset = 0) => {
 setLoading(true);
 setError(null);
 try {
 const res = await fetchChangeFeed({
 grade: grade || undefined,
 status: status || undefined,
 dept: dept || undefined,
 legalClass: legalClass || undefined,
 includeFiltered,
 limit: pageSize,
 offset });
 setTotal(res.total);
 setHasMore(res.has_more);
 setItems((prev) => (offset === 0 ? res.items : [...prev, ...res.items]));
 } catch (e) {
 setError(e instanceof Error ? e.message : String(e));
 } finally {
 setLoading(false);
 }
 }, [grade, status, dept, legalClass, includeFiltered, pageSize]);

 useEffect(() => {
 void load(0);
 // eslint-disable-next-line react-hooks/exhaustive-deps
 }, [grade, status, dept, legalClass, includeFiltered]);

 // v4.2 M3 — focusId 가 변경되거나 items 가 로드된 직후, 해당 row 확장·스크롤·하이라이트.
 useEffect(() => {
 if (!focusId || items.length === 0) return;
 const targetId = Number(focusId);
 if (!Number.isFinite(targetId)) return;
 const match = items.find((it) => it.id === targetId);
 if (!match) return;

 setExpandedId(targetId);
 setHighlightedId(targetId);

 // DOM 업데이트 직후 scrollIntoView — listRef 내부에서 검색.
 const raf = window.requestAnimationFrame(() => {
 const el = listRef.current?.querySelector<HTMLLIElement>(`[data-change-id="${targetId}"]`);
 el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
 });

 // 3초 후 하이라이트 해제
 const timer = window.setTimeout(() => setHighlightedId(null), 3000);
 return () => {
 window.cancelAnimationFrame(raf);
 window.clearTimeout(timer);
 };
 }, [focusId, items]);

 const handleAck = async (id: number) => {
 try {
 await acknowledgeChange(id);
 setItems((prev) => prev.map((c) => (c.id === id ? { ...c, acknowledged: true } : c)));
 addToast({ type: 'success', message: '확인 처리되었습니다.' });
 } catch (e) {
 addToast({
 type: 'error',
 message: '확인 실패: ' + (e instanceof Error ? e.message : String(e)) });
 }
 };

 const handleTransition = async (id: number, newStatus: ChangeStatus) => {
 try {
 await transitionChangeStatus(id, newStatus);
 setItems((prev) => prev.map((c) => (c.id === id ? { ...c, status: newStatus } : c)));
 addToast({ type: 'success', message: `상태 → ${STATUS_LABEL[newStatus]}` });
 } catch (e) {
 addToast({
 type: 'error',
 message: '상태 전환 실패: ' + (e instanceof Error ? e.message : String(e)) });
 }
 };

 // P2 D5 — Feedback Loop: 사용자 수정
 const handleCorrect = async (
 id: number,
 field: CorrectableField,
 newValue: unknown,
 note?: string,
 ) => {
 try {
 await correctChange(id, field, newValue, note);
 // optimistic update
 setItems((prev) =>
 prev.map((c) => {
 if (c.id !== id) return c;
 return { ...c, [field]: newValue } as ChangeFeedItem;
 }),
 );
 addToast({ type: 'success', message: `${field} 수정 완료 (학습 데이터 적재됨)` });
 } catch (e) {
 addToast({
 type: 'error',
 message: '수정 실패: ' + (e instanceof Error ? e.message : String(e)) });
 }
 };

 return (
 <section className="lg-card">
 <div className="lg-card-h">
 <div>
 <div className="lg-eyebrow">CHANGE FEED · 변경 피드</div>
 <h2 className="lg-h2">규제 변경 자동 감지 결과</h2>
 </div>
 <span className="lg-pill">총 {total}건</span>
 </div>

 {/* 필터 바 */}
 <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
 <select
 className="lg-select sm"
 value={grade}
 onChange={(e) => setGrade(e.target.value as ChangeGrade | '')}
 aria-label="등급 필터"
 >
 <option value="">전체 등급</option>
 <option value="CRITICAL">CRITICAL</option>
 <option value="HIGH">HIGH</option>
 <option value="MEDIUM">MEDIUM</option>
 <option value="LOW">LOW</option>
 </select>
 <select
 className="lg-select sm"
 value={status}
 onChange={(e) => setStatus(e.target.value as ChangeStatus | '')}
 aria-label="상태 필터"
 >
 <option value="">전체 상태</option>
 <option value="pending">대기</option>
 <option value="reviewing">검토중</option>
 <option value="planning">계획수립</option>
 <option value="announced">공지발송</option>
 <option value="done">완료</option>
 </select>
 <input
 className="lg-input sm"
 type="text"
 placeholder="부서명 (예: 안전보건팀)"
 value={dept}
 onChange={(e) => setDept(e.target.value)}
 aria-label="부서 필터"
 style={{ minWidth: 180 }}
 />
 <select
 className="lg-select sm"
 value={legalClass}
 onChange={(e) => setLegalClass(e.target.value as LegalClass | '')}
 aria-label="법무 분류 필터"
 >
 <option value="">전체 분류</option>
 {(Object.keys(LEGAL_LABEL) as LegalClass[]).map((c) => (
 <option key={c} value={c}>
 {LEGAL_LABEL[c].ko}
 </option>
 ))}
 </select>
 <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
 <input
 type="checkbox"
 checked={includeFiltered}
 onChange={(e) => setIncludeFiltered(e.target.checked)}
 />
 노이즈 archive 포함
 </label>
 <button className="lg-btn sm ghost" onClick={() => void load(0)} disabled={loading}>
 {loading ? '' : '↻ 새로고침'}
 </button>
 </div>

 {error && (
 <p style={{ color: 'var(--hud-red, #f33)', fontSize: 13 }}> 로드 실패: {error}</p>
 )}

 {!loading && items.length === 0 && !error && (
 <p style={{ color: 'var(--hud-text-dim)', fontSize: 13 }}>
 감지된 변경이 없습니다. 크롤러를 두 번 이상 실행하면 차이점이 자동으로 감지됩니다.
 </p>
 )}

 <ul ref={listRef} style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
 {items.map((item) => (
 <li
 key={item.id}
 data-change-id={item.id}
 style={{
 listStyle: 'none',
 borderRadius: 8,
 transition: 'box-shadow 0.3s ease, outline-color 0.3s ease',
 outline: highlightedId === item.id ? '2px solid var(--hud-primary)' : '2px solid transparent',
 boxShadow: highlightedId === item.id
 ? '0 0 0 4px color-mix(in oklab, var(--hud-primary) 22%, transparent)'
 : 'none',
 }}
 >
 <ChangeCard
 item={item}
 expanded={expandedId === item.id}
 onToggle={() => setExpandedId((cur) => (cur === item.id ? null : item.id))}
 onAck={() => handleAck(item.id)}
 onTransition={(s) => handleTransition(item.id, s)}
 onCorrect={(field, value, note) => handleCorrect(item.id, field, value, note)}
 />
 </li>
 ))}
 </ul>

 {hasMore && (
 <div style={{ marginTop: 12, textAlign: 'center' }}>
 <button
 className="lg-btn sm"
 disabled={loading}
 onClick={() => void load(items.length)}
 >
 {loading ? '' : `더 보기 (${total - items.length}건 남음)`}
 </button>
 </div>
 )}

 {/* AI 자동 분류 disclaimer */}
 <p style={{ marginTop: 16, fontSize: 11, color: 'var(--hud-text-dim)' }}>
 ※ 등급·요약·영향 매핑은 AI 자동 분류 결과입니다. 최종 판단은 담당자가 수행하세요.
 </p>
 </section>
 );
}

// ─────────────────────────────────────────────────────────────
// ChangeCard
// ─────────────────────────────────────────────────────────────

interface CardProps {
 item: ChangeFeedItem;
 expanded: boolean;
 onToggle: () => void;
 onAck: () => void;
 onTransition: (s: ChangeStatus) => void;
 onCorrect: (field: CorrectableField, value: unknown, note?: string) => void;
}

function ChangeCard({ item, expanded, onToggle, onAck, onTransition, onCorrect }: CardProps) {
 const gradeStyle = getComplianceGradeMeta(item.grade);
 const typeLabel = TYPE_LABEL[item.change_type] ?? item.change_type;
 const [editing, setEditing] = useState<CorrectableField | null>(null);
 // P2 D8 — 유사 판례 lazy load
 const [cases, setCases] = useState<CaseLawItem[] | null>(null);
 const [casesLoading, setCasesLoading] = useState(false);
 const [casesNote, setCasesNote] = useState<string>('');

 const loadCases = async () => {
 if (cases !== null) {
 setCases(null);
 return;
 }
 setCasesLoading(true);
 try {
 const r = await fetchSimilarCases(item.id, 3);
 setCases(r.items);
 setCasesNote(r.note);
 } catch (e) {
 setCasesNote(e instanceof Error ? e.message : String(e));
 setCases([]);
 } finally {
 setCasesLoading(false);
 }
 };

 // P2 D7 — 영향 계약 lazy load
 const [contracts, setContracts] = useState<AffectedContractItem[] | null>(null);
 const [contractsLoading, setContractsLoading] = useState(false);

 const loadContracts = async () => {
 if (contracts !== null) {
 setContracts(null);
 return;
 }
 setContractsLoading(true);
 try {
 const r = await fetchAffectedContracts(item.id, 5);
 setContracts(r.items);
 } catch {
 setContracts([]);
 } finally {
 setContractsLoading(false);
 }
 };

 // P2 D6 — 영향 협력사 + 비용 시뮬레이션 lazy load
 const [suppliers, setSuppliers] = useState<AffectedSupplierItem[] | null>(null);
 const [suppliersLoading, setSuppliersLoading] = useState(false);
 const [costSim, setCostSim] = useState<CostSimulationResponse | null>(null);
 const [costSimLoading, setCostSimLoading] = useState(false);

 const loadSuppliers = async () => {
 if (suppliers !== null) {
 setSuppliers(null);
 return;
 }
 setSuppliersLoading(true);
 try {
 const r = await fetchAffectedSuppliers(item.id, 20);
 setSuppliers(r.items);
 } catch {
 setSuppliers([]);
 } finally {
 setSuppliersLoading(false);
 }
 };

 const loadCostSim = async () => {
 if (costSim !== null) {
 setCostSim(null);
 return;
 }
 setCostSimLoading(true);
 try {
 const r = await fetchCostSimulation(item.id, 25.0);
 setCostSim(r);
 } catch {
 setCostSim(null);
 } finally {
 setCostSimLoading(false);
 }
 };

 // P3 D9 — 협업 티켓 (다중 부서 영향 시만 노출)
 const [ticketResult, setTicketResult] = useState<{
 id: number;
 owners: number;
 slack_sent: boolean;
 } | null>(null);
 const [ticketCreating, setTicketCreating] = useState(false);
 const addToastForTicket = useToastStore.getState().addToast;

 // P3 D11 — 산업 트렌드 lazy
 const [industry, setIndustry] = useState<IndustryContextResponse | null>(null);
 const [industryLoading, setIndustryLoading] = useState(false);

 const loadIndustry = async () => {
 if (industry !== null) {
 setIndustry(null);
 return;
 }
 setIndustryLoading(true);
 try {
 const r = await fetchIndustryContext(item.id);
 setIndustry(r);
 } catch {
 setIndustry(null);
 } finally {
 setIndustryLoading(false);
 }
 };

 const handleCreateTicket = async () => {
 setTicketCreating(true);
 try {
 const r = await createCollabTicket(item.id);
 if (r.ok) {
 setTicketResult({
 id: r.ticket_id,
 owners: r.owners.length,
 slack_sent: r.slack_sent });
 addToastForTicket({
 type: 'success',
 message: `협업 티켓 #${r.ticket_id} 생성 완료 (책임자 ${r.owners.length}명, Slack ${r.slack_sent ? '발송' : '미발송'})` });
 } else {
 addToastForTicket({
 type: 'warning',
 message: r.error || '티켓 생성 실패' });
 }
 } catch (e) {
 addToastForTicket({
 type: 'error',
 message: '티켓 생성 실패: ' + (e instanceof Error ? e.message : String(e)) });
 } finally {
 setTicketCreating(false);
 }
 };

 return (
 <li
 style={{
 border: '1px solid var(--hud-border, #2a2a2a)',
 borderRadius: 2,
 padding: 12,
 background: 'var(--hud-card-bg, rgba(255,255,255,0.02))' }}
 >
 <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
 <span
 style={{
 background: gradeStyle.color,
 color: gradeStyle.foreground,
 padding: '2px 8px',
 fontSize: 11,
 fontWeight: 600,
 letterSpacing: 0.5 }}
 title={`${gradeStyle.grade} · ${gradeStyle.labelKo} · ${gradeStyle.actionLabel}`}
 >
 {gradeStyle.grade} · {gradeStyle.actionLabel}
 </span>
 <span className="lg-pill" style={{ fontSize: 10 }}>{typeLabel}</span>
 <strong style={{ flex: 1, fontSize: 14 }}>{item.item_title || '(제목 없음)'}</strong>
 <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
 {item.detected_at.slice(0, 16).replace('T', ' ')}
 </span>
 </div>

 <p style={{ margin: '8px 0 6px', fontSize: 13 }}>{item.summary_ko || '(AI 요약 없음)'}</p>

 {/* P1 D1 — 법무 5분류 배지 + 벌칙 한 줄 */}
 {(item.legal_class.length > 0 || item.penalty_extract) && (
 <div
 style={{
 display: 'flex',
 gap: 6,
 flexWrap: 'wrap',
 alignItems: 'center',
 marginBottom: 8,
 padding: '4px 8px',
 background: 'rgba(0,0,0,0.15)',
 borderLeft: '2px solid #7B1FA2',
 fontSize: 11 }}
 >
 {item.legal_class.map((lc) => {
 const meta = LEGAL_LABEL[lc];
 if (!meta) return null;
 return (
 <span
 key={lc}
 style={{
 background: meta.color,
 color: '#fff',
 padding: '1px 6px',
 fontWeight: 600 }}
 title={`법적 리스크: ${meta.ko}`}
 >
 {meta.ko}
 </span>
 );
 })}
 {item.penalty_extract && (
 <span style={{ color: 'var(--hud-text)' }}>
 {item.penalty_extract}
 </span>
 )}
 </div>
 )}

 {(item.affected_departments.length > 0 || item.affected_plants.length > 0) && (
 <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
 {item.affected_departments.map((d) => (
 <span key={'d-' + d} className="lg-pill" style={{ fontSize: 10 }}>
 {d}
 </span>
 ))}
 {item.affected_plants.map((p) => (
 <span key={'p-' + p} className="lg-pill" style={{ fontSize: 10 }}>
 {p}
 </span>
 ))}
 </div>
 )}

 <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
 <select
 className="lg-select sm"
 value={item.status}
 onChange={(e) => onTransition(e.target.value as ChangeStatus)}
 disabled={item.status === 'filtered'}
 aria-label="상태 전환"
 >
 {(['pending', 'reviewing', 'planning', 'announced', 'done'] as ChangeStatus[]).map((s) => (
 <option key={s} value={s}>{STATUS_LABEL[s]}</option>
 ))}
 {item.status === 'filtered' && <option value="filtered">자동 archive</option>}
 </select>

 <button className="lg-btn sm ghost" onClick={onToggle}>
 {expanded ? '접기 ▲' : 'diff 펼치기 ▼'}
 </button>

 {!item.acknowledged && (
 <button className="lg-btn sm ghost" onClick={onAck}>
 ✓ 확인
 </button>
 )}
 {item.acknowledged && (
 <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>✓ 확인 완료</span>
 )}

 {/* P2 D5 — AI 추천 수정 */}
 <button
 className="lg-btn sm ghost"
 onClick={() => setEditing((cur) => (cur ? null : 'legal_class'))}
 title="AI 추천 수정 (학습 데이터로 적재)"
 >
 수정
 </button>

 {/* P2 D8 — 유사 판례 (법무 5분류 있을 때만 노출) */}
 {item.legal_class.length > 0 && (
 <button
 className="lg-btn sm ghost"
 onClick={() => void loadCases()}
 disabled={casesLoading}
 title="대법원 종합법률정보 유사 판례 검색"
 >
 {casesLoading ? '' : cases !== null ? '판례 닫기' : '유사 판례'}
 </button>
 )}

 {/* P2 D7 — 영향 계약 */}
 <button
 className="lg-btn sm ghost"
 onClick={() => void loadContracts()}
 disabled={contractsLoading}
 title="진행 중 계약의 영향 조항 자동 추출"
 >
 {contractsLoading ? '' : contracts !== null ? '계약 닫기' : '영향 계약'}
 </button>

 {/* P2 D6 — 영향 협력사 */}
 <button
 className="lg-btn sm ghost"
 onClick={() => void loadSuppliers()}
 disabled={suppliersLoading}
 title="공급망 영향 협력사 자동 매핑"
 >
 {suppliersLoading ? '' : suppliers !== null ? '공급망 닫기' : '영향 협력사'}
 </button>

 {/* P2 D6 — 비용 시뮬레이션 */}
 <button
 className="lg-btn sm ghost"
 onClick={() => void loadCostSim()}
 disabled={costSimLoading}
 title="관세 25% / 화학물질 대체 시 원가 영향 시뮬레이션"
 >
 {costSimLoading ? '' : costSim !== null ? '비용 닫기' : '비용 시뮬'}
 </button>

 {/* P3 D9 — 협업 티켓 (다중 부서 영향 시만 노출) */}
 {item.affected_departments.length >= 2 && ticketResult === null && (
 <button
 className="lg-btn sm ghost"
 onClick={() => void handleCreateTicket()}
 disabled={ticketCreating}
 title="다중 부서 영향 — 협업 티켓 자동 생성 + Slack DM"
 >
 {ticketCreating ? '' : '협업 티켓 생성'}
 </button>
 )}
 {ticketResult !== null && (
 <span
 style={{
 fontSize: 11,
 padding: '2px 8px',
 background: '#388E3C',
 color: '#fff',
 borderRadius: 2 }}
 title={`책임자 ${ticketResult.owners}명 매핑${ticketResult.slack_sent ? ' / Slack 발송 완료' : ' / Slack 미발송'}`}
 >
 ✓ 티켓 #{ticketResult.id} 생성
 </span>
 )}

 {/* P3 D11 — 산업 비교 */}
 <button
 className="lg-btn sm ghost"
 onClick={() => void loadIndustry()}
 disabled={industryLoading}
 title="동종업계 5개사 DART 공시 비교 — 우리만 영향인지 산업 전반 영향인지"
 >
 {industryLoading ? '' : industry !== null ? '산업 닫기' : '산업 비교'}
 </button>
 </div>

 {cases !== null && (
 <SimilarCasesPanel cases={cases} note={casesNote} />
 )}

 {contracts !== null && (
 <AffectedContractsPanel contracts={contracts} />
 )}

 {suppliers !== null && (
 <AffectedSuppliersPanel
 suppliers={suppliers}
 changeId={item.id}
 />
 )}

 {costSim !== null && (
 <CostSimulationPanel cost={costSim} />
 )}

 {industry !== null && (
 <IndustryContextPanel data={industry} />
 )}

 {editing && (
 <CorrectionEditor
 item={item}
 initialField={editing}
 onCancel={() => setEditing(null)}
 onSubmit={(field, value, note) => {
 onCorrect(field, value, note);
 setEditing(null);
 }}
 />
 )}

 {expanded && (
 <div
 style={{
 marginTop: 10,
 padding: 8,
 background: 'rgba(0,0,0,0.2)',
 fontSize: 12,
 fontFamily: 'monospace' }}
 >
 {item.old_value && (
 <div style={{ marginBottom: 6 }}>
 <strong style={{ color: '#F57C00' }}>변경 내용:</strong>
 <pre style={{ margin: '4px 0', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
 {item.old_value}
 </pre>
 </div>
 )}
 {item.audit_trail.length > 0 && (
 <div>
 <strong>감사 이력:</strong>
 <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
 {item.audit_trail.map((e, i) => (
 <li key={i} style={{ color: 'var(--hud-text-dim)' }}>
 {e.ts.slice(0, 16).replace('T', ' ')} · {e.user || '-'} · {e.action}
 {e.from && e.to && ` (${e.from} → ${e.to})`}
 </li>
 ))}
 </ul>
 </div>
 )}
 </div>
 )}
 </li>
 );
}


// ─────────────────────────────────────────────────────────────
// P2 D5 — CorrectionEditor (인라인 편집 popup)
// ─────────────────────────────────────────────────────────────

interface EditorProps {
 item: ChangeFeedItem;
 initialField: CorrectableField;
 onCancel: () => void;
 onSubmit: (field: CorrectableField, value: unknown, note: string) => void;
}

function CorrectionEditor({ item, initialField, onCancel, onSubmit }: EditorProps) {
 const [field, setField] = useState<CorrectableField>(initialField);
 const [note, setNote] = useState('');

 // 필드 별 input 상태 — 단일 source-of-truth (string)
 // 다중값 필드는 콤마 구분으로 입력
 const initialValue = (() => {
 if (field === 'affected_departments') return item.affected_departments.join(', ');
 if (field === 'affected_plants') return item.affected_plants.join(', ');
 if (field === 'legal_class') return item.legal_class.join(', ');
 if (field === 'grade') return item.grade;
 if (field === 'summary_ko') return item.summary_ko;
 if (field === 'penalty_extract') return item.penalty_extract;
 return '';
 })();
 const [value, setValue] = useState(initialValue);

 // field 변경 시 value 초기화
 const handleFieldChange = (f: CorrectableField) => {
 setField(f);
 if (f === 'affected_departments') setValue(item.affected_departments.join(', '));
 else if (f === 'affected_plants') setValue(item.affected_plants.join(', '));
 else if (f === 'legal_class') setValue(item.legal_class.join(', '));
 else if (f === 'grade') setValue(item.grade);
 else if (f === 'summary_ko') setValue(item.summary_ko);
 else if (f === 'penalty_extract') setValue(item.penalty_extract);
 };

 const handleSubmit = () => {
 let parsed: unknown = value;
 if (field === 'affected_departments' || field === 'affected_plants' || field === 'legal_class') {
 parsed = value.split(',').map((s) => s.trim()).filter(Boolean);
 }
 onSubmit(field, parsed, note);
 };

 return (
 <div
 style={{
 marginTop: 10,
 padding: 12,
 background: 'rgba(123,31,162,0.08)',
 border: '1px solid #7B1FA2',
 borderRadius: 4 }}
 >
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8 }}>
 AI 추천 수정 — 수정 이력은 학습 데이터로 자동 적재됩니다.
 </div>
 <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
 <select
 className="lg-select sm"
 value={field}
 onChange={(e) => handleFieldChange(e.target.value as CorrectableField)}
 aria-label="수정할 필드"
 >
 <option value="legal_class">법무 5분류 (콤마 구분)</option>
 <option value="grade">등급</option>
 <option value="affected_departments">영향 부서 (콤마 구분)</option>
 <option value="affected_plants">영향 시설 (콤마 구분)</option>
 <option value="summary_ko">한 줄 요약</option>
 <option value="penalty_extract">벌칙 한 줄</option>
 </select>
 </div>

 {field === 'grade' ? (
 <select
 className="lg-select sm"
 value={value}
 onChange={(e) => setValue(e.target.value)}
 style={{ minWidth: 140 }}
 >
 <option value="CRITICAL">CRITICAL</option>
 <option value="HIGH">HIGH</option>
 <option value="MEDIUM">MEDIUM</option>
 <option value="LOW">LOW</option>
 </select>
 ) : (
 <input
 className="lg-input sm"
 type="text"
 value={value}
 onChange={(e) => setValue(e.target.value)}
 style={{ width: '100%', marginBottom: 6 }}
 placeholder={
 field === 'legal_class'
 ? '예: criminal, administrative'
 : field === 'affected_departments'
 ? '예: 안전보건팀, 품질경영팀'
 : '값 입력'
 }
 />
 )}

 <input
 className="lg-input sm"
 type="text"
 value={note}
 onChange={(e) => setNote(e.target.value)}
 style={{ width: '100%', marginTop: 6, marginBottom: 8 }}
 placeholder="수정 사유 (선택)"
 />

 <div style={{ display: 'flex', gap: 6 }}>
 <button className="lg-btn sm" onClick={handleSubmit}>
 저장
 </button>
 <button className="lg-btn sm ghost" onClick={onCancel}>
 취소
 </button>
 </div>
 </div>
 );
}


// ─────────────────────────────────────────────────────────────
// P2 D8 — SimilarCasesPanel (유사 판례 lazy 노출)
// ─────────────────────────────────────────────────────────────

function SimilarCasesPanel({ cases, note }: { cases: CaseLawItem[]; note: string }) {
 return (
 <div
 style={{
 marginTop: 10,
 padding: 10,
 background: 'rgba(25,118,210,0.08)',
 border: '1px solid #1976D2',
 borderRadius: 4 }}
 >
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8 }}>
 유사 판례 (대법원 종합법률정보) — 유사도 0.7 이상만 노출
 </div>
 {cases.length === 0 ? (
 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)', margin: 0 }}>
 {note || '매칭된 판례 없음'}
 </p>
 ) : (
 <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
 {cases.map((c) => (
 <li
 key={c.case_id}
 style={{
 marginBottom: 8,
 paddingBottom: 8,
 borderBottom: '1px solid rgba(255,255,255,0.05)' }}
 >
 <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
 <strong style={{ fontSize: 12 }}>{c.title || c.case_id}</strong>
 <span style={{ fontSize: 10, color: 'var(--hud-text-dim)' }}>
 {c.court} · {c.date}
 </span>
 <span
 style={{
 fontSize: 10,
 background: '#1976D2',
 color: '#fff',
 padding: '1px 6px' }}
 title={`유사도: ${c.similarity}`}
 >
 유사도 {(c.similarity * 100).toFixed(0)}%
 </span>
 </div>
 {c.summary_excerpt && (
 <p style={{ margin: '4px 0', fontSize: 11, color: 'var(--hud-text)', lineHeight: 1.5 }}>
 {c.summary_excerpt}
 </p>
 )}
 {c.full_url && (
 <a
 href={c.full_url}
 target="_blank"
 rel="noreferrer noopener"
 style={{ fontSize: 10, color: '#42a5f5' }}
 >
 원문 보기 →
 </a>
 )}
 </li>
 ))}
 </ul>
 )}
 <p style={{ marginTop: 6, fontSize: 10, color: 'var(--hud-text-dim)' }}>
 ※ AI 자문은 참고용 — 최종 판단은 법무팀.
 </p>
 </div>
 );
}


// ─────────────────────────────────────────────────────────────
// P2 D7 — AffectedContractsPanel
// ─────────────────────────────────────────────────────────────

function AffectedContractsPanel({ contracts }: { contracts: AffectedContractItem[] }) {
 return (
 <div
 style={{
 marginTop: 10,
 padding: 10,
 background: 'rgba(56,142,60,0.08)',
 border: '1px solid #388E3C',
 borderRadius: 4 }}
 >
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8 }}>
 영향 계약 — 진행 중 OEM·공급계약의 매칭 조항
 </div>
 {contracts.length === 0 ? (
 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)', margin: 0 }}>
 매칭된 계약 조항 없음 (계약 DB 미적재 또는 임계값 미달)
 </p>
 ) : (
 <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
 {contracts.map((c, i) => (
 <li
 key={`${c.contract_id}-${c.clause_no}-${i}`}
 style={{
 marginBottom: 8,
 paddingBottom: 8,
 borderBottom: '1px solid rgba(255,255,255,0.05)' }}
 >
 <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
 <strong style={{ fontSize: 12 }}>
 {c.counterparty || c.contract_id}
 {c.type && <span style={{ color: 'var(--hud-text-dim)', marginLeft: 4 }}>· {c.type}</span>}
 </strong>
 {c.clause_no && (
 <span className="lg-pill" style={{ fontSize: 10 }}>
 {c.clause_no}
 </span>
 )}
 <span
 style={{
 fontSize: 10,
 background: c.source === 'vector' ? '#388E3C' : '#1976D2',
 color: '#fff',
 padding: '1px 6px' }}
 title={`매칭 출처: ${c.source}`}
 >
 {c.source === 'vector'
 ? `의미 ${((c.similarity ?? 0) * 100).toFixed(0)}%`
 : `키워드 ${c.match_keywords.length}개`}
 </span>
 </div>
 {c.title && (
 <div style={{ fontSize: 11, marginTop: 2, color: 'var(--hud-text)' }}>
 {c.title}
 </div>
 )}
 {c.body_excerpt && (
 <p style={{ margin: '4px 0', fontSize: 11, color: 'var(--hud-text)', lineHeight: 1.5 }}>
 {c.body_excerpt}
 </p>
 )}
 {c.match_keywords.length > 0 && (
 <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
 {c.match_keywords.map((kw) => (
 <span key={kw} className="lg-pill" style={{ fontSize: 10 }}>
 {kw}
 </span>
 ))}
 </div>
 )}
 </li>
 ))}
 </ul>
 )}
 <p style={{ marginTop: 6, fontSize: 10, color: 'var(--hud-text-dim)' }}>
 ※ AI 추천 — 법무팀 검토 후 최종 판단.
 </p>
 </div>
 );
}


// ─────────────────────────────────────────────────────────────
// P2 D6 — AffectedSuppliersPanel + CostSimulationPanel
// ─────────────────────────────────────────────────────────────

function AffectedSuppliersPanel({
 suppliers,
 changeId }: {
 suppliers: AffectedSupplierItem[];
 changeId: number;
}) {
 const addToast = useToastStore.getState().addToast;
 const [sending, setSending] = useState<string | null>(null);

 const handleSendAssessment = async (supplierId: string) => {
 setSending(supplierId);
 try {
 const r = await sendSupplierAssessment(supplierId, changeId);
 addToast({
 type: r.sent_via_smtp ? 'success' : 'warning',
 message: r.sent_via_smtp
 ? `${supplierId} 자가진단 메일 발송 완료`
 : `${supplierId} 자가진단 큐 적재 (SMTP 미설정 — 발송은 별도 처리)` });
 } catch (e) {
 addToast({
 type: 'error',
 message: '자가진단 발송 실패: ' + (e instanceof Error ? e.message : String(e)) });
 } finally {
 setSending(null);
 }
 };

 return (
 <div
 style={{
 marginTop: 10,
 padding: 10,
 background: 'rgba(245,124,0,0.08)',
 border: '1px solid #F57C00',
 borderRadius: 4 }}
 >
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8 }}>
 영향 협력사 — HS / 키워드 / 국가 매칭 (총 {suppliers.length}건)
 </div>
 {suppliers.length === 0 ? (
 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)', margin: 0 }}>
 매칭된 협력사 없음 — suppliers.db 미적재 또는 HS 코드 mismatch
 </p>
 ) : (
 <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
 {suppliers.slice(0, 10).map((s) => (
 <li
 key={s.supplier_id}
 style={{
 display: 'flex',
 alignItems: 'center',
 gap: 8,
 marginBottom: 6,
 paddingBottom: 6,
 borderBottom: '1px solid rgba(255,255,255,0.05)',
 flexWrap: 'wrap' }}
 >
 <strong style={{ fontSize: 12 }}>{s.name}</strong>
 <span className="lg-pill" style={{ fontSize: 10 }}>
 T{s.tier} · {s.country}
 </span>
 <span
 className="lg-pill"
 style={{
 fontSize: 10,
 background: s.compliance_score >= 80 ? '#388E3C' : s.compliance_score >= 60 ? '#FBC02D' : '#D32F2F',
 color: '#fff' }}
 title="컴플라이언스 점수"
 >
 {s.compliance_score}점
 </span>
 <span style={{ fontSize: 10, color: 'var(--hud-text-dim)' }}>
 {s.match_reasons.join(', ')}
 </span>
 <button
 className="lg-btn sm ghost"
 style={{ marginLeft: 'auto' }}
 onClick={() => void handleSendAssessment(s.supplier_id)}
 disabled={sending === s.supplier_id}
 >
 {sending === s.supplier_id ? '' : '자가진단 발송'}
 </button>
 </li>
 ))}
 </ul>
 )}
 {suppliers.length > 10 && (
 <p style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginTop: 4 }}>
 + {suppliers.length - 10}건 추가 (스크롤 또는 협력사 페이지)
 </p>
 )}
 </div>
 );
}


function CostSimulationPanel({ cost }: { cost: CostSimulationResponse }) {
 const chemDelta = cost.chemical_substitution.estimated_delta_pct ?? 0;
 const detected = cost.chemical_substitution.substances_detected ?? [];

 return (
 <div
 style={{
 marginTop: 10,
 padding: 10,
 background: 'rgba(211,47,47,0.08)',
 border: '1px solid #D32F2F',
 borderRadius: 4 }}
 >
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 8 }}>
 비용 영향 시뮬레이션 (관세 {cost.scenario_rate_pct}% 시나리오)
 </div>

 <div
 style={{
 display: 'grid',
 gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
 gap: 8,
 marginBottom: 12 }}
 >
 <Stat label="현재 연간 원가" value={`${cost.baseline_cost_krw_mn.toLocaleString()}백만`} />
 <Stat label="신규 원가" value={`${cost.new_cost_krw_mn.toLocaleString()}백만`} accent="#D32F2F" />
 <Stat label="추가 비용" value={`+${cost.delta_krw_mn.toLocaleString()}백만`} accent="#F57C00" />
 <Stat label="증가율" value={`+${cost.delta_pct.toFixed(1)}%`} accent="#F57C00" />
 </div>

 {cost.applicable_hs.length > 0 && (
 <div style={{ marginBottom: 8, fontSize: 11 }}>
 <span style={{ color: 'var(--hud-text-dim)' }}>적용 HS: </span>
 {cost.applicable_hs.map((hs) => (
 <span key={hs} className="lg-pill" style={{ fontSize: 10, marginRight: 4 }}>
 {hs}
 </span>
 ))}
 </div>
 )}

 {cost.by_supplier.length > 0 && (
 <div style={{ marginBottom: 8 }}>
 <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginBottom: 4 }}>
 협력사별 추가 비용 (top 5):
 </div>
 <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 11 }}>
 {cost.by_supplier.slice(0, 5).map((s) => (
 <li key={s.supplier_id} style={{ marginBottom: 2 }}>
 {s.name} ({s.country}): +{s.additional_tariff_krw_mn.toLocaleString()}백만
 <span style={{ color: 'var(--hud-text-dim)', marginLeft: 4 }}>
 / 기준 {s.baseline_krw_mn.toLocaleString()}백만
 </span>
 </li>
 ))}
 </ul>
 </div>
 )}

 {detected.length > 0 && (
 <div
 style={{
 padding: 6,
 background: 'rgba(123,31,162,0.15)',
 border: '1px solid #7B1FA2',
 fontSize: 11 }}
 >
 화학물질 대체 추정: {detected.join(', ')} → 예상 단가 +{chemDelta}% (룰베이스)
 </div>
 )}

 <p style={{ marginTop: 6, fontSize: 10, color: 'var(--hud-text-dim)' }}>
 ※ AI 자동 추정 — 정확한 견적은 협력사 자가진단 회신 후 산출.
 </p>
 </div>
 );
}


function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
 return (
 <div
 style={{
 padding: '6px 10px',
 border: '1px solid var(--hud-border, #2a2a2a)',
 borderLeft: `2px solid ${accent || 'var(--hud-text-dim)'}` }}
 >
 <div style={{ fontSize: 10, color: 'var(--hud-text-dim)' }}>{label}</div>
 <div
 style={{
 fontSize: 14,
 fontWeight: 600,
 color: accent || 'var(--hud-text)',
 marginTop: 2 }}
 >
 {value}
 </div>
 </div>
 );
}


// ─────────────────────────────────────────────────────────────
// P3 D11 — IndustryContextPanel
// ─────────────────────────────────────────────────────────────

const VERDICT_LABEL: Record<string, { ko: string; color: string }> = {
 industry_wide: { ko: '산업 전반 영향', color: '#F57C00' },
 company_specific: { ko: '우리 회사 특이', color: '#7B1FA2' },
 no_data: { ko: '데이터 미수집', color: 'var(--hud-text-dim)' } };

function IndustryContextPanel({ data }: { data: IndustryContextResponse }) {
 const meta = VERDICT_LABEL[data.verdict] ?? VERDICT_LABEL.no_data;

 return (
 <div
 style={{
 marginTop: 10,
 padding: 10,
 background: 'rgba(33,150,243,0.08)',
 border: '1px solid #1976D2',
 borderRadius: 4 }}
 >
 <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
 <span
 style={{
 background: meta.color,
 color: '#fff',
 padding: '2px 8px',
 fontSize: 11,
 fontWeight: 600 }}
 >
 {meta.ko}
 </span>
 <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
 {data.matching_filings_count}건 매칭 · 산업 평균 {data.industry_average_filings}건
 </span>
 </div>

 {!data.available ? (
 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)', margin: 0 }}>
 산업 트렌드 데이터 미수집. 관리자가 <code>POST /api/compliance/industry-trend/fetch</code> 실행 필요.
 </p>
 ) : data.by_corp.length === 0 ? (
 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)', margin: 0 }}>
 매칭된 동종업계 공시 없음 — "{meta.ko}"으로 분류
 </p>
 ) : (
 <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
 {data.by_corp.map((c) => (
 <li
 key={c.corp_code}
 style={{
 marginBottom: 6,
 paddingBottom: 6,
 borderBottom: '1px solid rgba(255,255,255,0.05)',
 fontSize: 11 }}
 >
 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
 <strong>{c.corp_name}</strong>
 <span style={{ color: 'var(--hud-text-dim)' }}>{c.count}건</span>
 </div>
 {c.sample_reports.slice(0, 2).map((r) => (
 <div key={r.rcept_no} style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginLeft: 8 }}>
 · {r.report_nm} ({r.rcept_dt})
 </div>
 ))}
 </li>
 ))}
 </ul>
 )}

 {data.change_keywords.length > 0 && (
 <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
 {data.change_keywords.map((kw) => (
 <span key={kw} className="lg-pill" style={{ fontSize: 10 }}> {kw}</span>
 ))}
 </div>
 )}
 <p style={{ marginTop: 6, fontSize: 10, color: 'var(--hud-text-dim)' }}>
 ※ DART 공시 메타 기반 추정 — 실제 영향은 임원 / 경영기획팀 검토.
 </p>
 </div>
 );
}
