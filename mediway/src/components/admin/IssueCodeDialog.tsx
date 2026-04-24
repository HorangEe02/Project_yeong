import { useState, type FormEvent } from 'react';
import { Copy } from 'lucide-react';
import { issueBulkCodes } from '@/services/adminStaffCodes';
import type { StaffCode } from '@/types/staff-code';

interface IssueCodeDialogProps {
  open: boolean;
  onClose: () => void;
  onIssued: () => void;
}

export function IssueCodeDialog({ open, onClose, onIssued }: IssueCodeDialogProps) {
  const [hospitalId, setHospitalId] = useState('MediWay-Demo');
  const [department, setDepartment] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [expiresInDays, setExpiresInDays] = useState(30);
  const [issued, setIssued] = useState<StaffCode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const reset = () => {
    setIssued([]);
    setDepartment('');
    setQuantity(1);
    setError(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const results = await issueBulkCodes({
        hospitalId: hospitalId.trim(),
        department: department.trim(),
        quantity,
        expiresInDays,
      });
      setIssued(results);
      onIssued();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const copyAll = async () => {
    const text = issued.map((c) => c.code).join('\n');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // ignore
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <h3 className="text-base font-semibold text-on-surface">의료진 코드 발급</h3>

        {issued.length > 0 ? (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-sm text-on-surface-variant">
              {issued.length}개의 코드가 발급되었습니다. 지금 복사해 두세요.
            </p>
            <div className="max-h-56 overflow-y-auto rounded-lg border border-surface-container-high bg-surface">
              {issued.map((c) => (
                <div
                  key={c.code}
                  className="flex items-center justify-between border-b border-surface-container-high/60 px-3 py-2 text-xs font-mono last:border-0"
                >
                  <span>{c.code}</span>
                  <span className="text-on-surface-variant">{c.department}</span>
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={copyAll}
                className="flex items-center gap-1 rounded-lg border border-surface-container-high px-3 py-2 text-xs"
              >
                <Copy className="h-3.5 w-3.5" />
                전체 복사
              </button>
              <button
                type="button"
                onClick={reset}
                className="rounded-lg border border-surface-container-high px-3 py-2 text-xs"
              >
                추가 발급
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-on-primary"
              >
                닫기
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-3 text-sm">
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
              <span className="text-xs text-on-surface-variant">부서/진료과</span>
              <input
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                required
                placeholder="예: 내과"
                className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-on-surface-variant">수량 (1~100)</span>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                  className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-on-surface-variant">유효기간 (일)</span>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={expiresInDays}
                  onChange={(e) => setExpiresInDays(Number(e.target.value))}
                  className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
                />
              </label>
            </div>

            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
                {error}
              </p>
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
                disabled={loading}
                className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-on-primary disabled:opacity-50"
              >
                {loading ? '발급 중...' : '발급'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
