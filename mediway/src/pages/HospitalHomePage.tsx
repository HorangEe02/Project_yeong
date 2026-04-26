import { useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { HomeTab } from '@/components/patient/tabs/HomeTab';
import { AppointmentsTab } from '@/components/patient/tabs/AppointmentsTab';
import { InpatientTab } from '@/components/patient/tabs/InpatientTab';
import { CheckupTab } from '@/components/patient/tabs/CheckupTab';
import { GuideTab } from '@/components/patient/tabs/GuideTab';
import { MoreTab } from '@/components/patient/tabs/MoreTab';
import {
  ensureVisibleTab,
  normalizeTabId,
  visibleTabs,
  type TabId,
} from '@/components/patient/tabs/types';
import { useHospital, useHospitalFeatures } from '@/contexts/HospitalContext';

/**
 * `/h/:hospitalSlug/patient/home?tab=<id>` 환자용 탭 셸.
 *
 * 원칙:
 * - **Mount-all + hidden**: 6개 탭을 동시에 마운트하고 비활성 탭은 `hidden` 속성으로 감춘다.
 *   → 탭 전환 시 폼 입력·지도 viewport·구독 상태가 보존된다.
 * - **URL as source-of-truth**: `activeTab`은 `?tab=` 쿼리에서 파생. `?tab=` 누락/invalid면 'home'.
 * - **replace navigation**: 탭 전환은 history stack을 늘리지 않는다 (뒤로가기 한 번으로 페이지 전체 이탈).
 *   이 동작은 e2e-tab-session.html 시나리오 D 기대와 다를 수 있어 후속 검증 대상.
 *
 * 슬러그 검증은 부모 `<HospitalShell>` 가 처리 — 여기에 진입하는 시점에는 profile 보장됨.
 */
/** TabId → 패널 컴포넌트 매핑. features 에 의해 숨겨진 탭은 마운트도 하지 않는다 (구독 누수 방지). */
const TAB_PANELS: Record<TabId, () => JSX.Element> = {
  home: () => <HomeTab />,
  appointments: () => <AppointmentsTab />,
  inpatient: () => <InpatientTab />,
  checkup: () => <CheckupTab />,
  guide: () => <GuideTab />,
  more: () => <MoreTab />,
};

export function HospitalHomePage() {
  const { profile } = useHospital();
  const features = useHospitalFeatures();
  const [searchParams, setSearchParams] = useSearchParams();

  /** 사용자가 의도한 탭 (URL ?tab=) — features 검증 전 raw 값 */
  const desiredTab = useMemo<TabId>(
    () => normalizeTabId(searchParams.get('tab')),
    [searchParams],
  );

  /** 실제 활성 탭 — features 가 비활성화한 탭이면 'home' 으로 fallback */
  const activeTab = useMemo<TabId>(
    () => ensureVisibleTab(desiredTab, features),
    [desiredTab, features],
  );

  /** 사용자가 비활성 탭 URL 로 진입한 경우 URL 도 'home' 으로 정정 (지속 가능 상태 만들기) */
  useEffect(() => {
    if (activeTab !== desiredTab) {
      setSearchParams({ tab: activeTab }, { replace: true });
    }
  }, [activeTab, desiredTab, setSearchParams]);

  /** features 매트릭스에 따라 노출할 탭만 — admin 토글 즉시 반영 */
  const tabsToRender = useMemo(() => visibleTabs(features), [features]);

  const handleTabChange = useCallback(
    (next: TabId) => {
      setSearchParams({ tab: next }, { replace: true });
    },
    [setSearchParams],
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-4">
      {/* 병원명 — HospitalShell 의 useHospital() 컨텍스트에서 주입 */}
      <p className="mb-2 text-xs font-medium text-on-surface-variant">
        {profile.name}
      </p>

      <nav
        role="tablist"
        aria-label="환자 메뉴"
        className="sticky top-[60px] z-10 flex gap-1 overflow-x-auto border-b border-outline-variant bg-surface py-2"
      >
        {tabsToRender.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`tab-panel-${tab.id}`}
              onClick={() => handleTabChange(tab.id)}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary text-on-primary'
                  : 'text-on-surface-variant hover:bg-surface-container-low'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      <main className="mt-3">
        {tabsToRender.map((tab) => {
          const Panel = TAB_PANELS[tab.id];
          return (
            <div
              key={tab.id}
              role="tabpanel"
              id={`tab-panel-${tab.id}`}
              hidden={activeTab !== tab.id}
            >
              <Panel />
            </div>
          );
        })}
      </main>
    </div>
  );
}
