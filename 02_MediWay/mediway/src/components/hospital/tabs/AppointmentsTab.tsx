import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Calendar, Plus, X } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';
import { useAuthStore } from '@/stores/authStore';
import {
  cancelAppointment,
  createAppointment,
  isCancellable,
  subscribeMyAppointmentIndex,
} from '@/services/appointments';
import type { AppointmentIndexEntry } from '@/types/appointment';

const formSchema = z.object({
  department: z
    .string()
    .trim()
    .min(2, '부서명을 2자 이상 입력해 주세요')
    .max(40, '부서명이 너무 깁니다'),
  scheduledAt: z
    .string()
    .min(1, '예약 시간을 선택해 주세요')
    .refine(
      (v) => new Date(v).getTime() > Date.now(),
      '과거 시간은 예약할 수 없습니다',
    ),
  durationMin: z.number().int().min(5, '5분 이상').max(240, '240분 이하'),
  notes: z.string().trim().max(200, '메모는 200자 이내').optional(),
});

type FormValues = z.infer<typeof formSchema>;

/**
 * 외래 탭 — 예약 목록 + 신규 폼 + 취소.
 * P2 C4 MVP (실시간 대기 · 결제 · 처방전은 P3).
 */
export function AppointmentsTab() {
  const { slug, hospital } = useHospital();
  const user = useAuthStore((s) => s.user);
  const hospitalId = slug ?? '';
  const patientUid = user?.uid;

  const [list, setList] = useState<
    Array<AppointmentIndexEntry & { id: string }>
  >([]);
  const [showForm, setShowForm] = useState(false);
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

  const onCancel = async (apptId: string) => {
    if (!hospitalId || !patientUid) return;
    setErr(null);
    try {
      await cancelAppointment(hospitalId, patientUid, apptId);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  if (!hospital?.features?.appointments) {
    return (
      <div className="p-6 text-center text-on-surface-variant">
        이 병원은 외래 예약 기능을 아직 활성화하지 않았습니다.
      </div>
    );
  }

  return (
    <div className="p-4">
      <h2 className="sr-only">외래</h2>

      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold">내 예약</h3>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-sm text-on-primary"
        >
          <Plus className="h-4 w-4" />
          새 예약
        </button>
      </div>

      {err && (
        <div className="mb-3 rounded-lg bg-error-container p-3 text-sm text-error">
          {err}
        </div>
      )}

      {showForm && (
        <CreateForm
          hospitalId={hospitalId}
          patientUid={patientUid ?? ''}
          onCreated={() => {
            setShowForm(false);
          }}
          onError={setErr}
        />
      )}

      <ul className="flex flex-col gap-2">
        {list.length === 0 ? (
          <li className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 text-center text-on-surface-variant">
            예약된 진료가 없습니다.
          </li>
        ) : (
          list.map((a) => (
            <li
              key={a.id}
              className="flex items-start justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
            >
              <div className="flex items-start gap-3">
                <Calendar
                  className="mt-1 h-5 w-5 text-primary"
                  aria-hidden="true"
                />
                <div>
                  <div className="font-medium">{a.department}</div>
                  <div className="text-sm text-on-surface-variant">
                    {new Date(a.scheduledAt).toLocaleString('ko-KR')}
                  </div>
                  <div className="mt-1 text-xs">
                    <StatusBadge status={a.status} />
                  </div>
                </div>
              </div>
              {isCancellable(a.status) && (
                <button
                  type="button"
                  onClick={() => onCancel(a.id)}
                  aria-label="예약 취소"
                  className="rounded-full p-2 text-on-surface-variant hover:bg-surface-container"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

function StatusBadge({ status }: { status: AppointmentIndexEntry['status'] }) {
  const m = {
    scheduled: { label: '예약됨', cls: 'bg-primary/10 text-primary' },
    cancelled: {
      label: '취소됨',
      cls: 'bg-surface-container text-on-surface-variant',
    },
    completed: { label: '완료', cls: 'bg-secondary-fixed text-primary' },
  } as const;
  const { label, cls } = m[status];
  return (
    <span className={`rounded-full px-2 py-0.5 ${cls}`}>{label}</span>
  );
}

function CreateForm({
  hospitalId,
  patientUid,
  onCreated,
  onError,
}: {
  hospitalId: string;
  patientUid: string;
  onCreated: () => void;
  onError: (e: string) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { durationMin: 30 },
  });

  const onSubmit = async (values: FormValues) => {
    if (!hospitalId || !patientUid) {
      onError('로그인과 병원 컨텍스트가 필요합니다');
      return;
    }
    try {
      await createAppointment(hospitalId, patientUid, {
        department: values.department,
        scheduledAt: new Date(values.scheduledAt).getTime(),
        durationMin: values.durationMin,
        notes: values.notes?.trim() || undefined,
      });
      onCreated();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
    >
      <h4 className="mb-3 font-medium">새 예약 등록</h4>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          진료과
          <input
            {...register('department')}
            className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
            placeholder="예: 내과, 정형외과"
          />
          {errors.department && (
            <span className="text-xs text-error">
              {errors.department.message}
            </span>
          )}
        </label>
        <label className="text-sm">
          예약 시각
          <input
            type="datetime-local"
            {...register('scheduledAt')}
            className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
          />
          {errors.scheduledAt && (
            <span className="text-xs text-error">
              {errors.scheduledAt.message}
            </span>
          )}
        </label>
        <label className="text-sm">
          소요 시간 (분)
          <input
            type="number"
            {...register('durationMin', { valueAsNumber: true })}
            className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
          />
          {errors.durationMin && (
            <span className="text-xs text-error">
              {errors.durationMin.message}
            </span>
          )}
        </label>
        <label className="text-sm sm:col-span-2">
          메모 (선택)
          <input
            {...register('notes')}
            className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
            placeholder="상담 내용 메모"
          />
          {errors.notes && (
            <span className="text-xs text-error">{errors.notes.message}</span>
          )}
        </label>
      </div>
      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
      >
        {isSubmitting ? '저장 중...' : '예약 등록'}
      </button>
    </form>
  );
}
