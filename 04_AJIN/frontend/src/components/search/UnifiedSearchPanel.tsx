// UnifiedSearchPanel — Module A · 통합 검색.
// W2 산출물: 단일 검색 바 → 사람 / 문서 / SOP 3개 섹션으로 자동 분할.
//   - 백엔드 /employee/search, /search/documents, /sop/list 를 병렬 호출(클라이언트 fan-out)
//   - 클라이언트 휴리스틱으로 의도 배지 표시 (PEOPLE / DOCUMENT / SOP / MIXED)
//   - 각 섹션 상위 5개만 노출하고 "더 보기 →" 로 해당 탭/페이지로 점프
//
// 백엔드 신규 라우트 없이 동작 — 단일 입력으로 4개 자료원이 한 화면에 모인다.

import { useEffect, useMemo, useState } from 'react';
import { Search as SearchIcon, ArrowRight, User2, FileText, BookOpen } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { searchEmployees, type BackendEmployee } from '@api/employee';
import {
  searchDocuments,
  buildSnippet,
  extractTokens,
  type DocSearchResultItem,
} from '@api/search';
import { fetchSopList, type SopSummary } from '@api/sop';
import { useToast } from '@store/toast';
import { pushRecentQuery } from '@lib/searchHistory';

type Intent = 'people' | 'document' | 'sop' | 'mixed';

const PEOPLE_KEYWORDS = ['팀장', '대리', '과장', '차장', '부장', '사원', '주임', '이사', '님', '본부'];
const DOCUMENT_KEYWORDS = ['8D', 'ECN', 'PPAP', '회의록', '이메일', 'REACH', 'SVHC', '보고서', '변경'];
const SOP_KEYWORDS = ['SOP', '절차', '규정', '가이드', '매뉴얼'];

function detectIntent(query: string): Intent {
  const q = query.toLowerCase();
  const peopleHit = PEOPLE_KEYWORDS.some((k) => q.includes(k.toLowerCase()));
  const docHit = DOCUMENT_KEYWORDS.some((k) => q.includes(k.toLowerCase()));
  const sopHit = SOP_KEYWORDS.some((k) => q.includes(k.toLowerCase()));
  const namePattern = /^[가-힣]{2,4}\s*(팀장|대리|과장|차장|부장|사원|이사|주임|님)?$/.test(query.trim());
  if (namePattern) return 'people';
  const flags = [peopleHit, docHit, sopHit].filter(Boolean).length;
  if (flags > 1) return 'mixed';
  if (peopleHit) return 'people';
  if (docHit) return 'document';
  if (sopHit) return 'sop';
  return 'mixed';
}

const INTENT_LABEL: Record<Intent, string> = {
  people: '인사 의도',
  document: '문서 의도',
  sop: 'SOP / 절차 의도',
  mixed: '복합 의도',
};

interface ResultBundle {
  query: string;
  intent: Intent;
  people: BackendEmployee[];
  documents: DocSearchResultItem[];
  sop: SopSummary[];
}

interface PanelProps {
  onSwitchTab: (tab: 'people' | 'documents') => void;
  /** W4 — 부모에서 제공한 초기 쿼리 (HistoryFavoritesPanel 의 onPickQuery 와 연결). */
  initialQuery?: string;
  /** 초기 쿼리가 주입될 때마다 변경되는 nonce — 같은 쿼리라도 다시 실행 트리거. */
  triggerNonce?: number;
}

export function UnifiedSearchPanel({ onSwitchTab, initialQuery, triggerNonce }: PanelProps) {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [query, setQuery] = useState(initialQuery ?? '');
  const [busy, setBusy] = useState(false);
  const [bundle, setBundle] = useState<ResultBundle | null>(null);

  const tokens = useMemo(() => extractTokens(bundle?.query ?? ''), [bundle]);

  const runSearch = async (q: string) => {
    if (!q) return;
    setBusy(true);
    const intent = detectIntent(q);
    try {
      const [peopleResp, docResp, sopResp] = await Promise.allSettled([
        searchEmployees(q),
        searchDocuments({ query: q, k: 5 }),
        fetchSopList(),
      ]);

      const people = peopleResp.status === 'fulfilled' ? peopleResp.value.results.slice(0, 5) : [];
      const documents = docResp.status === 'fulfilled' ? docResp.value.results.slice(0, 5) : [];

      // SOP 목록은 클라이언트 측 부분 매칭 (백엔드 검색 API 없음 → 제목/카테고리 substring)
      const ql = q.toLowerCase();
      const sop =
        sopResp.status === 'fulfilled'
          ? sopResp.value.items
              .filter(
                (s) =>
                  s.title.toLowerCase().includes(ql) ||
                  s.category.toLowerCase().includes(ql) ||
                  s.department.toLowerCase().includes(ql),
              )
              .slice(0, 5)
          : [];

      setBundle({ query: q, intent, people, documents, sop });

      // W4 — 검색 이력 저장
      pushRecentQuery(q, people.length + documents.length + sop.length);

      const failed = [peopleResp, docResp, sopResp].filter((r) => r.status === 'rejected');
      if (failed.length) {
        addToast({
          type: 'warning',
          message: `${failed.length}개 자료원에서 응답 실패 — 일부 결과만 표시됩니다.`,
        });
      }
    } finally {
      setBusy(false);
    }
  };

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const q = query.trim();
    if (!q) {
      addToast({ type: 'warning', message: '검색어를 입력하세요.' });
      return;
    }
    await runSearch(q);
  };

  // W4 — 부모가 initialQuery 를 갱신하면 폼에 채우고 즉시 실행
  useEffect(() => {
    if (!initialQuery) return;
    setQuery(initialQuery);
    runSearch(initialQuery.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery, triggerNonce]);

  return (
    <>
      {/* SEARCH BAR */}
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">UNIFIED SEARCH · 통합 검색</div>
            <h2 className="lg-h2">한 번 입력 → 사람 / 문서 / SOP 자동 분할</h2>
          </div>
          <span className="lg-pill">FAN-OUT · 3 SOURCES</span>
        </div>

        <form onSubmit={handleSearch}>
          <div className="lg-field grow">
            <label>검색어 (이름 · 부서 · 8D · ECN · REACH · SOP …)</label>
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
                  placeholder='예: "품질팀 김 대리", "8D 누락 부품", "MSDS 절차"...'
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
            </div>
          </div>
        </form>

        {bundle && (
          <div
            style={{
              marginTop: 12,
              paddingTop: 12,
              borderTop: '1px dashed var(--hud-border, #2A2520)',
              display: 'flex',
              gap: 12,
              fontSize: 12,
              color: 'var(--hud-text-dim)',
            }}
          >
            <span>
              의도 추정: <b style={{ color: 'var(--hud-primary)' }}>{INTENT_LABEL[bundle.intent]}</b>
            </span>
            <span>
              결과: 인사 {bundle.people.length} · 문서 {bundle.documents.length} · SOP {bundle.sop.length}
            </span>
          </div>
        )}
      </section>

      {/* RESULTS — 3 SECTIONS */}
      {bundle && (
        <>
          {/* PEOPLE SECTION */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div
                  className="lg-eyebrow"
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <User2 size={12} strokeWidth={2} /> PEOPLE · 인사
                </div>
                <h2 className="lg-h2">{bundle.people.length}명</h2>
              </div>
              {bundle.people.length > 0 && (
                <button
                  className="lg-btn ghost sm"
                  onClick={() => onSwitchTab('people')}
                  type="button"
                >
                  인사 탭으로 <ArrowRight size={12} strokeWidth={2} />
                </button>
              )}
            </div>
            {bundle.people.length === 0 ? (
              <div className="dim" style={{ padding: 12, fontSize: 12 }}>
                매칭된 사원이 없습니다.
              </div>
            ) : (
              <div className="lg-table-wrap">
                <table className="lg-table">
                  <thead>
                    <tr>
                      <th>이름</th>
                      <th>본부 / 팀</th>
                      <th>직급</th>
                      <th>이메일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bundle.people.map((p, i) => (
                      <tr key={`${p.name}-${i}`}>
                        <td>
                          <span className="lg-name">{p.name}</span>
                        </td>
                        <td>
                          <div className="lg-deptcol">
                            <span className="hq-tag">{(p.division || '').replace('본부', '')}</span>
                            <span className="team-tag">{p.department}</span>
                          </div>
                        </td>
                        <td>
                          <span className="lg-pos">{p.position}</span>
                        </td>
                        <td className="lg-email">
                          {p.email ? <a href={`mailto:${p.email}`}>{p.email}</a> : <span className="dim">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* DOCUMENTS SECTION */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div
                  className="lg-eyebrow"
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <FileText size={12} strokeWidth={2} /> DOCUMENTS · 문서
                </div>
                <h2 className="lg-h2">{bundle.documents.length}건</h2>
              </div>
              {bundle.documents.length > 0 && (
                <button
                  className="lg-btn ghost sm"
                  onClick={() => onSwitchTab('documents')}
                  type="button"
                >
                  문서 탭으로 <ArrowRight size={12} strokeWidth={2} />
                </button>
              )}
            </div>
            {bundle.documents.length === 0 ? (
              <div className="dim" style={{ padding: 12, fontSize: 12 }}>
                매칭된 문서가 없습니다.
              </div>
            ) : (
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {bundle.documents.map((d) => (
                  <li
                    key={d.doc_id}
                    style={{
                      padding: '12px 14px',
                      border:
                        '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
                      borderRadius: 12,
                      background:
                        'color-mix(in oklab, var(--hud-surface) 40%, transparent)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ fontWeight: 600 }}>{d.title || '(제목 없음)'}</span>
                      <span className="mono dim" style={{ fontSize: 11 }}>
                        {d.doc_type} · rrf {d.score.toFixed(2)}
                      </span>
                    </div>
                    <div className="dim" style={{ marginTop: 4, fontSize: 12 }}>
                      {buildSnippet(d.content || '', tokens, 70)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* SOP SECTION */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div
                  className="lg-eyebrow"
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <BookOpen size={12} strokeWidth={2} /> SOP · 표준 작업 절차
                </div>
                <h2 className="lg-h2">{bundle.sop.length}건</h2>
              </div>
              {bundle.sop.length > 0 && (
                <button
                  className="lg-btn ghost sm"
                  onClick={() => navigate('/chat')}
                  type="button"
                  title="챗봇 페이지에서 SOP 전체 탐색"
                >
                  챗봇 SOP 탐색 <ArrowRight size={12} strokeWidth={2} />
                </button>
              )}
            </div>
            {bundle.sop.length === 0 ? (
              <div className="dim" style={{ padding: 12, fontSize: 12 }}>
                매칭된 SOP가 없습니다.
              </div>
            ) : (
              <ul
                style={{
                  listStyle: 'none',
                  margin: 0,
                  padding: 0,
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                  gap: 8,
                }}
              >
                {bundle.sop.map((s) => (
                  <li
                    key={s.sop_id}
                    style={{
                      padding: '12px 14px',
                      border:
                        '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
                      borderRadius: 12,
                      background:
                        'color-mix(in oklab, var(--hud-surface) 40%, transparent)',
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{s.title}</div>
                    <div className="dim" style={{ marginTop: 4, fontSize: 11 }}>
                      {s.department} · {s.category} · {s.steps_count} steps
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      {!bundle && !busy && (
        <section className="lg-card">
          <div className="dim" style={{ padding: 20, fontSize: 13, lineHeight: 1.7 }}>
            통합 검색은 한 번 입력으로 <b>사람·문서·SOP</b> 3개 자료원을 동시에 조회합니다.
            <br />
            예시: <code>품질팀 김 대리</code> · <code>8D 누락 부품</code> · <code>MSDS 절차</code>
          </div>
        </section>
      )}
    </>
  );
}
