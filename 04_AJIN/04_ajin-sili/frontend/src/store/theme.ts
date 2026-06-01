import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ThemePreference = 'light' | 'dark' | 'auto';
export type ResolvedTheme = 'light' | 'dark';

interface ThemeState {
  preference: ThemePreference;
  setPreference: (pref: ThemePreference) => void;
  resolved: () => ResolvedTheme;
}

const resolveAuto = (): ResolvedTheme => {
  const hour = new Date().getHours();
  return hour >= 6 && hour < 18 ? 'light' : 'dark';
};

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      // 신규 사용자(persisted state 없음) 기본값. 6~18시 light / 18~6시 dark 자동 분기.
      preference: 'auto',
      setPreference: (preference) => {
        set({ preference });
        document.documentElement.setAttribute(
          'data-theme',
          preference === 'auto' ? resolveAuto() : preference,
        );
      },
      resolved: () => {
        const pref = get().preference;
        return pref === 'auto' ? resolveAuto() : pref;
      },
    }),
    {
      name: 'ajin-theme',
      // v2: 기본값을 'dark' → 'auto' 로 전환. 기존 사용자도 한 번 auto 로 리셋.
      version: 2,
      migrate: (persistedState, fromVersion) => {
        if (fromVersion < 2) {
          return { ...(persistedState as Partial<ThemeState>), preference: 'auto' };
        }
        return persistedState as ThemeState;
      },
    },
  ),
);
