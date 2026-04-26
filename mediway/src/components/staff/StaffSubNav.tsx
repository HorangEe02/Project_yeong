import { Link } from 'react-router-dom';
import { useHospital, useFeature } from '@/contexts/HospitalContext';

export type StaffSubNavTab = 'dashboard' | 'queue' | 'emergency';

interface SubNavSpec {
  id: StaffSubNavTab;
  label: string;
  /** 슬러그를 받아 전체 경로로 변환 */
  to: (slug: string) => string;
  /** 'error' tone 은 응급 탭의 빨간 강조용 */
  tone?: 'error';
}

const TABS: readonly SubNavSpec[] = [
  { id: 'dashboard', label: '동선 전송', to: (s) => `/h/${s}/staff` },
  { id: 'queue', label: '대기열 콘솔', to: (s) => `/h/${s}/staff/queue` },
  {
    id: 'emergency',
    label: '응급',
    to: (s) => `/h/${s}/staff/emergency`,
    tone: 'error',
  },
];

/**
 * `/h/:slug/staff` 의 sub-navigation — 「동선 전송 / 대기열 콘솔 / 응급」.
 *
 * 가운데 정렬 정책 (2026-04-26):
 *  - `mx-auto` + `justify-center` — 부모 컨테이너 폭과 무관하게 항상 가운데
 *  - StaffPage(max-w-5xl) ↔ StaffQueuePage(max-w-3xl) 폭 차이로 탭이 좌측·우측으로
 *    이동하던 문제 해소
 *
 * 응급 탭 (2026-04-26):
 *  - features.emergencyCall 가드 — false 면 미노출 (default true)
 *  - 빨간 강조 (tone='error') — 즉시 식별
 *
 * 슬러그는 `useHospital()` 컨텍스트에서 가져옴 — Shell 외부에서 사용 시 throw.
 */
export function StaffSubNav({ active }: { active: StaffSubNavTab }) {
  const { slug } = useHospital();
  const emergencyOn = useFeature('emergencyCall');

  const visibleTabs = TABS.filter(
    (t) => t.id !== 'emergency' || emergencyOn,
  );

  return (
    <nav
      aria-label="의료진 메뉴"
      className="mx-auto mb-4 flex w-full max-w-2xl justify-center gap-1 rounded-xl bg-surface-container-high p-1 sm:w-auto"
    >
      {visibleTabs.map((tab) => {
        const isActive = tab.id === active;
        const errorTone = tab.tone === 'error';
        const activeClass = errorTone
          ? 'bg-surface-container-lowest text-error shadow-ambient'
          : 'bg-surface-container-lowest text-primary shadow-ambient';
        const inactiveClass = errorTone
          ? 'text-error/80 hover:bg-surface-container'
          : 'text-on-surface-variant hover:bg-surface-container';
        return (
          <Link
            key={tab.id}
            to={tab.to(slug)}
            aria-current={isActive ? 'page' : undefined}
            data-testid={`staff-nav-${tab.id}`}
            className={`flex-1 whitespace-nowrap rounded-lg px-4 py-2 text-center text-sm font-medium transition-colors no-underline sm:flex-none ${
              isActive ? activeClass : inactiveClass
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
