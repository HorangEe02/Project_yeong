import { useEffect, useMemo, useState } from 'react';
import { Bell, CheckCircle2, PlayCircle } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';
import {
  callNext,
  completeEntry,
  getTodayDateKst,
  startConsultation,
  subscribeDeptQueue,
} from '@/services/waitQueue';
import type { WaitEntry } from '@/types/wait-queue';

/**
 * 의료진 대기 콘솔 — `/h/:slug/staff/queue`.
 *
 * P3 C4: 부서·날짜별 대기열 구독 + Call Next + 진료 시작/완료.
 * Push 알림 트리거는 C5에서 onQueueCall Cloud Function이 처리.
 */
export function StaffQueuePage() {
  const { slug } = useHospital();
  const hospitalId = slug ?? '';

  const [department, setDepartment] = useState('내과');
  const [date, setDate] = useState(() => getTodayDateKst());
  const [entries, setEntries] = useState<WaitEntry[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!hospitalId || !department || !date) {
      setEntries([]);
      return;
    }
    const unsub = subscribeDeptQueue(
      hospitalId,
      department,
      date,
      setEntries,
      (e) => setErr(e.message),
    );
    return () => unsub();
  }, [hospitalId, department, date]);

  const counts = useMemo(() => {
    const by = { waiting: 0, called: 0, 'in-progress': 0 };
    entries.forEach((e) => {
      if (e.status in by) by[e.status as keyof typeof by] += 1;
    });
    return by;
  }, [entries]);

  const onCallNext = async () => {
    if (!hospitalId) return;
    setErr(null);
    setBusyId('__next__');
    try {
      const next = await callNext(hospitalId, department, date);
      if (!next) setErr('대기 중인 환자가 없습니다.');
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const onStart = async (e: WaitEntry) => {
    if (!hospitalId) return;
    setErr(null);
    setBusyId(e.id);
    try {
      await startConsultation(hospitalId, e);
    } catch (err) {
      setErr(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  const onComplete = async (e: WaitEntry) => {
    if (!hospitalId) return;
    setErr(null);
    setBusyId(e.id);
    try {
      await completeEntry(hospitalId, e);
    } catch (err) {
      setErr(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
          Clinical Queue
        </p>
        <h1 className="text-2xl font-bold">대기 환자 호출 콘솔</h1>
        <p className="mt-1 text-sm text-on-surface-variant">
          부서·날짜별 실시간 대기열. 순번에 따라 환자를 호출합니다.
        </p>
      </div>

      <div className="mb-4 grid gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-4 sm:grid-cols-[1fr_auto_auto]">
        <label className="text-sm">
          진료과
          <input
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
            placeholder="예: 내과"
          />
        </label>
        <label className="text-sm">
          날짜
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={onCallNext}
            disabled={busyId !== null || counts.waiting === 0}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            <Bell className="h-4 w-4" />
            다음 환자 호출
          </button>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2 text-center text-sm">
        <StatPill label="대기" value={counts.waiting} tone="waiting" />
        <StatPill label="호출됨" value={counts.called} tone="called" />
        <StatPill
          label="진료 중"
          value={counts['in-progress']}
          tone="progress"
        />
      </div>

      {err && (
        <div className="mb-3 rounded-lg bg-error-container p-3 text-sm text-error">
          {err}
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {entries.length === 0 ? (
          <li className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6 text-center text-on-surface-variant">
            활성 대기 환자가 없습니다.
          </li>
        ) : (
          entries.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
            >
              <div className="flex items-center gap-4">
                <div className="min-w-14 rounded-lg bg-primary/10 px-3 py-2 text-center">
                  <div className="text-xs text-on-surface-variant">순번</div>
                  <div className="text-xl font-bold text-primary tabular-nums">
                    {e.number}
                  </div>
                </div>
                <div>
                  <div className="font-medium">환자 #{e.patientUid.slice(0, 6)}</div>
                  <StatusBadge status={e.status} />
                </div>
              </div>
              <div className="flex gap-2">
                {e.status === 'called' && (
                  <button
                    type="button"
                    onClick={() => onStart(e)}
                    disabled={busyId === e.id}
                    className="flex items-center gap-1 rounded-lg border border-primary px-3 py-2 text-sm text-primary disabled:opacity-50"
                  >
                    <PlayCircle className="h-4 w-4" />
                    진료 시작
                  </button>
                )}
                {(e.status === 'called' || e.status === 'in-progress') && (
                  <button
                    type="button"
                    onClick={() => onComplete(e)}
                    disabled={busyId === e.id}
                    className="flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-sm text-on-primary disabled:opacity-50"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    완료
                  </button>
                )}
              </div>
            </li>
          ))
        )}
      </ul>
    </main>
  );
}

function StatPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'waiting' | 'called' | 'progress';
}) {
  const toneCls = {
    waiting: 'bg-surface-container text-on-surface',
    called: 'bg-primary/10 text-primary',
    progress: 'bg-secondary-fixed text-primary',
  }[tone];
  return (
    <div className={`rounded-xl p-3 ${toneCls}`}>
      <div className="text-xs opacity-70">{label}</div>
      <div className="text-xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: WaitEntry['status'] }) {
  const m = {
    waiting: { label: '대기', cls: 'bg-surface-container text-on-surface-variant' },
    called: { label: '호출됨', cls: 'bg-primary/10 text-primary' },
    'in-progress': { label: '진료 중', cls: 'bg-secondary-fixed text-primary' },
    completed: { label: '완료', cls: 'bg-surface-container text-on-surface-variant' },
    cancelled: { label: '취소', cls: 'bg-error-container text-error' },
  } as const;
  const { label, cls } = m[status];
  return (
    <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs ${cls}`}>
      {label}
    </span>
  );
}
