import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { useHospital } from '@/contexts/HospitalContext';
import { createVisit, subscribeRecentVisits, updateVisitStatus } from '@/services/visit';
import {
  VISIT_TYPE_REQUIRED_FIELDS,
  VISIT_NOTES_MAX_LENGTH,
  isInpatientVisit,
  type Visit,
  type VisitStatus,
  type VisitType,
} from '@/types/visit';
import { getCurrentUid } from '@/services/auth';
import { listUsers } from '@/services/adminUsers';
import type { UserProfile } from '@/types/auth';

/**
 * Phase H.6 — admin 의 환자 visit 등록 페이지.
 * 라우트: `/h/:slug/admin/visits` (HospitalShell 하위, ProtectedRoute requireRole=['admin'])
 *
 * 본 페이지 구성:
 *  - 단일 visit 등록 폼 (Phase H.6) — 4종 type conditional 필드
 *  - 최근 등록 visit 리스트 + status 변경 dropdown (Phase I.1.2)
 *
 * 본 sprint 비범위 (Phase I 후속):
 *  - 환자 검색 / uid 자동 완성 (I.5)
 *  - 부서별 일별 visit 대시보드 (I.2 — staff 콘솔 분리)
 */

const TYPE_OPTIONS: ReadonlyArray<{ value: VisitType; label: string }> = [
  { value: 'outpatient', label: '외래' },
  { value: 'inpatient', label: '입원' },
  { value: 'checkup', label: '검진' },
  { value: 'emergency', label: '응급' },
];

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

const RECENT_VISITS_LIMIT = 20;

export function AdminVisitsPage() {
  const { slug } = useHospital();
  const [type, setType] = useState<VisitType>('outpatient');
  const [patientUid, setPatientUid] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [zone, setZone] = useState('');
  const [department, setDepartment] = useState('');
  const [ward, setWard] = useState('');
  const [room, setRoom] = useState('');
  const [bed, setBed] = useState('');
  const [scheduledForLocal, setScheduledForLocal] = useState('');
  const [notes, setNotes] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ visitId: string; ts: number } | null>(null);

  const required = VISIT_TYPE_REQUIRED_FIELDS[type];

  const validate = useCallback((): string | null => {
    if (!patientUid.trim()) return '환자 uid 가 필요합니다';
    if (required.includes('zone') && !zone.trim()) return 'zone (구역) 이 필요합니다';
    if (required.includes('department') && !department.trim())
      return 'department (진료과) 가 필요합니다';
    if (required.includes('ward') && !ward.trim()) return 'ward (병동) 가 필요합니다';
    if (required.includes('room') && !room.trim()) return 'room (병실) 가 필요합니다';
    if (notes.length > VISIT_NOTES_MAX_LENGTH)
      return `notes 는 ${VISIT_NOTES_MAX_LENGTH}자 이하`;
    return null;
  }, [patientUid, required, zone, department, ward, room, notes]);

  const resetForm = useCallback(() => {
    setPatientUid('');
    setDisplayName('');
    setZone('');
    setDepartment('');
    setWard('');
    setRoom('');
    setBed('');
    setScheduledForLocal('');
    setNotes('');
  }, []);

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setError(null);
      const v = validate();
      if (v) {
        setError(v);
        return;
      }
      const myUid = getCurrentUid();
      if (!myUid) {
        setError('인증이 필요합니다');
        return;
      }
      setSubmitting(true);
      try {
        // inpatient 일 때 zone 미입력이면 ward-room 으로 자동 채움 (RTDB rules 의 zone 1자 이상 통과용).
        const finalZone =
          zone.trim() ||
          (type === 'inpatient' ? `${ward.trim()}-${room.trim()}` : zone.trim());
        const visitId = await createVisit(slug, {
          patientUid: patientUid.trim(),
          type,
          status: 'scheduled',
          zone: finalZone,
          ward: ward.trim() || undefined,
          room: room.trim() || undefined,
          bed: bed.trim() || undefined,
          department: department.trim() || undefined,
          displayName: displayName.trim() || undefined,
          scheduledFor: scheduledForLocal
            ? new Date(scheduledForLocal).getTime()
            : undefined,
          notes: notes.trim() || undefined,
          createdBy: myUid,
        });
        setSuccess({ visitId, ts: Date.now() });
        resetForm();
      } catch (err) {
        const msg = err instanceof Error ? err.message : '알 수 없는 오류';
        setError(`등록 실패: ${msg}`);
      } finally {
        setSubmitting(false);
      }
    },
    [
      slug,
      type,
      patientUid,
      displayName,
      zone,
      department,
      ward,
      room,
      bed,
      scheduledForLocal,
      notes,
      validate,
      resetForm,
    ],
  );

  const showOutpatientFields = type === 'outpatient' || type === 'emergency';
  const showInpatientFields = type === 'inpatient';

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-2 text-2xl font-bold text-on-surface">환자 visit 등록</h1>
      <p className="mb-6 text-sm text-on-surface-variant">
        {slug} 병원의 환자 방문 (외래/입원/검진/응급) 을 등록합니다.
      </p>

      {success && (
        <div
          role="status"
          data-testid="visit-success"
          className="mb-4 rounded-xl bg-green-50 p-4 text-sm text-green-800"
        >
          ✓ 등록 완료 — visitId: <code className="font-mono">{success.visitId}</code>
        </div>
      )}

      {error && (
        <div
          role="alert"
          data-testid="visit-error"
          className="mb-4 rounded-xl bg-error-container/30 p-4 text-sm text-error"
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* type radio */}
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-semibold text-on-surface">방문 유형</legend>
          <div className="flex flex-wrap gap-2" role="radiogroup">
            {TYPE_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`cursor-pointer rounded-lg border px-4 py-2 text-sm ${
                  type === opt.value
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-outline-variant text-on-surface-variant'
                }`}
              >
                <input
                  type="radio"
                  name="visit-type"
                  value={opt.value}
                  checked={type === opt.value}
                  onChange={() => setType(opt.value)}
                  className="sr-only"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </fieldset>

        {/* 환자 검색 (Phase I.5.2) */}
        <PatientSearchPicker
          onPick={(u) => {
            setPatientUid(u.uid);
            setDisplayName(u.displayName ?? '');
          }}
        />

        {/* patientUid */}
        <Field label="환자 uid" required>
          <input
            type="text"
            value={patientUid}
            onChange={(e) => setPatientUid(e.target.value)}
            className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
            placeholder="firebase auth uid"
            data-testid="visit-input-patientUid"
          />
        </Field>

        {/* displayName (optional) */}
        <Field label="환자 이름 (cache, 선택)">
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
            placeholder="환자 표시명"
            data-testid="visit-input-displayName"
          />
        </Field>

        {/* outpatient/emergency: department + zone */}
        {showOutpatientFields && (
          <>
            <Field label="진료과 (department)" required>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
                placeholder={type === 'emergency' ? 'ER' : '예: IM, GS, PED'}
                data-testid="visit-input-department"
              />
            </Field>
            <Field label="구역 (zone)" required>
              <input
                type="text"
                value={zone}
                onChange={(e) => setZone(e.target.value)}
                className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
                placeholder="예: Zone A-1"
                data-testid="visit-input-zone"
              />
            </Field>
          </>
        )}

        {/* inpatient: ward + room + bed */}
        {showInpatientFields && (
          <div className="grid grid-cols-3 gap-3">
            <Field label="병동 (ward)" required>
              <input
                type="text"
                value={ward}
                onChange={(e) => setWard(e.target.value)}
                className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
                placeholder="예: 3W"
                data-testid="visit-input-ward"
              />
            </Field>
            <Field label="병실 (room)" required>
              <input
                type="text"
                value={room}
                onChange={(e) => setRoom(e.target.value)}
                className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
                placeholder="예: 302"
                data-testid="visit-input-room"
              />
            </Field>
            <Field label="침대 (bed, 선택)">
              <input
                type="text"
                value={bed}
                onChange={(e) => setBed(e.target.value)}
                className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
                placeholder="예: A"
                data-testid="visit-input-bed"
              />
            </Field>
          </div>
        )}

        {/* checkup: zone */}
        {type === 'checkup' && (
          <Field label="구역 (zone)" required>
            <input
              type="text"
              value={zone}
              onChange={(e) => setZone(e.target.value)}
              className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
              placeholder="예: 검진실 1F"
              data-testid="visit-input-zone"
            />
          </Field>
        )}

        {/* scheduledFor */}
        <Field label="예약 시각 (선택)">
          <input
            type="datetime-local"
            value={scheduledForLocal}
            onChange={(e) => setScheduledForLocal(e.target.value)}
            className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
            data-testid="visit-input-scheduledFor"
          />
        </Field>

        {/* notes */}
        <Field label={`메모 (선택, 최대 ${VISIT_NOTES_MAX_LENGTH}자)`}>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            maxLength={VISIT_NOTES_MAX_LENGTH}
            className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
            data-testid="visit-input-notes"
          />
        </Field>

        <button
          type="submit"
          disabled={submitting}
          data-testid="visit-submit"
          className="mt-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary disabled:opacity-50"
        >
          {submitting ? '등록 중...' : 'visit 등록'}
        </button>
      </form>

      <RecentVisitsList slug={slug} />
    </div>
  );
}

/**
 * Phase I.1.2 — 최근 등록 visit 리스트 + status 변경 dropdown.
 * `subscribeRecentVisits` 로 실시간 구독, `updateVisitStatus` 로 토글.
 */
function RecentVisitsList({ slug }: { slug: string }) {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);

  useEffect(() => {
    return subscribeRecentVisits(slug, RECENT_VISITS_LIMIT, setVisits);
  }, [slug]);

  const handleStatusChange = useCallback(
    async (visitId: string, status: VisitStatus) => {
      setUpdatingId(visitId);
      setUpdateError(null);
      try {
        await updateVisitStatus(slug, visitId, status);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '알 수 없는 오류';
        setUpdateError(`status 변경 실패 (${visitId}): ${msg}`);
      } finally {
        setUpdatingId(null);
      }
    },
    [slug],
  );

  return (
    <section
      className="mt-10 border-t border-outline-variant pt-6"
      data-testid="recent-visits-section"
    >
      <h2 className="mb-3 text-lg font-bold text-on-surface">
        최근 등록된 visit ({visits.length})
      </h2>

      {updateError && (
        <div
          role="alert"
          data-testid="visit-status-update-error"
          className="mb-3 rounded-lg bg-error-container/30 p-3 text-sm text-error"
        >
          {updateError}
        </div>
      )}

      {visits.length === 0 ? (
        <p
          data-testid="recent-visits-empty"
          className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant"
        >
          등록된 visit 없음
        </p>
      ) : (
        <ul className="flex flex-col gap-2" data-testid="recent-visits-list">
          {visits.map((v) => (
            <VisitCard
              key={v.visitId}
              visit={v}
              updating={updatingId === v.visitId}
              onStatusChange={handleStatusChange}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function VisitCard({
  visit,
  updating,
  onStatusChange,
}: {
  visit: Visit;
  updating: boolean;
  onStatusChange: (visitId: string, status: VisitStatus) => void;
}) {
  const typeLabel = TYPE_OPTIONS.find((o) => o.value === visit.type)?.label ?? visit.type;
  const location = isInpatientVisit(visit)
    ? `${visit.ward}-${visit.room}${visit.bed ? `-${visit.bed}` : ''}`
    : visit.zone;
  const created = new Date(visit.createdAt).toLocaleString();

  return (
    <li
      className="flex flex-col gap-2 rounded-xl border border-outline-variant bg-surface-container-lowest p-3 sm:flex-row sm:items-center sm:justify-between"
      data-testid={`visit-card-${visit.visitId}`}
    >
      <div className="flex flex-col gap-1 text-sm">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
            {typeLabel}
          </span>
          <span
            className={`rounded-md px-2 py-0.5 text-xs font-semibold ${STATUS_BADGE_CLASS[visit.status]}`}
            data-testid={`visit-status-badge-${visit.visitId}`}
          >
            {STATUS_OPTIONS.find((s) => s.value === visit.status)?.label ?? visit.status}
          </span>
          <span className="text-on-surface-variant">{location}</span>
          {visit.department && (
            <span className="text-on-surface-variant">/ {visit.department}</span>
          )}
        </div>
        <div className="text-xs text-on-surface-variant">
          {visit.displayName ?? visit.patientUid} · {created}
        </div>
      </div>

      <select
        value={visit.status}
        disabled={updating}
        onChange={(e) => onStatusChange(visit.visitId, e.target.value as VisitStatus)}
        data-testid={`visit-status-select-${visit.visitId}`}
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

/**
 * Phase I.5.2 — 환자 검색 dropdown.
 * 마운트 시 listUsers() 1회 fetch + 클라이언트 substring filter (email/displayName).
 * 결과 클릭 시 onPick(user) 콜백 → 부모 폼 (patientUid + displayName) 자동 채움.
 */
function PatientSearchPicker({ onPick }: { onPick: (u: UserProfile) => void }) {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [query, setQuery] = useState('');

  useEffect(() => {
    listUsers().then(setUsers).catch(() => setUsers([]));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [] as UserProfile[];
    return users
      .filter(
        (u) =>
          (u.email && u.email.toLowerCase().includes(q)) ||
          (u.displayName && u.displayName.toLowerCase().includes(q)),
      )
      .slice(0, 8);
  }, [users, query]);

  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-semibold text-on-surface">환자 검색</span>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="이메일 또는 이름으로 검색"
        data-testid="visit-patient-search"
        className="rounded-lg border border-outline-variant px-3 py-2 text-sm"
      />
      {filtered.length > 0 && (
        <ul
          className="mt-1 flex flex-col gap-1 rounded-lg border border-outline-variant bg-surface-container-lowest p-1"
          data-testid="visit-patient-search-results"
        >
          {filtered.map((u) => (
            <li key={u.uid}>
              <button
                type="button"
                data-testid={`visit-patient-search-pick-${u.uid}`}
                className="w-full rounded px-2 py-1.5 text-left text-sm hover:bg-surface-container"
                onClick={() => {
                  onPick(u);
                  setQuery('');
                }}
              >
                <span className="font-medium text-on-surface">
                  {u.displayName ?? '(이름 없음)'}
                </span>
                <span className="ml-2 text-xs text-on-surface-variant">{u.email ?? ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-semibold text-on-surface">
        {label}
        {required && <span className="ml-1 text-error">*</span>}
      </span>
      {children}
    </label>
  );
}
