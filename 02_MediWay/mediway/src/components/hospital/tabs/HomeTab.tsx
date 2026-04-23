import { WidgetSlot } from '@/components/hospital/widgets/WidgetSlot';
import { TodayScheduleWidget } from '@/components/hospital/widgets/TodayScheduleWidget';
import { WaitQueueWidget } from '@/components/hospital/widgets/WaitQueueWidget';
import { EmergencyCtaWidget } from '@/components/hospital/widgets/EmergencyCtaWidget';

/**
 * 홈 탭 — 개인화 대시보드.
 *
 * v2 §Phase 2: 위젯 정확히 3개 (+1 선택 슬롯은 병원별 커스터마이즈 추후).
 *
 * 1. TodayScheduleWidget — 오늘 일정 (C4 appointments 연동 전 placeholder)
 * 2. WaitQueueWidget — 대기 순번 (P3 F1 실시간 연동 전 placeholder)
 * 3. EmergencyCtaWidget — 응급실 CTA (P4 F10을 P2로 당김)
 */
export function HomeTab() {
  return (
    <>
      <h2 className="sr-only">홈</h2>
      <WidgetSlot>
        <TodayScheduleWidget />
        <WaitQueueWidget />
        <EmergencyCtaWidget />
      </WidgetSlot>
    </>
  );
}
