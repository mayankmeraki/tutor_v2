import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from './auth';

beforeEach(() => {
  window.localStorage.clear();
  useAuthStore.setState({ token: null, user: null });
});

describe('useAuthStore', () => {
  it('starts unauthenticated', () => {
    const s = useAuthStore.getState();
    expect(s.token).toBeNull();
    expect(s.user).toBeNull();
    expect(s.isAuthenticated()).toBe(false);
  });

  it('setAuth populates token + user and persists to localStorage', () => {
    useAuthStore.getState().setAuth('tok', { email: 'a@b.com' } as never);
    const s = useAuthStore.getState();
    expect(s.token).toBe('tok');
    expect(s.user?.email).toBe('a@b.com');
    expect(s.isAuthenticated()).toBe(true);
    const persisted = window.localStorage.getItem('mockup_auth');
    expect(persisted).toContain('tok');
    expect(persisted).toContain('a@b.com');
  });

  it('clear() wipes both state and storage', () => {
    useAuthStore.getState().setAuth('tk', { email: 'a' } as never);
    useAuthStore.getState().clear();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated()).toBe(false);
  });

  it('setUser keeps existing token', () => {
    useAuthStore.getState().setAuth('tk', { email: 'a' } as never);
    useAuthStore.getState().setUser({ email: 'a', name: 'Alice' } as never);
    expect(useAuthStore.getState().token).toBe('tk');
    expect(useAuthStore.getState().user?.name).toBe('Alice');
  });
});
