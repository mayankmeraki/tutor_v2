import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { LoginPage } from './LoginPage';
import { AuthProvider } from '@/features/auth/AuthProvider';
import { useAuthStore } from '@/stores/auth';
import { ConfigProvider } from '@/features/config/ConfigProvider';
import { ToastProvider } from '@/components/ui/Toast';

const fetchMock = vi.fn();

beforeEach(() => {
  window.localStorage.clear();
  useAuthStore.setState({ token: null, user: null });
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
  // Default: config returns no googleClientId so the GoogleSignIn renders
  // its "not configured" placeholder and we don't load gsi script.
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify({ tts_enabled: false }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }),
  );
});

function jsonRes(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function Frame() {
  return (
    <ToastProvider>
      <ConfigProvider>
        <MemoryRouter initialEntries={['/login']}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/home" element={<div data-testid="home-page" />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </ConfigProvider>
    </ToastProvider>
  );
}

describe('LoginPage', () => {
  it('renders email/password fields and a Sign in button', async () => {
    render(<Frame />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    // The form's submit button is type=submit; the TopNav has a separate ghost button.
    const buttons = screen.getAllByRole('button', { name: /sign in/i });
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it('submits credentials → auth store populated', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('/api/v1/auth/login')) {
        return Promise.resolve(
          jsonRes(200, { token: 'tk', user: { email: 'a@b.com' } }),
        );
      }
      if (typeof url === 'string' && url.includes('/api/v1/auth/me')) {
        return Promise.resolve(jsonRes(200, { email: 'a@b.com' }));
      }
      return Promise.resolve(jsonRes(200, { tts_enabled: false }));
    });

    const { container } = render(<Frame />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'a@b.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'pw' },
    });
    const form = container.querySelector('form');
    expect(form).toBeTruthy();
    await act(async () => {
      fireEvent.submit(form!);
      await new Promise((r) => setTimeout(r, 50));
    });

    const loginCall = fetchMock.mock.calls.find((c) =>
      typeof c[0] === 'string' && (c[0] as string).includes('/api/v1/auth/login'),
    );
    expect(loginCall).toBeTruthy();
    expect(JSON.parse((loginCall![1] as RequestInit).body as string)).toEqual({
      email: 'a@b.com',
      password: 'pw',
    });
    expect(useAuthStore.getState().token).toBe('tk');
  });

  it('keeps auth empty on login failure', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('/api/v1/auth/login')) {
        return Promise.resolve(jsonRes(401, { detail: 'Bad credentials' }));
      }
      return Promise.resolve(jsonRes(200, { tts_enabled: false }));
    });
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { ...window.location, assign: vi.fn(), pathname: '/login' },
    });

    const { container } = render(<Frame />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'a@b.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'wrong' },
    });
    const form = container.querySelector('form')!;
    await act(async () => {
      fireEvent.submit(form);
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(useAuthStore.getState().token).toBeNull();
  });
});
