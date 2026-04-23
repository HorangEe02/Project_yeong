import { Navigate, Outlet, useParams } from 'react-router-dom';
import { HospitalProvider } from '@/contexts/HospitalContext';
import { HospitalGate } from './HospitalGate';
import { isValidSlug } from '@/services/hospitals';

/**
 * `/h/:slug/*` 라우트 최상단 래퍼.
 * - URL param `:slug` 유효성 검증
 * - HospitalProvider로 하위 Outlet 감쌈
 * - HospitalGate로 로딩·notFound·에러 UI 처리
 */
export function HospitalRouteWrapper() {
  const { slug } = useParams<{ slug: string }>();

  if (!slug || !isValidSlug(slug)) {
    // slug가 없거나 형식이 유효하지 않으면 홈/선택 페이지로
    return <Navigate to="/" replace />;
  }

  return (
    <HospitalProvider slug={slug}>
      <HospitalGate>
        <Outlet />
      </HospitalGate>
    </HospitalProvider>
  );
}
