import { create } from 'zustand';
import {
  setUiSenior as setUiSeniorRemote,
  subscribeUserPreferences,
} from '@/services/preferences';

/**
 * 고령자 모드 등 사용자 환경설정 상태.
 *
 * persist 전략 (2중화):
 *  - **Truth**: RTDB `/users/{uid}/preferences/uiSenior` — cross-device 공유
 *  - **Cache**: `localStorage.mediway_ui_senior` — 앱 부팅 직후 FOUC 방지용 즉시 적용
 *
 * 흐름:
 *  1) 앱 부팅 → `create(...)` 의 initial state 에서 localStorage 읽어 즉시 반영
 *  2) auth 준비되면 `init(uid)` → RTDB 구독 → 값 수신 시 store 갱신 + localStorage 동기화
 *  3) MoreTab 토글 → `setUiSenior(uid, v)` → localStorage 즉시 갱신 + RTDB write 후속
 */

const LS_KEY = 'mediway_ui_senior';

function readLocalUiSenior(): boolean {
  if (typeof localStorage === 'undefined') return false;
  try {
    return localStorage.getItem(LS_KEY) === '1';
  } catch {
    return false;
  }
}

function writeLocalUiSenior(value: boolean): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(LS_KEY, value ? '1' : '0');
  } catch {
    // quota / privacy — ignore
  }
}

interface PreferencesState {
  uiSenior: boolean;
  initialized: boolean;
  unsubscribe: (() => void) | null;

  /**
   * 로그인 uid 변경 시 호출. null 이면 구독 해제 + localStorage 값 유지.
   * 동일 uid 재호출은 중복 구독을 피하기 위해 내부에서 prev unsub 먼저 호출.
   */
  init: (uid: string | null) => void;

  /** 앱 언마운트 시 구독 정리 */
  cleanup: () => void;

  /** UI 토글 핸들러 — 로컬 즉시 갱신 + RTDB 비동기 write */
  setUiSenior: (uid: string | null, value: boolean) => Promise<void>;
}

export const usePreferencesStore = create<PreferencesState>((set, get) => ({
  uiSenior: readLocalUiSenior(),
  initialized: false,
  unsubscribe: null,

  init: (uid) => {
    const prev = get().unsubscribe;
    if (prev) prev();
    set({ unsubscribe: null, initialized: false });

    if (!uid) {
      // 로그아웃/익명 — localStorage fallback 유지
      set({ uiSenior: readLocalUiSenior(), initialized: true });
      return;
    }

    const unsub = subscribeUserPreferences(uid, (prefs) => {
      const value = !!prefs.uiSenior;
      writeLocalUiSenior(value);
      set({ uiSenior: value, initialized: true });
    });
    set({ unsubscribe: unsub });
  },

  cleanup: () => {
    const u = get().unsubscribe;
    if (u) u();
    set({ unsubscribe: null, initialized: false });
  },

  setUiSenior: async (uid, value) => {
    writeLocalUiSenior(value);
    set({ uiSenior: value });
    if (!uid) return;
    try {
      await setUiSeniorRemote(uid, value);
    } catch (err) {
      // 원격 실패해도 로컬은 유지 — 다음 세션에 동기화 시도
      console.warn('[preferencesStore] remote write failed', err);
    }
  },
}));
