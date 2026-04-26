import type { AppointmentPatientIndex } from '@/types/appointment';

/**
 * 외래 예약 내역 그룹화 — 사용자가 일/월/년 단위로 묶어서 볼 수 있게 한다.
 * KST(UTC+9) 기준 — `services/waitQueue.ts:todayDateKST` 와 동일 정책.
 */

export type Granularity = 'day' | 'month' | 'year';

const KOREAN_WEEKDAY = ['일', '월', '화', '수', '목', '금', '토'] as const;

/**
 * scheduledAt(epoch ms) → KST 기준 그룹 키.
 *
 * - 'day'   → 'YYYY-MM-DD'
 * - 'month' → 'YYYY-MM'
 * - 'year'  → 'YYYY'
 *
 * 같은 값이 같은 키로 매핑되도록 결정적. 정렬 시 문자열 비교 = 시간 비교 (오름차순).
 */
export function groupKey(scheduledAt: number, gran: Granularity): string {
  const kst = new Date(scheduledAt + 9 * 60 * 60 * 1000);
  const yyyy = kst.getUTCFullYear();
  const mm = String(kst.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(kst.getUTCDate()).padStart(2, '0');
  if (gran === 'year') return `${yyyy}`;
  if (gran === 'month') return `${yyyy}-${mm}`;
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * 그룹 키 → 사용자에게 보여줄 한국어 헤더.
 *
 * - 'day'   → '2026-04-26 (일)'
 * - 'month' → '2026년 4월'
 * - 'year'  → '2026년'
 */
export function formatGroupHeader(key: string, gran: Granularity): string {
  if (gran === 'year') return `${key}년`;
  if (gran === 'month') {
    const [y, m] = key.split('-');
    return `${y}년 ${parseInt(m, 10)}월`;
  }
  // 'day' — 요일 계산 (KST)
  const [y, m, d] = key.split('-').map((s) => parseInt(s, 10));
  // KST 자정의 epoch ms — 요일 계산 결정적
  const kstMidnight = Date.UTC(y, m - 1, d) - 9 * 60 * 60 * 1000;
  const dow = new Date(kstMidnight + 9 * 60 * 60 * 1000).getUTCDay();
  return `${key} (${KOREAN_WEEKDAY[dow]})`;
}

/**
 * 예약 list 를 granularity 단위로 그룹화 — 그룹은 키 오름차순(과거 → 미래) 정렬.
 * 각 그룹 내부도 scheduledAt 오름차순 정렬 (입력 순서와 무관하게 결정적).
 */
export function groupAppointments(
  list: AppointmentPatientIndex[],
  gran: Granularity,
): Array<{ key: string; entries: AppointmentPatientIndex[] }> {
  const buckets = new Map<string, AppointmentPatientIndex[]>();
  for (const a of list) {
    const k = groupKey(a.scheduledAt, gran);
    const arr = buckets.get(k);
    if (arr) arr.push(a);
    else buckets.set(k, [a]);
  }
  // 그룹 내부 정렬 + 그룹 키 정렬
  const groups: Array<{ key: string; entries: AppointmentPatientIndex[] }> = [];
  for (const [k, entries] of buckets) {
    entries.sort((a, b) => a.scheduledAt - b.scheduledAt);
    groups.push({ key: k, entries });
  }
  groups.sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  return groups;
}

/** 필터 UI 노출 임계 — 데이터가 적을 땐 noise 만 발생하므로 숨김. */
export const FILTER_VISIBILITY_THRESHOLD = 5;
