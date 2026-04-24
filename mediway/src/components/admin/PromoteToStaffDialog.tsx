import { useState, type FormEvent } from 'react';
import { Stethoscope, X, AlertTriangle } from 'lucide-react';
import { updateUserProfile, setUserRole } from '@/services/userProfile';
import { appendAudit } from '@/services/auditLog';

interface PromoteToStaffDialogProps {
  open: boolean;
  uid: string;
  displayName: string | null;
  onClose: () => void;
  onPromoted: () => void;
}

export function PromoteToStaffDialog({
  open,
  uid,
  displayName,
  onClose,
  onPromoted,
}: PromoteToStaffDialogProps) {
  const [hospitalId, setHospitalId] = useState('MediWay-Demo');
  const [department, setDepartment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!department.trim()) {
      setError('부서를 입력하세요');
      return;
    }
    setSaving(true);
    try {
      await updateUserProfile(uid, {
        hospitalId: hospitalId.trim(),
        department: department.trim(),
      });
      await setUserRole(uid, 'staff');
      await appendAudit('user.role.change', uid, {
        role: 'staff',
        hospitalId: hospitalId.trim(),
        department: department.trim(),
        via: 'admin_promote',
      });
      onPromoted();
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
              <Stethoscope className="h-4 w-4 text-primary" />
              의료진으로 승격
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              {displayName ?? uid} 의 역할을 의료진으로 변경합니다
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

        <div className="mb-3 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>
            승격 후 해당 사용자는 /staff 대시보드에 접근할 수 있습니다.
            기존 방문 계획은 유지되지만 의료진 역할에서는 사용되지 않습니다.
          </p>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-on-surface-variant">병원 ID</span>
            <input
              value={hospitalId}
              onChange={(e) => setHospitalId(e.target.value)}
              required
              className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-on-surface-variant">부서 / 진료과 *</span>
            <input
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              required
              placeholder="예: 내과, 영상의학과"
              className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
            />
          </label>

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
              disabled={saving}
              className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-on-primary disabled:opacity-50"
            >
              {saving ? '승격 중...' : '의료진으로 승격'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
