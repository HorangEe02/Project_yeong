import { createContext, useContext, useMemo, type ReactNode } from 'react';
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

/**
 * Hospital feature flag 의 기본값.
 *
 * RTDB `hospitals/{slug}/profile/features/{key}` 가 누락되어도 안전하게 동작하도록
 * 사용처는 `useHospitalFeatures()` 로 합쳐서 사용.
 *
 * 정책 (F1 기준):
 *  - `appointments=true` — wait queue + AppointmentsTab 의 핵심. demo 병원 default ON
 *  - `chatbot=true` — ChatbotWidget 의 default ON (admin UI 에는 노출 안 됨)
 *  - 그 외 (inpatient/checkup/payment/prescription/aiTriage/familyDelegation/healthRecords/parking) → false
 *
 * 알 수 없는 key 는 본 매트릭스 미존재 → `useFeature(unknownKey)` 는 false 반환.
 */
export const FEATURE_DEFAULTS: Readonly<Record<string, boolean>> = Object.freeze({
  appointments: true,
  chatbot: true,
  inpatient: false,
  checkup: false,
  payment: false,
  prescription: false,
  aiTriage: false,
  familyDelegation: false,
  healthRecords: false,
  parking: false,
  /**
   * 응급 호출 (119 + 현재 위치 표시) — 윤리·법적 검토 영역.
   * default false → 병원 admin 가 명시 enable 한 hospital 만 위젯 노출.
   * GuideTab 「응급 호출」 모드 탭이 features.emergencyCall=true 일 때만 추가됨.
   */
  emergencyCall: false,
});

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

/**
 * Hospital features 와 defaults 를 병합한 read-only 매트릭스.
 *
 * 우선순위: RTDB 값 > defaults. RTDB 가 명시적으로 `false` 로 설정한 값은 default 가 true 여도 false.
 * 키는 안정 정렬 (defaults 의 모든 key 가 항상 포함됨 → conditional render 가 undefined 분기 안 만들어도 됨).
 *
 * F1 기준 사용처:
 *  - `WaitQueueWidget` — `features.appointments` 가드
 *  - `HomeTab` — `features.chatbot`, `features.aiTriage` 분기
 *  - `HospitalHomePage` — `features.appointments|inpatient|checkup` 으로 탭 가시성
 */
export function useHospitalFeatures(): Readonly<Record<string, boolean>> {
  const { profile } = useHospital();
  return useMemo(
    () => Object.freeze({ ...FEATURE_DEFAULTS, ...(profile.features ?? {}) }),
    [profile.features],
  );
}

/** 단일 feature 의 boolean 평가. 알 수 없는 key 는 false. */
export function useFeature(key: string): boolean {
  return useHospitalFeatures()[key] === true;
}
