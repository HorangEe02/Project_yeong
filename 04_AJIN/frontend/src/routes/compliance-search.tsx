// G1-F6: 법규 검색 결과 전용 페이지.
// URL: /compliance/search?q=...&index=all|regulations|scenarios|glossary&page=1
//
//   - SearchBar 의 8건 드롭다운 초과 시 진입
//   - 인덱스별 필터 + 페이지네이션 (20건/페이지)
//   - 결과 클릭 → /compliance/reg/:id (regulations) / scenarios 모달 / glossary tooltip

import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  searchCompliance,
  type ComplianceSearchHit,
  type ComplianceSearchIndex,
} from '@api/compliance';

const PAGE_SIZE = 20;
const INDEX_FILTERS: { key: ComplianceSearchIndex; label: string; en: string }[] = [
  { key: 'all', label: '전체', en: 'ALL' },
  { key: 'regulations', label: '법령', en: 'REGULATIONS' },
  { key: 'scenarios', label: '시나리오', en: 'SCENARIOS' },
  { key: 'glossary', label: '용어', en: 'GLOSSARY' },
];

export function ComplianceSearchResults() {
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();

  const q = params.get('q') ?? '';
  const indexFilter = (params.get('index') as ComplianceSearchIndex) || 'all';
  const page = Math.max(1, Number(params.get('page')) || 1);

  const [qInput, setQInput] = useState(q);
  const [hits, setHits] = useState<ComplianceSearchHit[]>([]);
  const [total, setTotal] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [available, setAvailable] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 입력값과 URL q 동기화
  useEffect(() => {
    setQInput(q);
  }, [q]);

  // 검색 실행
  useEffect(() => {
    if (!q.trim()) {
      setHits([]);
      setTotal(0);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    searchCompliance({
      q,
      index: indexFilter,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })
      .then((r) => {
        if (cancelled) return;
        setHits(r.hits);
        setTotal(r.total);
        setElapsed(r.elapsed_ms);
        setAvailable(r.available);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : '검색 실패');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [q, indexFilter, page]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const updateParams = (next: Record<string, string | number | null>) => {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v === null || v === '' || v === undefined) merged.delete(k);
      else merged.set(k, String(v));
    }
    setParams(merged);
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateParams({ q: qInput.trim(), page: 1 });
  };

  const onSelect = (hit: ComplianceSearchHit) => {
    if (hit.index === 'regulations') {
      nav(`/compliance/reg/${encodeURIComponent(hit.id)}`);
    } else if (hit.index === 'scenarios') {
      // 시나리오는 메인 페이지의 모달이 담당 — 메인 페이지로 navigate + state
      nav('/compliance', { state: { openScenarioId: hit.id } });
    } else {
      const def = (hit.payload as { definition?: string })?.definition;
      if (def) alert(`${hit.title}\n\n${def}`);
    }
  };

  // 인덱스별 카운트는 현재 백엔드 응답 안에 없어 표시 생략 (필요 시 GET /search/health
  // 의 counts 와 결합해 추후 추가 가능)

  return (
    <div className="page lg-page" data-screen-label="D · Search Results">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">SEARCH RESULTS · MODULE D</div>
        <h1 className="lg-display">법규 검색 결과</h1>
        <p className="lg-sub">
          쿼리:{' '}
          <strong>{q || <em>(비어 있음)</em>}</strong>
          {q && (
            <>
              {' · '}
              <span className="dim">
                {total.toLocaleString()}건 매칭 · {elapsed}ms
              </span>
            </>
          )}
        </p>

        <form className="lg-results-search" onSubmit={onSubmit}>
          <input
            className="lg-search-input"
            type="search"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="키워드 입력 후 Enter"
            aria-label="검색어"
          />
          <button type="submit" className="lg-btn">
            검색
          </button>
        </form>

        <div className="lg-tabs">
          {INDEX_FILTERS.map((f) => (
            <button
              key={f.key}
              className={'lg-tab' + (indexFilter === f.key ? ' on' : '')}
              onClick={() => updateParams({ index: f.key, page: 1 })}
            >
              <span className="en">{f.en}</span>
              <span className="ko">{f.label}</span>
            </button>
          ))}
        </div>
      </section>

      {!available && (
        <p className="lg-error">
          ⚠ 검색 서버를 사용할 수 없습니다. 잠시 후 다시 시도하세요.
        </p>
      )}
      {error && <p className="lg-error">⚠ {error}</p>}

      {loading && <div className="lg-empty">검색 중…</div>}

      {!loading && !error && available && q.trim() && hits.length === 0 && (
        <div className="lg-empty">결과가 없습니다.</div>
      )}

      {!loading && hits.length > 0 && (
        <ol className="lg-results-list">
          {hits.map((h) => (
            <li
              key={`${h.index}:${h.id}`}
              className="lg-results-item"
              onClick={() => onSelect(h)}
            >
              <div className="lg-results-row">
                <span className={`lg-search-tag tag-${h.index}`}>
                  {labelOf(h.index)}
                </span>
                <h4
                  className="lg-results-title"
                  dangerouslySetInnerHTML={{ __html: h.title }}
                />
              </div>
              {h.snippet && (
                <p
                  className="lg-results-snippet"
                  dangerouslySetInnerHTML={{ __html: h.snippet }}
                />
              )}
              <div className="lg-results-meta dim">
                <span className="mono">id: {h.id}</span>
                {h.index === 'regulations' && (
                  <Link
                    to={`/compliance/reg/${encodeURIComponent(h.id)}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    상세 →
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}

      {totalPages > 1 && (
        <nav className="lg-pagination" aria-label="페이지네이션">
          <button
            className="lg-btn"
            onClick={() => updateParams({ page: Math.max(1, page - 1) })}
            disabled={page <= 1}
          >
            ← 이전
          </button>
          <span className="dim mono">
            {page} / {totalPages}
          </span>
          <button
            className="lg-btn"
            onClick={() => updateParams({ page: Math.min(totalPages, page + 1) })}
            disabled={page >= totalPages}
          >
            다음 →
          </button>
        </nav>
      )}
    </div>
  );
}

function labelOf(idx: ComplianceSearchHit['index']): string {
  return idx === 'regulations' ? '법령' : idx === 'scenarios' ? '시나리오' : '용어';
}

export default ComplianceSearchResults;
