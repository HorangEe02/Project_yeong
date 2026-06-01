// 모바일 BottomTab prefs — 서버 user_prefs 와 동기화 (v4.5).
//
// GET 1회 (로그인 직후 자동) + PUT (사용자가 설정 변경 시 즉시).
// 네트워크 실패 시 in-memory 상태 유지. localStorage 미사용 (서버가 진실 소스).

import { useCallback, useEffect, useState } from 'react';

import { api } from '@api/client';
import { useAuthStore } from '@store/auth';
import { DEFAULT_CUSTOM_SLOTS, type MobileTabPrefs } from '@components/shell/mobileTabs';

interface ServerPrefs {
  override: boolean;
  custom_slots: string[];
  updated_at?: string | null;
}

const DEFAULTS: MobileTabPrefs = {
  override: false,
  customSlots: DEFAULT_CUSTOM_SLOTS,
};

interface State extends MobileTabPrefs {
  loaded: boolean;
  saving: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  save: (next: Partial<MobileTabPrefs>) => Promise<void>;
  resetDefaults: () => Promise<void>;
}

export function useMobileTabPrefs(): State {
  const user = useAuthStore((s) => s.user);
  const [prefs, setPrefs] = useState<MobileTabPrefs>(DEFAULTS);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!user) {
      setPrefs(DEFAULTS);
      setLoaded(true);
      return;
    }
    setError(null);
    try {
      const { data } = await api.get<ServerPrefs>('/me/mobile-tab-prefs');
      const slots = (data.custom_slots ?? DEFAULT_CUSTOM_SLOTS).slice(0, 2);
      while (slots.length < 2) slots.push(DEFAULT_CUSTOM_SLOTS[slots.length]);
      setPrefs({
        override: !!data.override,
        customSlots: [slots[0], slots[1]],
      });
    } catch (err) {
      // 미존재·네트워크 실패 → 기본값 유지. 사용자에겐 silent (BottomTabBar는 페르소나 자동으로 동작).
      const msg = err instanceof Error ? err.message : String(err);
      console.warn('[mobile-tab-prefs] GET 실패:', msg);
      setError(msg);
      setPrefs(DEFAULTS);
    } finally {
      setLoaded(true);
    }
  }, [user]);

  const save = useCallback(
    async (next: Partial<MobileTabPrefs>) => {
      const merged: MobileTabPrefs = {
        override: next.override ?? prefs.override,
        customSlots: next.customSlots ?? prefs.customSlots,
      };
      setPrefs(merged); // optimistic
      if (!user) return;
      setSaving(true);
      setError(null);
      try {
        await api.put('/me/mobile-tab-prefs', {
          override: merged.override,
          custom_slots: merged.customSlots,
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.warn('[mobile-tab-prefs] PUT 실패:', msg);
        setError(msg);
      } finally {
        setSaving(false);
      }
    },
    [prefs.override, prefs.customSlots, user],
  );

  const resetDefaults = useCallback(async () => {
    await save({ override: false, customSlots: DEFAULT_CUSTOM_SLOTS });
  }, [save]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    ...prefs,
    loaded,
    saving,
    error,
    refresh,
    save,
    resetDefaults,
  };
}
