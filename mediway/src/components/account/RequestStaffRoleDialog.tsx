import { useState, type FormEvent } from 'react';
import { X, Stethoscope } from 'lucide-react';
import { submitRoleRequest } from '@/services/roleRequest';

interface RequestStaffRoleDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmitted: () => void;
}

export function RequestStaffRoleDialog({
  open,
  onClose,
  onSubmitted,
}: RequestStaffRoleDialogProps) {
  const [hospitalId, setHospitalId] = useState('MediWay-Demo');
  const [department, setDepartment] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await submitRoleRequest({ hospitalId, department, reason });
      onSubmitted();
      onClose();
      setDepartment('');
      setReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-on-surface">
              <Stethoscope className="h-4 w-4 text-primary" />
              의료진 전환 신청
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              관리자가 확인 후 승인/거절합니다
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
              placeholder="예: 내과"
              className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-on-surface-variant">신청 사유 (선택)</span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={300}
              className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
              placeholder="예: 내과 OOO 간호사. 입사 후 의료진 계정 필요"
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
              {saving ? '신청 중...' : '신청하기'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
