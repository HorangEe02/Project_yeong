import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useHospital } from '@/contexts/HospitalContext';
import { useAuthStore } from '@/stores/authStore';
import { useVisitHistory } from '@/hooks/useVisitHistory';
import {
  isInpatientVisit,
  type Visit,
  type VisitStatus,
  type VisitType,
} from '@/types/visit';

/**
 * Phase I.4.2 — 환자 본인의 visit history 페이지.
 * 라우트: `/h/:slug/patient/history` (HospitalShell 하위, ProtectedRoute — 인증 필요).
 *
 * 표시: useVisitHistory(slug, profile.uid) — 최신 50건, createdAt desc.
 * 카드: type / status / 부서 / 위치 / 날짜 / notes preview.
 */

const TYPE_LABELS: Record<VisitType, string> = {
  outpatient: '외래',
  inpatient: '입원',
  checkup: '검진',
  emergency: '응급',
};

const STATUS_LABELS: Record<VisitStatus, string> = {
  scheduled: '예약됨',
  'checked-in': '접수',
  'in-progress': '진료 중',
  completed: '종료',
  cancelled: '취소',
};

const STATUS_BADGE_CLASS: Record<VisitStatus, string> = {
  scheduled: 'bg-surface-container text-on-surface-variant',
  'checked-in': 'bg-blue-50 text-blue-700',
  'in-progress': 'bg-amber-50 text-amber-700',
  completed: 'bg-green-50 text-green-700',
  cancelled: 'bg-error-container/30 text-error',
};

export function PatientHistoryPage() {
  const { slug } = useHospital();
  const profile = useAuthStore((s) => s.profile);
  const patientUid = profile?.uid ?? null;
  const { visits, loading, error } = useVisitHistory(slug, patientUid);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4">
        <Link
          to={`/h/${slug}/patient/home`}
          className="inline-flex items-center gap-1 text-sm text-on-surface-variant hover:underline"
          data-testid="history-back-home"
        >
          <ArrowLeft className="h-4 w-4" />
          홈으로
        </Link>
      </div>

      <h1 className="mb-2 text-2xl font-bold text-on-surface">방문 이력</h1>
      <p className="mb-6 text-sm text-on-surface-variant">
        최근 50건까지 조회됩니다.
      </p>

      {!patientUid && (
        <p
          role="alert"
          data-testid="history-no-auth"
          className="rounded-xl bg-error-container/30 p-4 text-sm text-error"
        >
          로그인이 필요합니다.
        </p>
      )}

      {patientUid && loading && (
        <p
          data-testid="history-loading"
          className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant"
        >
          불러오는 중...
        </p>
      )}

      {patientUid && error && (
        <div
          role="alert"
          data-testid="history-error"
          className="rounded-xl bg-error-container/30 p-4 text-sm text-error"
        >
          {error}
        </div>
      )}

      {patientUid && !loading && !error && visits.length === 0 && (
        <p
          data-testid="history-empty"
          className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant"
        >
          방문 이력이 없습니다.
        </p>
      )}

      {patientUid && !loading && visits.length > 0 && (
        <ul className="flex flex-col gap-3" data-testid="history-list">
          {visits.map((v) => (
            <HistoryCard key={v.visitId} visit={v} />
          ))}
        </ul>
      )}
    </div>
  );
}

function HistoryCard({ visit }: { visit: Visit }) {
  const typeLabel = TYPE_LABELS[visit.type] ?? visit.type;
  const location = isInpatientVisit(visit)
    ? `${visit.ward}-${visit.room}${visit.bed ? `-${visit.bed}` : ''}`
    : visit.zone;
  const date = new Date(visit.createdAt).toLocaleDateString();
  const notesPreview = visit.notes
    ? visit.notes.slice(0, 60) + (visit.notes.length > 60 ? '...' : '')
    : null;

  return (
    <li
      className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
      data-testid={`history-card-${visit.visitId}`}
    >
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
          {typeLabel}
        </span>
        <span
          className={`rounded-md px-2 py-0.5 text-xs font-semibold ${STATUS_BADGE_CLASS[visit.status]}`}
        >
          {STATUS_LABELS[visit.status]}
        </span>
        {visit.department && (
          <span className="text-xs text-on-surface-variant">{visit.department}</span>
        )}
      </div>
      <p className="mt-1 text-sm font-semibold text-on-surface">{location}</p>
      <p className="mt-0.5 text-xs text-on-surface-variant">{date}</p>
      {notesPreview && (
        <p className="mt-2 text-xs text-on-surface-variant">{notesPreview}</p>
      )}
    </li>
  );
}
