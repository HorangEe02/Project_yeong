// G7: 글로서리 풀 페이지.
// URL: /compliance/glossary
// - 검색 + 카테고리 필터 + 카드 목록
// - 신입 P1 학습용

import { useMemo, useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useGlossary } from '@components/compliance/GlossaryProvider';
import type { GlossaryTermData } from '@components/compliance/GlossaryProvider';

const CATEGORY_LABELS: Record<string, string> = {
  chemical: '화학물질',
  safety: '안전보건',
  iso: 'ISO 표준',
  automotive_quality: '자동차 품질',
  automotive_environmental: '자동차 환경',
  esg: 'ESG',
  trade: '무역',
  certification: '인증',
  ev: '전기차',
  ajin_product: 'AJIN 제품',
};

export function ComplianceGlossary() {
  const { list, loading, error } = useGlossary();
  const [params, setParams] = useSearchParams();
  const initialQ = params.get('q') || '';
  const [q, setQ] = useState(initialQ);
  const [cat, setCat] = useState<string>('all');

  // q 변경 시 URL 동기화
  useEffect(() => {
    if (q) params.set('q', q); else params.delete('q');
    setParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const categories = useMemo(() => {
    const s = new Set<string>();
    for (const it of list) {
      if (it.category) s.add(it.category);
    }
    return Array.from(s).sort();
  }, [list]);

  const filtered = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return list.filter((it) => {
      if (cat !== 'all' && it.category !== cat) return false;
      if (!ql) return true;
      const haystack = [
        it.term,
        it.ko,
        it.en,
        it.definition,
        ...(it.aliases ?? []),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(ql);
    });
  }, [list, q, cat]);

  return (
    <div className="page lg-page" data-screen-label="D · Glossary">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">GLOSSARY · MODULE D</div>
        <h1 className="lg-display">법규·품질 용어 사전</h1>
        <p className="lg-sub">
          REACH·CBAM·IATF·OEM 명칭 등 <strong>{list.length}</strong>개 용어.
          본문에서 마우스 hover 시 풀이가 자동 표시됩니다.
        </p>
        <div className="lg-crumb">
          <Link to="/compliance">← 법규 모니터</Link>
          {' · '}
          <Link to="/compliance/search">검색</Link>
        </div>
      </section>

      <section className="lg-card lg-prefs-section">
        <div className="lg-glossary-controls">
          <input
            type="search"
            className="lg-search-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="용어 / 한글 / 영문 / 정의 검색…"
            aria-label="용어 검색"
          />
          <select
            className="lg-select"
            value={cat}
            onChange={(e) => setCat(e.target.value)}
          >
            <option value="all">전체 카테고리</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c] || c}
              </option>
            ))}
          </select>
          <span className="dim mono small">{filtered.length} / {list.length}</span>
        </div>
      </section>

      {loading && <div className="lg-empty">로드 중…</div>}
      {error && <p className="lg-error">⚠ {error}</p>}

      {!loading && !error && (
        <ul className="lg-glossary-grid">
          {filtered.map((it) => (
            <GlossaryCard key={it.term} item={it} />
          ))}
          {filtered.length === 0 && (
            <li className="lg-empty">검색 결과가 없습니다.</li>
          )}
        </ul>
      )}
    </div>
  );
}

function GlossaryCard({ item }: { item: GlossaryTermData }) {
  return (
    <li className="lg-glossary-card lg-card">
      <div className="lg-glossary-card-head">
        <strong className="lg-glossary-card-term">{item.term}</strong>
        {item.category && (
          <span className="lg-chip">
            {CATEGORY_LABELS[item.category] || item.category}
          </span>
        )}
      </div>
      {item.ko && <p className="lg-glossary-card-ko">{item.ko}</p>}
      {item.en && (
        <p className="dim small lg-glossary-card-en">
          <span className="label-en">{item.en}</span>
        </p>
      )}
      <p className="lg-glossary-card-def">{item.definition}</p>
      {item.aliases && item.aliases.length > 0 && (
        <div className="lg-glossary-card-aliases dim small">
          별칭: {item.aliases.join(', ')}
        </div>
      )}
    </li>
  );
}

export default ComplianceGlossary;
