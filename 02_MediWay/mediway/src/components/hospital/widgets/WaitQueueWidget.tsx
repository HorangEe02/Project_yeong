import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';
import { useAuthStore } from '@/stores/authStore';
import { subscribeMyEntries } from '@/services/waitQueue';
import type { WaitEntryIndex } from '@/types/wait-queue';
import { isActiveStatus } from '@/types/wait-queue';

/**
 * 대기 순번 위젯 — v2 홈 위젯 #2.
 *
 * P3 C3: `/wait_queue_by_patient/{uid}` 실시간 구독.
 * 활성(waiting/called/in-progress) entry 중 가장 앞선 것을 우선 표시.
 */
export function WaitQueueWidget() {
  const { slug } = useHospital();
  const uid = useAuthStore((s) => s.user?.uid);
  const hospitalId = slug ?? '';

  const [entries, setEntries] = useState<Array<WaitEntryIndex & { id: string }>>(
    [],
  );

  useEffect(() => {
    if (!hospitalId || !uid) {
      setEntries([]);
      return;
    }
    const unsub = subscribeMyEntries(hospitalId, uid, setEntries);
    return () => unsub();
  }, [hospitalId, uid]);

  const active = entries.filter((e) => isActiveStatus(e.status));
  const current = active[0] ?? null;

  return (
    <article
      className={`rounded-xl border p-4 transition-colors ${
        current?.status === 'called'
          ? 'border-primary bg-primary-container/40'
          : 'border-outline-variant bg-surface-container-lowest'
      }`}
      aria-labelledby="wait-queue-title"
    >
      <header className="mb-2 flex items-center gap-2">
        <Clock className="h-5 w-5 text-primary" aria-hidden="true" />
        <h3 id="wait-queue-title" className="text-base font-semibold">
          진료 대기
        </h3>
      </header>

      {!current ? (
        <p className="text-sm text-on-surface-variant">
          접수된 진료가 없습니다.
        </p>
      ) : (
        <div className="space-y-1">
          <p className="text-sm text-on-surface-variant">
            {current.department} · {current.date}
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            순번 <span className="text-primary">{current.number}</span>번
          </p>
          <StatusLine status={current.status} />
        </div>
      )}
    </article>
  );
}

function StatusLine({ status }: { status: WaitEntryIndex['status'] }) {
  if (status === 'called') {
    return (
      <p className="text-sm font-medium text-primary">
        호출됨 — 진료실로 이동해 주세요
      </p>
    );
  }
  if (status === 'in-progress') {
    return <p className="text-sm text-on-surface-variant">진료 중</p>;
  }
  return <p className="text-sm text-on-surface-variant">대기 중</p>;
}
