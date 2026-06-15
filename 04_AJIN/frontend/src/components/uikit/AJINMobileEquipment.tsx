// AJINMobileEquipment — iPhone 모바일 설비/공정 AI 화면.
// 디자인 시스템: aj-screen / aj-bg-grad / aj-glass / aj-grid-2 / aj-divlist / aj-kpi.
//
// 2026-05-28 사용자 모바일 피드백:
//   "설비 기능 탭에서도 볼수만 있지 아무 기능도 없이 만들 수 있는지 이해가 안 된다."
//   "웹에서 가능한 기능은 전부 모바일에서도 할 수 있어야 실리 경진대회 취지에 맞다."
//
// 해결: 4 카드 (MANUAL/INSPECTION/PREDICTIVE/SPC) accordion + 실제 기능.
// 데스크탑 8 sub-tab 풀 진입은 FAB.

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Cpu,
  FileSearch,
  RefreshCw,
  Search as SearchIcon,
  TrendingUp,
} from 'lucide-react';

import { useEquipmentRTDB } from '@hooks/useEquipmentRTDB';
import {
  fetchChecklist,
  fetchMTBF,
  fetchSPCViolationsRecent,
  searchError,
} from '@api/equipment';
import type {
  ChecklistItem,
  ErrorSearchResult,
  MTBFItem,
  RecentViolation,
} from '@/types/equipment';

const EQUIPMENT_TOTAL = 97;

type CardId = 'manual' | 'inspection' | 'predictive' | 'spc';

const CARDS: { id: CardId; Icon: typeof FileSearch; ko: string; en: string; sub: string }[] = [
  { id: 'manual',     Icon: FileSearch,    ko: '매뉴얼 / 에러 검색', en: 'MANUAL · ERROR',  sub: '7장비 × 증상 RAG' },
  { id: 'inspection', Icon: ClipboardList, ko: '점검 이력',          en: 'INSPECTION',      sub: '오늘 + 주간 체크리스트' },
  { id: 'predictive', Icon: TrendingUp,    ko: '예측 정비',          en: 'PREDICTIVE',      sub: 'MTBF · 베어링 수명' },
  { id: 'spc',        Icon: Cpu,           ko: 'SPC · Nelson 8',     en: 'SPC',             sub: '실시간 공정 제어' },
];

export function AJINMobileEquipment() {
  const navigate = useNavigate();
  const violations = useEquipmentRTDB();
  const ok = Math.max(0, EQUIPMENT_TOTAL - violations.length);
  const alarms = violations.length;

  const [open, setOpen] = useState<CardId | null>(null);

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div
          className="aj-scroll"
          style={{
            paddingTop: 18,
            paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 140px)',
            position: 'relative',
            zIndex: 3,
            minHeight: '100vh',
          }}
        >
          {/* Header */}
          <div style={{ padding: '12px 20px 4px' }}>
            <div className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)' }}>
              EQUIPMENT · F
            </div>
            <h1 style={{ margin: '6px 0 4px', fontSize: 28, fontWeight: 700, letterSpacing: '-0.018em' }}>
              설비 AI
            </h1>
            <div style={{ fontSize: 13, opacity: 0.65 }}>
              7장비 · 실시간 SPC · 매뉴얼 RAG · 점검 이력
            </div>
          </div>

          {/* KPI 2-col — minHeight 통일 */}
          <div className="aj-grid-2" style={{ paddingTop: 12, alignItems: 'stretch' }}>
            <div className="aj-glass aj-kpi" style={{ minHeight: 124, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div className="k">EQUIPMENT OK</div>
              <div className="v">{ok}<i>/{EQUIPMENT_TOTAL}</i></div>
              <div className={'delta ' + (alarms > 0 ? 'down' : 'up')}>
                {alarms > 0 ? `${alarms} alerts` : 'all clear'}
              </div>
            </div>
            <div className="aj-glass aj-kpi" style={{ minHeight: 124, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div className="k">SPC 알람</div>
              <div className="v">{alarms}</div>
              <div className={'delta ' + (alarms > 0 ? 'down' : '')}>
                {alarms > 0 ? '즉시 조치' : '정상'}
              </div>
            </div>
          </div>

          {/* SPC 알람 toast (있을 때) */}
          {alarms > 0 && (
            <div style={{ padding: '12px 12px 0' }}>
              <div className="aj-glass aj-toast">
                <div className="icn"><AlertTriangle size={16} aria-hidden /></div>
                <div style={{ minWidth: 0 }}>
                  <div className="ttl">{violations[0]?.message || 'SPC 위반 감지'}</div>
                  <div className="sub">{violations[0]?.process_name || '확인 필요'}</div>
                </div>
              </div>
            </div>
          )}

          {/* Accordion cards */}
          <div className="aj-sect-h">
            <h3>빠른 작업 · Quick</h3>
            <span className="more">탭하여 펼치기</span>
          </div>
          <div style={{ padding: '0 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {CARDS.map(({ id, Icon, ko, en, sub }) => {
              const isOpen = open === id;
              return (
                <div key={id} className="aj-glass" style={{ borderRadius: 14, overflow: 'hidden' }}>
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : id)}
                    aria-expanded={isOpen}
                    style={{
                      width: '100%',
                      display: 'grid',
                      gridTemplateColumns: '44px 1fr auto',
                      gap: 10,
                      padding: '12px 14px',
                      background: 'transparent',
                      border: 0,
                      cursor: 'pointer',
                      color: 'inherit',
                      fontFamily: 'inherit',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(252,177,50,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--aj-gold, #FCB132)' }}>
                      <Icon size={18} aria-hidden />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{ko}</div>
                      <div className="aj-mono" style={{ fontSize: 10, opacity: 0.55, marginTop: 2 }}>{en} · {sub}</div>
                    </div>
                    {isOpen ? <ChevronUp size={16} aria-hidden /> : <ChevronDown size={16} aria-hidden />}
                  </button>
                  {isOpen && (
                    <div style={{ borderTop: '1px solid rgba(127,127,127,0.18)', padding: '12px 14px' }}>
                      {id === 'manual' && <ManualErrorPanel />}
                      {id === 'inspection' && <InspectionPanel />}
                      {id === 'predictive' && <PredictivePanel />}
                      {id === 'spc' && <SPCPanel />}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* 최근 알람 list */}
          {alarms > 0 && (
            <>
              <div className="aj-sect-h">
                <h3>최근 알람 · Recent</h3>
                <span className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)', fontSize: 10 }}>LIVE</span>
              </div>
              <div className="aj-glass aj-divlist" style={{ margin: '0 12px 14px' }}>
                {violations.slice(0, 4).map((v, i) => {
                  const ts = v.timestamp
                    ? new Date(v.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
                    : '—';
                  return (
                    <div
                      key={String(v.id ?? i)}
                      style={{ display: 'grid', gridTemplateColumns: '52px 1fr auto', gap: 10, padding: '12px 14px', alignItems: 'center' }}
                    >
                      <div className="aj-mono" style={{ fontSize: 11, opacity: 0.6 }}>{ts}</div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 500 }}>{v.message}</div>
                        <div style={{ fontSize: 11, opacity: 0.55, marginTop: 1 }}>{v.process_name}</div>
                      </div>
                      <span className="aj-status crit">{String(v.severity || 'warning').toUpperCase()}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* FAB → desktop full view */}
        <button
          type="button"
          onClick={() => navigate('/equipment')}
          aria-label="데스크탑 전체 보기 (8 탭)"
          title="데스크탑 전체 보기"
          style={{
            position: 'fixed',
            right: 16,
            bottom: 'calc(env(safe-area-inset-bottom, 0px) + 80px)',
            width: 52, height: 52, borderRadius: 999,
            background: 'var(--aj-gold, #FCB132)',
            color: '#1A1004', border: 0, cursor: 'pointer',
            boxShadow: '0 12px 28px -10px rgba(252,177,50,0.55)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 20,
          }}
        >
          <Cpu size={20} aria-hidden />
        </button>
      </div>
    </div>
  );
}

// ─── Manual · Error 검색 ────────────────────────────────────────────────
function ManualErrorPanel() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ErrorSearchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSearch = async () => {
    if (!query.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await searchError({ query, top_k: 5 });
      setResults(res.results || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') onSearch(); }}
          placeholder="에러코드 또는 증상 (예: E102 또는 프레스 끼임)"
          style={{
            flex: 1, minWidth: 0, padding: '10px 12px', borderRadius: 10,
            border: '1px solid rgba(127,127,127,0.25)',
            background: 'rgba(127,127,127,0.06)',
            color: 'inherit', fontFamily: 'inherit', fontSize: 14, outline: 0,
          }}
        />
        <button
          type="button"
          onClick={onSearch}
          disabled={!query.trim() || busy}
          aria-label="검색"
          style={{
            width: 44, height: 44, borderRadius: 10,
            background: query.trim() ? 'var(--aj-gold, #FCB132)' : 'rgba(127,127,127,0.18)',
            color: query.trim() ? '#1A1004' : 'inherit',
            border: 0, cursor: query.trim() && !busy ? 'pointer' : 'not-allowed',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          {busy ? <RefreshCw size={16} /> : <SearchIcon size={16} />}
        </button>
      </div>
      {err && <div style={{ marginTop: 8, fontSize: 12, color: '#FF7565' }}>{err}</div>}
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {results.length === 0 && !busy && (
          <div style={{ fontSize: 12, opacity: 0.55, padding: '6px 0' }}>
            검색어를 입력하고 enter — TF-IDF + 의미 매칭 (동의어 79)
          </div>
        )}
        {results.map((r, i) => (
          <div
            key={String(r.code || i)}
            style={{
              padding: 10, borderRadius: 10,
              background: 'rgba(127,127,127,0.06)',
              border: '1px solid rgba(127,127,127,0.15)',
              fontSize: 13,
            }}
          >
            <div style={{ fontWeight: 600 }}>{r.code} · {r.description}</div>
            <div style={{ marginTop: 4, opacity: 0.7, fontSize: 11 }}>
              {r.equipment_type} · {r.category}
            </div>
            <div style={{ marginTop: 4, opacity: 0.8, fontSize: 12 }}>{r.cause}</div>
            <div style={{ marginTop: 4, opacity: 0.65, fontSize: 11 }}>조치: {r.action}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Inspection 체크리스트 ──────────────────────────────────────────────
function InspectionPanel() {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetchChecklist('press');
        const firstTemplate = res.templates?.[0];
        if (alive) setItems(firstTemplate?.items ?? []);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const total = items.length;
  const done = Object.values(checked).filter(Boolean).length;

  return (
    <div>
      <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>
        오늘 점검 · 프레스 라인 — 진행 {done}/{total}
      </div>
      {loading && (
        <div style={{ fontSize: 12, opacity: 0.55, padding: '8px 0' }}>
          <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} /> 불러오는 중…
        </div>
      )}
      {err && <div style={{ fontSize: 12, color: '#FF7565' }}>{err}</div>}
      {!loading && items.length === 0 && (
        <div style={{ fontSize: 12, opacity: 0.55, padding: '8px 0' }}>등록된 체크리스트 없음</div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.slice(0, 6).map((it, i) => {
          const key = String(i);
          const isChecked = !!checked[key];
          return (
            <label
              key={key}
              style={{
                display: 'grid', gridTemplateColumns: '24px 1fr', gap: 10,
                padding: 8, borderRadius: 8,
                background: isChecked ? 'rgba(79,183,116,0.10)' : 'rgba(127,127,127,0.05)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={(e) => setChecked((p) => ({ ...p, [key]: e.target.checked }))}
                style={{ width: 18, height: 18 }}
              />
              <div>
                <div style={{ fontSize: 13, textDecoration: isChecked ? 'line-through' : 'none', opacity: isChecked ? 0.65 : 1 }}>
                  {it.item}
                </div>
                {it.standard && (
                  <div style={{ fontSize: 11, opacity: 0.55 }}>기준: {it.standard}{it.unit ? ` ${it.unit}` : ''}</div>
                )}
              </div>
            </label>
          );
        })}
      </div>
      {items.length > 6 && (
        <div style={{ marginTop: 6, fontSize: 11, opacity: 0.55, textAlign: 'center' }}>
          + {items.length - 6} 더 (데스크탑에서 전체)
        </div>
      )}
    </div>
  );
}

// ─── Predictive (MTBF) ──────────────────────────────────────────────────
function PredictivePanel() {
  const [items, setItems] = useState<MTBFItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetchMTBF();
        if (alive) setItems(res.items ?? []);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const top5 = items.slice(0, 5);

  return (
    <div>
      <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>
        장비별 MTBF (평균 고장 간격) · top 5
      </div>
      {loading && (
        <div style={{ fontSize: 12, opacity: 0.55 }}>
          <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} /> 불러오는 중…
        </div>
      )}
      {err && <div style={{ fontSize: 12, color: '#FF7565' }}>{err}</div>}
      {!loading && top5.length === 0 && (
        <div style={{ fontSize: 12, opacity: 0.55 }}>표시할 데이터가 없습니다.</div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {top5.map((it) => (
          <div
            key={it.machine_id}
            style={{
              display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 10,
              padding: '8px 10px', borderRadius: 8,
              background: 'rgba(127,127,127,0.06)',
              fontSize: 13, alignItems: 'center',
            }}
          >
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.machine_name}</span>
            <span className="aj-mono" style={{ fontSize: 11, opacity: 0.7 }}>
              {Math.round(it.mtbf_days)}d
            </span>
            <span style={{ fontSize: 11, opacity: 0.55 }}>수리 {it.total_repairs}회</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SPC · Nelson 8 위반 list ───────────────────────────────────────────
function SPCPanel() {
  const [items, setItems] = useState<RecentViolation[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetchSPCViolationsRecent(0, 5);
        if (alive) setItems(res.items ?? []);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  return (
    <div>
      <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>
        최근 Nelson Rule 위반 · top 5
      </div>
      {loading && (
        <div style={{ fontSize: 12, opacity: 0.55 }}>
          <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} /> 불러오는 중…
        </div>
      )}
      {err && <div style={{ fontSize: 12, color: '#FF7565' }}>{err}</div>}
      {!loading && items.length === 0 && (
        <div style={{ fontSize: 12, opacity: 0.55 }}>최근 위반 없음 — all clear</div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((v) => {
          const ts = v.timestamp
            ? new Date(v.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
            : '—';
          return (
            <div
              key={v.id}
              style={{
                display: 'grid', gridTemplateColumns: '48px 1fr auto', gap: 8,
                padding: 8, borderRadius: 8,
                background: 'rgba(127,127,127,0.06)',
                fontSize: 13, alignItems: 'center',
              }}
            >
              <span className="aj-mono" style={{ fontSize: 11, opacity: 0.65 }}>{ts}</span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  R{v.rule_number} · {v.message}
                </div>
                <div style={{ fontSize: 11, opacity: 0.55 }}>{v.process_id} · {v.process_name}</div>
              </div>
              <span className={'aj-status ' + (String(v.severity || 'medium').toLowerCase() === 'critical' ? 'crit' : 'warn')}>
                {String(v.severity || 'medium').toUpperCase()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AJINMobileEquipment;
