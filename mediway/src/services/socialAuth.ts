import { signInWithCustomToken } from 'firebase/auth';
import { httpsCallable } from 'firebase/functions';
import { auth, functions } from '@/config/firebase';
import { ensureUserProfile } from '@/services/userProfile';
import type { AuthProvider, UserProfile } from '@/types/auth';

export type SocialProvider = 'kakao' | 'naver';

const STORAGE_KEY = 'mediway.oauth.state';

function redirectUri(provider: SocialProvider): string {
  const origin =
    import.meta.env.VITE_SOCIAL_CALLBACK_ORIGIN || window.location.origin;
  return `${origin}/auth/callback/${provider}`;
}

function generateState(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** 카카오 OAuth 인가 페이지로 이동 */
export function startKakaoLogin(): void {
  const clientId = import.meta.env.VITE_KAKAO_CLIENT_ID;
  if (!clientId) {
    throw new Error('VITE_KAKAO_CLIENT_ID 미설정');
  }
  const state = generateState();
  sessionStorage.setItem(STORAGE_KEY, state);
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri('kakao'),
    state,
  });
  window.location.href = `https://kauth.kakao.com/oauth/authorize?${params.toString()}`;
}

/** 네이버 OAuth 인가 페이지로 이동 */
export function startNaverLogin(): void {
  const clientId = import.meta.env.VITE_NAVER_CLIENT_ID;
  if (!clientId) {
    throw new Error('VITE_NAVER_CLIENT_ID 미설정');
  }
  const state = generateState();
  sessionStorage.setItem(STORAGE_KEY, state);
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri('naver'),
    state,
  });
  window.location.href = `https://nid.naver.com/oauth2.0/authorize?${params.toString()}`;
}

/** 콜백 페이지에서 code/state를 서버에 전달해 Custom Token 교환 + 로그인 */
export async function completeSocialLogin(
  provider: SocialProvider,
  code: string,
  state: string | null,
): Promise<UserProfile> {
  const expected = sessionStorage.getItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
  if (expected && state && expected !== state) {
    throw new Error('state 검증에 실패했습니다');
  }

  const fnName = provider === 'kakao' ? 'kakaoAuth' : 'naverAuth';
  const callable = httpsCallable<
    { code: string; state?: string; redirectUri: string },
    { token: string }
  >(functions, fnName);
  const result = await callable({
    code,
    state: state ?? undefined,
    redirectUri: redirectUri(provider),
  });

  const credential = await signInWithCustomToken(auth, result.data.token);
  const providerKey: AuthProvider = provider;
  return ensureUserProfile(credential.user.uid, {
    email: credential.user.email,
    displayName: credential.user.displayName,
    providers: [providerKey],
    role: 'patient',
  });
}

export function buildAuthorizeUrlForTest(
  provider: SocialProvider,
  clientId: string,
  origin: string,
  state: string,
): string {
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: `${origin}/auth/callback/${provider}`,
    state,
  });
  const base =
    provider === 'kakao'
      ? 'https://kauth.kakao.com/oauth/authorize'
      : 'https://nid.naver.com/oauth2.0/authorize';
  return `${base}?${params.toString()}`;
}
