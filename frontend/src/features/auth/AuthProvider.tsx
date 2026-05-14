import { createContext, useCallback, useContext, useEffect, type ReactNode } from 'react';
import { authApi, ApiError } from '@/lib/api';
import { useAuthStore, type AuthUser } from '@/stores/auth';

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Legacy compatibility: migrate `mockup_auth_token` + `mockup_auth_user` (set
 * by the vanilla-JS legacy app) into the new Zustand-persisted store the first
 * time the React app loads. Runs synchronously at module load to avoid a flash
 * of unauthenticated UI.
 */
function migrateLegacyAuthOnce(): void {
  if (typeof window === 'undefined') return;
  try {
    const token = window.localStorage.getItem('mockup_auth_token');
    const userJson = window.localStorage.getItem('mockup_auth_user');
    const newState = window.localStorage.getItem('mockup_auth');
    if (token && userJson && !newState) {
      const user = JSON.parse(userJson);
      useAuthStore.getState().setAuth(token, user);
      // Keep the legacy keys in place for now so a user toggling between apps
      // during the rollout still works. They will be cleared on logout.
    }
  } catch {
    /* ignore */
  }
}
migrateLegacyAuthOnce();

export function AuthProvider({ children }: { children: ReactNode }) {
  const { token, user, setAuth, clear } = useAuthStore();

  const validate = useCallback(async () => {
    if (!token) return;
    try {
      const me = await authApi.me();
      useAuthStore.getState().setUser(me);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clear();
      }
    }
  }, [token, clear]);

  useEffect(() => {
    validate();
  }, [validate]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await authApi.login(email, password);
      setAuth(res.token, res.user);
    },
    [setAuth],
  );

  const loginWithGoogle = useCallback(
    async (credential: string) => {
      const res = await authApi.google(credential);
      setAuth(res.token, res.user);
    },
    [setAuth],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    }
    clear();
    // Also wipe legacy storage so the migration shim can't re-authenticate.
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.removeItem('mockup_auth_token');
        window.localStorage.removeItem('mockup_auth_user');
      } catch {
        /* ignore */
      }
    }
  }, [clear]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        loading: false,
        login,
        loginWithGoogle,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
