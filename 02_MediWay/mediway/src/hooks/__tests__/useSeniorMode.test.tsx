import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// authStore mock
const authStoreState: {
  user: { uid: string; isAnonymous: boolean } | null;
  profile: { preferences?: { largeUi?: boolean } } | null;
} = {
  user: { uid: 'uid-a', isAnonymous: false },
  profile: { preferences: { largeUi: false } },
};
vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: typeof authStoreState) => unknown) =>
    selector(authStoreState),
}));

const updatePreferencesMock = vi.fn();
vi.mock('@/services/userPreferences', () => ({
  updatePreferences: (uid: string, patch: unknown) =>
    updatePreferencesMock(uid, patch),
}));

import { useSeniorMode } from '../useSeniorMode';

beforeEach(() => {
  updatePreferencesMock.mockReset();
  authStoreState.user = { uid: 'uid-a', isAnonymous: false };
  authStoreState.profile = { preferences: { largeUi: false } };
  document.documentElement.classList.remove('ui-senior');
});

describe('useSeniorMode', () => {
  it('profile.largeUi=false 시작 → html에 class 없음', () => {
    renderHook(() => useSeniorMode());
    expect(document.documentElement.classList.contains('ui-senior')).toBe(false);
  });

  it('profile.largeUi=true 시작 → html에 class 자동 주입', () => {
    authStoreState.profile = { preferences: { largeUi: true } };
    renderHook(() => useSeniorMode());
    expect(document.documentElement.classList.contains('ui-senior')).toBe(true);
  });

  it('setEnabled(true) → class 주입 + updatePreferences 호출', async () => {
    updatePreferencesMock.mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useSeniorMode());
    await act(async () => {
      await result.current.setEnabled(true);
    });
    expect(document.documentElement.classList.contains('ui-senior')).toBe(true);
    expect(updatePreferencesMock).toHaveBeenCalledWith('uid-a', {
      largeUi: true,
    });
  });

  it('익명 유저는 서버 persist 생략 (local only)', async () => {
    authStoreState.user = { uid: 'anon', isAnonymous: true };
    const { result } = renderHook(() => useSeniorMode());
    await act(async () => {
      await result.current.setEnabled(true);
    });
    expect(document.documentElement.classList.contains('ui-senior')).toBe(true);
    expect(updatePreferencesMock).not.toHaveBeenCalled();
  });

  it('서버 실패 시 에러 전파', async () => {
    updatePreferencesMock.mockRejectedValueOnce(new Error('offline'));
    const { result } = renderHook(() => useSeniorMode());
    await expect(
      act(async () => {
        await result.current.setEnabled(true);
      }),
    ).rejects.toThrow('offline');
    expect(updatePreferencesMock).toHaveBeenCalled();
  });
});
