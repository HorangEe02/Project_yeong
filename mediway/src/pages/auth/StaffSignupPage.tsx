import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthCard } from '@/components/auth/AuthCard';
import { TextField } from '@/components/auth/TextField';
import { PasswordStrength } from '@/components/auth/PasswordStrength';
import { signUpStaff } from '@/services/auth';
import { validateStaffCode } from '@/services/staffCode';

export function StaffSignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: '',
    password: '',
    name: '',
    staffCode: '',
  });
  const [codeStatus, setCodeStatus] = useState<
    | { state: 'idle' }
    | { state: 'checking' }
    | { state: 'ok'; department: string }
    | { state: 'error'; message: string }
  >({ state: 'idle' });
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onCheckCode = async () => {
    const code = form.staffCode.trim();
    if (!code) return;
    setCodeStatus({ state: 'checking' });
    try {
      const result = await validateStaffCode(code);
      if (result.valid) {
        setCodeStatus({ state: 'ok', department: result.code.department });
      } else {
        setCodeStatus({
          state: 'error',
          message:
            result.reason === 'not_found'
              ? '존재하지 않는 코드입니다'
              : result.reason === 'expired'
                ? '만료된 코드입니다'
                : '이미 사용된 코드입니다',
        });
      }
    } catch (err) {
      setCodeStatus({
        state: 'error',
        message: err instanceof Error ? err.message : '검증 실패',
      });
    }
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (form.password.length < 8) {
      setFormError('비밀번호는 8자 이상이어야 합니다');
      return;
    }
    if (codeStatus.state !== 'ok') {
      setFormError('의료진 ID 코드를 먼저 확인해주세요');
      return;
    }
    setLoading(true);
    try {
      await signUpStaff({
        email: form.email,
        password: form.password,
        displayName: form.name,
        staffCode: form.staffCode,
      });
      navigate('/staff', { replace: true });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const codeHint =
    codeStatus.state === 'checking'
      ? '확인 중...'
      : codeStatus.state === 'ok'
        ? `확인 완료 — ${codeStatus.department}`
        : undefined;
  const codeError =
    codeStatus.state === 'error' ? codeStatus.message : undefined;

  return (
    <AuthCard
      title="의료진 회원가입"
      subtitle="병원에서 발급받은 ID 코드가 필요합니다"
      footer={
        <span>
          이미 계정이 있으신가요?{' '}
          <Link to="/login" className="font-medium text-primary">
            로그인
          </Link>
        </span>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <TextField
                label="의료진 ID 코드"
                required
                autoCapitalize="characters"
                value={form.staffCode}
                onChange={(e) => {
                  setForm({ ...form, staffCode: e.target.value });
                  setCodeStatus({ state: 'idle' });
                }}
                error={codeError}
                hint={codeHint}
                placeholder="예: DEMO01"
              />
            </div>
            <button
              type="button"
              onClick={onCheckCode}
              disabled={!form.staffCode.trim() || codeStatus.state === 'checking'}
              className="h-[42px] shrink-0 rounded-lg border border-primary bg-surface px-3 text-xs font-medium text-primary disabled:opacity-50"
            >
              확인
            </button>
          </div>
        </div>

        <TextField
          label="이름"
          required
          autoComplete="name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <TextField
          label="이메일"
          type="email"
          required
          autoComplete="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <div className="flex flex-col gap-2">
          <TextField
            label="비밀번호"
            type="password"
            required
            autoComplete="new-password"
            hint="8자 이상"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <PasswordStrength password={form.password} />
        </div>

        {formError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
            {formError}
          </p>
        )}

        <button
          type="submit"
          disabled={loading || codeStatus.state !== 'ok'}
          className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
        >
          {loading ? '가입 중...' : '가입하기'}
        </button>
      </form>
    </AuthCard>
  );
}
