import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AuthUser {
  employee_id: string;
  username: string;
  role_name: string;
  role_level: number;
  department?: string;
  position?: string;
  firebase_uid?: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: () => boolean;
  setSession: (
    accessToken: string,
    refreshToken: string,
    user: AuthUser,
    firebaseUid?: string,
  ) => void;
  setFirebaseUid: (uid: string | null) => void;
  setAccessToken: (token: string) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: () => Boolean(get().accessToken && get().user),
      setSession: (accessToken, refreshToken, user, firebaseUid) =>
        set({
          accessToken,
          refreshToken,
          user: firebaseUid ? { ...user, firebase_uid: firebaseUid } : user,
        }),
      setFirebaseUid: (uid) => {
        const u = get().user;
        if (!u) return;
        set({ user: { ...u, firebase_uid: uid ?? undefined } });
      },
      setAccessToken: (token) => set({ accessToken: token }),
      clear: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: 'ajin-auth' },
  ),
);
