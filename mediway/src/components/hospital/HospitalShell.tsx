import { useEffect, useState } from 'react';
import { Navigate, Outlet, useParams } from 'react-router-dom';
import { Loading } from '@/components/common/Loading';
import { HospitalProvider } from '@/contexts/HospitalContext';
import {
  resolveThemeColor,
  subscribeHospitalProfile,
} from '@/services/hospitalProfile';
import { useAuthStore } from '@/stores/authStore';
import type { HospitalProfile } from '@/types/hospital';

/**
 * `/h/:hospitalSlug/*` 라우트 wrapper.
 *
 * 책임:
 *  1. URL 의 `:hospitalSlug` 추출 → `/hospitals/{slug}/profile` 실시간 구독
 *  2. profile 미존재 → 404 안내 (NotFoundHospital)
 *  3. profile.status === 'suspended' → `/forbidden?reason=hospital-suspended`
 *  4. cross-tenant 가드:
 *      - 로그인 + profile.hospitalId 있음 + slug 와 다름 + role !== 'platformAdmin'
 *      - → `/forbidden?reason=cross-tenant`
 *      - (익명, role='admin' 인 경우는 본 가드 적용. platformAdmin 만 자유 열람)
 *  5. themeColor 를 CSS var `--theme-primary` 에 주입 (`#deadbe` 같은 invalid 값은 fallback)
 *  6. ready 상태에서 `<HospitalProvider>` 로 `<Outlet/>` 감쌈
 *
 * 비관심사:
 *  - role 게이트는 자식 라우트의 `ProtectedRoute` 가 담당 (staff/admin 분기)
 *  - tab 라우팅, header 표시는 별도 컴포넌트
 */

type ShellState =
  | { kind: 'loading' }
  | { kind: 'not-found' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; profile: HospitalProfile };

export function HospitalShell() {
  const { hospitalSlug } = useParams<{ hospitalSlug: string }>();
  const user = useAuthStore((s) => s.user);
  const profile = useAuthStore((s) => s.profile);
  const initialized = useAuthStore((s) => s.initialized);

  const [state, setState] = useState<ShellState>({ kind: 'loading' });

  // 1) profile 구독
  useEffect(() => {
    if (!hospitalSlug) {
      setState({ kind: 'not-found' });
      return;
    }
    setState({ kind: 'loading' });
    const unsub = subscribeHospitalProfile(
      hospitalSlug,
      (data) => {
        if (!data) {
          setState({ kind: 'not-found' });
        } else {
          setState({ kind: 'ready', profile: data });
        }
      },
      (err) => {
        setState({
          kind: 'error',
          message: err.message || '병원 정보를 불러오지 못했습니다',
        });
      },
    );
    return unsub;
  }, [hospitalSlug]);

  // 2) themeColor 주입 (ready 상태에서만)
  useEffect(() => {
    if (state.kind !== 'ready') return;
    const color = resolveThemeColor(state.profile.themeColor);
    const root = document.documentElement;
    const prev = root.style.getPropertyValue('--theme-primary');
    root.style.setProperty('--theme-primary', color);
    return () => {
      // 다른 슬러그로 이동하거나 Shell 언마운트 시 이전 값 복원
      if (prev) root.style.setProperty('--theme-primary', prev);
      else root.style.removeProperty('--theme-primary');
    };
  }, [state]);

  if (state.kind === 'loading') {
    return <Loading message="병원 정보를 불러오는 중..." />;
  }

  if (state.kind === 'not-found') {
    return <NotFoundHospital slug={hospitalSlug ?? ''} />;
  }

  if (state.kind === 'error') {
    return <ErrorHospital slug={hospitalSlug ?? ''} message={state.message} />;
  }

  // suspended → forbidden
  if (state.profile.status === 'suspended') {
    return <Navigate to="/forbidden?reason=hospital-suspended" replace />;
  }

  // cross-tenant 가드 — initialized 후에만 평가 (auth 부팅 중에 false 평가하지 않도록)
  const isLoggedIn = !!user && !user.isAnonymous;
  const isPlatformAdmin = profile?.role === 'platformAdmin';
  if (
    initialized &&
    isLoggedIn &&
    profile?.hospitalId &&
    profile.hospitalId !== hospitalSlug &&
    !isPlatformAdmin
  ) {
    return <Navigate to="/forbidden?reason=cross-tenant" replace />;
  }

  return (
    <HospitalProvider
      value={{ slug: hospitalSlug as string, profile: state.profile }}
    >
      <Outlet />
    </HospitalProvider>
  );
}

function NotFoundHospital({ slug }: { slug: string }) {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16 text-center">
      <h1 className="text-2xl font-bold text-on-surface">
        병원을 찾을 수 없습니다
      </h1>
      <p className="mt-2 text-sm text-on-surface-variant">
        슬러그{' '}
        <code className="rounded bg-surface-container-low px-1.5">{slug}</code>{' '}
        에 해당하는 병원이 존재하지 않거나 삭제되었습니다.
      </p>
    </main>
  );
}

function ErrorHospital({ slug, message }: { slug: string; message: string }) {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16 text-center">
      <h1 className="text-2xl font-bold text-on-surface">
        병원 정보 로드 실패
      </h1>
      <p className="mt-2 text-sm text-on-surface-variant">
        슬러그{' '}
        <code className="rounded bg-surface-container-low px-1.5">{slug}</code>{' '}
        의 정보를 가져오지 못했습니다.
      </p>
      <p className="mt-1 text-xs text-on-surface-variant/70">{message}</p>
    </main>
  );
}
