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
}

export const TAB_ORDER: readonly TabSpec[] = [
  { id: 'home', label: '홈' },
  { id: 'appointments', label: '외래' },
  { id: 'inpatient', label: '입원' },
  { id: 'checkup', label: '건강검진' },
  { id: 'guide', label: '안내' },
  { id: 'more', label: '더보기' },
];

const VALID_TAB_IDS: ReadonlySet<string> = new Set(TAB_ORDER.map((t) => t.id));

/** 외부 입력(URL query 등)을 안전하게 정규화. 유효하지 않으면 'home'. */
export function normalizeTabId(raw: string | null | undefined): TabId {
  if (raw && VALID_TAB_IDS.has(raw)) return raw as TabId;
  return 'home';
}
