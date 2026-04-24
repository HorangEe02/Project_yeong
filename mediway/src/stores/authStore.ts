import { create } from 'zustand';
import type { User } from 'firebase/auth';
import { onAuthChange, syncEmailToProfile } from '@/services/auth';
import { subscribeUserProfile } from '@/services/userProfile';
import { isFirebaseConfigured } from '@/config/firebase';
import { refreshMyClaims } from '@/hooks/useRefreshToken';
import type { UserProfile, UserRole } from '@/types/auth';

/**
 * 한 uid 당 한 번만 claim 자동 주입을 시도한다 (부팅·재구독마다 호출 방지).
 * 가입 직후 or ensureUserRecord 실패 직후 등 claim이 비어있는 edge case만 커버.
 */
const claimsCheckedForUid = new Set<string>();

async function ensureClaimsForUser(user: User): Promise<void> {
  if (user.isAnonymous) return;
  if (claimsCheckedForUid.has(user.uid)) return;
  claimsCheckedForUid.add(user.uid);
  try {
    const tokenResult = await user.getIdTokenResult();
    if (typeof tokenResult.claims.role === 'string') return;
    await refreshMyClaims();
  } catch (err) {
    // 실패해도 로그인 자체는 유지 — 다음 상호작용에서 재시도 가능
    console.warn('[authStore] claim 자동 갱신 실패', err);
  }
}

interface AuthState {
  user: User | null;
  profile: UserProfile | null;
  initialized: boolean;
  loading: boolean;
  profileUnsub: (() => void) | null;
  authUnsub: (() => void) | null;

  init: () => void;
  cleanup: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  profile: null,
  initialized: false,
  loading: false,
  profileUnsub: null,
  authUnsub: null,

  init: () => {
    if (get().authUnsub) return; // 중복 구독 방지

    if (!isFirebaseConfigured()) {
      set({ initialized: true });
      return;
    }

    const authUnsub = onAuthChange((user) => {
      // 이전 프로필 구독 해제
      const prevProfileUnsub = get().profileUnsub;
      if (prevProfileUnsub) prevProfileUnsub();

      if (!user) {
        // 로그아웃 시 자동 claim 체크 기록 초기화 — 재로그인 시 (특히 admin이 권한을
        // 바꾼 뒤) 다시 한 번 최신 claim을 확인할 기회를 확보한다.
        claimsCheckedForUid.clear();
        set({
          user: null,
          profile: null,
          profileUnsub: null,
          initialized: true,
        });
        return;
      }

      // 익명 사용자는 프로필을 구독하지 않는다
      if (user.isAnonymous) {
        set({ user, profile: null, profileUnsub: null, initialized: true });
        return;
      }

      const profileUnsub = subscribeUserProfile(user.uid, (profile) => {
        // 프로필이 존재할 때만 이메일 동기화 — 존재하지 않으면 signUp* 플로우가
        // ensureUserProfile로 완전한 프로필을 생성하도록 맡긴다. (race condition 방지)
        if (profile) {
          void syncEmailToProfile(user, profile.email ?? null).catch(() => {});
          // 프로필이 존재하면 claim도 있어야 정상 — 누락된 경우만 1회 자동 주입
          void ensureClaimsForUser(user);
        }
        set({ profile, initialized: true });
      });
      set({ user, profileUnsub, initialized: true });
    });

    set({ authUnsub });
  },

  cleanup: () => {
    const { authUnsub, profileUnsub } = get();
    if (authUnsub) authUnsub();
    if (profileUnsub) profileUnsub();
    set({ authUnsub: null, profileUnsub: null });
  },

  setLoading: (loading) => set({ loading }),
}));

// --- 셀렉터 ---

export const selectIsAuthenticated = (s: AuthState): boolean =>
  !!s.user && !s.user.isAnonymous;

export const selectRole = (s: AuthState): UserRole | null =>
  s.profile?.role ?? null;

export const selectIsStaff = (s: AuthState): boolean =>
  s.profile?.role === 'staff' || s.profile?.role === 'admin';

export const selectIsAdmin = (s: AuthState): boolean =>
  s.profile?.role === 'admin';

export const selectIsSuspended = (s: AuthState): boolean =>
  s.profile?.status === 'suspended' || s.profile?.status === 'deleted';
