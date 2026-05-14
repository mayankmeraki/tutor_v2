import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card } from '@/components/ui/Card';
import { useAuth } from '@/features/auth/AuthProvider';
import { GoogleSignIn } from '@/features/auth/GoogleSignIn';
import { useToast } from '@/components/ui/Toast';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? '/home';

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      toast((err as Error).message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="app-screen flex items-center justify-center px-4 pt-12">
        <Card className="w-full max-w-[400px]">
          <h1 className="text-2xl font-bold mb-1">Welcome back</h1>
          <p className="text-sm text-text-muted mb-6">
            Sign in to continue learning.
          </p>

          <div className="mb-4">
            <GoogleSignIn
              text="continue_with"
              onSuccess={() => navigate(from, { replace: true })}
              onError={(err) => toast(err.message, 'error')}
            />
          </div>

          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-text-dim uppercase tracking-wider">or</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <label className="block">
              <span className="text-xs text-text-muted block mb-1">Email</span>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>
            <label className="block">
              <span className="text-xs text-text-muted block mb-1">Password</span>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </label>
            <Button type="submit" variant="accent" loading={submitting}>
              Sign in
            </Button>
          </form>

          <p className="text-xs text-text-dim mt-4 text-center">
            New here? Sign in with Google to create an account.
          </p>
          <p className="text-xs text-text-dim mt-3 text-center">
            <Link to="/" className="hover:text-text-muted">
              ← Back home
            </Link>
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
