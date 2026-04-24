import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { AccountLayout } from '@/components/account/AccountLayout';
import { TextField } from '@/components/auth/TextField';
import { PasswordStrength } from '@/components/auth/PasswordStrength';
import {
  canChangePassword,
  changePassword,
  sendPasswordResetToCurrentUser,
} from '@/services/auth';
import { useAuthStore } from '@/stores/authStore';
import { scorePassword } from '@/utils/password';

export function ChangePasswordPage() {
  const user = useAuthStore((s) => s.user);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resetSentTo, setResetSentTo] = useState<string | null>(null);

  if (!canChangePassword(user)) {
    return (
      <AccountLayout title="비밀번호" description="비밀번호 변경 및 재설정">
        <div className="flex flex-col gap-3">
          <p className="text-sm text-on-surface-variant">
            이 계정은 소셜 로그인(예: Google)으로 가입되어 비밀번호를 직접 변경할 수
            없습니다. 공급자 측에서 비밀번호를 관리하세요.
          </p>
          <Link
            to="/"
            className="self-start rounded-lg border border-surface-container-high px-4 py-2 text-sm text-on-surface no-underline"
          >
            홈으로
          </Link>
        </div>
      </AccountLayout>
    );
  }

  const nextScore = scorePassword(next);
  const matches = next.length > 0 && next === confirm;
  const canSubmit =
    current.length > 0 && nextScore.strength !== 'too-short' && matches && !loading;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (nextScore.strength === 'too-short') {
      setError('새 비밀번호는 8자 이상이어야 합니다');
      return;
    }
    if (next === current) {
      setError('새 비밀번호가 현재 비밀번호와 동일합니다');
      return;
    }
    if (!matches) {
      setError('새 비밀번호 확인이 일치하지 않습니다');
      return;
    }
    setLoading(true);
    try {
      await changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      setSuccess('비밀번호가 변경되었습니다');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('auth/wrong-password') || msg.includes('auth/invalid-credential')) {
        setError('현재 비밀번호가 올바르지 않습니다');
      } else if (msg.includes('auth/weak-password')) {
        setError('비밀번호가 너무 약합니다');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const onSendResetLink = async () => {
    setError(null);
    setSuccess(null);
    try {
      const sentTo = await sendPasswordResetToCurrentUser();
      setResetSentTo(sentTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <AccountLayout title="비밀번호" description="보안을 위해 주기적으로 변경하세요">
      <form onSubmit={onSubmit} className="flex max-w-md flex-col gap-4">
        <TextField
          label="현재 비밀번호"
          type="password"
          autoComplete="current-password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />

        <div className="flex flex-col gap-2">
          <TextField
            label="새 비밀번호"
            type="password"
            autoComplete="new-password"
            required
            hint="8자 이상 · 대소문자·숫자·기호 혼합 권장"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <PasswordStrength password={next} />
        </div>

        <TextField
          label="새 비밀번호 확인"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={
            confirm.length > 0 && !matches ? '비밀번호가 일치하지 않습니다' : undefined
          }
        />

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
            {error}
          </p>
        )}
        {success && (
          <p className="rounded-lg bg-green-50 px-3 py-2 text-xs text-green-700">
            {success}
          </p>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
        >
          {loading ? '변경 중...' : '비밀번호 변경'}
        </button>
      </form>

      <div className="mt-8 border-t border-surface-container-high pt-6">
        <div className="flex items-start gap-3 rounded-xl bg-surface-container-low p-4">
          <Mail className="mt-0.5 h-4 w-4 shrink-0 text-on-surface-variant" />
          <div className="flex-1">
            <p className="text-sm font-medium text-on-surface">
              현재 비밀번호를 잊으셨나요?
            </p>
            <p className="mt-1 text-xs text-on-surface-variant">
              가입 이메일로 재설정 링크를 보내드립니다.
            </p>
            {resetSentTo ? (
              <p className="mt-2 text-xs text-green-700">
                {resetSentTo} 로 재설정 메일을 발송했습니다.
              </p>
            ) : (
              <button
                type="button"
                onClick={onSendResetLink}
                className="mt-2 rounded-lg border border-primary px-3 py-1.5 text-xs font-medium text-primary"
              >
                재설정 메일 보내기
              </button>
            )}
          </div>
        </div>
      </div>
    </AccountLayout>
  );
}
