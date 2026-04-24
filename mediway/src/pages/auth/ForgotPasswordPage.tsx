import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { AuthCard } from '@/components/auth/AuthCard';
import { TextField } from '@/components/auth/TextField';
import { sendPasswordReset } from '@/services/auth';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<
    { state: 'idle' } | { state: 'sending' } | { state: 'sent' } | { state: 'error'; message: string }
  >({ state: 'idle' });

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus({ state: 'sending' });
    try {
      await sendPasswordReset(email);
      setStatus({ state: 'sent' });
    } catch (err) {
      setStatus({
        state: 'error',
        message: err instanceof Error ? err.message : String(err),
      });
    }
  };

  return (
    <AuthCard
      title="비밀번호 재설정"
      subtitle="가입 시 이메일로 재설정 링크를 보내드립니다"
      footer={
        <Link to="/login" className="font-medium text-primary">
          로그인으로 돌아가기
        </Link>
      }
    >
      {status.state === 'sent' ? (
        <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">
          <p className="font-medium">메일을 발송했습니다</p>
          <p className="mt-1 text-xs">
            받은편지함에서 재설정 링크를 확인해주세요.
          </p>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <TextField
            label="이메일"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          {status.state === 'error' && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
              {status.message}
            </p>
          )}
          <button
            type="submit"
            disabled={status.state === 'sending'}
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            {status.state === 'sending' ? '발송 중...' : '재설정 메일 발송'}
          </button>
        </form>
      )}
    </AuthCard>
  );
}
