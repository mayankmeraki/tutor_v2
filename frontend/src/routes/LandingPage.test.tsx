import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { LandingPage } from './LandingPage';
import { AuthProvider } from '@/features/auth/AuthProvider';
import { useAuthStore } from '@/stores/auth';
import { ConfigProvider } from '@/features/config/ConfigProvider';

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  useAuthStore.setState({ token: null, user: null });
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(JSON.stringify({ tts_enabled: false }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    ),
  );
});

function Frame() {
  return (
    <ConfigProvider>
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<div data-testid="login-page" />} />
            <Route path="/home" element={<div data-testid="home-page" />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </ConfigProvider>
  );
}

describe('LandingPage', () => {
  it('renders the headline and prompt input', () => {
    render(<Frame />);
    expect(
      screen.getByPlaceholderText(/what do you want to learn/i),
    ).toBeInTheDocument();
  });

  it('clicking "Try it now" stores prompt to sessionStorage and navigates to /login', () => {
    render(<Frame />);
    const input = screen.getByPlaceholderText(/what do you want to learn/i);
    fireEvent.change(input, { target: { value: 'binary search trees' } });
    fireEvent.click(screen.getByRole('button', { name: /try it now/i }));
    expect(window.sessionStorage.getItem('lp_prompt')).toBe('binary search trees');
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });

  it('redirects authenticated users to /home', async () => {
    useAuthStore.setState({ token: 'tk', user: { email: 'a@b.com' } as never });
    render(<Frame />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(screen.getByTestId('home-page')).toBeInTheDocument();
  });
});
