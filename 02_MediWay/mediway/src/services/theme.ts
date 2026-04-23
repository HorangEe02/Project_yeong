import type { HospitalProfile } from '@/types/hospital';

/**
 * 화이트라벨 런타임 테마 주입.
 * HospitalProvider에서 병원 프로필 로드 시 호출.
 *
 * 구조:
 * - CSS custom property `--color-primary` 등을 `document.documentElement`에 주입
 * - Tailwind 토큰은 `var(--color-primary)`를 참조하므로 빌드 재생성 불필요
 * - SSR 안전 (document 부재 시 no-op)
 */

/** 기본 테마 — 병원 미선택 시 fallback */
export const DEFAULT_THEME = {
  primary: '#004e9f',
  primaryContainer: '#0066cc',
  primaryLight: '#3b82f6',
} as const;

/** CSS custom property 이름 상수 (외부 참조용) */
export const THEME_VARS = {
  primary: '--color-primary',
  primaryContainer: '--color-primary-container',
  primaryLight: '--color-primary-light',
} as const;

/**
 * 병원 프로필 기반으로 테마 주입.
 * profile === null이면 기본 테마로 리셋.
 */
export function applyHospitalTheme(profile: HospitalProfile | null): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;

  const primary = profile?.themeColor ?? DEFAULT_THEME.primary;

  root.style.setProperty(THEME_VARS.primary, primary);
  // container·light는 추후 병원 프로필에 필드가 늘어나면 개별 주입.
  // 현재는 기본값 유지 (병원별 다른 브랜드 팔레트 필요 시 HospitalProfile 확장)
  root.style.setProperty(
    THEME_VARS.primaryContainer,
    DEFAULT_THEME.primaryContainer,
  );
  root.style.setProperty(THEME_VARS.primaryLight, DEFAULT_THEME.primaryLight);
}

/** 명시적으로 기본 테마로 되돌리기 */
export function resetHospitalTheme(): void {
  applyHospitalTheme(null);
}
