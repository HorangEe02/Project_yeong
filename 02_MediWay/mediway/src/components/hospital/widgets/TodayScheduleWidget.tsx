import { Calendar } from 'lucide-react';

/**
 * 오늘 일정 위젯 — v2 홈 위젯 #1.
 *
 * P2 C3: 빈 상태 UI만. 실제 일정 데이터는 C4 appointments 서비스 구독.
 * 현재는 "오늘 일정 없음" placeholder 유지.
 */
export function TodayScheduleWidget() {
  return (
    <article
      className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
      aria-labelledby="today-schedule-title"
    >
      <header className="mb-2 flex items-center gap-2">
        <Calendar className="h-5 w-5 text-primary" aria-hidden="true" />
        <h3 id="today-schedule-title" className="text-base font-semibold">
          오늘 일정
        </h3>
      </header>
      <p className="text-sm text-on-surface-variant">
        오늘 예정된 진료나 검사가 없습니다.
      </p>
    </article>
  );
}
