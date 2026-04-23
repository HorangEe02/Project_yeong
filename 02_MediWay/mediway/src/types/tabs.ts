import type { HospitalFeatures } from '@/types/hospital';

/** 병원 대시보드 상단 탭 ID */
export type TabId =
  | 'home'
  | 'appointments'
  | 'inpatient'
  | 'checkup'
  | 'guide'
  | 'more';

/** 탭 정의 — 라벨·경로·features flag 조건·접근 가능 조건 */
export interface TabDef {
  id: TabId;
  label: string;
  /** 항상 노출할지, 또는 HospitalFeatures 필드 1개가 true일 때만 노출할지 */
  requiresFeature?: keyof HospitalFeatures;
  /** 기본 홈 탭 여부 — URL에 tab 파라미터 없을 때 fallback */
  isDefault?: boolean;
}

/**
 * Phase 2 MVP 탭 정의 6개.
 *
 * v2 §Phase 2 규칙:
 * - 홈·안내·더보기는 항상 표시
 * - 외래·입원·검진은 features flag 기반 동적 노출
 * - 탭 순서 고정: home → appointments → inpatient → checkup → guide → more
 * - 6개 초과 시 "더보기" 드롭다운 (모바일)
 */
export const TAB_DEFS: TabDef[] = [
  { id: 'home', label: '홈', isDefault: true },
  { id: 'appointments', label: '외래', requiresFeature: 'appointments' },
  { id: 'inpatient', label: '입원', requiresFeature: 'inpatient' },
  { id: 'checkup', label: '건강검진', requiresFeature: 'checkup' },
  { id: 'guide', label: '안내' },
  { id: 'more', label: '더보기' },
];

/** 유효한 TabId인지 타입 guard */
export function isTabId(value: string | null | undefined): value is TabId {
  if (!value) return false;
  return TAB_DEFS.some((t) => t.id === value);
}

/** features flag 기반으로 노출될 탭만 필터 */
export function filterVisibleTabs(
  features: HospitalFeatures | undefined,
): TabDef[] {
  return TAB_DEFS.filter((t) => {
    if (!t.requiresFeature) return true;
    return Boolean(features?.[t.requiresFeature]);
  });
}
