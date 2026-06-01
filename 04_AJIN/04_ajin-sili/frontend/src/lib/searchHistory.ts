// searchHistory — Module A · 클라이언트 측 검색 이력/즐겨찾기/최근 본 항목 저장소.
// localStorage 기반. 사용자 단위 격리는 key 에 user.id 접미사. 서버 동기화는 W7 에서 추가 가능.

const KEY_QUERIES = 'ajin-search-recent-queries';
const KEY_PEOPLE_VIEWED = 'ajin-search-recent-people';
const KEY_DOCS_VIEWED = 'ajin-search-recent-docs';
const KEY_FAVORITE_PEOPLE = 'ajin-search-favorite-people';
const KEY_FEEDBACK = 'ajin-search-feedback';
const KEY_QUERY_LOG = 'ajin-search-query-log';

const MAX_QUERIES = 12;
const MAX_VIEWED = 8;
const MAX_FAVORITES = 24;
const MAX_QUERY_LOG = 200;
const MAX_FEEDBACK = 200;

export interface RecentQuery {
  query: string;
  timestamp: number; // epoch ms
  hits?: number;     // 결과 건수 (있으면)
}

export interface ViewedPerson {
  id: string;
  name: string;
  team: string;
  position: string;
  timestamp: number;
}

export interface ViewedDoc {
  doc_id: string;
  title: string;
  doc_type: string;
  timestamp: number;
}

export interface FavoritePerson {
  id: string;
  name: string;
  team: string;
  position: string;
  email?: string;
  addedAt: number;
}

// ─────────────────────────────────────────────────────────────
// helpers
// ─────────────────────────────────────────────────────────────

function safeRead<T>(key: string): T[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as T[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function safeWrite<T>(key: string, value: T[]): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
    // storage 이벤트는 다른 탭에만 발생 — 같은 탭 동기화는 커스텀 이벤트로.
    window.dispatchEvent(new CustomEvent('ajin-search-history-changed', { detail: { key } }));
  } catch {
    // 용량 초과 등 — 조용히 실패
  }
}

// ─────────────────────────────────────────────────────────────
// Recent queries
// ─────────────────────────────────────────────────────────────

export function getRecentQueries(): RecentQuery[] {
  return safeRead<RecentQuery>(KEY_QUERIES);
}

export function pushRecentQuery(query: string, hits?: number): void {
  const trimmed = query.trim();
  if (!trimmed) return;
  const list = getRecentQueries().filter((q) => q.query !== trimmed);
  list.unshift({ query: trimmed, timestamp: Date.now(), hits });
  safeWrite(KEY_QUERIES, list.slice(0, MAX_QUERIES));

  // W8 — 분석용 영구 로그 (top queries 집계용, dedup 안 함)
  const log = safeRead<RecentQuery>(KEY_QUERY_LOG);
  log.unshift({ query: trimmed, timestamp: Date.now(), hits });
  safeWrite(KEY_QUERY_LOG, log.slice(0, MAX_QUERY_LOG));
}

export function clearRecentQueries(): void {
  safeWrite(KEY_QUERIES, []);
}

// ─────────────────────────────────────────────────────────────
// Recent viewed people
// ─────────────────────────────────────────────────────────────

export function getViewedPeople(): ViewedPerson[] {
  return safeRead<ViewedPerson>(KEY_PEOPLE_VIEWED);
}

export function pushViewedPerson(p: Omit<ViewedPerson, 'timestamp'>): void {
  const list = getViewedPeople().filter((x) => x.id !== p.id);
  list.unshift({ ...p, timestamp: Date.now() });
  safeWrite(KEY_PEOPLE_VIEWED, list.slice(0, MAX_VIEWED));
}

// ─────────────────────────────────────────────────────────────
// Recent viewed documents
// ─────────────────────────────────────────────────────────────

export function getViewedDocs(): ViewedDoc[] {
  return safeRead<ViewedDoc>(KEY_DOCS_VIEWED);
}

export function pushViewedDoc(d: Omit<ViewedDoc, 'timestamp'>): void {
  const list = getViewedDocs().filter((x) => x.doc_id !== d.doc_id);
  list.unshift({ ...d, timestamp: Date.now() });
  safeWrite(KEY_DOCS_VIEWED, list.slice(0, MAX_VIEWED));
}

// ─────────────────────────────────────────────────────────────
// Favorite people
// ─────────────────────────────────────────────────────────────

export function getFavoritePeople(): FavoritePerson[] {
  return safeRead<FavoritePerson>(KEY_FAVORITE_PEOPLE);
}

export function isFavoritePerson(id: string): boolean {
  return getFavoritePeople().some((x) => x.id === id);
}

export function toggleFavoritePerson(p: Omit<FavoritePerson, 'addedAt'>): boolean {
  const list = getFavoritePeople();
  const existing = list.find((x) => x.id === p.id);
  if (existing) {
    safeWrite(KEY_FAVORITE_PEOPLE, list.filter((x) => x.id !== p.id));
    return false;
  }
  const next = [{ ...p, addedAt: Date.now() }, ...list].slice(0, MAX_FAVORITES);
  safeWrite(KEY_FAVORITE_PEOPLE, next);
  return true;
}

// ─────────────────────────────────────────────────────────────
// Subscription helper for React components
// ─────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────
// W8 — 검색 품질 피드백 (도움됨/도움안됨)
// ─────────────────────────────────────────────────────────────

export interface SearchFeedback {
  query: string;
  docId: string;
  docTitle: string;
  helpful: boolean;
  timestamp: number;
}

export function pushFeedback(f: Omit<SearchFeedback, 'timestamp'>): void {
  const list = safeRead<SearchFeedback>(KEY_FEEDBACK);
  // 같은 (query, docId) 조합은 최신 피드백으로 갱신
  const next = list.filter((x) => !(x.query === f.query && x.docId === f.docId));
  next.unshift({ ...f, timestamp: Date.now() });
  safeWrite(KEY_FEEDBACK, next.slice(0, MAX_FEEDBACK));
}

export function getFeedback(): SearchFeedback[] {
  return safeRead<SearchFeedback>(KEY_FEEDBACK);
}

export function getFeedbackFor(query: string, docId: string): SearchFeedback | null {
  return getFeedback().find((x) => x.query === query && x.docId === docId) ?? null;
}

// ─────────────────────────────────────────────────────────────
// W8 — 분석 집계 헬퍼
// ─────────────────────────────────────────────────────────────

export interface QueryAggregate {
  query: string;
  count: number;
  hitsAvg: number;
  zeroResults: number;
  lastAt: number;
}

export function aggregateQueryLog(): QueryAggregate[] {
  const log = safeRead<RecentQuery>(KEY_QUERY_LOG);
  const map = new Map<string, QueryAggregate>();
  for (const e of log) {
    const cur = map.get(e.query) ?? {
      query: e.query,
      count: 0,
      hitsAvg: 0,
      zeroResults: 0,
      lastAt: 0,
    };
    cur.count += 1;
    cur.hitsAvg = (cur.hitsAvg * (cur.count - 1) + (e.hits ?? 0)) / cur.count;
    cur.zeroResults += (e.hits ?? 0) === 0 ? 1 : 0;
    if (e.timestamp > cur.lastAt) cur.lastAt = e.timestamp;
    map.set(e.query, cur);
  }
  return Array.from(map.values()).sort((a, b) => b.count - a.count);
}

export interface FeedbackAggregate {
  total: number;
  helpful: number;
  unhelpful: number;
  ctrLikeRate: number; // helpful / total
}

export function aggregateFeedback(): FeedbackAggregate {
  const fb = getFeedback();
  const helpful = fb.filter((x) => x.helpful).length;
  const unhelpful = fb.length - helpful;
  return {
    total: fb.length,
    helpful,
    unhelpful,
    ctrLikeRate: fb.length === 0 ? 0 : helpful / fb.length,
  };
}

export function getQueryLog(): RecentQuery[] {
  return safeRead<RecentQuery>(KEY_QUERY_LOG);
}

export function clearAnalytics(): void {
  safeWrite(KEY_QUERY_LOG, []);
  safeWrite(KEY_FEEDBACK, []);
}

export function subscribeHistoryChanges(cb: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = () => cb();
  window.addEventListener('ajin-search-history-changed', handler);
  window.addEventListener('storage', handler);
  return () => {
    window.removeEventListener('ajin-search-history-changed', handler);
    window.removeEventListener('storage', handler);
  };
}
