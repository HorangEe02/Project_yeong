// useBreakpoint — viewport 폭 → 카테고리 매핑 (v4.4).
//
// breakpoints.css 와 동일한 임계값 사용:
//   sm:  ≤480px
//   md:  ≤640px (모바일)
//   lg:  ≤1024px (태블릿)
//   xl:  >1024px (데스크탑/와이드)
//
// SSR 안전: 초기 mount 전에 window 부재 가능 → 데스크탑 기본 가정.

import { useEffect, useState } from 'react';

export type Breakpoint = 'sm' | 'md' | 'lg' | 'xl';

const Q = {
  sm: '(max-width: 480px)',
  md: '(min-width: 481px) and (max-width: 640px)',
  lg: '(min-width: 641px) and (max-width: 1024px)',
  xl: '(min-width: 1025px)',
} as const;

function compute(): Breakpoint {
  if (typeof window === 'undefined') return 'xl';
  if (window.matchMedia(Q.sm).matches) return 'sm';
  if (window.matchMedia(Q.md).matches) return 'md';
  if (window.matchMedia(Q.lg).matches) return 'lg';
  return 'xl';
}

export function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(() => compute());

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = () => setBp(compute());
    // 4 query 모두 구독 — 어느 쪽 변화든 재계산
    const watchers = (Object.values(Q) as readonly string[]).map((q) => {
      const mql = window.matchMedia(q);
      mql.addEventListener('change', handler);
      return mql;
    });
    return () => watchers.forEach((m) => m.removeEventListener('change', handler));
  }, []);

  return bp;
}

/** ≤640px (모바일) — 하단 탭 바·Drawer 활성 분기. */
export function useIsMobile(): boolean {
  const bp = useBreakpoint();
  return bp === 'sm' || bp === 'md';
}

/** 641-1024px (태블릿 portrait / 모바일 landscape) — slim sidebar. */
export function useIsTablet(): boolean {
  return useBreakpoint() === 'lg';
}

/** ≥1025px (데스크탑) — 기존 3열 HUD. */
export function useIsDesktop(): boolean {
  return useBreakpoint() === 'xl';
}

/** prefers-reduced-motion 사용자 선호도. */
export function usePrefersReducedMotion(): boolean {
  const [reduce, setReduce] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = () => setReduce(mql.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);
  return reduce;
}
