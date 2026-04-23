import { useCallback, useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { updatePreferences } from '@/services/userPreferences';

const ROOT_CLASS = 'ui-senior';

/**
 * 고령자 모드 훅.
 *
 * v2 §Phase 2: P2부터 토글 인프라 도입 (v1은 P4 전용).
 * P4에서 본격 고령자 UI 확장이 이 훅 위에 얹힘.
 *
 * 동작:
 * - 서버 값: `/users/{uid}/preferences/largeUi`
 * - 로컬 반영: `<html>`에 `.ui-senior` class 부여/제거
 * - 로그인 사용자만 서버 persist; 익명 유저는 local only.
 */
export interface UseSeniorModeResult {
  enabled: boolean;
  /** 서버에 쓰는 중 */
  pending: boolean;
  toggle: () => Promise<void>;
  setEnabled: (next: boolean) => Promise<void>;
}

export function useSeniorMode(): UseSeniorModeResult {
  const user = useAuthStore((s) => s.user);
  const profile = useAuthStore((s) => s.profile);
  const enabled = Boolean(profile?.preferences?.largeUi);

  // profile이 로드되거나 enabled가 바뀔 때마다 <html> class 동기화
  useEffect(() => {
    const el = document.documentElement;
    if (enabled) el.classList.add(ROOT_CLASS);
    else el.classList.remove(ROOT_CLASS);
  }, [enabled]);

  const setEnabled = useCallback(
    async (next: boolean) => {
      const el = document.documentElement;
      const before = el.classList.contains(ROOT_CLASS);

      // 즉시 class 반영 (낙관적 UX)
      if (next) el.classList.add(ROOT_CLASS);
      else el.classList.remove(ROOT_CLASS);

      if (user && !user.isAnonymous) {
        try {
          await updatePreferences(user.uid, { largeUi: next });
        } catch (e) {
          // 실패 → 이전 상태로 원복
          if (before) el.classList.add(ROOT_CLASS);
          else el.classList.remove(ROOT_CLASS);
          throw e;
        }
      }
    },
    [user],
  );

  const toggle = useCallback(() => setEnabled(!enabled), [enabled, setEnabled]);

  return { enabled, pending: false, toggle, setEnabled };
}
