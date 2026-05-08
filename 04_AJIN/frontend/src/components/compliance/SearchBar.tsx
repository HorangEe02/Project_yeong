// G1 + F2: 법규 전문 검색 바.
// /api/compliance/search 호출 (Meilisearch). 200ms 디바운스.
//
// F2 키보드 네비게이션:
//   ↓        : 다음 결과로
//   ↑        : 이전 결과로
//   Home/End : 처음/끝으로
//   Enter    : 활성 항목 선택 (없으면 첫 결과)
//   Escape   : 드롭다운 닫기 + 입력 비우기 (포커스는 유지)
//
// ARIA combobox 패턴 (WAI-ARIA 1.2):
//   - input  role="combobox", aria-expanded, aria-controls, aria-activedescendant
//   - ul     role="listbox"   id="search-listbox"
//   - li     role="option"    aria-selected, id="search-hit-{idx}"

import { useEffect, useId, useRef, useState } from 'react';
import {
  searchCompliance,
  type ComplianceSearchHit,
} from '@api/compliance';

interface Props {
  onSelect?: (hit: ComplianceSearchHit) => void;
  /** "전체 결과 보기" 클릭 시 호출. 제공하지 않으면 푸터 링크 숨김. */
  onSeeAll?: (q: string) => void;
  placeholder?: string;
  limit?: number;
}

export function SearchBar({
  onSelect,
  onSeeAll,
  placeholder = '법규 / 시나리오 / 용어 검색…',
  limit = 8,
}: Props) {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<ComplianceSearchHit[]>([]);
  const [total, setTotal] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [available, setAvailable] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number>(-1);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const baseId = useId();
  const listboxId = `${baseId}-listbox`;
  const hitId = (i: number) => `${baseId}-hit-${i}`;

  // 검색 (200ms 디바운스)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setHits([]);
      setTotal(0);
      setError(null);
      setActiveIndex(-1);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await searchCompliance({ q, limit });
        setHits(r.hits);
        setTotal(r.total);
        setAvailable(r.available);
        setOpen(true);
        setActiveIndex(r.hits.length > 0 ? 0 : -1);
      } catch (e) {
        const msg = e instanceof Error ? e.message : '검색 실패';
        setError(msg);
        setHits([]);
        setOpen(true);
        setActiveIndex(-1);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [q, limit]);

  // 활성 항목 스크롤 동기화
  useEffect(() => {
    if (activeIndex < 0 || !listRef.current) return;
    const li = listRef.current.querySelector<HTMLElement>(
      `[data-idx="${activeIndex}"]`,
    );
    li?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open) {
      if (e.key === 'ArrowDown' && hits.length > 0) {
        setOpen(true);
        setActiveIndex(0);
        e.preventDefault();
      }
      return;
    }
    switch (e.key) {
      case 'ArrowDown':
        if (hits.length > 0) {
          setActiveIndex((i) => (i + 1) % hits.length);
          e.preventDefault();
        }
        break;
      case 'ArrowUp':
        if (hits.length > 0) {
          setActiveIndex((i) => (i - 1 + hits.length) % hits.length);
          e.preventDefault();
        }
        break;
      case 'Home':
        if (hits.length > 0) {
          setActiveIndex(0);
          e.preventDefault();
        }
        break;
      case 'End':
        if (hits.length > 0) {
          setActiveIndex(hits.length - 1);
          e.preventDefault();
        }
        break;
      case 'Enter': {
        const idx = activeIndex >= 0 ? activeIndex : 0;
        const hit = hits[idx];
        if (hit) {
          onSelect?.(hit);
          setOpen(false);
        }
        e.preventDefault();
        break;
      }
      case 'Escape':
        if (open) {
          setOpen(false);
          e.preventDefault();
        } else if (q) {
          setQ('');
        }
        break;
      default:
        break;
    }
  };

  return (
    <div className="lg-search">
      <input
        className="lg-search-input"
        type="search"
        role="combobox"
        aria-label="법규 검색"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={
          open && activeIndex >= 0 ? hitId(activeIndex) : undefined
        }
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        onFocus={() => hits.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && (
        <ul
          ref={listRef}
          id={listboxId}
          role="listbox"
          className="lg-search-results glass"
        >
          {loading && (
            <li className="lg-search-empty" aria-live="polite">
              검색 중…
            </li>
          )}
          {!loading && error && (
            <li className="lg-search-error" role="alert">⚠ {error}</li>
          )}
          {!loading && !error && !available && (
            <li className="lg-search-error">검색 서버를 사용할 수 없습니다.</li>
          )}
          {!loading && !error && available && hits.length === 0 && (
            <li className="lg-search-empty">결과 없음</li>
          )}
          {!loading && !error && hits.map((h, i) => (
            <li
              key={`${h.index}:${h.id}`}
              id={hitId(i)}
              role="option"
              data-idx={i}
              aria-selected={i === activeIndex}
              className={
                'lg-search-hit' + (i === activeIndex ? ' active' : '')
              }
              onMouseEnter={() => setActiveIndex(i)}
              onMouseDown={() => onSelect?.(h)}
            >
              <span className={`lg-search-tag tag-${h.index}`}>
                {labelOf(h.index)}
              </span>
              <strong
                className="lg-search-title"
                dangerouslySetInnerHTML={{ __html: h.title }}
              />
              {h.snippet && (
                <p
                  className="lg-search-snippet"
                  dangerouslySetInnerHTML={{ __html: h.snippet }}
                />
              )}
            </li>
          ))}
          {!loading && !error && hits.length > 0 && onSeeAll && total > hits.length && (
            <li className="lg-search-more">
              <button
                type="button"
                className="lg-search-more-btn"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onSeeAll(q);
                  setOpen(false);
                }}
              >
                전체 {total.toLocaleString()}건 결과 보기 →
              </button>
            </li>
          )}
          {!loading && !error && hits.length > 0 && (
            <li className="lg-search-hint" aria-hidden="true">
              <kbd>↑↓</kbd> 이동 · <kbd>Enter</kbd> 선택 · <kbd>Esc</kbd> 닫기
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function labelOf(index: ComplianceSearchHit['index']): string {
  switch (index) {
    case 'regulations':
      return '법령';
    case 'scenarios':
      return '시나리오';
    case 'glossary':
      return '용어';
    default:
      return index;
  }
}
