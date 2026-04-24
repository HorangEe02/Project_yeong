import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthCard } from '@/components/auth/AuthCard';
import { TextField } from '@/components/auth/TextField';
import { PasswordStrength } from '@/components/auth/PasswordStrength';
import { signUpPatient } from '@/services/auth';

export function PatientSignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '', name: '' });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (form.password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다');
      return;
    }
    setLoading(true);
    try {
      await signUpPatient({
        email: form.email,
        password: form.password,
        displayName: form.name,
      });
      navigate('/patient', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard
      title="환자 회원가입"
      subtitle="선택적 가입 — QR만으로도 사용 가능합니다"
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
        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
        >
          {loading ? '가입 중...' : '가입하기'}
        </button>
      </form>
    </AuthCard>
  );
}
