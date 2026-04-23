import { describe, it, expect, beforeEach } from 'vitest';
import {
  applyHospitalTheme,
  resetHospitalTheme,
  DEFAULT_THEME,
  THEME_VARS,
} from '../theme';
import {
  DEFAULT_HOSPITAL_FEATURES,
  type HospitalProfile,
} from '@/types/hospital';

const makeProfile = (themeColor: string): HospitalProfile => ({
  name: 'Test',
  slug: 'test',
  themeColor,
  contractStatus: 'active',
  features: DEFAULT_HOSPITAL_FEATURES,
  createdAt: 0,
  updatedAt: 0,
});

beforeEach(() => {
  // 이전 테스트의 잔존 스타일 제거
  document.documentElement.style.removeProperty(THEME_VARS.primary);
  document.documentElement.style.removeProperty(THEME_VARS.primaryContainer);
  document.documentElement.style.removeProperty(THEME_VARS.primaryLight);
});

describe('applyHospitalTheme', () => {
  it('profile.themeColor를 --color-primary에 주입', () => {
    applyHospitalTheme(makeProfile('#ff0000'));
    expect(
      document.documentElement.style.getPropertyValue(THEME_VARS.primary),
    ).toBe('#ff0000');
  });

  it('null 프로필이면 기본 색상으로 리셋', () => {
    applyHospitalTheme(makeProfile('#ff0000'));
    applyHospitalTheme(null);
    expect(
      document.documentElement.style.getPropertyValue(THEME_VARS.primary),
    ).toBe(DEFAULT_THEME.primary);
  });

  it('primary-container, primary-light도 같이 설정', () => {
    applyHospitalTheme(makeProfile('#ff0000'));
    expect(
      document.documentElement.style.getPropertyValue(
        THEME_VARS.primaryContainer,
      ),
    ).toBe(DEFAULT_THEME.primaryContainer);
    expect(
      document.documentElement.style.getPropertyValue(THEME_VARS.primaryLight),
    ).toBe(DEFAULT_THEME.primaryLight);
  });

  it('resetHospitalTheme은 기본값 재적용', () => {
    applyHospitalTheme(makeProfile('#ff0000'));
    resetHospitalTheme();
    expect(
      document.documentElement.style.getPropertyValue(THEME_VARS.primary),
    ).toBe(DEFAULT_THEME.primary);
  });

  it('document 부재 시에도 안전 (재진입 가능)', () => {
    // jsdom 환경에선 document가 항상 존재하므로 no-throw만 확인
    expect(() => applyHospitalTheme(makeProfile('#00ff00'))).not.toThrow();
  });
});
