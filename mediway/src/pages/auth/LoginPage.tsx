import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AuthCard } from '@/components/auth/AuthCard';
import { TextField } from '@/components/auth/TextField';
import { GoogleButton } from '@/components/auth/GoogleButton';
import { KakaoButton } from '@/components/auth/KakaoButton';
import { NaverButton } from '@/components/auth/NaverButton';
import { signInWithEmail, signInWithGoogle } from '@/services/auth';
import { startKakaoLogin, startNaverLogin } from '@/services/socialAuth';
import type { UserProfile } from '@/types/auth';

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const redirect = params.get('redirect');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const afterLogin = (profile: UserProfile) => {
    if (redirect) {
      navigate(redirect, { replace: true });
      return;
    }
    if (profile.role === 'staff' || profile.role === 'admin') {
      navigate('/staff', { replace: true });
    } else {
      navigate('/patient', { replace: true });
    }
  };

  const onEmailSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const profile = await signInWithEmail(email, password);
      afterLogin(profile);
    } catch (err) {
      setError(translateAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  const onGoogle = async () => {
    setError(null);
    setLoading(true);
    try {
      const profile = await signInWithGoogle();
      afterLogin(profile);
    } catch (err) {
      setError(translateAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard
      title="로그인"
      subtitle="MediWay 계정으로 로그인합니다"
      footer={
        <span>
          계정이 없으신가요?{' '}
          <Link to="/signup" className="font-medium text-primary">
            회원가입
          </Link>
        </span>
      }
    >
      <form onSubmit={onEmailSubmit} className="flex flex-col gap-4">
        <TextField
          label="이메일"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="비밀번호"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
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
          {loading ? '로그인 중...' : '로그인'}
        </button>

        <div className="flex items-center justify-between text-xs">
          <Link to="/forgot-password" className="text-on-surface-variant">
            비밀번호 찾기
          </Link>
        </div>
      </form>

      <div className="my-5 flex items-center gap-3">
        <div className="h-px flex-1 bg-surface-container-high" />
        <span className="text-xs text-on-surface-variant">또는</span>
        <div className="h-px flex-1 bg-surface-container-high" />
      </div>

      <div className="flex flex-col gap-2">
        <GoogleButton onClick={onGoogle} disabled={loading} />
        <KakaoButton
          onClick={() => {
            try {
              startKakaoLogin();
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            }
          }}
          disabled={loading}
        />
        <NaverButton
          onClick={() => {
            try {
              startNaverLogin();
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            }
          }}
          disabled={loading}
        />
      </div>
    </AuthCard>
  );
}

function translateAuthError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.includes('auth/invalid-credential') || msg.includes('auth/wrong-password')) {
    return '이메일 또는 비밀번호가 올바르지 않습니다';
  }
  if (msg.includes('auth/user-not-found')) {
    return '등록되지 않은 계정입니다';
  }
  if (msg.includes('auth/too-many-requests')) {
    return '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요';
  }
  if (msg.includes('auth/popup-closed-by-user')) {
    return '로그인이 취소되었습니다';
  }
  return msg;
}
