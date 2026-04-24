import { useEffect, useState, type FormEvent } from 'react';
import { AlertTriangle, Shield, X } from 'lucide-react';
import { setUserRole, updateUserProfile } from '@/services/userProfile';
import { appendAudit } from '@/services/auditLog';
import { formatRoleLabel } from '@/utils/format';
import type { AdminUserRow } from '@/types/admin';
import type { UserRole } from '@/types/auth';

interface ChangeRoleDialogProps {
  open: boolean;
  row: AdminUserRow | null;
  onClose: () => void;
  onChanged: () => void;
}

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'patient', label: '환자 · 보호자' },
  { value: 'staff', label: '의료진' },
  { value: 'admin', label: '관리자' },
];

const ROLE_RANK: Record<UserRole, number> = {
  patient: 1,
  staff: 2,
  admin: 3,
  platformAdmin: 4,
};

export function ChangeRoleDialog({
  open,
  row,
  onClose,
  onChanged,
}: ChangeRoleDialogProps) {
  const [targetRole, setTargetRole] = useState<UserRole>('staff');
  const [hospitalId, setHospitalId] = useState('MediWay-Demo');
  const [department, setDepartment] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !row) return;
    // 기본 제안 역할: 환자→의료진, 의료진→관리자, 관리자→의료진
    const next: UserRole =
      row.role === 'patient' ? 'staff' : row.role === 'staff' ? 'admin' : 'staff';
    setTargetRole(next);
    setHospitalId(row.hospitalId ?? 'MediWay-Demo');
    setDepartment(row.department ?? '');
    setConfirmText('');
    setError(null);
  }, [open, row]);

  if (!open || !row) return null;

  const isPromote = ROLE_RANK[targetRole] > ROLE_RANK[row.role];
  const isDemote = ROLE_RANK[targetRole] < ROLE_RANK[row.role];
  const isNoChange = targetRole === row.role;
  const needsDept = targetRole === 'staff';
  const requiresStrongConfirm =
    targetRole === 'admin' || // 관리자 승격/유지
    row.role === 'admin'; // 관리자 강등
  const confirmOk = !requiresStrongConfirm || confirmText === targetRole.toUpperCase();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isNoChange) {
      setError('현재 역할과 동일합니다');
      return;
    }
    if (needsDept && !department.trim()) {
      setError('의료진 역할에는 부서가 필요합니다');
      return;
    }
    if (!confirmOk) {
      setError(`확인을 위해 "${targetRole.toUpperCase()}" 을(를) 입력하세요`);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      // 의료진 역할에는 병원/부서 필수, 그 외는 기존 필드 유지(이력 보존)
      if (targetRole === 'staff') {
        await updateUserProfile(row.uid, {
          hospitalId: hospitalId.trim(),
          department: department.trim(),
        });
      }
      await setUserRole(row.uid, targetRole);
      await appendAudit('user.role.change', row.uid, {
        from: row.role,
        to: targetRole,
        via: 'inline',
        ...(needsDept
          ? { hospitalId: hospitalId.trim(), department: department.trim() }
          : {}),
      });
      onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-on-surface">
              <Shield className="h-4 w-4 text-primary" />
              역할 변경
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              {row.displayName ?? row.uid} · 현재 {formatRoleLabel(row.role)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container-low"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-on-surface-variant">대상 역할</span>
            <select
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value as UserRole)}
              className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-sm outline-none focus:border-primary"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>

          {needsDept && (
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-on-surface-variant">병원 ID *</span>
                <input
                  value={hospitalId}
                  onChange={(e) => setHospitalId(e.target.value)}
                  required
                  className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-on-surface-variant">부서 *</span>
                <input
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  required
                  placeholder="내과"
                  className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
                />
              </label>
            </div>
          )}

          {isPromote && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                <span className="font-semibold">권한 상향</span> — 이 사용자는{' '}
                {targetRole === 'admin' ? '모든 관리자 기능' : '의료진 대시보드'}에 접근할 수 있게 됩니다.
              </p>
            </div>
          )}

          {isDemote && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-xs text-red-700">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                <span className="font-semibold">권한 축소</span> — 이 사용자는{' '}
                {row.role === 'admin' ? '관리자 페이지' : '의료진 대시보드'}에 더 이상 접근할 수 없습니다.
                {targetRole === 'patient' && ' 소속/부서 필드는 이력을 위해 유지됩니다.'}
              </p>
            </div>
          )}

          {requiresStrongConfirm && (
            <label className="flex flex-col gap-1">
              <span className="text-xs text-on-surface-variant">
                계속하려면{' '}
                <span className="font-mono text-red-600">
                  {targetRole.toUpperCase()}
                </span>{' '}
                을(를) 입력하세요
              </span>
              <input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
              />
            </label>
          )}

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">{error}</p>
          )}

          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-surface-container-high px-3 py-2 text-xs"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={saving || isNoChange || !confirmOk}
              className={`rounded-lg px-3 py-2 text-xs font-medium text-on-primary disabled:opacity-50 ${
                isDemote || targetRole === 'admin' ? 'bg-red-600' : 'bg-primary'
              }`}
            >
              {saving
                ? '변경 중...'
                : isDemote
                  ? '권한 축소'
                  : isPromote
                    ? '승격'
                    : '변경'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
