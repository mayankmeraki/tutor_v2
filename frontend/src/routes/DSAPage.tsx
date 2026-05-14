import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs } from '@/components/ui/Tabs';
import { dsaApi } from '@/lib/api';
import { cn } from '@/components/ui/cn';

const DIFFICULTY_FILTERS: { id: string; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'easy', label: 'Easy' },
  { id: 'medium', label: 'Medium' },
  { id: 'hard', label: 'Hard' },
  { id: 'neetcode-150', label: 'NeetCode 150' },
  { id: 'blind-75', label: 'Blind 75' },
];

export function DSAPage() {
  return (
    <AppShell>
      <div className="app-screen max-w-[1100px] mx-auto px-6 pt-8 pb-16">
        <h1 className="text-[28px] font-extrabold tracking-[-0.5px] mb-1">
          DSA &amp; System Design
        </h1>
        <p className="text-sm text-text-muted mb-6">
          Practice with a live tutor — pick any problem, get explained step by step.
        </p>
        <Tabs
          tabs={[
            { id: 'dsa', label: 'DSA Problems', content: <DSAList /> },
            { id: 'sd-hld', label: 'System Design (HLD)', content: <SDList type="hld" /> },
            { id: 'sd-lld', label: 'Low-Level Design (LLD)', content: <SDList type="lld" /> },
          ]}
        />
      </div>
    </AppShell>
  );
}

function DSAList() {
  const [q, setQ] = useState('');
  const [topicFilter, setTopicFilter] = useState<string | null>(null);
  const [difficulty, setDifficulty] = useState('all');
  const problems = useQuery({
    queryKey: ['dsa', 'problems'],
    queryFn: () => dsaApi.listProblems({ limit: 200 }),
  });
  const topics = useQuery({
    queryKey: ['dsa', 'topics'],
    queryFn: () => dsaApi.topics(),
  });

  const filtered = useMemo(() => {
    let list = problems.data ?? [];
    if (q.trim()) {
      const lq = q.toLowerCase();
      list = list.filter(
        (p) => p.name.toLowerCase().includes(lq) || p.slug.toLowerCase().includes(lq),
      );
    }
    if (topicFilter) {
      list = list.filter((p) => p.topics?.includes(topicFilter));
    }
    if (difficulty !== 'all') {
      if (difficulty === 'neetcode-150') {
        list = list.filter((p) => (p.lists ?? []).some((l) => /neetcode/i.test(l)));
      } else if (difficulty === 'blind-75') {
        list = list.filter((p) => (p.lists ?? []).some((l) => /blind\s*75/i.test(l)));
      } else {
        list = list.filter((p) => p.difficulty?.toLowerCase() === difficulty);
      }
    }
    return list;
  }, [problems.data, q, topicFilter, difficulty]);

  if (problems.isLoading) {
    return (
      <div className="flex items-center gap-2 text-text-muted">
        <Spinner /> Loading problems...
      </div>
    );
  }
  if (problems.isError) {
    return (
      <Card className="text-center py-6 text-bad text-sm">
        Failed to load DSA problems: {(problems.error as Error).message}
      </Card>
    );
  }

  return (
    <>
      <div className="flex flex-wrap gap-2 mb-3" data-testid="dsa-filters">
        {DIFFICULTY_FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setDifficulty(f.id)}
            className={cn(
              'text-xs px-3 py-1 rounded-full border transition-colors',
              difficulty === f.id
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-muted hover:text-text',
            )}
            data-testid={`dsa-filter-${f.id}`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search problems..."
          className="max-w-[320px]"
          data-testid="dsa-search"
        />
        <select
          value={topicFilter ?? ''}
          onChange={(e) => setTopicFilter(e.target.value || null)}
          className="h-10 px-3 bg-bg-surface border border-border rounded-[8px] text-sm text-text"
          data-testid="dsa-topic-select"
        >
          <option value="">All topics</option>
          {(topics.data ?? []).map((t) => (
            <option key={t.topic} value={t.topic}>
              {t.topic} ({t.count})
            </option>
          ))}
        </select>
      </div>
      <p className="text-xs text-text-dim mb-3">
        Showing {filtered.length} of {problems.data?.length ?? 0} problems
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="dsa-problem-grid">
        {filtered.map((p) => (
          <Link key={p.slug} to={`/dsa/${p.slug}`} className="block" data-testid="dsa-problem-card">
            <Card className="hover:border-border-active transition-colors h-full">
              <div className="flex items-start justify-between mb-1.5 gap-2">
                <h3 className="text-base font-semibold text-white truncate">
                  {p.num ? `${p.num}. ` : ''}
                  {p.name}
                </h3>
                {p.difficulty && (
                  <span
                    className={cn(
                      'text-[10px] px-2 py-0.5 rounded-full font-semibold flex-shrink-0',
                      p.difficulty === 'Easy' && 'bg-good/15 text-good',
                      p.difficulty === 'Medium' && 'bg-warn/15 text-warn',
                      p.difficulty === 'Hard' && 'bg-bad/15 text-bad',
                    )}
                  >
                    {p.difficulty}
                  </span>
                )}
              </div>
              {p.topics && p.topics.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {p.topics.slice(0, 3).map((t) => (
                    <span
                      key={t}
                      className="text-[10px] text-text-muted bg-bg-hover rounded-full px-2 py-0.5"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}

function SDList({ type }: { type: 'hld' | 'lld' }) {
  const sdQ = useQuery({
    queryKey: ['sd', 'problems'],
    queryFn: () => dsaApi.sdProblems(),
  });
  const conceptsQ = useQuery({
    queryKey: ['sd', 'concepts'],
    queryFn: () => dsaApi.sdConcepts(),
  });
  if (sdQ.isLoading)
    return (
      <div className="flex items-center gap-2 text-text-muted">
        <Spinner /> Loading...
      </div>
    );
  const all = sdQ.data ?? [];
  const filtered = all.filter((p) =>
    type === 'lld' ? p.type === 'lld' : p.type !== 'lld',
  );
  return (
    <>
      {conceptsQ.data && conceptsQ.data.length > 0 && (
        <div className="mb-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
            Concepts
          </h3>
          <div className="flex flex-wrap gap-2">
            {conceptsQ.data.slice(0, 12).map((c) => (
              <Link
                key={c.id}
                to={`/tutor?q=${encodeURIComponent('Teach me: ' + c.name)}`}
                className="text-xs px-3 py-1.5 rounded-full bg-bg-hover hover:bg-bg-elevated text-text-muted hover:text-text transition-colors"
              >
                {c.name}
              </Link>
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid={`sd-${type}-grid`}>
        {filtered.map((p) => (
          <Link key={p.slug} to={`/sd/${p.slug}`} data-testid="sd-problem-card">
            <Card className="hover:border-border-active transition-colors">
              <h3 className="text-base font-semibold text-white">{p.name}</h3>
              {p.description && (
                <p className="text-xs text-text-muted mt-1 line-clamp-2">
                  {p.description}
                </p>
              )}
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
