import { useState, type FormEvent } from 'react';
import { Copy, Mail, UserPlus, X } from 'lucide-react';
import { buildInviteUrl, createStaffInvitation } from '@/services/staffInvitation';
import type { StaffInvitation } from '@/types/staff-invitation';

interface InviteStaffDialogProps {
  open: boolean;
  onClose: () => void;
  onIssued: () => void;
}

const TTL_OPTIONS = [
  { label: '1일', ms: 24 * 3_600_000 },
  { label: '3일', ms: 3 * 24 * 3_600_000 },
  { label: '7일 (기본)', ms: 7 * 24 * 3_600_000 },
  { label: '14일', ms: 14 * 24 * 3_600_000 },
];

export function InviteStaffDialog({ open, onClose, onIssued }: InviteStaffDialogProps) {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [hospitalId, setHospitalId] = useState('MediWay-Demo');
  const [department, setDepartment] = useState('');
  const [ttlMs, setTtlMs] = useState(TTL_OPTIONS[2].ms);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<StaffInvitation | null>(null);
  const [copied, setCopied] = useState(false);

  if (!open) return null;

  const reset = () => {
    setCreated(null);
    setEmail('');
    setDisplayName('');
    setDepartment('');
    setError(null);
    setCopied(false);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const invitation = await createStaffInvitation({
        email,
        displayName,
        hospitalId,
        department,
        ttlMs,
      });
      setCreated(invitation);
      onIssued();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const copy = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(buildInviteUrl(created.token));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-on-surface">
              <UserPlus className="h-4 w-4 text-primary" />
              의료진 초대
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              이메일과 소속을 지정해 가입 링크를 생성합니다
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              reset();
              onClose();
            }}
            className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container-low"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {created ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-2 rounded-lg bg-green-50 p-3 text-xs text-green-800">
              <Mail className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <p className="font-semibold">초대 링크가 생성되었습니다</p>
                <p className="mt-0.5 text-green-800/80">
                  {created.email} 에게 아래 링크를 전달하세요. 링크를 클릭한 후 해당 이메일로 가입 또는 로그인해야 수락됩니다.
                </p>
              </div>
            </div>

            <div>
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                초대 URL
              </p>
              <div className="flex items-stretch gap-2">
                <div className="flex-1 overflow-hidden rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-xs">
                  <span className="block truncate">{buildInviteUrl(created.token)}</span>
                </div>
                <button
                  type="button"
                  onClick={copy}
                  className="flex items-center gap-1 rounded-lg border border-primary px-3 text-xs font-medium text-primary"
                >
                  <Copy className="h-3.5 w-3.5" />
                  {copied ? '복사됨' : '복사'}
                </button>
              </div>
            </div>

            <div className="text-[11px] text-on-surface-variant">
              만료: {new Date(created.expiresAt).toLocaleString()}
            </div>

            <div className="mt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={reset}
                className="rounded-lg border border-surface-container-high px-3 py-2 text-xs"
              >
                추가 초대
              </button>
              <button
                type="button"
                onClick={() => {
                  reset();
                  onClose();
                }}
                className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-on-primary"
              >
                완료
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-on-surface-variant">이메일 *</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="doctor@hospital.org"
                className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-on-surface-variant">이름 (선택)</span>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="예: 김내과"
                className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
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
            <label className="flex flex-col gap-1">
              <span className="text-xs text-on-surface-variant">만료 기간</span>
              <select
                value={ttlMs}
                onChange={(e) => setTtlMs(Number(e.target.value))}
                className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-xs"
              >
                {TTL_OPTIONS.map((o) => (
                  <option key={o.ms} value={o.ms}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>

            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
                {error}
              </p>
            )}

            <div className="mt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  reset();
                  onClose();
                }}
                className="rounded-lg border border-surface-container-high px-3 py-2 text-xs"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-on-primary disabled:opacity-50"
              >
                {saving ? '생성 중...' : '초대 링크 생성'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
