// search store — Module A · Sprint 1 P0.
// 전역 검색 입력/결과/최근쿼리/카테고리 상태 단일 출처.
// 기존 lib/searchHistory.ts (localStorage) 을 reactivity 레이어로 감싼다.
//   - 변경 이벤트 ('ajin-search-history-changed') 구독으로 자동 hydrate.
//   - 기존 pushRecentQuery 호출 사이트와 호환 (store 가 자동 반영).
//
// 카테고리는 v4 의도 라우터(10 의도) 와 동일한 키 사용 — Sprint 2 에서 확장.

import { create } from 'zustand';
import {
  getRecentQueries,
  pushRecentQuery as libPushRecent,
  clearRecentQueries as libClearRecent,
  subscribeHistoryChanges,
  type RecentQuery,
} from '@lib/searchHistory';

export type SearchCategory =
  | 'page'
  | 'person'
  | 'doc'
  | 'sop'
  | 'regulation'
  | 'equipment_error'
  | 'scenario'
  | 'org_chart'
  | 'draft'
  | 'metric';

// v4.7 Sprint 2 P0 — Palette 모드.
//   - 'global': 기본 (⌘K) — 결과 클릭 시 페이지 이동
//   - 'chat-overlay': InputComposer "/" 트리거 — 클릭 시 onSelect 콜백
//   - 'vision-search': 이미지 첨부 후 "/" — Gemini OCR 결과 통합 표시
export type PaletteMode = 'global' | 'chat-overlay' | 'vision-search';

/** Palette 결과 한 항목 — chat-overlay onSelect 콜백용 정규화 페이로드. */
export interface PaletteItem {
  kind: 'person' | 'doc' | 'page' | 'drawing' | 'ocr';
  id: string;
  title: string;
  hint: string;
}

/** v4.7 Sprint 2 P0 — `/search/intent` 응답 (10 카테고리 + confidence). */
export interface IntentResult {
  intent: string;
  confidence: number;          // 0.0~1.0
  /** 백엔드가 반환하는 카테고리 키. SearchCategory 와 동일 set 이지만,
   *  미래 확장(unknown) 대비 string 으로 받고 사용 측에서 narrowing. */
  suggested_category: string | null;
  alternatives: { intent: string; confidence: number }[];
}

const VALID_CATEGORIES: ReadonlySet<SearchCategory> = new Set<SearchCategory>([
  'page',
  'person',
  'doc',
  'sop',
  'regulation',
  'equipment_error',
  'scenario',
  'org_chart',
  'draft',
  'metric',
]);

export function asSearchCategory(value: string | null | undefined): SearchCategory | null {
  if (!value) return null;
  return VALID_CATEGORIES.has(value as SearchCategory) ? (value as SearchCategory) : null;
}

interface OpenPaletteOptions {
  mode?: PaletteMode;
  seed?: string;
  onSelect?: (item: PaletteItem) => void;
  /** vision-search 모드에서 즉시 OCR 호출에 사용되는 이미지 파일. */
  image?: File | null;
}

export const CATEGORY_LABEL: Record<SearchCategory, string> = {
  page: '페이지 점프',
  person: '인사',
  doc: '문서',
  sop: 'SOP',
  regulation: '규정',
  equipment_error: '설비 에러',
  scenario: '협업 시나리오',
  org_chart: '조직도',
  draft: '초안',
  metric: '지표',
};

export const CATEGORY_EYEBROW: Record<SearchCategory, string> = {
  page: 'PAGES',
  person: 'PEOPLE',
  doc: 'DOCUMENTS',
  sop: 'SOP',
  regulation: 'REGULATIONS',
  equipment_error: 'EQUIPMENT',
  scenario: 'SCENARIOS',
  org_chart: 'ORG CHART',
  draft: 'DRAFTS',
  metric: 'METRICS',
};

interface SearchState {
  // 입력
  query: string;
  setQuery: (q: string) => void;

  // 최근 쿼리 — localStorage 와 양방향 동기화
  recent: RecentQuery[];
  pushQuery: (query: string, hits?: number) => void;
  clearRecent: () => void;
  refreshRecent: () => void;

  // 활성 카테고리 (Tab 키 네비)
  activeCategory: SearchCategory | null;
  setActiveCategory: (c: SearchCategory | null) => void;

  // 팔레트 열림 상태 — 전역 트리거용 (GlobalSearchProvider 가 Sprint 2 에서 사용)
  isPaletteOpen: boolean;
  paletteMode: PaletteMode;
  paletteImage: File | null;
  /** chat-overlay/vision-search 모드의 결과 클릭 콜백. */
  paletteOnSelect: ((item: PaletteItem) => void) | null;

  // v4.7 Sprint 2 P0 — Intent → Palette auto-category
  lastIntent: IntentResult | null;
  smartSortEnabled: boolean;
  /** 사용자가 수동 카테고리를 클릭한 시점 (intent 무시 timer 시작점, ms). */
  manualCategoryUntil: number;
  setIntent: (r: IntentResult | null) => void;
  toggleSmartSort: () => void;
  /** 수동 카테고리 클릭 — 30s 동안 intent 자동 재정렬 무시. */
  markManualCategory: () => void;

  /** v4.7 Sprint 2 — openPalette 시그니처 확장 (기존 string 호출과 100% 호환).
   *  - string  → 기존 동작 (initialQuery seed, mode='global')
   *  - object  → mode/seed/onSelect/image 지정
   *  - 미지정  → 빈 입력으로 global 모드 오픈
   */
  openPalette: (arg?: string | OpenPaletteOptions) => void;
  closePalette: () => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  query: '',
  setQuery: (query) => set({ query }),

  recent: typeof window === 'undefined' ? [] : getRecentQueries(),
  pushQuery: (query, hits) => {
    libPushRecent(query, hits);
    set({ recent: getRecentQueries() });
  },
  clearRecent: () => {
    libClearRecent();
    set({ recent: [] });
  },
  refreshRecent: () => set({ recent: getRecentQueries() }),

  activeCategory: null,
  setActiveCategory: (activeCategory) => set({ activeCategory }),

  isPaletteOpen: false,
  paletteMode: 'global',
  paletteImage: null,
  paletteOnSelect: null,
  lastIntent: null,
  smartSortEnabled: true,
  manualCategoryUntil: 0,
  setIntent: (r) => set({ lastIntent: r }),
  toggleSmartSort: () => set((s) => ({ smartSortEnabled: !s.smartSortEnabled })),
  markManualCategory: () => set({ manualCategoryUntil: Date.now() + 30_000 }),
  openPalette: (arg) => {
    if (typeof arg === 'string') {
      set({
        isPaletteOpen: true,
        query: arg,
        paletteMode: 'global',
        paletteImage: null,
        paletteOnSelect: null,
      });
      return;
    }
    const opts = arg ?? {};
    set({
      isPaletteOpen: true,
      paletteMode: opts.mode ?? 'global',
      paletteImage: opts.image ?? null,
      paletteOnSelect: opts.onSelect ?? null,
      ...(opts.seed !== undefined ? { query: opts.seed } : {}),
    });
  },
  closePalette: () =>
    set({
      isPaletteOpen: false,
      paletteMode: 'global',
      paletteImage: null,
      paletteOnSelect: null,
    }),
}));

// 다른 컴포넌트가 lib/searchHistory 의 pushRecentQuery 를 호출해도
// store 가 자동 동기화되도록 — 한 번만 등록.
if (typeof window !== 'undefined') {
  subscribeHistoryChanges(() => {
    useSearchStore.getState().refreshRecent();
  });
}
