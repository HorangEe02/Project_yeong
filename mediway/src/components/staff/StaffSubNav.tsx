import { Link } from 'react-router-dom';
import { useHospital } from '@/contexts/HospitalContext';

export type StaffSubNavTab = 'dashboard' | 'queue';

interface SubNavSpec {
  id: StaffSubNavTab;
  label: string;
  /** 슬러그를 받아 전체 경로로 변환 */
  to: (slug: string) => string;
}

const TABS: readonly SubNavSpec[] = [
  { id: 'dashboard', label: '동선 전송', to: (s) => `/h/${s}/staff` },
  { id: 'queue', label: '대기열 콘솔', to: (s) => `/h/${s}/staff/queue` },
];

/**
 * `/h/:slug/staff` 와 `/h/:slug/staff/queue` 사이 공통 sub-navigation.
 *
 * F1.2 도입: 두 페이지 사이 내부 링크가 0건이라 staff 가 콘솔을 발견하기 어려운
 * UX 문제 해소. StaffShell wrapper 까지 만드는 안은 비범위 — 본 컴포넌트는
 * 단순 NavLink 묶음.
 *
 * 마운트 위치:
 *  - StaffPage 상단 (`active="dashboard"`)
 *  - StaffQueuePage 상단 (`active="queue"`)
 *
 * 슬러그는 `useHospital()` 컨텍스트에서 가져옴 — Shell 외부에서 사용 시 throw.
 */
export function StaffSubNav({ active }: { active: StaffSubNavTab }) {
  const { slug } = useHospital();
  return (
    <nav
      aria-label="의료진 메뉴"
      className="mb-4 flex w-full max-w-md gap-1 rounded-xl bg-surface-container-high p-1 sm:w-auto"
    >
      {TABS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <Link
            key={tab.id}
            to={tab.to(slug)}
            aria-current={isActive ? 'page' : undefined}
            className={`flex-1 whitespace-nowrap rounded-lg px-4 py-2 text-center text-sm font-medium transition-colors no-underline sm:flex-none ${
              isActive
                ? 'bg-surface-container-lowest text-primary shadow-ambient'
                : 'text-on-surface-variant hover:bg-surface-container'
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
