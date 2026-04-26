import { useCallback, useState, type FormEvent } from 'react';
import { useHospital } from '@/contexts/HospitalContext';
import { createVisit } from '@/services/visit';
import {
  VISIT_TYPE_REQUIRED_FIELDS,
  VISIT_NOTES_MAX_LENGTH,
  type VisitType,
} from '@/types/visit';
import { getCurrentUid } from '@/services/auth';

/**
 * Phase H.6 — admin 의 환자 visit 등록 페이지.
 * 라우트: `/h/:slug/admin/visits` (HospitalShell 하위, ProtectedRoute requireRole=['admin', 'platformAdmin'])
 *
 * 본 sprint 범위:
 *  - 단일 visit 등록 폼 (외래/입원/검진/응급 4종, type 별 conditional 필드)
 *  - 제출 → createVisit + success/error 표시
 *
 * 본 sprint 비범위 (Phase I):
 *  - 환자 검색 / uid 자동 완성
 *  - 등록된 visit 리스트 + status 변경
 *  - 부서별 일별 visit 대시보드
 */

const TYPE_OPTIONS: ReadonlyArray<{ value: VisitType; label: string }> = [
  { value: 'outpatient', label: '외래' },
  { value: 'inpatient', label: '입원' },
  { value: 'checkup', label: '검진' },
  { value: 'emergency', label: '응급' },
];

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
