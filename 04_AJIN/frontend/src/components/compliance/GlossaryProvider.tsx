// G7: 글로서리 데이터 로더 + 텍스트 자동 감지.
//
// - GlossaryProvider 가 한 번 데이터를 로드해 컨텍스트에 캐싱
// - useGlossary() 가 (term/alias → data) 룩업 헬퍼 + 텍스트 highlighter 제공
// - GlossaryAutoText 는 string 을 받아 매칭되는 용어를 GlossaryTerm 으로 감싼다

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { fetchGlossary } from '@api/compliance';
import { GlossaryTerm } from './GlossaryTerm';

export interface GlossaryTermData {
  term: string;
  ko?: string;
  en?: string;
  definition: string;
  category?: string;
  aliases?: string[];
}

interface GlossaryContextValue {
  byKey: Map<string, GlossaryTermData>;   // 모든 키(term + aliases) 가 소문자로 정규화
  list: GlossaryTermData[];
  loading: boolean;
  error: string | null;
}

const GlossaryContext = createContext<GlossaryContextValue>({
  byKey: new Map(),
  list: [],
  loading: false,
  error: null,
});

function buildKeyMap(items: GlossaryTermData[]): Map<string, GlossaryTermData> {
  const map = new Map<string, GlossaryTermData>();
  for (const it of items) {
    map.set(normKey(it.term), it);
    for (const a of it.aliases ?? []) {
      const k = normKey(a);
      if (!map.has(k)) map.set(k, it);
    }
  }
  return map;
}

function normKey(s: string): string {
  return s.trim().toLowerCase();
}

export function GlossaryProvider({ children }: { children: ReactNode }) {
  const [list, setList] = useState<GlossaryTermData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchGlossary()
      .then((r) => {
        if (!cancelled) setList(r.terms || []);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : '글로서리 로드 실패');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const byKey = useMemo(() => buildKeyMap(list), [list]);

  return (
    <GlossaryContext.Provider value={{ byKey, list, loading, error }}>
      {children}
    </GlossaryContext.Provider>
  );
}

export function useGlossary() {
  return useContext(GlossaryContext);
}

/**
 * 임의 텍스트에서 글로서리 용어를 자동으로 GlossaryTerm 컴포넌트로 감싼다.
 *
 * 매칭 정책:
 *  - 단어 경계 기반 (영문은 \b, 한국어는 인접 비-한글)
 *  - 길이 우선 (긴 매칭이 우선) — 'IATF 16949' 가 'IATF' 보다 우선
 *  - 동일 텍스트에서 같은 용어는 첫 번째 출현만 강조 (잡음 감소)
 */
export function GlossaryAutoText({ text }: { text: string }) {
  const { byKey, list } = useGlossary();

  const annotated = useMemo(() => {
    if (!text || list.length === 0) return [text];

    // 모든 가능한 키 (term + aliases) 수집, 길이 내림차순
    const keys: string[] = [];
    for (const it of list) {
      keys.push(it.term);
      for (const a of it.aliases ?? []) keys.push(a);
    }
    keys.sort((a, b) => b.length - a.length);

    const seen = new Set<string>();
    const segments: (string | { key: string; matched: string; data: GlossaryTermData })[] = [text];

    for (const key of keys) {
      const re = makePattern(key);
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (typeof seg !== 'string') continue;
        const m = seg.match(re);
        if (!m || m.index === undefined) continue;

        const data = byKey.get(normKey(key));
        if (!data) continue;
        if (seen.has(data.term)) continue;       // 첫 출현만
        seen.add(data.term);

        const before = seg.slice(0, m.index);
        const after = seg.slice(m.index + m[0].length);
        const out: typeof segments = [];
        if (before) out.push(before);
        out.push({ key: data.term, matched: m[0], data });
        if (after) out.push(after);

        segments.splice(i, 1, ...out);
        i += out.length - 1;       // 새 세그먼트 건너뛰기
        break;                      // 다음 key 로
      }
    }

    return segments;
  }, [text, byKey, list]);

  return (
    <>
      {annotated.map((seg, i) =>
        typeof seg === 'string' ? (
          <span key={i}>{seg}</span>
        ) : (
          <GlossaryTerm key={i} term={seg.matched} data={seg.data} />
        ),
      )}
    </>
  );
}

function makePattern(key: string): RegExp {
  // 한글 포함 여부에 따라 단어 경계 패턴 분기
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const hasKorean = /[ㄱ-힝]/.test(key);
  if (hasKorean) {
    // 한국어: 단어 경계가 없으므로 그대로 + 대소문자 구분 없음
    return new RegExp(escaped, 'i');
  }
  return new RegExp(`\\b${escaped}\\b`, 'i');
}
