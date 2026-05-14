import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/features/auth/AuthProvider';
import { Button } from '@/components/ui/Button';

export function TopNav() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <nav className="sticky top-0 z-50 flex items-center justify-between h-[60px] px-[clamp(20px,4vw,48px)] bg-[rgba(9,9,11,0.85)] backdrop-blur-2xl border-b border-border">
      <Link
        to={isAuthenticated ? '/home' : '/'}
        className="text-[22px] font-extrabold tracking-[-0.5px] text-text no-underline"
      >
        <em className="not-italic text-accent">E</em>uler{' '}
        <sup className="text-[9px] font-medium text-white/25 tracking-wider">
          beta
        </sup>
      </Link>
      <div className="flex items-center gap-3">
        <Link
          to="/for-business"
          className="text-sm text-text-muted hover:text-text transition-colors"
        >
          For Institutions
        </Link>
        {isAuthenticated ? (
          <>
            <Link
              to="/paths"
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Paths
            </Link>
            <Link
              to="/dsa"
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              DSA
            </Link>
            <Link
              to="/mock"
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Mock
            </Link>
            <Link
              to="/byo"
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Materials
            </Link>
            <Link
              to="/artifacts"
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Notes
            </Link>
            <span className="text-sm text-text-dim hidden lg:inline">{user?.email}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                await logout();
                navigate('/');
              }}
            >
              Sign out
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>
              Sign in
            </Button>
            <Button variant="accent" size="sm" onClick={() => navigate('/login')}>
              Get started
            </Button>
          </>
        )}
      </div>
    </nav>
  );
}
