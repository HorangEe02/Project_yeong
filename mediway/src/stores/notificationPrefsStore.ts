import { create } from 'zustand';
import {
  revokeAllNotifications,
  restoreNotifications,
  setNotificationChannel as setChannelRemote,
  setNotificationScenario as setScenarioRemote,
  subscribeNotificationPrefs,
} from '@/services/notificationPrefs';
import type {
  NotificationChannel,
  NotificationEventType,
  UserNotificationPrefs,
} from '@/types/notificationPrefs';

/**
 * F5c 사용자 알림 prefs 스토어.
 *
 * 흐름:
 *  1) MoreTab 진입 시 `init(uid)` → /users/{uid}/notifications 구독 시작
 *  2) 서버에서 값 수신 → store 갱신 → UI 자동 반영
 *  3) 토글 조작 → set*Remote → onValue 이벤트 재수신 → store 최종 확정 (optimistic 업데이트 없이 단순 패턴)
 */

interface NotificationPrefsState {
  prefs: UserNotificationPrefs;
  initialized: boolean;
  unsubscribe: (() => void) | null;
  error: string | null;

  init: (uid: string | null) => void;
  cleanup: () => void;
  setChannel: (uid: string, channel: NotificationChannel, enabled: boolean) => Promise<void>;
  setScenario: (uid: string, scenario: NotificationEventType, enabled: boolean) => Promise<void>;
  revokeAll: (uid: string) => Promise<void>;
  restore: (uid: string) => Promise<void>;
}

export const useNotificationPrefsStore = create<NotificationPrefsState>((set, get) => ({
  prefs: {},
  initialized: false,
  unsubscribe: null,
  error: null,

  init: (uid) => {
    const prev = get().unsubscribe;
    if (prev) prev();
    set({ unsubscribe: null, initialized: false, error: null });

    if (!uid) {
      set({ prefs: {}, initialized: true });
      return;
    }
    const unsub = subscribeNotificationPrefs(
      uid,
      (prefs) => set({ prefs, initialized: true }),
      (err) => set({ error: err.message || '알림 설정 불러오기 실패' }),
    );
    set({ unsubscribe: unsub });
  },

  cleanup: () => {
    const u = get().unsubscribe;
    if (u) u();
    set({ unsubscribe: null, initialized: false });
  },

  setChannel: async (uid, channel, enabled) => {
    try {
      await setChannelRemote(uid, channel, enabled);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '채널 저장 실패' });
    }
  },

  setScenario: async (uid, scenario, enabled) => {
    try {
      await setScenarioRemote(uid, scenario, enabled);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '시나리오 저장 실패' });
    }
  },

  revokeAll: async (uid) => {
    try {
      await revokeAllNotifications(uid);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '전체 거부 실패' });
    }
  },

  restore: async (uid) => {
    try {
      await restoreNotifications(uid);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '전체 거부 해제 실패' });
    }
  },
}));
