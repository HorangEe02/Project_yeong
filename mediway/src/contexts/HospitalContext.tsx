import { createContext, useContext, type ReactNode } from 'react';
import type { HospitalProfile } from '@/types/hospital';

/**
 * `HospitalShell` 가 자식들에게 슬러그/프로필을 주입하기 위한 React Context.
 *
 * - `slug`: URL `:hospitalSlug` 파라미터 그대로
 * - `profile`: `subscribeHospitalProfile(slug)` 의 최신 스냅샷 (non-null 보장 — Shell 가 ready 상태에서만 Provider 마운트)
 *
 * 후속 컨슈머:
 *  - `HospitalHomePage` → 디버그 slug 표시를 `profile.name` 으로 치환
 *  - 향후 staff/queue, patient/* 페이지가 hospitalId 대신 본 컨텍스트 사용 가능
 */
export interface HospitalContextValue {
  slug: string;
  profile: HospitalProfile;
}

const HospitalContext = createContext<HospitalContextValue | null>(null);

export function HospitalProvider({
  value,
  children,
}: {
  value: HospitalContextValue;
  children: ReactNode;
}) {
  return (
    <HospitalContext.Provider value={value}>{children}</HospitalContext.Provider>
  );
}

/**
 * 강제 컨슈머 — Shell 외부에서 호출되면 throw.
 * 라우트가 항상 `<HospitalShell>` 아래에 있다는 가정을 컴파일 시에는 표현 못 하므로 런타임 가드.
 */
export function useHospital(): HospitalContextValue {
  const ctx = useContext(HospitalContext);
  if (!ctx) {
    throw new Error(
      'useHospital must be used within <HospitalShell> / <HospitalProvider>',
    );
  }
  return ctx;
}

/**
 * 옵셔널 컨슈머 — Shell 가 없는 페이지(랜딩/관리자/계정)에서도 안전하게 호출.
 * Shell 외부에서는 null 반환.
 */
export function useOptionalHospital(): HospitalContextValue | null {
  return useContext(HospitalContext);
}
