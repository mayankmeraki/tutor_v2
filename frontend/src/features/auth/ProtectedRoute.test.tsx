import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { useAuthStore } from '@/stores/auth';
import { AuthProvider } from './AuthProvider';

beforeEach(() => {
  window.localStorage.clear();
  useAuthStore.setState({ token: null, user: null });
  // Stub /me so AuthProvider's validate effect is harmless.
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(JSON.stringify({ email: 'a@b.com' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    ),
  );
});

function Frame({ initialPath }: { initialPath: string }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>LOGIN</div>} />
          <Route
            path="/secret"
            element={
              <ProtectedRoute>
                <div>SECRET</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('ProtectedRoute', () => {
  it('redirects unauthenticated users to /login', () => {
    render(<Frame initialPath="/secret" />);
    expect(screen.getByText('LOGIN')).toBeInTheDocument();
    expect(screen.queryByText('SECRET')).toBeNull();
  });

  it('renders children when authenticated', () => {
    useAuthStore.setState({
      token: 'tok',
      user: { email: 'a@b.com' } as never,
    });
    render(<Frame initialPath="/secret" />);
    expect(screen.getByText('SECRET')).toBeInTheDocument();
  });
});
