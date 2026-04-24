import { useState, type FormEvent } from 'react';
import {
  UserPlus,
  X,
  Mail,
  KeyRound,
  CheckCircle2,
  Copy,
  AlertTriangle,
} from 'lucide-react';
import { createStaffAccount } from '@/services/staffAccount';
import type {
  CreateStaffMode,
  CreateStaffAccountResult,
} from '@/services/staffAccount';

interface CreateStaffAccountDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function CreateStaffAccountDialog({
  open,
  onClose,
  onCreated,
}: CreateStaffAccountDialogProps) {
  const [mode, setMode] = useState<CreateStaffMode>('email_reset');
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [hospitalId, setHospitalId] = useState('MediWay-Demo');
  const [department, setDepartment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CreateStaffAccountResult | null>(null);
  const [copied, setCopied] = useState<'link' | 'pwd' | null>(null);

  if (!open) return null;

  const reset = () => {
    setEmail('');
    setDisplayName('');
    setDepartment('');
    setError(null);
    setResult(null);
    setCopied(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const res = await createStaffAccount({
        email: email.trim(),
        displayName: displayName.trim() || undefined,
        department: department.trim(),
        hospitalId: hospitalId.trim(),
        mode,
      });
      setResult(res);
      onCreated();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('already-exists')) {
        setError(
          '이미 가입된 이메일입니다. 기존 계정을 의료진으로 승격하려면 "사용자" 탭의 역할 관리를 사용하세요.',
        );
      } else if (msg.includes('failed-precondition') || msg.includes('internal')) {
        setError(
          msg +
            ' — Functions 배포가 안 되어 있을 수 있습니다. Blaze 플랜 전환 후 재시도.',
        );
      } else {
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const copy = async (text: string, kind: 'link' | 'pwd') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      setTimeout(() => setCopied(null), 1500);
    } catch {}
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-on-surface">
              <UserPlus className="h-4 w-4 text-primary" />
              의료진 계정 직접 생성
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              관리자가 Auth 계정과 프로필을 즉시 만듭니다
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

        {result ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-2 rounded-xl bg-green-50 p-3 text-xs text-green-800">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-semibold">계정이 생성되었습니다</p>
                <p className="mt-0.5">{result.email}</p>
              </div>
            </div>

            {result.mode === 'email_reset' && result.resetLink && (
              <div>
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                  비밀번호 설정 링크 (이메일도 자동 발송됨)
                </p>
                <div className="flex items-stretch gap-2">
                  <div className="flex-1 overflow-hidden rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-xs">
                    <span className="block truncate">{result.resetLink}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => copy(result.resetLink!, 'link')}
                    className="flex items-center gap-1 rounded-lg border border-primary px-3 text-xs font-medium text-primary"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    {copied === 'link' ? '복사됨' : '복사'}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-on-surface-variant">
                  수신자가 이메일을 못 받으면 이 링크를 직접 전달하세요.
                </p>
              </div>
            )}

            {result.mode === 'temp_password' && result.tempPassword && (
              <div>
                <div className="mb-2 flex items-start gap-2 rounded-lg bg-amber-50 p-2 text-[11px] text-amber-700">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                  <p>
                    임시 비밀번호는 지금 한 번만 표시됩니다. 안전하게 전달하고
                    사용자가 즉시 변경하도록 안내하세요.
                  </p>
                </div>
                <div className="flex items-stretch gap-2">
                  <div className="flex-1 rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-center font-mono text-base tracking-widest">
                    {result.tempPassword}
                  </div>
                  <button
                    type="button"
                    onClick={() => copy(result.tempPassword!, 'pwd')}
                    className="flex items-center gap-1 rounded-lg border border-primary px-3 text-xs font-medium text-primary"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    {copied === 'pwd' ? '복사됨' : '복사'}
                  </button>
                </div>
              </div>
            )}

            <div className="mt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={reset}
                className="rounded-lg border border-surface-container-high px-3 py-2 text-xs"
              >
                추가 생성
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
            <div className="flex gap-1 rounded-lg bg-surface-container-high p-1">
              <button
                type="button"
                onClick={() => setMode('email_reset')}
                className={`flex-1 rounded px-3 py-1.5 text-xs font-medium ${
                  mode === 'email_reset'
                    ? 'bg-surface-container-lowest text-primary shadow-ambient'
                    : 'text-on-surface-variant'
                }`}
              >
                <Mail className="mr-1 inline h-3 w-3" />
                이메일 재설정 링크
              </button>
              <button
                type="button"
                onClick={() => setMode('temp_password')}
                className={`flex-1 rounded px-3 py-1.5 text-xs font-medium ${
                  mode === 'temp_password'
                    ? 'bg-surface-container-lowest text-primary shadow-ambient'
                    : 'text-on-surface-variant'
                }`}
              >
                <KeyRound className="mr-1 inline h-3 w-3" />
                임시 비밀번호
              </button>
            </div>

            <p className="rounded-lg bg-surface-container-low p-2 text-[11px] text-on-surface-variant">
              {mode === 'email_reset'
                ? '수신자 이메일로 비밀번호 설정 링크가 전송됩니다(Firebase 내장). 복사 가능한 링크도 제공됩니다.'
                : '임시 비밀번호가 한 번만 화면에 표시됩니다. 오프라인 전달에 적합.'}
            </p>

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
                {saving ? '생성 중...' : '계정 생성'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
