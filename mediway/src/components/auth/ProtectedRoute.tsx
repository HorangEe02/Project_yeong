import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuthStore, selectIsSuspended } from '@/stores/authStore';
import { Loading } from '@/components/common/Loading';
import type { UserRole } from '@/types/auth';

interface ProtectedRouteProps {
  children: ReactNode;
  /** 허용되는 역할 목록. 미지정 시 로그인만 요구 */
  requireRole?: UserRole[];
  /** 미로그인 리다이렉트 경로 */
  redirectTo?: string;
}

export function ProtectedRoute({
  children,
  requireRole,
  redirectTo = '/login',
}: ProtectedRouteProps) {
  const location = useLocation();
  const { user, profile, initialized } = useAuthStore();
  const suspended = useAuthStore(selectIsSuspended);

  if (!initialized) {
    return <Loading message="인증 상태 확인 중..." />;
  }

  // 1) 미로그인(익명 포함)
  if (!user || user.isAnonymous) {
    const search = `?redirect=${encodeURIComponent(location.pathname + location.search)}`;
    return <Navigate to={`${redirectTo}${search}`} replace />;
  }

  // 2) 프로필 미확보 — 역할 요구 라우트에서만 로딩 처리
  if (requireRole && !profile) {
    return <Loading message="프로필 확인 중..." />;
  }

  // 3) 계정 정지/삭제
  if (suspended) {
    return <Navigate to="/forbidden?reason=suspended" replace />;
  }

  // 4) 역할 불일치
  if (requireRole && profile && !requireRole.includes(profile.role)) {
    return <Navigate to="/forbidden?reason=role" replace />;
  }

  return <>{children}</>;
}
