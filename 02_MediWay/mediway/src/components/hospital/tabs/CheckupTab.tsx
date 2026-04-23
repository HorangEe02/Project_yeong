import { useEffect, useMemo, useState } from 'react';
import { Activity, Calendar, Stethoscope } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';
import { useAuthStore } from '@/stores/authStore';
import {
  createAppointment,
  subscribeMyAppointmentIndex,
} from '@/services/appointments';
import type { AppointmentIndexEntry } from '@/types/appointment';

const CHECKUP_TYPES = [
  { value: '일반건강검진', label: '일반 건강검진' },
  { value: '종합건강검진', label: '종합 건강검진' },
  { value: '암검진', label: '암 검진' },
  { value: '특수건강검진', label: '특수 건강검진 (직무)' },
] as const;

type CheckupType = (typeof CHECKUP_TYPES)[number]['value'];

/**
 * 건강검진 탭 — 검진 예약 + 간이 이력.
 *
 * P3 C12: appointments 서비스 재사용 (department = 검진 유형).
 * 검진 결과 무기한 보관은 P5 MOAT.
 */
export function CheckupTab() {
  const { slug, hospital } = useHospital();
  const user = useAuthStore((s) => s.user);
  const hospitalId = slug ?? '';
  const patientUid = user?.uid;

  const [list, setList] = useState<Array<AppointmentIndexEntry & { id: string }>>(
    [],
  );
  const [checkupType, setCheckupType] = useState<CheckupType>('일반건강검진');
  const [scheduledAt, setScheduledAt] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!hospitalId || !patientUid) {
      setList([]);
      return;
    }
    const unsub = subscribeMyAppointmentIndex(
      hospitalId,
      patientUid,
      setList,
      (e) => setErr(e.message),
    );
    return () => unsub();
  }, [hospitalId, patientUid]);

  const checkupList = useMemo(
    () =>
      list.filter((a) =>
        CHECKUP_TYPES.some((t) => t.value === a.department),
      ),
    [list],
  );

  if (!hospital?.features?.checkup) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
        <div className="p-6 text-center text-on-surface-variant">
          이 병원은 건강검진 기능을 아직 활성화하지 않았습니다.
        </div>
      </main>
    );
  }

  const canSubmit =
    !!hospitalId &&
    !!patientUid &&
    !!scheduledAt &&
    new Date(scheduledAt).getTime() > Date.now() &&
    !busy;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setErr(null);
    setBusy(true);
    try {
      await createAppointment(hospitalId, patientUid, {
        department: checkupType,
        scheduledAt: new Date(scheduledAt).getTime(),
        durationMin: 60,
      });
      setScheduledAt('');
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <h2 className="sr-only">건강검진</h2>

      <section className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
        <header className="mb-3 flex items-center gap-2">
          <Stethoscope className="h-5 w-5 text-primary" aria-hidden="true" />
          <h3 className="text-base font-semibold">검진 예약</h3>
        </header>

        <form onSubmit={onSubmit} className="grid gap-2 sm:grid-cols-2">
          <label className="text-sm">
            검진 종류
            <select
              value={checkupType}
              onChange={(e) =>
                setCheckupType(e.target.value as CheckupType)
              }
              className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
            >
              {CHECKUP_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            희망 일시
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
            />
          </label>
          {err && (
            <p role="alert" className="sm:col-span-2 text-xs text-error">
              {err}
            </p>
          )}
          <button
            type="submit"
            disabled={!canSubmit}
            className="sm:col-span-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            {busy ? '저장 중…' : '검진 예약 등록'}
          </button>
        </form>
      </section>

      <section aria-labelledby="checkup-list">
        <h3
          id="checkup-list"
          className="mb-2 flex items-center gap-2 text-base font-semibold"
        >
          <Calendar className="h-5 w-5 text-primary" aria-hidden="true" />내
          검진 예약
        </h3>
        {checkupList.length === 0 ? (
          <p className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 text-center text-sm text-on-surface-variant">
            아직 검진 예약이 없습니다.
          </p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {checkupList.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
              >
                <div className="flex items-center gap-2">
                  <Activity
                    className="h-4 w-4 text-primary"
                    aria-hidden="true"
                  />
                  <div>
                    <div className="font-medium">{c.department}</div>
                    <div className="text-xs text-on-surface-variant">
                      {new Date(c.scheduledAt).toLocaleString('ko-KR')}
                    </div>
                  </div>
                </div>
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                  {statusLabel(c.status)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function statusLabel(s: AppointmentIndexEntry['status']): string {
  return { scheduled: '예약됨', cancelled: '취소됨', completed: '완료' }[s];
}
