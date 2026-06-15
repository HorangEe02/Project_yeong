import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AuthUser {
  employee_id: string;
  username: string;
  role_name: string;
  role_level: number;
  department?: string;
  position?: string;
}

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: () => boolean;
  setSession: (user: AuthUser) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: () => Boolean(get().user),
      setSession: (user) => set({ user }),
      clear: () => set({ user: null }),
    }),
    { name: 'ajin-auth' },
  ),
);
