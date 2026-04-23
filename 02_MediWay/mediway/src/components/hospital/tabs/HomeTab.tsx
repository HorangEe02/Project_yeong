import { WidgetSlot } from '@/components/hospital/widgets/WidgetSlot';
import { TodayScheduleWidget } from '@/components/hospital/widgets/TodayScheduleWidget';
import { WaitQueueWidget } from '@/components/hospital/widgets/WaitQueueWidget';
import { EmergencyCtaWidget } from '@/components/hospital/widgets/EmergencyCtaWidget';
import { SymptomTriageWidget } from '@/components/hospital/widgets/SymptomTriageWidget';
import { useHospital } from '@/hooks/useHospital';

/**
 * 홈 탭 — 개인화 대시보드.
 *
 * v2 §Phase 2: 위젯 정확히 3개 (+1 선택 슬롯은 병원별 커스터마이즈).
 * P3 C10: `features.aiTriage=true` 병원은 4번째 슬롯으로 SymptomTriageWidget.
 */
export function HomeTab() {
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
