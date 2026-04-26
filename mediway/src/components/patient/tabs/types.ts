/**
 * HospitalHomePage 의 6-tab 구성.
 *
 * ID는 URL query parameter `?tab=<id>` 값과 일치한다.
 * production bundle의 e2e-tab-session.html이 `appointments`·`guide`·`more`를
 * 참조하므로 그 네이밍을 따라 고정한다.
 */
export type TabId =
  | 'home'
  | 'appointments'
  | 'inpatient'
  | 'checkup'
  | 'guide'
  | 'more';

export interface TabSpec {
  id: TabId;
  label: string;
  /**
   * 탭이 활성화되려면 truthy 여야 하는 hospital feature key.
   *  - undefined  → 항상 표시 (`home`, `guide`, `more`)
   *  - 'appointments' → `features.appointments` 가 true 여야 표시
   *  - 'inpatient'    → `features.inpatient` 가 true 여야 표시
   *  - 'checkup'      → `features.checkup` 가 true 여야 표시
   *
   * `useHospitalFeatures()` 매트릭스의 키와 일치 (FEATURE_DEFAULTS 참조).
   */
  feature?: string;
}

export const TAB_ORDER: readonly TabSpec[] = [
  { id: 'home', label: '홈' },
  { id: 'appointments', label: '외래', feature: 'appointments' },
  { id: 'inpatient', label: '입원', feature: 'inpatient' },
  { id: 'checkup', label: '건강검진', feature: 'checkup' },
  { id: 'guide', label: '안내' },
  { id: 'more', label: '더보기' },
];

const VALID_TAB_IDS: ReadonlySet<string> = new Set(TAB_ORDER.map((t) => t.id));

/** 외부 입력(URL query 등)을 안전하게 정규화. 유효하지 않으면 'home'. */
export function normalizeTabId(raw: string | null | undefined): TabId {
  if (raw && VALID_TAB_IDS.has(raw)) return raw as TabId;
  return 'home';
}

/**
 * features 매트릭스에 따라 표시할 탭만 필터.
 *  - `feature` 미지정 → 항상 통과
 *  - `feature` 지정 → `features[feature] === true` 일 때만 통과
 *
 * `home` 은 안전망으로 항상 첫 위치에 보장되도록 호출 측이 결과 길이가 1 이상인지 확인.
 */
export function visibleTabs(
  features: Readonly<Record<string, boolean>>,
): TabSpec[] {
  return TAB_ORDER.filter((t) => !t.feature || features[t.feature] === true);
}

/**
 * URL `?tab=` 또는 사용자 선택 값이 features 에 의해 비활성화된 경우 'home' 으로 fallback.
 * 활성화된 탭이라면 그대로 반환.
 */
export function ensureVisibleTab(
  desired: TabId,
  features: Readonly<Record<string, boolean>>,
): TabId {
  const spec = TAB_ORDER.find((t) => t.id === desired);
  if (!spec) return 'home';
  if (spec.feature && features[spec.feature] !== true) return 'home';
  return desired;
}
