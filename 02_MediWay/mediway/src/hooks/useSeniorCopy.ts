import { useCallback } from 'react';
import seniorCopy from '@/i18n/senior.json';
import { useSeniorMode } from '@/hooks/useSeniorMode';

type SeniorCopyDict = Record<string, string>;
const DICT = seniorCopy as SeniorCopyDict;

/**
 * 고령자 모드용 카피 치환 훅.
 *
 * 원칙:
 * - senior 모드 OFF → 항상 fallback 반환 (일반 사용자 경험 불변)
 * - senior 모드 ON → 사전 key 존재 시 치환, 없으면 fallback
 * - 의료 정확성 필요 용어(진단·처방·약품명)는 사전에 등록하지 않아 자동으로 원문 유지
 *
 * 사용:
 * ```tsx
 * const copy = useSeniorCopy();
 * <h3>{copy('widget.schedule.title', '오늘 일정')}</h3>
 * ```
 */
export function useSeniorCopy(): (key: string, fallback: string) => string {
  const { enabled } = useSeniorMode();
  return useCallback(
    (key: string, fallback: string) => {
      if (!enabled) return fallback;
      const replacement = DICT[key];
      return typeof replacement === 'string' && replacement.length > 0
        ? replacement
        : fallback;
    },
    [enabled],
  );
}

/** 사전에 등록된 모든 key (테스트/개발 디버깅용) */
export function listSeniorCopyKeys(): string[] {
  return Object.keys(DICT).filter((k) => !k.startsWith('$'));
}
