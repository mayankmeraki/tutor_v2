import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { sessionsApi, pathsApi, byoApi } from '@/lib/api';
import { Tabs } from '@/components/ui/Tabs';
import { useAuth } from '@/features/auth/AuthProvider';
import { DashBg } from '@/components/effects/DashBg';

function timeOfDayGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

function timeAgo(iso?: string): string {
  if (!iso) return '';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '';
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return 'just now';
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day === 1) return 'yesterday';
  if (day < 7) return `${day}d ago`;
  return new Date(t).toLocaleDateString();
}

export function HomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [prompt, setPrompt] = useState('');

  // Legacy parity: when arriving on home with a pending prompt from landing,
  // forward it directly to the tutor route.
  useEffect(() => {
    const pending =
      sessionStorage.getItem('lp_prompt') ??
      sessionStorage.getItem('capacity_pending_prompt');
    if (pending) {
      sessionStorage.setItem('lp_prompt', pending);
      sessionStorage.removeItem('capacity_pending_prompt');
      navigate('/tutor', { replace: true });
    }
  }, [navigate]);

  const onAsk = () => {
    const t = prompt.trim();
    if (!t) return;
    sessionStorage.setItem('lp_prompt', t);
    navigate('/tutor');
  };

  const firstName =
    user?.name?.split(' ')[0] ?? user?.email?.split('@')[0] ?? 'there';

  return (
    <AppShell>
      <DashBg />
      <div className="app-screen max-w-[1080px] mx-auto px-6 pt-10 pb-20 relative">
        <div className="mb-8 stagger">
          <h1 className="text-[28px] font-extrabold tracking-[-0.5px] mb-1">
            {timeOfDayGreeting()}, {firstName} —
            <br className="md:hidden" /> what would you like to learn?
          </h1>
          <p className="text-sm text-text-muted">
            Ask anything, paste a video, or pick up where you left off.
          </p>
        </div>

        <div className="mb-10 flex gap-2 max-w-[720px]">
          <Input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="What do you want to learn?"
            onKeyDown={(e) => {
              if (e.key === 'Enter') onAsk();
            }}
            data-testid="home-ask-input"
          />
          <Button variant="accent" onClick={onAsk} data-testid="home-ask-button">
            Ask
          </Button>
        </div>

        <Tabs
          tabs={[
            {
              id: 'sessions',
              label: 'Recent sessions',
              content: <SessionsTab />,
            },
            {
              id: 'paths',
              label: 'Learning paths',
              content: <PathsTab />,
            },
            {
              id: 'collections',
              label: 'My materials',
              content: <CollectionsTab />,
            },
          ]}
        />
      </div>
    </AppShell>
  );
}

function SessionsTab() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const { data: paths } = useQuery({
    queryKey: ['paths', 'home'],
    queryFn: () => pathsApi.list(),
  });
  const { data: allSessions, isLoading } = useQuery({
    queryKey: ['sessions', 'me', 'all'],
    queryFn: () => sessionsApi.listMine(),
  });

  // Server-side search across all sessions, only when the query is long enough.
  const { data: searchResults, isFetching: searching } = useQuery({
    queryKey: ['sessions', 'search', query],
    queryFn: () => sessionsApi.searchAll(query),
    enabled: query.trim().length >= 3,
    staleTime: 30_000,
  });

  // Build the set of session ids that already belong to a path so we don't
  // double-render them. This mirrors legacy `_buildHomeActivity`.
  const pathSessionIds = useMemo(() => {
    const s = new Set<string>();
    for (const p of paths ?? []) {
      for (const n of p.nodes ?? []) {
        if (n.sessionId) s.add(n.sessionId);
      }
    }
    return s;
  }, [paths]);

  const baseList = query.trim().length >= 3 ? (searchResults ?? []) : (allSessions ?? []);
  const filtered = baseList.filter((s) => !pathSessionIds.has(s.sessionId));

  if (isLoading) {
    return (
      <div className="text-text-muted flex items-center gap-2">
        <Spinner /> Loading sessions...
      </div>
    );
  }
  if (!allSessions || allSessions.length === 0) {
    return (
      <Card className="text-center py-10 text-text-muted">
        No sessions yet. Start by asking a question above.
      </Card>
    );
  }

  return (
    <>
      <div className="mb-4 max-w-[420px] flex items-center gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search sessions..."
          data-testid="sessions-search"
        />
        {searching && <Spinner />}
      </div>
      {filtered.length === 0 ? (
        <Card className="text-center py-8 text-text-muted text-sm">
          No matching sessions.
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((s) => (
            <Card
              key={s.sessionId}
              className="cursor-pointer hover:border-border-active transition-colors"
              onClick={() => navigate(`/session/${s.sessionId}`)}
              data-testid="session-card"
            >
              <div className="text-xs text-text-dim mb-1 flex items-center gap-2">
                <span>{timeAgo(s.startedAt)}</span>
                {s.sessionMode && s.sessionMode !== 'general' && (
                  <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-bg-hover text-accent">
                    {s.sessionMode}
                  </span>
                )}
              </div>
              <h3 className="text-base font-semibold text-white truncate">
                {s.topic ?? s.problemTitle ?? 'Session'}
              </h3>
              {s.headlines && s.headlines.length > 0 && (
                <ul className="mt-2 text-xs text-text-muted leading-relaxed list-disc list-inside">
                  {s.headlines.slice(0, 3).map((h, i) => (
                    <li key={i} className="truncate">
                      {h}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

function PathsTab() {
  const { data: paths, isLoading } = useQuery({
    queryKey: ['paths'],
    queryFn: () => pathsApi.list(),
  });
  if (isLoading)
    return (
      <div className="text-text-muted flex items-center gap-2">
        <Spinner /> Loading paths...
      </div>
    );
  if (!paths || paths.length === 0)
    return (
      <Card className="text-center py-10 text-text-muted">
        No paths yet — start a multi-step learning path from any question.
      </Card>
    );
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {paths.map((p) => {
        const nextNode =
          (p.nodes ?? []).find((n) => n.status !== 'completed' && n.status !== 'skipped');
        const continueHref = nextNode
          ? `/tutor?pathId=${p.pathId}&nodeId=${nextNode.id}`
          : `/paths`;
        return (
          <Link key={p.pathId} to={continueHref} className="block">
            <Card className="hover:border-border-active transition-colors cursor-pointer">
              <div className="text-xs text-text-dim mb-1">
                {p.status ?? 'in_progress'}
              </div>
              <h3 className="text-base font-semibold text-white">
                {p.title ?? p.intent ?? 'Untitled path'}
              </h3>
              <p className="text-xs text-text-muted mt-1">
                {p.nodes?.length ?? 0} steps
                {nextNode ? ` · next: ${nextNode.title ?? '—'}` : ''}
              </p>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}

function CollectionsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['byo', 'collections'],
    queryFn: () => byoApi.listCollections(),
  });
  if (isLoading)
    return (
      <div className="text-text-muted flex items-center gap-2">
        <Spinner /> Loading...
      </div>
    );
  if (!data || data.length === 0)
    return (
      <Card className="text-center py-10 text-text-muted">
        No collections yet. Upload notes, PDFs, or videos to get started.
      </Card>
    );
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {data.map((c) => (
        <Link key={c.collection_id} to={`/byo`}>
          <Card className="hover:border-border-active transition-colors cursor-pointer">
            <h3 className="text-base font-semibold text-white">{c.name}</h3>
            <p className="text-xs text-text-muted mt-1">
              {c.resource_count ?? 0} resources
            </p>
            {c.description && (
              <p className="text-xs text-text-dim mt-2">{c.description}</p>
            )}
          </Card>
        </Link>
      ))}
    </div>
  );
}
