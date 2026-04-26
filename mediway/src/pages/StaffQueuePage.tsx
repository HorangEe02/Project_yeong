import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useHospital } from '@/contexts/HospitalContext';
import { StaffSubNav } from '@/components/staff/StaffSubNav';
import {
  callNextWaiting,
  markCompleted,
  markInProgress,
  subscribeDeptQueue,
  todayDateKST,
} from '@/services/waitQueue';
import type { WaitQueueEntry, WaitQueueStatus } from '@/types/waitQueue';

/**
 * 의료진 대기열 콘솔.
 *
 * 경로: `/h/:slug/staff/queue` (B-3.10 nested routing 이후).
 *
 * Slug 소스 (F1.2):
 *  - 이전: `profile.hospitalId` (사용자 home hospital)
 *  - 현재: `useHospital().slug` (URL 기준 — staff 가 다른 병원 방문 시 정합)
 *
 * 역할:
 *  - `/hospitals/{slug}/wait_queue/{dept}/{date}` 실시간 구독
 *  - "다음 환자 호출" → callNextWaiting (lowest-number waiting → called)
 *  - 카드별 [진료 시작] / [완료] 액션
 *  - 상단 stats: 대기 / 호출됨 / 진료 중 카운트
 *  - 상단 sub-nav (F1.2) — 동선 전송 ↔ 대기열 콘솔
 *
 * UX 원칙:
 *  - Call Next 버튼 urgency 강조 (primary color + 큰 터치 타겟)
 *  - 호출된 카드는 ring 강조 → staff 가 즉시 인지
 *  - 액션 실패는 inline 에러 배너 (페이지 reload 없이 복구)
 *  - 빈 상태는 소극적 회색 텍스트
 *
 * TODO(별도 sprint):
 *  - 부서 목록을 `/hospitals/{slug}/departments` 에서 동기화 (현재는 하드코딩)
 *  - "오늘만" vs "완료 포함" 토글 (includeCompleted)
 *  - 호출 취소 / 재호출 버튼
 *  - 호출 후 N 분 무응답 → 자동 스킵 제안
 */

const DEPARTMENTS = [
  '내과',
  '외과',
  '정형외과',
  '소아청소년과',
  '가정의학과',
  '응급의학과',
  '영상의학과',
];

const STATUS_LABELS: Record<WaitQueueStatus, string> = {
  waiting: '대기',
  called: '호출됨',
  'in-progress': '진료 중',
  completed: '완료',
  cancelled: '취소',
};

export function StaffQueuePage() {
  const { slug: hospitalId } = useHospital();

  const [department, setDepartment] = useState<string>(DEPARTMENTS[0]);
  const [date, setDate] = useState<string>(() => todayDateKST());
  const [entries, setEntries] = useState<WaitQueueEntry[]>([]);
  const [subError, setSubError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [callingNext, setCallingNext] = useState(false);

  useEffect(() => {
    const unsub = subscribeDeptQueue(
      hospitalId,
      department,
      date,
      (data) => {
        setEntries(data);
        setSubError(null);
      },
      (err) => setSubError(err.message || '대기열 구독 실패'),
    );
    return unsub;
  }, [hospitalId, department, date]);

  const stats = useMemo(() => {
    const s = { waiting: 0, called: 0, 'in-progress': 0 };
    for (const e of entries) {
      if (e.status === 'waiting') s.waiting += 1;
      else if (e.status === 'called') s.called += 1;
      else if (e.status === 'in-progress') s['in-progress'] += 1;
    }
    return s;
  }, [entries]);

  const handleCallNext = useCallback(async () => {
    if (callingNext) return;
    setCallingNext(true);
    setActionError(null);
    try {
      const called = await callNextWaiting(hospitalId, department, date);
      if (!called) setActionError('호출할 대기 환자가 없습니다.');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '호출 처리 실패');
    } finally {
      setCallingNext(false);
    }
  }, [hospitalId, department, date, callingNext]);

  const handleStart = useCallback(
    async (entry: WaitQueueEntry) => {
      setActionError(null);
      try {
        await markInProgress(hospitalId, entry);
      } catch (err) {
        setActionError(err instanceof Error ? err.message : '진료 시작 실패');
      }
    },
    [hospitalId],
  );

  const handleComplete = useCallback(
    async (entry: WaitQueueEntry) => {
      setActionError(null);
      try {
        await markCompleted(hospitalId, entry);
      } catch (err) {
        setActionError(err instanceof Error ? err.message : '완료 처리 실패');
      }
    },
    [hospitalId],
  );

  // hospitalId 는 useHospital() 으로부터 항상 보장 — HospitalShell ready 상태에서만 마운트.

  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      {/* F1.2: dashboard ↔ queue 발견성 보강 */}
      <StaffSubNav active="queue" />
      <header className="mb-4">
        <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
          Clinical Queue
        </p>
        <h1 className="text-2xl font-bold text-on-surface">대기 환자 호출 콘솔</h1>
        <p className="mt-1 text-sm text-on-surface-variant">
          부서·날짜별 실시간 대기열. 순번에 따라 환자를 호출합니다.
        </p>
      </header>

      <div className="mb-4 grid gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-4 sm:grid-cols-[1fr_auto_auto]">
        <label className="relative">
          <span className="mb-1 block text-xs font-medium text-on-surface-variant">부서</span>
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="w-full appearance-none rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 pr-8 text-sm text-on-surface"
          >
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-[28px] h-4 w-4 text-on-surface-variant" />
        </label>
        <label>
          <span className="mb-1 block text-xs font-medium text-on-surface-variant">날짜</span>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm text-on-surface"
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={handleCallNext}
            disabled={callingNext || stats.waiting === 0}
            className="w-full whitespace-nowrap rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary transition-opacity disabled:opacity-50"
          >
            {callingNext ? '호출 중...' : '다음 환자 호출'}
          </button>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2 text-center text-sm">
        <Stat label="대기" value={stats.waiting} tone="waiting" />
        <Stat label="호출됨" value={stats.called} tone="called" />
        <Stat label="진료 중" value={stats['in-progress']} tone="progress" />
      </div>

      {subError && (
        <div className="mb-3 rounded-lg bg-error-container p-3 text-sm text-error">
          {subError}
        </div>
      )}
      {actionError && (
        <div className="mb-3 rounded-lg bg-error-container p-3 text-sm text-error">
          {actionError}
        </div>
      )}

      {entries.length === 0 ? (
        <p className="rounded-xl bg-surface-container-lowest p-6 text-center text-sm text-on-surface-variant">
          대기 중인 환자가 없습니다.
        </p>
      ) : (
        <ul className="space-y-2">
          {entries.map((e) => (
            <QueueCard
              key={e.id}
              entry={e}
              onStart={() => handleStart(e)}
              onComplete={() => handleComplete(e)}
            />
          ))}
        </ul>
      )}
    </main>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'waiting' | 'called' | 'progress';
}) {
  const toneClass = {
    waiting: 'bg-surface-container text-on-surface',
    called: 'bg-primary/10 text-primary',
    progress: 'bg-secondary-fixed text-primary',
  }[tone];
  return (
    <div className={`rounded-lg py-3 ${toneClass}`}>
      <p className="text-xs font-medium uppercase tracking-wider opacity-80">{label}</p>
      <p className="mt-1 text-xl font-bold tabular-nums">{value}</p>
    </div>
  );
}

function QueueCard({
  entry,
  onStart,
  onComplete,
}: {
  entry: WaitQueueEntry;
  onStart: () => void;
  onComplete: () => void;
}) {
  const isCalled = entry.status === 'called';
  const isInProgress = entry.status === 'in-progress';
  return (
    <li
      className={`flex items-center gap-3 rounded-xl p-4 ${
        isCalled
          ? 'bg-primary/5 ring-2 ring-primary'
          : 'bg-surface-container-lowest'
      }`}
    >
      <div className="flex-1">
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-bold text-primary tabular-nums">{entry.number}</span>
          <span className="rounded-full bg-surface-container px-2 py-0.5 text-xs text-on-surface-variant">
            {STATUS_LABELS[entry.status]}
          </span>
        </div>
        <p className="mt-1 text-xs text-on-surface-variant">
          환자 UID: <code>{entry.patientUid.slice(0, 8)}…</code>
          {entry.appointmentId && (
            <>
              {' · 예약 연결: '}
              <code>{entry.appointmentId.slice(0, 6)}…</code>
            </>
          )}
        </p>
      </div>
      {isCalled && (
        <button
          type="button"
          onClick={onStart}
          className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-on-primary"
        >
          진료 시작
        </button>
      )}
      {isInProgress && (
        <button
          type="button"
          onClick={onComplete}
          className="rounded-lg border border-primary px-3 py-2 text-sm font-medium text-primary"
        >
          완료
        </button>
      )}
    </li>
  );
}
