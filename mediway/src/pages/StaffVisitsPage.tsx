import { useCallback, useState } from 'react';
import { useHospital } from '@/contexts/HospitalContext';
import { useAuthStore } from '@/stores/authStore';
import { useStaffActiveVisits } from '@/hooks/useStaffActiveVisits';
import { updateVisitStatus } from '@/services/visit';
import { isInpatientVisit, type Visit, type VisitStatus } from '@/types/visit';
import { StaffSubNav } from '@/components/staff/StaffSubNav';

/**
 * Phase I.2.4 — Staff visit 콘솔.
 * 라우트: `/h/:slug/staff/visits` (HospitalShell 하위, ProtectedRoute requireRole=['staff', 'admin'])
 *
 * 표시: 본인 부서 (profile.department) 의 오늘 active visit (checked-in / in-progress).
 * 정렬: createdAt asc (오래된 환자 먼저).
 * 액션: status select 변경 → updateVisitStatus (RTDB rules — staff status update 허용 in I.2.1).
 */

const STATUS_OPTIONS: ReadonlyArray<{ value: VisitStatus; label: string }> = [
  { value: 'scheduled', label: '예약됨' },
  { value: 'checked-in', label: '접수' },
  { value: 'in-progress', label: '진료 중' },
  { value: 'completed', label: '종료' },
  { value: 'cancelled', label: '취소' },
];

const STATUS_BADGE_CLASS: Record<VisitStatus, string> = {
  scheduled: 'bg-surface-container text-on-surface-variant',
  'checked-in': 'bg-blue-50 text-blue-700',
  'in-progress': 'bg-amber-50 text-amber-700',
  completed: 'bg-green-50 text-green-700',
  cancelled: 'bg-error-container/30 text-error',
};

export function StaffVisitsPage() {
  const { slug } = useHospital();
  const profile = useAuthStore((s) => s.profile);
  const dept = profile?.department ?? null;
  const { visits, loading } = useStaffActiveVisits(slug, dept);

  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleStatusChange = useCallback(
    async (visitId: string, status: VisitStatus) => {
      setUpdatingId(visitId);
      setError(null);
      try {
        await updateVisitStatus(slug, visitId, status);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '알 수 없는 오류';
        setError(`status 변경 실패 (${visitId}): ${msg}`);
      } finally {
        setUpdatingId(null);
      }
    },
    [slug],
  );

  return (
    <div className="mx-auto max-w-3xl p-6">
      <StaffSubNav active="visits" />

      <h1 className="mb-2 text-2xl font-bold text-on-surface">환자 진료</h1>
      <p className="mb-6 text-sm text-on-surface-variant">
        {dept
          ? `${dept} 부서 · 오늘 active 환자 ${visits.length}명`
          : '담당 부서가 설정되지 않았습니다.'}
      </p>

      {!dept && (
        <div
          role="alert"
          data-testid="staff-visits-no-dept"
          className="mb-3 rounded-xl bg-error-container/30 p-4 text-sm text-error"
        >
          담당 부서가 프로필에 설정되지 않았습니다. 관리자에게 문의해주세요.
        </div>
      )}

      {dept && error && (
        <div
          role="alert"
          data-testid="staff-visits-error"
          className="mb-3 rounded-xl bg-error-container/30 p-4 text-sm text-error"
        >
          {error}
        </div>
      )}

      {dept && loading && (
        <p
          data-testid="staff-visits-loading"
          className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant"
        >
          불러오는 중...
        </p>
      )}

      {dept && !loading && visits.length === 0 && (
        <p
          data-testid="staff-visits-empty"
          className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant"
        >
          현재 active 환자 없음
        </p>
      )}

      {dept && !loading && visits.length > 0 && (
        <ul className="flex flex-col gap-2" data-testid="staff-visits-list">
          {visits.map((v) => (
            <VisitRow
              key={v.visitId}
              visit={v}
              updating={updatingId === v.visitId}
              onStatusChange={handleStatusChange}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function VisitRow({
  visit,
  updating,
  onStatusChange,
}: {
  visit: Visit;
  updating: boolean;
  onStatusChange: (visitId: string, status: VisitStatus) => void;
}) {
  const location = isInpatientVisit(visit)
    ? `${visit.ward}-${visit.room}${visit.bed ? `-${visit.bed}` : ''}`
    : visit.zone;
  const created = new Date(visit.createdAt).toLocaleTimeString();

  return (
    <li
      className="flex flex-col gap-2 rounded-xl border border-outline-variant bg-surface-container-lowest p-3 sm:flex-row sm:items-center sm:justify-between"
      data-testid={`staff-visit-${visit.visitId}`}
    >
      <div className="flex flex-col gap-1 text-sm">
        <div className="flex items-center gap-2">
          <span
            className={`rounded-md px-2 py-0.5 text-xs font-semibold ${STATUS_BADGE_CLASS[visit.status]}`}
          >
            {STATUS_OPTIONS.find((s) => s.value === visit.status)?.label ?? visit.status}
          </span>
          <span className="font-semibold text-on-surface">
            {visit.displayName ?? visit.patientUid}
          </span>
          <span className="text-on-surface-variant">· {location}</span>
        </div>
        <div className="text-xs text-on-surface-variant">접수 {created}</div>
      </div>

      <select
        value={visit.status}
        disabled={updating}
        onChange={(e) => onStatusChange(visit.visitId, e.target.value as VisitStatus)}
        data-testid={`staff-visit-status-select-${visit.visitId}`}
        className="rounded-lg border border-outline-variant px-2 py-1.5 text-xs disabled:opacity-50"
      >
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </li>
  );
}
