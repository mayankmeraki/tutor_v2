import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Direct logic test for the legacy-auth migration shim. We re-import the
// AuthProvider module fresh so its module-load `migrateLegacyAuthOnce()` runs
// against our seeded storage, then we read state from the matching
// freshly-imported auth store.
async function importFresh() {
  vi.resetModules();
  // Importing AuthProvider runs migrateLegacyAuthOnce() at module load.
  await import('./AuthProvider');
  const { useAuthStore } = await import('@/stores/auth');
  return { useAuthStore };
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AuthProvider — legacy migration shim', () => {
  it('migrates mockup_auth_token + mockup_auth_user into the new store', async () => {
    window.localStorage.setItem('mockup_auth_token', 'legacy-tok');
    window.localStorage.setItem(
      'mockup_auth_user',
      JSON.stringify({ email: 'old@x.com', name: 'Old' }),
    );

    const { useAuthStore } = await importFresh();
    const s = useAuthStore.getState();
    expect(s.token).toBe('legacy-tok');
    expect(s.user?.email).toBe('old@x.com');
    expect(s.isAuthenticated()).toBe(true);
  });

  it('does NOT migrate when the new-store key already has data', async () => {
    window.localStorage.setItem('mockup_auth_token', 'legacy-tok');
    window.localStorage.setItem(
      'mockup_auth_user',
      JSON.stringify({ email: 'old@x.com' }),
    );
    window.localStorage.setItem(
      'mockup_auth',
      JSON.stringify({
        state: { token: 'new-tok', user: { email: 'new@x.com' } },
        version: 0,
      }),
    );

    const { useAuthStore } = await importFresh();
    expect(useAuthStore.getState().token).toBe('new-tok');
    expect(useAuthStore.getState().user?.email).toBe('new@x.com');
  });

  it('is a no-op when neither legacy nor new-store keys are set', async () => {
    const { useAuthStore } = await importFresh();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});
