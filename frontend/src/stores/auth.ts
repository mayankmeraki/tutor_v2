import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AuthUser {
  email: string;
  name?: string;
  picture?: string;
  is_admin?: boolean;
  [key: string]: unknown;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: () => boolean;
  setAuth: (token: string, user: AuthUser) => void;
  clear: () => void;
  setUser: (user: AuthUser) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: () => !!get().token && !!get().user,
      setAuth: (token, user) => set({ token, user }),
      clear: () => set({ token: null, user: null }),
      setUser: (user) => set({ user }),
    }),
    {
      name: 'mockup_auth',
      partialize: (s) => ({ token: s.token, user: s.user }),
    },
  ),
);

export function getToken(): string | null {
  return useAuthStore.getState().token;
}
