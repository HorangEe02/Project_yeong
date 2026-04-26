import { Navigate, useLocation, useParams } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { Loading } from '@/components/common/Loading';

/**
 * 로그아웃 / 익명 사용자의 fallback 슬러그.
 * 멀티 테넌트 확장 시 ENV (`VITE_DEFAULT_HOSPITAL_SLUG`) 로 분리 가능. 현재는 단일 'demo'.
 */
export const DEFAULT_HOSPITAL_SLUG = 'demo';

/**
 * 인증 상태로부터 redirect 대상 슬러그 결정.
 *  - `null` → 아직 auth 초기화 전 (호출 측은 로딩 표시)
 *  - 로그인 + profile.hospitalId → 그 값
 *  - 로그아웃 / 익명 / profile 없음 → DEFAULT_HOSPITAL_SLUG
 */
export function useResolvedHospitalSlug(): string | null {
  const initialized = useAuthStore((s) => s.initialized);
  const profile = useAuthStore((s) => s.profile);
  if (!initialized) return null;
  return profile?.hospitalId ?? DEFAULT_HOSPITAL_SLUG;
}

/**
 * Flat 라우트(`/patient`, `/staff`, …) 를 nested(`/h/:slug/...`) 로 redirect 하는 wrapper.
 *
 * 동작:
 *  - auth 초기화 전 → `<Loading/>` 표시 (slug 결정 보류)
 *  - 초기화 후 → `buildTarget(slug, params)` 가 만든 경로로 `replace` redirect
 *  - search/hash 는 보존 — bookmark 의 쿼리 파라미터(`?tab=`, `?mode=` 등)도 유지
 */
export function LegacyHospitalRedirect({
  buildTarget,
}: {
  buildTarget: (
    slug: string,
    params: Record<string, string | undefined>,
  ) => string;
}) {
  const slug = useResolvedHospitalSlug();
  const params = useParams<Record<string, string | undefined>>();
  const location = useLocation();

  if (slug === null) {
    return <Loading message="이동할 병원을 확인 중..." />;
  }

  const target = buildTarget(slug, params);
  return (
    <Navigate to={`${target}${location.search}${location.hash}`} replace />
  );
}
