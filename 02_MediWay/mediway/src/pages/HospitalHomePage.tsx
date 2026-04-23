import { HospitalTabs } from '@/components/hospital/HospitalTabs';
import { TabErrorBoundary } from '@/components/hospital/TabErrorBoundary';
import { HomeTab } from '@/components/hospital/tabs/HomeTab';
import { AppointmentsTab } from '@/components/hospital/tabs/AppointmentsTab';
import { InpatientTab } from '@/components/hospital/tabs/InpatientTab';
import { CheckupTab } from '@/components/hospital/tabs/CheckupTab';
import { GuideTab } from '@/components/hospital/tabs/GuideTab';
import { MoreTab } from '@/components/hospital/tabs/MoreTab';
import { useHospital } from '@/hooks/useHospital';
import { useTabState } from '@/hooks/useTabState';
import { useFcmToken } from '@/hooks/useFcmToken';
import type { TabId } from '@/types/tabs';
import type { ReactNode } from 'react';

/**
 * 병원 환자 대시보드 홈.
 *
 * URL: `/h/:slug/patient/home?tab=<id>`
 *
 * 전략 (v2 §Phase 2 "세션 보존 최우선"):
 * - Mount-all — 모든 탭 DOM에 마운트, `hidden` 속성으로 visibility 토글
 * - 탭 전환해도 입력 상태·QR 스캐너·구독 그대로 유지
 * - TabErrorBoundary로 탭 간 격리 (한 탭 에러가 다른 탭 안 깨뜨림)
 */
export function HospitalHomePage() {
  const { hospital } = useHospital();
  const { activeTab, visibleTabs, setTab } = useTabState(hospital?.features);
  useFcmToken();

  return (
    <div className="flex min-h-[calc(100vh-64px)] flex-col">
      <HospitalTabs
        tabs={visibleTabs}
        activeTab={activeTab}
        onChange={setTab}
      />
      <div className="flex-1">
        <TabPanel id="home" active={activeTab === 'home'}>
          <TabErrorBoundary tabLabel="홈">
            <HomeTab />
          </TabErrorBoundary>
        </TabPanel>
        <TabPanel id="appointments" active={activeTab === 'appointments'}>
          <TabErrorBoundary tabLabel="외래">
            <AppointmentsTab />
          </TabErrorBoundary>
        </TabPanel>
        <TabPanel id="inpatient" active={activeTab === 'inpatient'}>
          <TabErrorBoundary tabLabel="입원">
            <InpatientTab />
          </TabErrorBoundary>
        </TabPanel>
        <TabPanel id="checkup" active={activeTab === 'checkup'}>
          <TabErrorBoundary tabLabel="건강검진">
            <CheckupTab />
          </TabErrorBoundary>
        </TabPanel>
        <TabPanel id="guide" active={activeTab === 'guide'}>
          <TabErrorBoundary tabLabel="안내">
            <GuideTab />
          </TabErrorBoundary>
        </TabPanel>
        <TabPanel id="more" active={activeTab === 'more'}>
          <TabErrorBoundary tabLabel="더보기">
            <MoreTab />
          </TabErrorBoundary>
        </TabPanel>
      </div>
    </div>
  );
}

function TabPanel({
  id,
  active,
  children,
}: {
  id: TabId;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <section
      role="tabpanel"
      id={`tabpanel-${id}`}
      aria-labelledby={`tab-${id}`}
      hidden={!active}
    >
      {children}
    </section>
  );
}
