import { TodayScheduleWidget } from '@/components/hospital/widgets/TodayScheduleWidget';
import { WaitQueueWidget } from '@/components/hospital/widgets/WaitQueueWidget';
import { EmergencyCtaWidget } from '@/components/hospital/widgets/EmergencyCtaWidget';
import { useSeniorCopy } from '@/hooks/useSeniorCopy';

/**
 * 고령자 모드 전용 홈 탭 레이아웃.
 *
 * v2 §4.1: 위젯을 표준 4개 → 2~3개로 단순화, AI 요소 제외.
 * 인지부하 감소가 목표이므로 WidgetSlot 자동 배열 대신 명시적 flex로 배치.
 *
 * 구성:
 * 1. SeniorGreeting     — 오늘 날짜 + 인사 (심리적 안정감)
 * 2. 오늘 일정          — 가장 긴급한 관심사
 * 3. 진료 대기 순번      — 접수 후 상황 중요
 * 4. 응급실 바로가기     — 하단 고정 (v2 §4.5)
 *
 * AI 증상 triage·검진 추천 등 인지 부담 있는 요소는 senior 모드에서 제외.
 */
export function SeniorHome() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <h2 className="sr-only">홈</h2>
      <SeniorGreeting />
      <div className="flex flex-col gap-6">
        <TodayScheduleWidget />
        <WaitQueueWidget />
        <EmergencyCtaWidget />
      </div>
    </main>
  );
}

function SeniorGreeting() {
  const copy = useSeniorCopy();
  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });
  return (
    <section
      aria-label="오늘 날짜 인사"
      className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
    >
      <p className="text-sm text-on-surface-variant">{today}</p>
      <p className="mt-1 text-lg font-medium">
        {copy('greeting.wellbeing', '오늘도 건강하세요')}
      </p>
    </section>
  );
}
