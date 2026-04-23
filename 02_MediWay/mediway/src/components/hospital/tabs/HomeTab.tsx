import { TodayScheduleWidget } from '@/components/hospital/widgets/TodayScheduleWidget';
import { WaitQueueWidget } from '@/components/hospital/widgets/WaitQueueWidget';
import { EmergencyCtaWidget } from '@/components/hospital/widgets/EmergencyCtaWidget';
import { SymptomTriageWidget } from '@/components/hospital/widgets/SymptomTriageWidget';
import { HomeGreeting } from '@/components/hospital/home/HomeGreeting';
import { QuickActionRow } from '@/components/hospital/home/QuickActionRow';
import { RecentResultsStub } from '@/components/hospital/home/RecentResultsStub';
import { useHospital } from '@/hooks/useHospital';
import { useSeniorMode } from '@/hooks/useSeniorMode';
import { SeniorHome } from './SeniorHome';

/**
 * 홈 탭 — 개인화 대시보드.
 *
 * 분기:
 *   - 고령자 모드 ON → SeniorHome (단순화된 액션 런처 + 응급)
 *   - 일반 → StandardHome (시안 PlusUltra SaaS 1 정렬: 2컬럼 + Greeting + QuickActions)
 *
 * P4.U U2: 데스크톱에서 좌 1.5 (일정 + AI) / 우 1 (대기·응급·결과stub) 그리드.
 * 모바일(< lg)은 1컬럼 stack으로 fallback.
 */
export function HomeTab() {
  const { enabled: senior } = useSeniorMode();
  return senior ? <SeniorHome /> : <StandardHome />;
}

function StandardHome() {
  const { hospital } = useHospital();
  const aiTriage = Boolean(hospital?.features?.aiTriage);
  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-6xl">
      <h2 className="sr-only">홈</h2>
      <HomeGreeting />
      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <section aria-label="오늘 일정 영역" className="flex flex-col gap-4">
          <TodayScheduleWidget />
          {aiTriage ? <SymptomTriageWidget /> : null}
        </section>
        <aside
          aria-label="대기·응급·결과 영역"
          className="flex flex-col gap-4"
        >
          <WaitQueueWidget />
          <EmergencyCtaWidget />
          <RecentResultsStub />
        </aside>
      </div>
      <section aria-label="빠른 작업" className="mt-6">
        <QuickActionRow />
      </section>
    </main>
  );
}
