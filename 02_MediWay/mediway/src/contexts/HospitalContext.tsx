import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { subscribeHospitalProfile } from '@/services/hospitals';
import { applyHospitalTheme } from '@/services/theme';
import type { HospitalProfile } from '@/types/hospital';

/**
 * 현재 세션의 활성 병원 컨텍스트.
 *
 * - slug === `hospitalId` (URL 세그먼트와 DB 키 일치)
 * - slug가 null이면 "병원 미선택" 상태
 * - 프로필은 RTDB `onValue` 구독으로 실시간 반영 — feature flag·테마 변경 즉시 적용
 */
export interface HospitalContextValue {
  /** URL slug — null이면 병원 미선택 */
  slug: string | null;
  /** 실시간 구독된 프로필 — 로딩·에러·미선택 시 null */
  hospital: HospitalProfile | null;
  /** 초기 로딩 중 */
  loading: boolean;
  /** 로딩 실패 · 권한 거부 시 */
  error: Error | null;
  /** 프로필 없음(slug 유효 but DB 레코드 없음) */
  notFound: boolean;
}

const defaultValue: HospitalContextValue = {
  slug: null,
  hospital: null,
  loading: false,
  error: null,
  notFound: false,
};

const HospitalContext = createContext<HospitalContextValue>(defaultValue);

export interface HospitalProviderProps {
  /** URL slug — `/h/:slug/*` 라우트 param에서 주입 */
  slug: string | null;
  children: ReactNode;
}

/**
 * HospitalProvider — 상위 라우트에서 slug를 받아 병원 프로필을 구독.
 * slug가 바뀌면 이전 구독을 해제하고 새로 구독.
 */
export function HospitalProvider({ slug, children }: HospitalProviderProps) {
  const [hospital, setHospital] = useState<HospitalProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!slug) {
      setHospital(null);
      setLoading(false);
      setError(null);
      setNotFound(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);

    const unsub = subscribeHospitalProfile(
      slug,
      (profile) => {
        setHospital(profile);
        setNotFound(profile === null);
        setLoading(false);
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );
    return () => unsub();
  }, [slug]);

  // 병원 프로필 변경 시 화이트라벨 테마 주입
  useEffect(() => {
    applyHospitalTheme(hospital);
  }, [hospital]);

  const value = useMemo<HospitalContextValue>(
    () => ({ slug, hospital, loading, error, notFound }),
    [slug, hospital, loading, error, notFound],
  );

  return (
    <HospitalContext.Provider value={value}>{children}</HospitalContext.Provider>
  );
}

/**
 * 현재 활성 병원 컨텍스트 소비 — 컴포넌트 내부에서 직접 사용.
 * Provider 바깥에서 호출해도 안전한 기본값을 반환.
 */
export function useHospital(): HospitalContextValue {
  return useContext(HospitalContext);
}

/**
 * "반드시 병원 로드 완료 상태가 필요한" 컴포넌트를 위한 엄격 훅.
 * hospital이 null이면 throw — 사용 전 HospitalGate 등으로 보장 필요.
 */
export function useHospitalStrict(): HospitalProfile & { slug: string } {
  const { hospital, slug } = useHospital();
  if (!hospital || !slug) {
    throw new Error(
      'useHospitalStrict: 병원이 로드되지 않았습니다. HospitalGate로 감싸주세요.',
    );
  }
  return { ...hospital, slug };
}

/**
 * 특정 feature가 현재 병원에서 활성인지 확인.
 * 컨텍스트에 병원이 없으면 false.
 */
export function useHospitalFeature(
  feature: keyof HospitalProfile['features'],
): boolean {
  const { hospital } = useHospital();
  return Boolean(hospital?.features?.[feature]);
}
