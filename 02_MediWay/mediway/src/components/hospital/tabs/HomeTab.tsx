import { WidgetSlot } from '@/components/hospital/widgets/WidgetSlot';
import { TodayScheduleWidget } from '@/components/hospital/widgets/TodayScheduleWidget';
import { WaitQueueWidget } from '@/components/hospital/widgets/WaitQueueWidget';
import { EmergencyCtaWidget } from '@/components/hospital/widgets/EmergencyCtaWidget';
import { SymptomTriageWidget } from '@/components/hospital/widgets/SymptomTriageWidget';
import { useHospital } from '@/hooks/useHospital';
import { useSeniorMode } from '@/hooks/useSeniorMode';
import { SeniorHome } from './SeniorHome';

/**
 * 홈 탭 — 개인화 대시보드.
 *
 * 분기:
 *   - 고령자 모드 ON → SeniorHome (위젯 2~3개 + 인사, AI 제외)
 *   - 일반 → StandardHome (v2 §Phase 2: 위젯 3개 + aiTriage 병원이면 +1)
 */
export function HomeTab() {
  const { enabled: senior } = useSeniorMode();
  return senior ? <SeniorHome /> : <StandardHome />;
}

function StandardHome() {
  const { hospital } = useHospital();
  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <h2 className="sr-only">홈</h2>
      <WidgetSlot>
        <TodayScheduleWidget />
        <WaitQueueWidget />
        <EmergencyCtaWidget />
        {hospital?.features?.aiTriage ? <SymptomTriageWidget /> : null}
      </WidgetSlot>
    </main>
  );
}
