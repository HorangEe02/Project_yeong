// CommandPalette — Module A · 글로벌 ⌘K 검색 팔레트.
// 디자인 시스템 v3.5: Liquid Glass 모달 + lg-* 토큰. 영문 eyebrow + 한글 본문.
//   - 외곽 16px radius, 입력 12px, 페이지 점프 항목 12px (active=12px)
//   - 글래스: --glass-bg / --glass-border / --glass-blur / --glass-saturate
//   - ⌘K / Ctrl+K 토글, ↑↓ 키보드 네비, Enter 점프, ESC 닫기

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Search as SearchIcon, X, ArrowRight, User2, FileText, Compass, Sparkles, Camera } from 'lucide-react';
import { searchEmployees, type BackendEmployee } from '@api/employee';
import { searchDocuments, fetchIntent, visionQuerySearch, type DocSearchResultItem, type VisionSearchResult } from '@api/search';
import {
  useSearchStore,
  CATEGORY_EYEBROW,
  asSearchCategory,
  type SearchCategory,
  type PaletteItem,
  type PaletteMode,
} from '@store/search';
import { SyntheticBadge } from '@lib/syntheticBadge';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** v4.7 Sprint 2 P0 — chat-overlay / vision-search 모드 override.
   *  미지정 시 store.paletteMode 사용 (전역 ⌘K 호출 시).
   */
  mode?: PaletteMode;
  /** chat-overlay 모드에서 결과 클릭 시 호출 — page 이동 대신 onSelect 만 호출. */
  onSelect?: (item: PaletteItem) => void;
  /** vision-search 모드에서 OCR 호출에 사용할 이미지 파일. */
  image?: File | null;
}

interface PageShortcut {
  id: string;
  label: string;
  hint: string;
  to: string;
}

const PAGE_SHORTCUTS: PageShortcut[] = [
  { id: 'page-search-unified', label: '통합 검색', hint: 'PEOPLE · DOC · SOP', to: '/search' },
  { id: 'page-search-people', label: '인사 검색', hint: 'ORG TREE · DIRECTORY', to: '/search?tab=people' },
  { id: 'page-search-docs', label: '문서 검색', hint: '8D · ECN · MEETING', to: '/search?tab=documents' },
  { id: 'page-chat', label: 'AI 업무 도우미', hint: 'CHAT · SOP', to: '/chat' },
  { id: 'page-draft', label: '문서 초안', hint: 'TEMPLATES', to: '/draft' },
  { id: 'page-compliance', label: '컴플라이언스', hint: 'REG. MONITOR', to: '/compliance' },
  { id: 'page-equipment', label: '설비 / SPC', hint: 'NELSON 8 RULES', to: '/equipment' },
];

interface Item {
  kind: 'page' | 'person' | 'doc';
  id: string;
  title: string;
  hint: string;
  go: () => void;
  isSynthetic?: boolean;
}

export function CommandPalette({ isOpen, onClose, mode: modeProp, onSelect: onSelectProp, image: imageProp }: Props) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  // Sprint 1 P0 — store 가 query / pushQuery / recent 단일 출처.
  const q = useSearchStore((s) => s.query);
  const setQ = useSearchStore((s) => s.setQuery);
  const pushQuery = useSearchStore((s) => s.pushQuery);

  // v4.7 Sprint 2 P0 — Palette 모드 / onSelect / vision image.
  const storeMode = useSearchStore((s) => s.paletteMode);
  const storeOnSelect = useSearchStore((s) => s.paletteOnSelect);
  const storeImage = useSearchStore((s) => s.paletteImage);
  const mode: PaletteMode = modeProp ?? storeMode;
  const onSelect = onSelectProp ?? storeOnSelect ?? null;
  const image = imageProp ?? storeImage ?? null;

  // v4.7 Sprint 2 P0 — Intent → Palette auto-category (축 ②).
  const lastIntent = useSearchStore((s) => s.lastIntent);
  const setIntent = useSearchStore((s) => s.setIntent);
  const smartSortEnabled = useSearchStore((s) => s.smartSortEnabled);
  const toggleSmartSort = useSearchStore((s) => s.toggleSmartSort);
  const manualCategoryUntil = useSearchStore((s) => s.manualCategoryUntil);
  const setActiveCategory = useSearchStore((s) => s.setActiveCategory);

  const [people, setPeople] = useState<BackendEmployee[]>([]);
  const [docs, setDocs] = useState<DocSearchResultItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  // 축 ④ — vision-search 결과 (OCR 텍스트 + 검색 결과).
  const [vision, setVision] = useState<VisionSearchResult | null>(null);
  const [visionBusy, setVisionBusy] = useState(false);
  const [visionError, setVisionError] = useState<string | null>(null);

  // 열릴 때 입력 자동 포커스 + 상태 초기화
  useEffect(() => {
    if (isOpen) {
      // chat-overlay/vision-search 시 store 가 seed query 를 채웠을 수 있으므로 비우지 않음.
      if (mode === 'global') setQ('');
      setPeople([]);
      setDocs([]);
      setActiveIdx(0);
      setVision(null);
      setVisionError(null);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isOpen, mode, setQ]);

  // v4.7 Sprint 2 P0 (축 ④) — vision-search 모드 진입 시 즉시 OCR + 검색.
  useEffect(() => {
    if (!isOpen) return;
    if (mode !== 'vision-search') return;
    if (!image) return;
    let cancelled = false;
    setVisionBusy(true);
    setVisionError(null);
    visionQuerySearch(image)
      .then((r) => {
        if (cancelled) return;
        setVision(r);
        // OCR 텍스트를 입력란에 미리 채워 사용자가 편집 가능하도록.
        if (r.ocr_text && !q.trim()) setQ(r.ocr_text.slice(0, 200));
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error;
        setVisionError(msg === 'vision_disabled' ? 'vision_disabled' : 'vision_failed');
      })
      .finally(() => {
        if (!cancelled) setVisionBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, mode, image]);

  // 디바운스 검색 + intent 동시 호출 (축 ②).
  useEffect(() => {
    if (!isOpen) return;
    const trimmed = q.trim();
    if (!trimmed) {
      setPeople([]);
      setDocs([]);
      setIntent(null);
      return;
    }
    setBusy(true);
    const t = setTimeout(async () => {
      const [pResp, dResp, iResp] = await Promise.allSettled([
        searchEmployees(trimmed),
        searchDocuments({ query: trimmed, k: 5 }),
        fetchIntent(trimmed),
      ]);
      setPeople(pResp.status === 'fulfilled' ? pResp.value.results.slice(0, 5) : []);
      setDocs(dResp.status === 'fulfilled' ? dResp.value.results.slice(0, 5) : []);
      // 축 ② — Intent 결과 store 반영 + smart sort 자동 적용.
      if (iResp.status === 'fulfilled') {
        const result = iResp.value;
        setIntent(result);
        const now = Date.now();
        const respectManual = manualCategoryUntil > now;
        const cat = asSearchCategory(result.suggested_category);
        if (smartSortEnabled && !respectManual && result.confidence >= 0.7 && cat) {
          setActiveCategory(cat);
        }
      } else {
        setIntent(null);
      }
      setBusy(false);
    }, 250);
    return () => {
      clearTimeout(t);
      setBusy(false);
    };
  }, [q, isOpen, smartSortEnabled, manualCategoryUntil, setIntent, setActiveCategory]);

  const items = useMemo<Item[]>(() => {
    const list: Item[] = [];
    // chat-overlay/vision-search 모드에서는 결과 클릭이 onSelect 콜백을 호출.
    const isOverlay = mode === 'chat-overlay' || mode === 'vision-search';
    const fire = (payload: PaletteItem, fallback: () => void) => {
      if (isOverlay && onSelect) {
        onSelect(payload);
        onClose();
        return;
      }
      fallback();
    };

    // vision-search 모드: OCR 결과 우선 노출 (Items kind='ocr' 가상 항목)
    if (mode === 'vision-search' && vision && vision.search_results.length > 0) {
      for (const r of vision.search_results.slice(0, 8)) {
        const payload: PaletteItem = {
          kind: 'ocr',
          id: r.doc_id || r.title,
          title: r.title || r.doc_id,
          hint: `${r.doc_type || 'OCR'} · ${(r.score || 0).toFixed(2)}`,
        };
        list.push({
          kind: 'doc',
          id: `ocr-${r.doc_id}`,
          title: payload.title,
          hint: payload.hint,
          go: () =>
            fire(payload, () => {
              navigate(`/search?tab=documents`, { state: { focusDocId: r.doc_id } });
              onClose();
            }),
        });
      }
      return list;
    }

    if (!q.trim()) {
      // overlay 모드 + 빈 입력 → 페이지 점프 항목은 의미가 약하므로 추천 메시지만.
      if (isOverlay) return list;
      for (const p of PAGE_SHORTCUTS) {
        list.push({
          kind: 'page',
          id: p.id,
          title: p.label,
          hint: p.hint,
          go: () => {
            navigate(p.to);
            onClose();
          },
        });
      }
      return list;
    }
    for (let i = 0; i < people.length; i++) {
      const p = people[i];
      const payload: PaletteItem = {
        kind: 'person',
        id: `person:${p.name}`,
        title: `${p.name}${p.position ? `(${p.position})` : ''}`,
        hint: `${p.division || '—'} / ${p.department || '—'}${p.email ? ' · ' + p.email : ''}`,
      };
      list.push({
        kind: 'person',
        id: `person-${i}`,
        title: `${p.name} · ${p.position}`,
        hint: payload.hint,
        isSynthetic: p.is_synthetic === 1,
        go: () =>
          fire(payload, () => {
            if (q.trim()) pushQuery(q.trim(), people.length + docs.length);
            navigate(`/search?tab=people`, { state: { initialQuery: p.name } });
            onClose();
          }),
      });
    }
    for (const d of docs) {
      const payload: PaletteItem = {
        kind: 'doc',
        id: `doc:${d.doc_id}`,
        title: d.title || '(제목 없음)',
        hint: `${d.doc_type || 'DOC'}${d.part_name ? ' · ' + d.part_name : ''}`,
      };
      list.push({
        kind: 'doc',
        id: `doc-${d.doc_id}`,
        title: d.title || '(제목 없음)',
        hint: `${d.doc_type || 'DOC'}${d.part_name ? ' · ' + d.part_name : ''} · RRF ${d.score.toFixed(2)}`,
        go: () =>
          fire(payload, () => {
            if (q.trim()) pushQuery(q.trim(), people.length + docs.length);
            navigate(`/search?tab=documents`, { state: { focusDocId: d.doc_id } });
            onClose();
          }),
      });
    }
    if (!isOverlay) {
      const ql = q.toLowerCase();
      for (const p of PAGE_SHORTCUTS) {
        if (p.label.toLowerCase().includes(ql) || p.hint.toLowerCase().includes(ql)) {
          list.push({
            kind: 'page',
            id: p.id,
            title: p.label,
            hint: p.hint,
            go: () => {
              navigate(p.to);
              onClose();
            },
          });
        }
      }
    }
    return list;
  }, [q, people, docs, navigate, onClose, mode, vision, onSelect, pushQuery]);

  useEffect(() => {
    if (activeIdx >= items.length) setActiveIdx(0);
  }, [items.length, activeIdx]);

  // Sprint 1 P0 — kind 별 그룹 + 그룹 시작 인덱스 (Tab 키 jump 용).
  const groups = useMemo(() => {
    const map = new Map<Item['kind'], { startIdx: number; items: Item[] }>();
    items.forEach((it, i) => {
      const g = map.get(it.kind);
      if (g) g.items.push(it);
      else map.set(it.kind, { startIdx: i, items: [it] });
    });
    return Array.from(map.entries());
  }, [items]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(items.length - 1, i + 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
      return;
    }
    if (e.key === 'Tab') {
      // 다음/이전 카테고리의 첫 항목으로 점프 (Shift+Tab = 이전).
      e.preventDefault();
      if (groups.length <= 1) return;
      const currentGroupIdx = groups.findIndex(
        ([, g]) => activeIdx >= g.startIdx && activeIdx < g.startIdx + g.items.length,
      );
      const nextGroupIdx = e.shiftKey
        ? (currentGroupIdx - 1 + groups.length) % groups.length
        : (currentGroupIdx + 1) % groups.length;
      const target = groups[nextGroupIdx]?.[1].startIdx ?? 0;
      setActiveIdx(target);
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const it = items[activeIdx];
      if (it) it.go();
      return;
    }
  };

  if (!isOpen) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="명령 팔레트"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background:
          'color-mix(in oklab, var(--hud-bg, #0A0E14) 60%, transparent)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '12vh',
        backdropFilter: 'blur(4px) saturate(120%)',
        WebkitBackdropFilter: 'blur(4px) saturate(120%)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
        style={{
          width: 'min(640px, 92vw)',
          background: 'var(--glass-bg-strong, var(--hud-surface, #111820))',
          backdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
          WebkitBackdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
          border: '1px solid var(--glass-border, color-mix(in oklab, var(--hud-text) 12%, transparent))',
          borderRadius: 16,
          boxShadow:
            'inset 0 1px 0 var(--glass-highlight, rgba(255,255,255,0.18)), 0 30px 80px -20px var(--glass-shadow, rgba(0,0,0,0.4))',
          overflow: 'hidden',
        }}
      >
        {/* INPUT — 12px 라운드 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '14px 16px',
            borderBottom:
              '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
          }}
        >
          <SearchIcon size={16} strokeWidth={2} style={{ color: 'var(--hud-primary)' }} />
          <input
            ref={inputRef}
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="이름 · 부서 · 8D · ECN · REACH · 페이지 점프..."
            aria-label="명령 팔레트 검색어"
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--hud-text)',
              fontFamily: 'var(--hud-font, inherit)',
              fontSize: 16,
              fontWeight: 500,
              letterSpacing: 0,
            }}
          />
          {/* Smart Sort 🌟 토글 (축 ②) */}
          <button
            type="button"
            onClick={toggleSmartSort}
            aria-label="Smart Sort 토글"
            aria-pressed={smartSortEnabled}
            title={
              smartSortEnabled
                ? '의도 기반 자동 카테고리 정렬 ON'
                : '의도 기반 자동 카테고리 정렬 OFF'
            }
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 8px',
              border: '1px solid color-mix(in oklab, var(--hud-text) 12%, transparent)',
              borderRadius: 8,
              background: smartSortEnabled
                ? 'color-mix(in oklab, var(--hud-primary) 12%, transparent)'
                : 'transparent',
              color: smartSortEnabled ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.14em',
              cursor: 'pointer',
            }}
          >
            <Sparkles size={10} strokeWidth={2} />
            SMART SORT
          </button>
          <span
            className="mono"
            style={{
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.14em',
              color: busy || visionBusy ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
            }}
          >
            {visionBusy ? 'OCR…' : busy ? 'SEARCHING…' : 'ESC'}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="lg-btn ghost sm"
            style={{ padding: '6px 8px' }}
          >
            <X size={13} strokeWidth={2} />
          </button>
        </div>

        {/* Intent hint (축 ②) — confidence 0.5 이상이면 표시 */}
        {mode !== 'vision-search' && lastIntent && lastIntent.confidence >= 0.5 && (
          <div
            style={{
              padding: '6px 16px',
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.14em',
              color: 'var(--hud-text-dim)',
              borderBottom: '1px solid color-mix(in oklab, var(--hud-text) 6%, transparent)',
            }}
          >
            INTENT · {(lastIntent.suggested_category ?? lastIntent.intent.replace(/^keyword:/, '')).toUpperCase()} · {Math.round(lastIntent.confidence * 100)}%
            {lastIntent.confidence >= 0.7 && smartSortEnabled ? ' · AUTO-SORTED' : ''}
          </div>
        )}

        {/* Vision-search 헤더 (축 ④) */}
        {mode === 'vision-search' && (
          <div
            style={{
              padding: '8px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.14em',
              color: visionError ? 'var(--hud-danger, #D32F2F)' : 'var(--hud-primary)',
              borderBottom: '1px solid color-mix(in oklab, var(--hud-text) 6%, transparent)',
            }}
          >
            <Camera size={12} strokeWidth={2} />
            {visionBusy
              ? '🔍 OCR 검색 중...'
              : visionError === 'vision_disabled'
                ? 'GEMINI_API_KEY 미설정 — vision-search 비활성'
                : visionError
                  ? 'OCR 실패 — 일반 검색으로 전환됨'
                  : vision
                    ? `OCR · ${(vision.ocr_text || '').slice(0, 60) || '(텍스트 없음)'}`
                    : 'VISION SEARCH'}
          </div>
        )}

        {/* RESULTS */}
        <div style={{ maxHeight: '60vh', overflow: 'auto' }}>
          {items.length === 0 ? (
            <div
              style={{
                padding: 28,
                textAlign: 'center',
                fontSize: 13,
                color: 'var(--hud-text-dim)',
                lineHeight: 1.7,
              }}
            >
              {q.trim() ? (
                <>
                  <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
                    NO RESULTS · 결과 없음
                  </div>
                  검색어를 줄이거나 다른 키워드를 시도하세요.
                </>
              ) : (
                <>
                  <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
                    QUICK JUMP · 빠른 점프
                  </div>
                  검색어를 입력하거나 페이지로 점프하세요.
                </>
              )}
            </div>
          ) : (
            <div style={{ padding: 8 }}>
              {groups.map(([kind, g]) => {
                const eyebrow = CATEGORY_EYEBROW[kind as SearchCategory] ?? String(kind).toUpperCase();
                return (
                  <section key={kind} aria-label={eyebrow} style={{ marginBottom: 4 }}>
                    <div
                      className="lg-eyebrow"
                      style={{
                        padding: '8px 12px 4px',
                        fontFamily: 'var(--hud-font-mono)',
                        fontSize: 10,
                        letterSpacing: '0.14em',
                        color: 'var(--hud-text-dim)',
                      }}
                    >
                      {eyebrow} · {g.items.length}
                    </div>
                    <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                      {g.items.map((it, k) => {
                        const i = g.startIdx + k;
                        const isActive = i === activeIdx;
                        return (
                          <li key={it.id}>
                            <button
                              type="button"
                              onClick={() => it.go()}
                              onMouseEnter={() => setActiveIdx(i)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 12,
                                width: '100%',
                                padding: '12px 14px',
                                borderRadius: 12,
                                background: isActive ? 'var(--hud-primary)' : 'transparent',
                                color: isActive ? 'var(--hud-bg)' : 'var(--hud-text)',
                                textAlign: 'left',
                                border: 'none',
                                cursor: 'pointer',
                                fontFamily: 'var(--hud-font, inherit)',
                                transition: 'background .15s',
                              }}
                            >
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  width: 22,
                                  color: isActive ? 'var(--hud-bg)' : 'var(--hud-primary)',
                                }}
                              >
                                {it.kind === 'person' ? (
                                  <User2 size={14} strokeWidth={2} />
                                ) : it.kind === 'doc' ? (
                                  <FileText size={14} strokeWidth={2} />
                                ) : (
                                  <Compass size={14} strokeWidth={2} />
                                )}
                              </span>
                              <span style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontWeight: 600, fontSize: 14 }}>
                                  {it.title}
                                  {it.isSynthetic && <SyntheticBadge show />}
                                </div>
                                <div
                                  style={{
                                    fontSize: 11,
                                    marginTop: 2,
                                    letterSpacing: '0.04em',
                                    color: isActive
                                      ? 'color-mix(in oklab, var(--hud-bg) 80%, transparent)'
                                      : 'var(--hud-text-dim)',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {it.hint}
                                </div>
                              </span>
                              <ArrowRight size={12} strokeWidth={2} />
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
            </div>
          )}
        </div>

        {/* FOOTER */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            padding: '10px 16px',
            borderTop:
              '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            fontFamily: 'var(--hud-font-mono)',
            fontSize: 10,
            letterSpacing: '0.14em',
            color: 'var(--hud-text-dim)',
          }}
        >
          <span>↑↓ NAV · TAB GROUP · ENTER GO · ESC CLOSE</span>
          <span style={{ color: 'var(--hud-primary)' }}>⌘K · CTRL+K</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
