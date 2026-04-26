import { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useHospital } from '@/contexts/HospitalContext';
import {
  cancelAppointment,
  createAppointment,
  subscribeMyAppointments,
} from '@/services/appointments';
import {
  checkInToQueue,
  subscribeMyWaitQueue,
  todayDateKST,
} from '@/services/waitQueue';
import type {
  AppointmentPatientIndex,
  AppointmentStatus,
} from '@/types/appointment';
import type { WaitQueuePatientIndex } from '@/types/waitQueue';

/**
 * 외래 탭 — 환자의 예약 목록 + 접수 + 취소 + 새 예약.
 *
 * 데이터 소스:
 *  - `subscribeMyAppointments` → 예약 레코드 (scheduledAt 오름차순)
 *  - `subscribeMyWaitQueue` → 오늘 접수된 wait_queue 엔트리 (접수 상태 판별용)
 *
 * Slug 소스 (F1.1d):
 *  - 이전: `profile.hospitalId` (사용자 home hospital)
 *  - 현재: `useHospital().slug` (URL `/h/{slug}/...` 의 현재 방문 병원)
 *  - cross-tenant 차단은 HospitalShell 가드가 담당.
 *
 * 마운트 가드:
 *  - HospitalHomePage 가 features.appointments=true 일 때만 본 탭을 마운트
 *    (commit F1.1b 의 visibleTabs). 본 컴포넌트는 그 전제 위에서 동작.
 *
 * 상태별 카드 동작:
 *  - scheduled + 오늘이면서 아직 접수 안 됨: [접수] + [X 취소]
 *  - scheduled + 이미 접수됨: '접수됨' 뱃지 + [X 취소] (접수 취소는 별도 flow)
 *  - scheduled + 과거: '지난 일정' 표시만, 액션 없음
 *  - cancelled / completed: 뱃지만, 액션 없음
 *
 * 새 예약 form:
 *  - 부서 select + 일시 (datetime-local) + 진료 시간 (min) + 메모 (선택)
 *
 * TODO(별도 sprint):
 *  - 부서 목록을 hospitals/{slug}/departments 동기화 (현 schema 미정)
 *  - 반복 예약 / 예약 수정
 *  - 담당 의료진 선택
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

const STATUS_LABELS: Record<AppointmentStatus, string> = {
  scheduled: '예약됨',
  cancelled: '취소됨',
  completed: '완료',
};

const STATUS_STYLES: Record<AppointmentStatus, string> = {
  scheduled: 'bg-primary/10 text-primary',
  cancelled: 'bg-surface-container text-on-surface-variant line-through',
  completed: 'bg-surface-container text-on-surface-variant',
};

export function AppointmentsTab() {
  const user = useAuthStore((s) => s.user);
  const { slug: hospitalId } = useHospital();
  const uid = user?.uid ?? null;
  const isAnon = user?.isAnonymous ?? true;

  const [appointments, setAppointments] = useState<AppointmentPatientIndex[]>([]);
  const [waitQueue, setWaitQueue] = useState<WaitQueuePatientIndex[]>([]);
  const [subError, setSubError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyApptId, setBusyApptId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    if (!uid || isAnon) return;
    const unsubA = subscribeMyAppointments(
      hospitalId,
      uid,
      (list) => {
        setAppointments(list);
        setSubError(null);
      },
      (err) => setSubError(err.message || '예약 구독 실패'),
    );
    const unsubQ = subscribeMyWaitQueue(hospitalId, uid, (list) => setWaitQueue(list));
    return () => {
      unsubA();
      unsubQ();
    };
  }, [hospitalId, uid, isAnon]);

  const today = useMemo(() => todayDateKST(), []);

  const isCheckedInToday = useCallback(
    (dept: string) =>
      waitQueue.some(
        (w) =>
          w.department === dept &&
          w.date === today &&
          w.status !== 'completed' &&
          w.status !== 'cancelled',
      ),
    [waitQueue, today],
  );

  const isToday = useCallback((scheduledAt: number) => {
    const d = new Date(scheduledAt + 9 * 60 * 60 * 1000);
    return d.toISOString().slice(0, 10) === today;
  }, [today]);

  const handleCheckIn = useCallback(
    async (appt: AppointmentPatientIndex) => {
      if (!uid) return;
      setActionError(null);
      setBusyApptId(appt.id);
      try {
        await checkInToQueue(hospitalId, uid, {
          department: appt.department,
          date: today,
          appointmentId: appt.id,
        });
      } catch (err) {
        setActionError(err instanceof Error ? err.message : '접수 실패');
      } finally {
        setBusyApptId(null);
      }
    },
    [hospitalId, uid, today],
  );

  const handleCancel = useCallback(
    async (appt: AppointmentPatientIndex) => {
      if (!uid) return;
      setActionError(null);
      setBusyApptId(appt.id);
      try {
        await cancelAppointment(hospitalId, uid, appt.id);
      } catch (err) {
        setActionError(err instanceof Error ? err.message : '취소 실패');
      } finally {
        setBusyApptId(null);
      }
    },
    [hospitalId, uid],
  );

  if (!user || isAnon) {
    return (
      <section className="space-y-4 p-4">
        <p className="text-sm text-on-surface-variant">로그인하면 예약을 관리할 수 있습니다.</p>
      </section>
    );
  }
  // hospitalId 는 useHospital() 으로부터 항상 보장됨 (HospitalShell ready 상태에서만 마운트).

  return (
    <section className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-on-surface">외래</h2>
        <button
          type="button"
          onClick={() => setFormOpen((o) => !o)}
          className="flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-on-primary"
        >
          <Plus className="h-4 w-4" />
          {formOpen ? '닫기' : '새 예약'}
        </button>
      </div>

      {formOpen && (
        <NewAppointmentForm
          hospitalId={hospitalId}
          uid={uid!}
          onCreated={() => setFormOpen(false)}
          onError={(e) => setActionError(e)}
        />
      )}

      {subError && (
        <div className="rounded-lg bg-surface-container-lowest p-3 text-sm text-primary">
          {subError}
        </div>
      )}
      {actionError && (
        <div className="rounded-lg bg-surface-container-lowest p-3 text-sm text-primary">
          {actionError}
        </div>
      )}

      {appointments.length === 0 ? (
        <p className="rounded-xl bg-surface-container-lowest p-6 text-center text-sm text-on-surface-variant">
          예약된 진료가 없습니다.
        </p>
      ) : (
        <ul className="space-y-2">
          {appointments.map((a) => {
            const busy = busyApptId === a.id;
            const alreadyCheckedIn = a.status === 'scheduled' && isCheckedInToday(a.department);
            const canCheckIn =
              a.status === 'scheduled' && isToday(a.scheduledAt) && !alreadyCheckedIn;
            const canCancel = a.status === 'scheduled';
            return (
              <li
                key={a.id}
                className="flex items-center gap-3 rounded-xl bg-surface-container-lowest p-4"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-semibold text-on-surface">
                      {a.department}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[a.status]}`}
                    >
                      {STATUS_LABELS[a.status]}
                    </span>
                    {alreadyCheckedIn && (
                      <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-on-primary">
                        접수됨
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-on-surface-variant">
                    {new Date(a.scheduledAt).toLocaleString('ko-KR', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {canCheckIn && (
                    <button
                      type="button"
                      onClick={() => handleCheckIn(a)}
                      disabled={busy}
                      className="rounded-lg border border-primary px-3 py-1 text-xs font-medium text-primary disabled:opacity-50"
                    >
                      {busy ? '접수 중…' : '접수'}
                    </button>
                  )}
                  {canCancel && (
                    <button
                      type="button"
                      onClick={() => handleCancel(a)}
                      disabled={busy}
                      aria-label="예약 취소"
                      className="rounded-full p-2 text-on-surface-variant hover:bg-surface-container disabled:opacity-50"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function NewAppointmentForm({
  hospitalId,
  uid,
  onCreated,
  onError,
}: {
  hospitalId: string;
  uid: string;
  onCreated: () => void;
  onError: (msg: string) => void;
}) {
  const [department, setDepartment] = useState<string>(DEPARTMENTS[0]);
  const [whenLocal, setWhenLocal] = useState<string>(() => {
    // 기본값: 오늘 + 1시간 뒤 (KST) — datetime-local 포맷 'YYYY-MM-DDTHH:mm'
    const d = new Date(Date.now() + 60 * 60 * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  });
  const [durationMin, setDurationMin] = useState<number>(30);
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const scheduledAt = new Date(whenLocal).getTime();
      await createAppointment(hospitalId, uid, {
        department,
        scheduledAt,
        durationMin,
        ...(notes.trim() ? { notes: notes.trim() } : {}),
      });
      onCreated();
    } catch (err) {
      onError(err instanceof Error ? err.message : '예약 생성 실패');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-on-surface-variant">부서</span>
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm"
          >
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-on-surface-variant">진료 시간 (분)</span>
          <input
            type="number"
            min={5}
            max={120}
            value={durationMin}
            onChange={(e) => setDurationMin(Number(e.target.value))}
            className="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-xs font-medium text-on-surface-variant">예약 일시</span>
          <input
            type="datetime-local"
            value={whenLocal}
            onChange={(e) => setWhenLocal(e.target.value)}
            className="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-xs font-medium text-on-surface-variant">메모 (선택)</span>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={200}
            className="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm"
          />
        </label>
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
        >
          {submitting ? '예약 중…' : '예약'}
        </button>
      </div>
    </form>
  );
}
