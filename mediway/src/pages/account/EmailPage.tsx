import { useState, type FormEvent } from 'react';
import { Mail, Info } from 'lucide-react';
import { AccountLayout } from '@/components/account/AccountLayout';
import { TextField } from '@/components/auth/TextField';
import { canChangeEmail, requestEmailChange } from '@/services/auth';
import { useAuthStore } from '@/stores/authStore';

export function EmailPage() {
  const user = useAuthStore((s) => s.user);
  const [newEmail, setNewEmail] = useState('');
  const [password, setPassword] = useState('');
  const [status, setStatus] = useState<
    | { state: 'idle' }
    | { state: 'sending' }
    | { state: 'sent'; email: string }
    | { state: 'error'; message: string }
  >({ state: 'idle' });

  if (!user) return null;

  if (!canChangeEmail(user)) {
    return (
      <AccountLayout title="이메일" description="로그인 이메일 관리">
        <p className="text-sm text-on-surface-variant">
          이 계정은 소셜 로그인으로 가입되어 이메일을 직접 변경할 수 없습니다.
          공급자 측 계정에서 이메일을 관리하세요.
        </p>
      </AccountLayout>
    );
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus({ state: 'sending' });
    try {
      await requestEmailChange(password, newEmail);
      setStatus({ state: 'sent', email: newEmail.trim().toLowerCase() });
      setPassword('');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('auth/wrong-password') || msg.includes('auth/invalid-credential')) {
        setStatus({ state: 'error', message: '현재 비밀번호가 올바르지 않습니다' });
      } else if (msg.includes('auth/email-already-in-use')) {
        setStatus({ state: 'error', message: '이미 사용 중인 이메일입니다' });
      } else if (msg.includes('auth/invalid-email')) {
        setStatus({ state: 'error', message: '이메일 형식이 올바르지 않습니다' });
      } else {
        setStatus({ state: 'error', message: msg });
      }
    }
  };

  return (
    <AccountLayout title="이메일" description="로그인에 사용하는 이메일 주소를 변경합니다">
      <div className="mb-5 flex items-center gap-3 rounded-lg bg-surface-container-low p-4">
        <Mail className="h-4 w-4 text-on-surface-variant" />
        <div>
          <p className="text-[11px] uppercase tracking-wider text-on-surface-variant">
            현재 이메일
          </p>
          <p className="text-sm font-medium text-on-surface">{user.email}</p>
        </div>
      </div>

      {status.state === 'sent' ? (
        <div className="flex flex-col gap-3 rounded-lg bg-green-50 p-4">
          <p className="text-sm font-medium text-green-800">검증 메일을 발송했습니다</p>
          <p className="text-xs text-green-700">
            <span className="font-medium">{status.email}</span> 으로 전송된 링크를 클릭하면
            이메일 변경이 완료됩니다. 이후 다음 로그인부터 새 이메일을 사용하세요.
          </p>
          <button
            type="button"
            onClick={() => setStatus({ state: 'idle' })}
            className="self-start rounded-lg border border-green-700 px-3 py-1.5 text-xs font-medium text-green-800"
          >
            다시 변경
          </button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="flex max-w-md flex-col gap-4">
          <TextField
            label="새 이메일"
            type="email"
            autoComplete="email"
            required
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
          />
          <TextField
            label="현재 비밀번호"
            type="password"
            autoComplete="current-password"
            required
            hint="본인 확인을 위해 필요합니다"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {status.state === 'error' && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
              {status.message}
            </p>
          )}
          <button
            type="submit"
            disabled={
              status.state === 'sending' || !newEmail.trim() || password.length === 0
            }
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            {status.state === 'sending' ? '발송 중...' : '검증 메일 발송'}
          </button>
        </form>
      )}

      <div className="mt-8 flex items-start gap-3 rounded-xl bg-amber-50 p-4 text-xs text-amber-800">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-medium">변경 절차</p>
          <ol className="mt-1 list-decimal space-y-0.5 pl-4">
            <li>새 이메일로 검증 메일이 발송됩니다</li>
            <li>메일의 링크를 24시간 내에 클릭하세요</li>
            <li>다음 로그인부터 새 이메일이 활성화됩니다</li>
          </ol>
        </div>
      </div>
    </AccountLayout>
  );
}
