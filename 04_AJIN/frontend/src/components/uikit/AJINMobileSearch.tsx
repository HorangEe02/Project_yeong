// AJINMobileSearch — iPhone 모바일 검색 화면, reference MobSearch 패턴 유지.
//
// reference: uiux/AJIN AI Assistant Design System/ui_kits/mobile/MobScreens.jsx::MobSearch (L214-301)
//
// 구조:
//   .aj-mobile > .aj-screen.dark > .aj-bg-grad.dark
//   ├─ .aj-title (sub: SEARCH · HYBRID BM25+VEC + h1: 검색)
//   ├─ .aj-glass.aj-search (검색 바 + mic — Phase 2 에서 voice 구현)
//   ├─ filter chips (All / SOP / ECN / Quality / HR — 클릭 시 결과 즉시 갱신)
//   └─ .aj-stack 결과 list (로딩/에러/빈 결과 / DocSearchResultItem 카드)
//
// 2026-05-28 Phase 1 (PR #A1) — 데이터 fetch 실작동 + UI 스크롤 fix
//  - 이전 RESULTS 하드코딩 3개 제거 → POST /search/documents 실호출
//  - q / filter 변경 시 250ms debounce 후 자동 검색 (navigate 안 함)
//  - URL ?q=&filter= 와 state 양방향 동기화 (useSearchParams)
//  - minHeight 100vh 3중 (외부/aj-screen/aj-scroll) 제거 → flex/100% 패턴
//    (chat PR #49 와 동일 — Shell <main> 의 padding-bottom 으로 BottomTabBar 자리 처리)
//  - loading / error / empty / 결과 list 4-state UI
//  - pushRecentQuery() 로 검색 analytics
//  - 카드 클릭 시 /chat?prefill={query} 로 임시 라우팅 (Phase 4 에서 bottom-sheet detail 로 교체)

import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, Download, MessageSquare, Mic, Search } from 'lucide-react';

import { useAuthStore } from '@store/auth';
import {
  buildSnippet,
  extractTokens,
  searchDocuments,
  type DocSearchResultItem,
} from '@api/search';
import { pushRecentQuery } from '@lib/searchHistory';
import { searchEmployees, type BackendEmployee } from '@api/employee';

// 결과 카드 → markdown 직렬화 후 .md 다운로드.
// Phase 4 bottom-sheet 에서 DownloadActions 전체 (pdf/hwp/docx 등) 옵션 노출 예정.
function downloadResultAsMarkdown(r: DocSearchResultItem) {
  const lines = [
    `# ${r.title || r.doc_id}`,
    '',
    `- 문서 ID: \`${r.doc_id}\``,
    `- 종류: ${r.doc_type}`,
    ...(r.part_name ? [`- 부품/대상: ${r.part_name}`] : []),
    `- 점수: ${(r.score * 100).toFixed(1)} / 100`,
    '',
    '## 내용',
    '',
    r.content,
    '',
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${r.doc_id}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

// reference L233-238 filter chips
const FILTER_CHIPS = [
  { id: 'all', ko: 'All · 전체', gold: true,  dot: true,  filter: null },
  { id: 'sop', ko: 'SOP',        gold: false, dot: false, filter: 'sop' },
  { id: 'ecn', ko: 'ECN',        gold: false, dot: false, filter: 'ecn' },
  { id: 'qm',  ko: 'Quality',    gold: false, dot: false, filter: 'qm' },
  { id: 'hr',  ko: 'HR',         gold: false, dot: false, filter: 'hr' },
] as const;

// 모바일 chip → 백엔드 doc_type 매핑.
// 백엔드 doc_type: '8d_report' | 'ecn' | 'email' | 'meeting_note' | 'ppap'
// sop / hr 는 백엔드 미정의 → undefined (전체 검색 fallback, UI active state 만 변경).
function chipToDocType(filter: string | null): string | undefined {
  if (!filter) return undefined;
  const map: Record<string, string | undefined> = {
    ecn: 'ecn',
    qm: '8d_report',
  };
  return map[filter];
}

// doc_type 별 tier 배지 (모바일 ResultCard 의 right-side L1/L3 표시).
// ECN 등 변경 통보 / 8D 등 품질 보고서는 restricted (L3), 그 외 public.
function docTypeToTier(docType: string): 'public' | 'restricted' {
  const restricted = new Set(['ecn', '8d_report']);
  return restricted.has(docType) ? 'restricted' : 'public';
}

export function AJINMobileSearch() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [q, setQ] = useState<string>(searchParams.get('q') ?? '');
  const [activeFilter, setActiveFilter] = useState<string | null>(
    searchParams.get('filter'),
  );
  const [results, setResults] = useState<DocSearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [mode, setMode] = useState<'docs' | 'people'>('docs');
  const [people, setPeople] = useState<BackendEmployee[]>([]);

  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const userAvatar = (user?.username || '익').charAt(0);
  const debounceRef = useRef<number | null>(null);

  // URL ↔ state 양방향 sync (q / filter 변경 시 URL 갱신, replace 로 history 오염 X)
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (q.trim()) next.set('q', q.trim());
    else next.delete('q');
    if (activeFilter) next.set('filter', activeFilter);
    else next.delete('filter');
    // tab 은 데스크탑/모바일 공유 — 모바일은 documents 만 (Phase 3 에서 확장)
    if (!next.get('tab')) next.set('tab', 'documents');
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, activeFilter]);

  // 자동 검색 — q 또는 filter 변경 시 250ms debounce 후 API 호출
  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      setPeople([]);
      setHasSearched(false);
      setError(null);
      return;
    }
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      void runSearch(q.trim(), activeFilter);
    }, 250);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, activeFilter, mode]);

  async function runSearch(query: string, filter: string | null) {
    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      if (mode === 'people') {
        const resp = await searchEmployees(query);
        setPeople(resp.results ?? []);
        setResults([]);
        pushRecentQuery(query, resp.results?.length ?? 0);
      } else {
        const docType = chipToDocType(filter);
        const resp = await searchDocuments({
          query,
          doc_type_filter: docType,
          k: 8,
        });
        setResults(resp.results ?? []);
        setPeople([]);
        pushRecentQuery(query, resp.results?.length ?? 0);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setResults([]);
      setPeople([]);
    } finally {
      setLoading(false);
    }
  }

  const handleSubmit = () => {
    if (!q.trim()) return;
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    void runSearch(q.trim(), activeFilter);
  };

  const handleFilter = (filter: string | null) => {
    setActiveFilter(filter);
    // useEffect 가 URL sync + 자동 재검색 처리
  };

  // 결과 카드 → 챗봇으로 prefill (카드 default 동작)
  const handleAskChat = (r: DocSearchResultItem) => {
    const prefill = `${r.title || r.doc_id} (${r.doc_id}) 자세히 알려줘`;
    navigate(`/chat?prefill=${encodeURIComponent(prefill)}`);
  };

  // 결과 카드 → .md 다운로드 (Phase 4 에서 DownloadActions 전체 옵션 노출 예정)
  const handleDownload = (r: DocSearchResultItem) => {
    downloadResultAsMarkdown(r);
  };

  const queryTokens = extractTokens(q);

  return (
    <div className="aj-mobile" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div
        className="aj-screen dark"
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
        }}
      >
        <div className="aj-bg-grad dark" />

        <div
          className="aj-scroll"
          style={{
            paddingTop: 56,
            position: 'relative',
            zIndex: 3,
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* aj-title — mono sub + 검색 h1 + avatar */}
          <div className="aj-title" style={{ padding: '8px 16px 14px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div className="sub">SEARCH · HYBRID BM25+VEC</div>
                <h1 style={{ margin: '4px 0 0' }}>검색</h1>
              </div>
              <div
                aria-label="user avatar"
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 999,
                  background:
                    'color-mix(in oklab, var(--aj-gold, #FCB132) 22%, transparent)',
                  color: 'var(--aj-gold, #FCB132)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 14,
                  fontWeight: 700,
                }}
              >
                {userAvatar}
              </div>
            </div>
          </div>

          {/* Search bar — aj-glass aj-search */}
          <div style={{ padding: '4px 16px 12px' }}>
            <div
              className="aj-glass aj-search"
              style={{ borderRadius: 18, height: 52, padding: '0 16px' }}
            >
              <span className="icn" style={{ display: 'inline-flex' }} aria-hidden>
                <Search size={18} />
              </span>
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSubmit();
                }}
                placeholder="문서, SOP, ECN, 사람 검색"
                aria-label="검색"
              />
              {/* Mic — Phase 2 에서 voice (useSpeechToText) 구현. 현재는 submit 트리거. */}
              <button
                type="button"
                onClick={handleSubmit}
                aria-label="검색 실행"
                title="검색 실행 (Phase 2: 음성 검색 예정)"
                style={{
                  background: 'transparent',
                  border: 0,
                  cursor: 'pointer',
                  color: 'var(--aj-gold, #FCB132)',
                  display: 'inline-flex',
                  padding: 0,
                }}
              >
                <Mic size={18} aria-hidden />
              </button>
            </div>
          </div>

          {/* 검색 모드 — 문서 / 인원(사람) */}
          <div style={{ display: 'flex', gap: 6, padding: '0 16px 12px' }}>
            {([['docs', '문서'], ['people', '인원']] as const).map(([m, label]) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={'aj-chip' + (mode === m ? ' gold' : '')}
                style={{ flex: 1, border: 0, cursor: 'pointer', fontFamily: 'inherit' }}
                aria-pressed={mode === m}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Filter chips — flexWrap (모바일 폭 초과 시 HR 잘림 fix)
              2026-05-28 follow-up: padding-bottom 14 → 20 + .aj-stack 의 paddingTop 8
              추가로 result card 와 chip row 사이 명확한 분리. (이전: 결과 카드 첫 line
              이 chip row 와 시각적 겹침 문제) */}
          {mode === 'docs' && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              padding: '0 16px 20px',
              overflowX: 'auto',
              scrollbarWidth: 'none',
            }}
          >
            {FILTER_CHIPS.map((chip) => {
              const isActive =
                chip.filter === activeFilter ||
                (chip.id === 'all' && activeFilter === null);
              const className =
                'aj-chip' +
                (isActive && chip.gold ? ' gold' : '') +
                (chip.dot ? ' dot' : '');
              return (
                <button
                  key={chip.id}
                  type="button"
                  onClick={() => handleFilter(chip.filter)}
                  className={className}
                  style={{
                    border: 0,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    fontFamily: 'inherit',
                  }}
                  aria-pressed={isActive}
                >
                  {chip.ko}
                </button>
              );
            })}
          </div>
          )}

          {/* Results — 5-state (loading / error / starter / empty / list)
              paddingTop 8 추가 → chip row 와 첫 result card 시각적 분리. */}
          <div className="aj-stack" style={{ flex: 1, paddingTop: 8 }}>
            {loading && (
              <div
                style={{
                  margin: '8px 12px',
                  padding: 14,
                  textAlign: 'center',
                  fontSize: 13,
                  opacity: 0.65,
                }}
              >
                검색 중…
              </div>
            )}

            {!loading && error && (
              <div
                className="aj-glass"
                style={{
                  margin: '8px 12px',
                  padding: 14,
                  borderLeft: '2px solid #FF7565',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 13,
                }}
              >
                <AlertCircle size={16} color="#FF7565" aria-hidden />
                <div>
                  <div style={{ color: '#FF7565', fontWeight: 600 }}>검색 오류</div>
                  <div style={{ opacity: 0.7, marginTop: 2 }}>{error}</div>
                </div>
              </div>
            )}

            {!loading && !error && !hasSearched && (
              <div
                style={{
                  margin: '8px 12px',
                  padding: '24px 14px',
                  textAlign: 'center',
                  fontSize: 13,
                  opacity: 0.55,
                }}
              >
                검색어를 입력하세요.
                <br />
                <span style={{ fontSize: 11, opacity: 0.7 }}>
                  SOP / ECN / 품질 보고서 / 사내 문서 통합 검색.
                </span>
              </div>
            )}

            {!loading && !error && hasSearched && (mode === 'docs' ? results.length === 0 : people.length === 0) && (
              <div
                style={{
                  margin: '8px 12px',
                  padding: '24px 14px',
                  textAlign: 'center',
                  fontSize: 13,
                  opacity: 0.55,
                }}
              >
                검색 결과가 없습니다.
                <br />
                <span style={{ fontSize: 11, opacity: 0.7 }}>
                  다른 키워드 또는 filter 를 시도해 보세요.
                </span>
              </div>
            )}

            {!loading &&
              !error &&
              mode === 'docs' &&
              results.map((r) => {
                const snippet = buildSnippet(r.content, queryTokens, 80);
                // score 는 0~1 범위 — 100 점 환산 후 1자리 소수.
                const scoreStr = (Math.min(1, Math.max(0, r.score)) * 100).toFixed(1);
                const tier = docTypeToTier(r.doc_type);
                const meta = [r.doc_type, r.part_name].filter(Boolean).join(' · ');
                return (
                  <ResultCard
                    key={r.doc_id}
                    code={r.doc_id}
                    ko={r.title || r.doc_id}
                    en={r.doc_type}
                    meta={meta}
                    score={scoreStr}
                    snippet={snippet || r.content.slice(0, 160)}
                    tier={tier}
                    onChat={() => handleAskChat(r)}
                    onDownload={() => handleDownload(r)}
                  />
                );
              })}

            {!loading &&
              !error &&
              mode === 'people' &&
              people.map((p, i) => (
                <PersonCard
                  key={`${p.email || p.name}-${i}`}
                  p={p}
                  onChat={() =>
                    navigate(
                      `/chat?prefill=${encodeURIComponent(`${p.name} (${p.department} ${p.position}) 담당 업무/연락처 알려줘`)}`,
                    )
                  }
                />
              ))}
          </div>

          {/* Shell main 의 padding-bottom 으로 BottomTabBar 자리 처리 — 16 만 여유 */}
          <div style={{ height: 16 }} />
        </div>
      </div>
    </div>
  );
}

// ─── ResultCard (reference MobScreens.jsx::ResultCard L279-301 매핑 + footer action 추가) ───
// 2026-05-28 follow-up: button → div(role=button) 로 변경 (footer 의 nested button
// HTML invalid issue 해결). 카드 default 클릭 = onChat (챗봇 prefill), footer 의
// [다운로드] button 은 stopPropagation 으로 독립 동작.
function ResultCard({
  code,
  ko,
  en,
  meta,
  score,
  snippet,
  tier,
  onChat,
  onDownload,
}: {
  code: string;
  ko: string;
  en: string;
  meta: string;
  score: string;
  snippet: string;
  tier: 'public' | 'restricted';
  onChat?: () => void;
  onDownload?: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onChat?.()}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onChat?.();
        }
      }}
      className="aj-glass"
      style={{
        padding: 14,
        margin: '0 4px 10px',
        cursor: 'pointer',
        color: 'inherit',
        fontFamily: 'inherit',
        width: 'calc(100% - 8px)',
      }}
      aria-label={`${code}: ${ko} — 카드 클릭 시 챗봇으로 이동`}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 6,
        }}
      >
        <span className="aj-mono" style={{ fontSize: 10, color: '#FCB132' }}>
          {code}
        </span>
        <span className="aj-status ok">SCORE {score}</span>
        <span
          className="aj-status"
          style={{
            marginLeft: 'auto',
            background:
              tier === 'restricted'
                ? 'rgba(255,117,101,0.18)'
                : 'rgba(255,255,255,0.08)',
            color: tier === 'restricted' ? '#FF7565' : 'rgba(255,255,255,0.6)',
          }}
        >
          {tier === 'restricted' ? 'L3' : 'L1 PUBLIC'}
        </span>
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.01em' }}>
        {ko}
      </div>
      <div style={{ fontSize: 11, opacity: 0.5, marginTop: 1 }}>
        {en} · {meta}
      </div>
      <div
        style={{
          marginTop: 10,
          padding: '10px 12px',
          borderRadius: 12,
          background: 'rgba(252,177,50,0.06)',
          borderLeft: '2px solid #FCB132',
          fontSize: 13,
          lineHeight: 1.5,
          opacity: 0.92,
        }}
      >
        {snippet}
      </div>
      {/* Footer — 다운로드 / 챗봇 action row.
          - 다운로드: .md 자체 다운로드 (Phase 4 sheet 에서 DownloadActions 전체 옵션 노출 예정)
          - 챗봇: 카드 default 와 동일 동작 (명시 visual cue) */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          marginTop: 12,
          justifyContent: 'flex-end',
        }}
      >
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDownload?.();
          }}
          aria-label={`${code} 다운로드`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '6px 10px',
            borderRadius: 999,
            border: '1px solid var(--hud-border-light)',
            background: 'var(--hud-surface-2)',
            color: 'inherit',
            fontFamily: 'inherit',
            fontSize: 11,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <Download size={12} aria-hidden /> 다운로드
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onChat?.();
          }}
          aria-label={`${code} 챗봇으로 더 보기`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '6px 10px',
            borderRadius: 999,
            border: '1px solid rgba(252,177,50,0.50)',
            background: 'var(--hud-primary-dim)',
            color: 'var(--aj-gold, #FCB132)',
            fontFamily: 'inherit',
            fontSize: 11,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          <MessageSquare size={12} aria-hidden /> 챗봇
        </button>
      </div>
    </div>
  );
}

// ─── PersonCard — 인원(사람) 검색 결과 카드 (POST /employee/search) ───
function PersonCard({ p, onChat }: { p: BackendEmployee; onChat: () => void }) {
  const initial = (p.name || '?').charAt(0);
  const demo = p.is_synthetic === 1;
  const sub = [p.position, p.department || p.division].filter(Boolean).join(' · ');
  const tel = [p.extension ? `내선 ${p.extension}` : '', p.phone || ''].filter(Boolean).join(' · ');
  return (
    <div
      className="aj-glass"
      style={{ padding: 14, margin: '0 4px 10px', width: 'calc(100% - 8px)', display: 'flex', gap: 12, alignItems: 'flex-start' }}
    >
      <div
        aria-hidden
        style={{
          width: 40,
          height: 40,
          borderRadius: 999,
          flexShrink: 0,
          background: 'color-mix(in oklab, var(--aj-gold, #FCB132) 22%, transparent)',
          color: 'var(--aj-gold, #FCB132)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 15,
          fontWeight: 700,
        }}
      >
        {initial}
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>{p.name}</span>
          {demo && (
            <span className="aj-status" style={{ background: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.6)' }}>
              DEMO
            </span>
          )}
        </div>
        {sub && <div style={{ fontSize: 12, opacity: 0.65, marginTop: 2 }}>{sub}</div>}
        <div className="aj-mono" style={{ fontSize: 11, opacity: 0.6, marginTop: 6, lineHeight: 1.6, wordBreak: 'break-all' }}>
          {p.email && <div>✉ {p.email}</div>}
          {tel && <div>☎ {tel}</div>}
          {p.plant && <div>📍 {p.plant}</div>}
        </div>
      </div>
      <button
        type="button"
        onClick={onChat}
        aria-label={`${p.name} 챗봇으로 더 보기`}
        style={{
          flexShrink: 0,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: '6px 10px',
          borderRadius: 999,
          border: '1px solid rgba(252,177,50,0.50)',
          background: 'var(--hud-primary-dim)',
          color: 'var(--aj-gold, #FCB132)',
          fontFamily: 'inherit',
          fontSize: 11,
          fontWeight: 700,
          cursor: 'pointer',
        }}
      >
        <MessageSquare size={12} aria-hidden /> 챗봇
      </button>
    </div>
  );
}
