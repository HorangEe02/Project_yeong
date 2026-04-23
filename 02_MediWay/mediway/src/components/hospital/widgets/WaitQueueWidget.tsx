import { Clock } from 'lucide-react';

/**
 * 대기 순번 위젯 — v2 홈 위젯 #2.
 *
 * P2 C3: placeholder. 실시간 대기 로직은 P3 F1에서 /wait_queue 구독.
 */
export function WaitQueueWidget() {
  return (
    <article
      className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
      aria-labelledby="wait-queue-title"
    >
      <header className="mb-2 flex items-center gap-2">
        <Clock className="h-5 w-5 text-primary" aria-hidden="true" />
        <h3 id="wait-queue-title" className="text-base font-semibold">
          진료 대기
        </h3>
      </header>
      <p className="text-sm text-on-surface-variant">
        접수 후 대기 순번이 이곳에 표시됩니다.
      </p>
    </article>
  );
}
