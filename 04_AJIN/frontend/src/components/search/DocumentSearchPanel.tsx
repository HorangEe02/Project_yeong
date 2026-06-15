// DocumentSearchPanel — Module A · 문서 검색 메인 패널.
// W1 산출물: 검색바 + 필터 + 결과 카드 + 상세 드로어.
//   - 백엔드 POST /search/documents (BM25+Vector RRF) 호출
//   - 키워드 하이라이트 + 스니펫 + 메타 표시
//   - 결과 카드 클릭 → DocumentDetailDrawer (초안/챗봇/복사 액션)

import { useMemo, useState } from 'react';
import { Search as SearchIcon, X } from 'lucide-react';
import {
  searchDocuments,
  extractTokens,
  buildSnippet,
  type DocSearchResultItem,
} from '@api/search';
import { DocumentResultCard } from './DocumentResultCard';
import { DocumentDetailDrawer } from './DocumentDetailDrawer';
import { useToast } from '@store/toast';
import { pushRecentQuery, pushViewedDoc } from '@lib/searchHistory';

type DocTypeFilter =
  | 'all'
  | '8d_report'
  | 'ecn'
  | 'email'
  | 'meeting_note'
  | 'ppap'
  | 'sop'
  | 'glossary'
  | 'department_guide'
  | 'collaboration_guide'
  | 'fmea'
  | 'control_plan'
  | 'audit_report'
  | 'inspection_report'
  | 'training_material';

// 2026-05-25: SOP/Glossary/Department/Collaboration 노출 추가 (corpus 분포 49/96/27/25 chunk).
// 2026-05-25 2차: FMEA/Control Plan/Audit/Inspection/Training 신규 양식 7건 (60 chunks).
//   Gemini 3.5 Flash 로 AJIN 컨텍스트 (EWP/B-Pillar/CCH) 적용하여 생성, IATF 16949 표준 양식.
// Backend searcher 가 lower+space 정규화하여 corpus metadata 의 "8D Report"/"SOP"/"FMEA" 등과 매칭.
const DOC_TYPE_OPTIONS: { value: DocTypeFilter; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: '8d_report', label: '8D 보고서' },
  { value: 'ecn', label: 'ECN (설계변경)' },
  { value: 'email', label: '이메일' },
  { value: 'meeting_note', label: '회의록' },
  { value: 'ppap', label: 'PPAP' },
  { value: 'sop', label: 'SOP (표준작업절차)' },
  { value: 'fmea', label: 'FMEA (고장모드분석)' },
  { value: 'control_plan', label: 'Control Plan (관리계획서)' },
  { value: 'audit_report', label: '내부 감사 보고서' },
  { value: 'inspection_report', label: '수입/공정 검사' },
  { value: 'training_material', label: '교육 자료' },
  { value: 'glossary', label: '용어집' },
  { value: 'department_guide', label: '부서 가이드' },
  { value: 'collaboration_guide', label: '협업 가이드' },
];

export function DocumentSearchPanel() {
  const { addToast } = useToast();

  const [query, setQuery] = useState('');
  const [docType, setDocType] = useState<DocTypeFilter>('all');
  const [partName, setPartName] = useState('');
  const [k, setK] = useState<number>(8);

  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<DocSearchResultItem[] | null>(null);
  const [lastQuery, setLastQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<DocSearchResultItem | null>(null);

  const tokens = useMemo(() => extractTokens(lastQuery), [lastQuery]);

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const q = query.trim();
    const hasDocTypeFilter = docType !== 'all';
    const hasPartNameFilter = partName.trim().length > 0;
    // v4.x — 검색어 + 필터 모두 비어있을 때만 reject. 둘 중 하나만 있어도 검색 진행.
    if (!q && !hasDocTypeFilter && !hasPartNameFilter) {
      addToast({
        type: 'warning',
        message: '검색어를 입력하거나 문서 유형/부품명 필터를 선택하세요.',
      });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const resp = await searchDocuments({
        query: q,  // 빈 문자열이면 백엔드가 metadata-only 모드로 동작
        k,
        doc_type_filter: hasDocTypeFilter ? docType : undefined,
        part_name_filter: hasPartNameFilter ? partName.trim() : undefined,
      });
      setResults(resp.results);
      setLastQuery(q);
      // W4 — 이력 저장 (검색어 있을 때만)
      if (q) {
        pushRecentQuery(q, resp.results.length);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '검색 중 오류가 발생했습니다.';
      setError(msg);
      setResults([]);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = () => {
    setQuery('');
    setDocType('all');
    setPartName('');
    setK(8);
    setResults(null);
    setError(null);
    setLastQuery('');
  };

  return (
    <>
      {/* SEARCH BAR */}
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">DOCUMENT SEARCH · 문서 본문 검색</div>
            <h2 className="lg-h2">사내 문서 (8D · ECN · 이메일 · 회의록 · PPAP)</h2>
          </div>
          <span className="lg-pill">BM25 + Vector RRF</span>
        </div>

        <form onSubmit={handleSearch} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="lg-field grow">
            <label>검색어</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <SearchIcon
                  size={14}
                  strokeWidth={2}
                  style={{
                    position: 'absolute',
                    left: 10,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    pointerEvents: 'none',
                    opacity: 0.6,
                  }}
                />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="예: 8D 보고서 누락 부품, ECN 변경 사유, REACH SVHC..."
                  style={{ paddingLeft: 30, width: '100%' }}
                  autoFocus
                />
              </div>
              <button
                type="submit"
                className="lg-btn"
                disabled={busy}
                aria-busy={busy}
              >
                {busy ? '검색 중…' : '검색'}
              </button>
              <button
                type="button"
                className="lg-btn ghost"
                onClick={handleReset}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <X size={14} strokeWidth={2} /> 초기화
              </button>
            </div>
          </div>

          <div className="lg-filter-grid">
            <div className="lg-field">
              <label>문서 유형</label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value as DocTypeFilter)}
              >
                {DOC_TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="lg-field">
              <label>부품명 (선택)</label>
              <input
                type="text"
                value={partName}
                onChange={(e) => setPartName(e.target.value)}
                placeholder="예: DASH COMPL, EWP..."
              />
            </div>
            <div className="lg-field">
              <label>결과 개수 (k)</label>
              <select value={k} onChange={(e) => setK(Number(e.target.value))}>
                {[5, 8, 12, 16, 20].map((n) => (
                  <option key={n} value={n}>
                    {n}건
                  </option>
                ))}
              </select>
            </div>
          </div>
        </form>
      </section>

      {/* RESULTS */}
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">RESULTS · 검색 결과</div>
            <h2 className="lg-h2">
              {results === null
                ? '검색을 시작하세요'
                : `${results.length}건${lastQuery ? ` · "${lastQuery}"` : ''}`}
            </h2>
          </div>
          {results !== null && results.length > 0 && (
            <span className="lg-pill">RRF 점수 내림차순</span>
          )}
        </div>

        {busy && (
          <div className="dim" style={{ padding: 24, textAlign: 'center' }}>
            검색 중…
          </div>
        )}

        {error && (
          <div
            style={{
              padding: 16,
              border: '1px solid color-mix(in oklab, var(--hud-red, #C0392B) 50%, transparent)',
              background: 'color-mix(in oklab, var(--hud-red, #C0392B) 8%, transparent)',
              borderRadius: 12,
              color: 'var(--hud-red, #C0392B)',
              fontSize: 13,
              letterSpacing: 0,
            }}
          >
            오류 — {error}
          </div>
        )}

        {!busy && results !== null && results.length === 0 && !error && (
          <div className="lg-empty" style={{ padding: 32, textAlign: 'center' }}>
            검색 결과가 없습니다. 키워드를 줄이거나 필터를 해제해 보세요.
          </div>
        )}

        {!busy && results !== null && results.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {results.map((r) => (
              <DocumentResultCard
                key={r.doc_id || `${r.title}-${r.score}`}
                item={r}
                query={lastQuery}
                tokens={tokens}
                snippet={buildSnippet(r.content || '', tokens, 90)}
                onSelect={(item) => {
                  setSelected(item);
                  // W4 — 최근 본 문서 기록
                  pushViewedDoc({
                    doc_id: item.doc_id,
                    title: item.title,
                    doc_type: item.doc_type,
                  });
                }}
              />
            ))}
          </div>
        )}

        {!busy && results === null && (
          <div className="dim" style={{ padding: 24, fontSize: 13, lineHeight: 1.7 }}>
            <div style={{ marginBottom: 8 }}>예시 검색어:</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              <li>"8D 보고서 누락 부품" — 8D 카테고리 우선</li>
              <li>"ECN DASH COMPL 두께 변경" — 부품명 필터 활용</li>
              <li>"REACH SVHC 등재 화학물질" — 회의록/이메일 교차 매칭</li>
            </ul>
          </div>
        )}
      </section>

      {/* DETAIL DRAWER */}
      <DocumentDetailDrawer
        doc={selected}
        isOpen={selected !== null}
        onClose={() => setSelected(null)}
        tokens={tokens}
      />
    </>
  );
}
