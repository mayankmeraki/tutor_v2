import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { dsaApi, sessionsApi } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { cn } from '@/components/ui/cn';

const COMPANIES = ['Any', 'Google', 'Meta', 'Amazon', 'Microsoft', 'Apple', 'Netflix'];
const DIFFICULTIES = ['Any', 'Easy', 'Medium', 'Hard'];
const TYPES: { id: 'dsa' | 'sd'; label: string; sub: string }[] = [
  { id: 'dsa', label: 'Coding (DSA)', sub: 'Algorithms + data structures, 30-45 min' },
  { id: 'sd', label: 'System Design', sub: 'High-level architecture, 45 min' },
];

function newSessionId() {
  return 's_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export function MockPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [starting, setStarting] = useState(false);
  const [type, setType] = useState<'dsa' | 'sd'>('dsa');
  const [company, setCompany] = useState('Any');
  const [difficulty, setDifficulty] = useState('Any');
  const [topic, setTopic] = useState('');

  const onStart = async () => {
    setStarting(true);
    try {
      // Backend `/api/v1/mock/start` returns `{ problem, config }` and does NOT
      // generate a session id. We create one client-side, attach the mock config
      // via `sessionsApi.create`, then navigate to /session.
      const sessionId = newSessionId();
      const params: Record<string, string> = { type };
      if (company !== 'Any') params.company = company;
      if (difficulty !== 'Any') params.difficulty = difficulty;
      if (topic.trim()) params.topic = topic.trim();

      const res = await dsaApi.startMock(params);
      try {
        await sessionsApi.create({
          sessionId,
          startedAt: new Date().toISOString(),
          sessionMode: 'mock_interview',
          mockCompany: company !== 'Any' ? company : undefined,
          problemTitle: res.problem?.name,
          problemSlug: res.problem?.slug,
          problemDifficulty: res.problem?.difficulty,
          topic: topic || res.problem?.name,
        });
      } catch {
        /* session create failure is non-fatal — proceed to mock UI */
      }
      navigate(`/session/${sessionId}`, { state: { mockConfig: res.config, problem: res.problem } });
    } catch (err) {
      toast((err as Error).message, 'error');
    } finally {
      setStarting(false);
    }
  };

  return (
    <AppShell>
      <div className="app-screen max-w-[640px] mx-auto px-6 pt-12">
        <h1 className="text-[28px] font-extrabold tracking-[-0.5px] mb-1">
          Mock Interview
        </h1>
        <p className="text-sm text-text-muted mb-8">
          A live, time-boxed interview. The tutor asks the question, listens, and
          gives feedback at the end.
        </p>
        <Card>
          <label className="block mb-4">
            <span className="text-xs text-text-muted block mb-2">Format</span>
            <div className="grid grid-cols-2 gap-2">
              {TYPES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setType(t.id)}
                  className={cn(
                    'border rounded-[8px] px-3 py-2 text-left transition-colors',
                    type === t.id
                      ? 'border-accent bg-accent/10'
                      : 'border-border hover:border-border-active',
                  )}
                  data-testid={`mock-type-${t.id}`}
                >
                  <div className="text-sm font-semibold">{t.label}</div>
                  <div className="text-[11px] text-text-dim mt-0.5">{t.sub}</div>
                </button>
              ))}
            </div>
          </label>
          <label className="block mb-3">
            <span className="text-xs text-text-muted block mb-1">Company</span>
            <select
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="w-full h-10 px-3 bg-bg-surface border border-border rounded-[8px] text-sm"
              data-testid="mock-company-select"
            >
              {COMPANIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="block mb-3">
            <span className="text-xs text-text-muted block mb-1">Difficulty</span>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="w-full h-10 px-3 bg-bg-surface border border-border rounded-[8px] text-sm"
              data-testid="mock-difficulty-select"
            >
              {DIFFICULTIES.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <label className="block mb-4">
            <span className="text-xs text-text-muted block mb-1">Topic (optional)</span>
            <input
              className="w-full h-10 px-3 bg-bg-surface border border-border rounded-[8px] text-sm"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Arrays, Graphs, Dynamic Programming"
              data-testid="mock-topic-input"
            />
          </label>
          <Button
            variant="accent"
            className="w-full"
            loading={starting}
            onClick={onStart}
            data-testid="mock-start-btn"
          >
            Start mock interview
          </Button>
        </Card>
      </div>
    </AppShell>
  );
}
