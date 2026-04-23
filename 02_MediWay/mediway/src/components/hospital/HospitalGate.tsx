import { type ReactNode } from 'react';
import { useHospital } from '@/hooks/useHospital';

/**
 * 병원 프로필 로딩 상태에 따라 UI를 분기.
 * - loading: 스피너/메시지
 * - error: 에러 메시지
 * - notFound: "존재하지 않는 병원"
 * - loaded: children 렌더
 *
 * HospitalProvider 내부에 배치. `/h/:slug/*` 라우트 트리의 최상단.
 */
export interface HospitalGateProps {
  children: ReactNode;
  /** 로딩 UI 커스터마이즈 — 기본값 있음 */
  loadingFallback?: ReactNode;
  /** notFound UI 커스터마이즈 */
  notFoundFallback?: ReactNode;
}

export function HospitalGate({
  children,
  loadingFallback,
  notFoundFallback,
}: HospitalGateProps) {
  const { loading, notFound, error } = useHospital();

  if (loading) {
    return (
      loadingFallback ?? (
        <div className="p-8 text-center text-muted" role="status" aria-live="polite">
          병원 정보를 불러오는 중...
        </div>
      )
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-danger" role="alert">
        병원 정보를 불러오지 못했습니다. ({error.message})
      </div>
    );
  }

  if (notFound) {
    return (
      notFoundFallback ?? (
        <div className="p-8 text-center">
          <h2 className="text-xl font-semibold mb-2">존재하지 않는 병원입니다</h2>
          <p className="text-muted mb-4">URL의 병원 slug를 다시 확인해 주세요.</p>
          <a href="/" className="text-primary underline">
            병원 선택 페이지로 돌아가기
          </a>
        </div>
      )
    );
  }

  return <>{children}</>;
}
