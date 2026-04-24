import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AuthCard } from '@/components/auth/AuthCard';
import { completeSocialLogin, type SocialProvider } from '@/services/socialAuth';

export function SocialCallbackPage() {
  const { provider = '' } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const ran = useRef(false);
  const [status, setStatus] = useState<
    { state: 'processing' } | { state: 'error'; message: string }
  >({ state: 'processing' });

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const code = params.get('code');
    const state = params.get('state');
    const error = params.get('error') ?? params.get('error_description');

    if (!isValidProvider(provider)) {
      setStatus({ state: 'error', message: '지원하지 않는 공급자입니다' });
      return;
    }
    if (error) {
      setStatus({ state: 'error', message: error });
      return;
    }
    if (!code) {
      setStatus({ state: 'error', message: '인가 코드가 없습니다' });
      return;
    }

    void (async () => {
      try {
        const profile = await completeSocialLogin(provider as SocialProvider, code, state);
        if (profile.role === 'staff' || profile.role === 'admin') {
          navigate('/staff', { replace: true });
        } else {
          navigate('/patient', { replace: true });
        }
      } catch (err) {
        setStatus({
          state: 'error',
          message: err instanceof Error ? err.message : String(err),
        });
      }
    })();
  }, [provider, params, navigate]);

  return (
    <AuthCard
      title={status.state === 'processing' ? '로그인 처리 중' : '로그인 실패'}
      subtitle={providerLabel(provider)}
    >
      {status.state === 'processing' ? (
        <div className="flex items-center gap-3 text-sm text-on-surface-variant">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          잠시만 기다려주세요...
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
            {status.message}
          </p>
          <button
            type="button"
            onClick={() => navigate('/login', { replace: true })}
            className="self-start rounded-lg border border-surface-container-high px-3 py-2 text-xs"
          >
            로그인 페이지로
          </button>
        </div>
      )}
    </AuthCard>
  );
}

function isValidProvider(p: string): boolean {
  return p === 'kakao' || p === 'naver';
}

function providerLabel(p: string): string {
  if (p === 'kakao') return '카카오 로그인';
  if (p === 'naver') return '네이버 로그인';
  return '';
}
