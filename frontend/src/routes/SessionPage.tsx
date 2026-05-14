import { useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Board, type BoardHandle } from '@/features/board/Board';
import { TopNav } from '@/components/layout/TopNav';
import { sessionsApi } from '@/lib/api';
import { Spinner } from '@/components/ui/Spinner';

interface MockState {
  mockConfig?: { durationMin?: number };
  problem?: { name?: string; difficulty?: string };
}

export function SessionPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const boardRef = useRef<BoardHandle>(null);
  const replayDoneRef = useRef(false);

  const sessionQ = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => sessionsApi.get(sessionId!),
    enabled: !!sessionId,
    retry: false,
  });

  const framesQ = useQuery({
    queryKey: ['session', sessionId, 'board-frames'],
    queryFn: () => sessionsApi.boardFrames(sessionId!),
    enabled: !!sessionId,
    retry: false,
  });

  // Replay board frames once frames are loaded. While replaying we toggle
  // `replayMode` so the engine renders text instantly instead of typing.
  useEffect(() => {
    if (!framesQ.data || !boardRef.current || replayDoneRef.current) return;
    const board = boardRef.current;
    board.setReplayMode(true);
    board.clearAll();
    for (const f of framesQ.data) {
      const cmd = (f.command ?? f) as Record<string, unknown>;
      if (cmd && typeof cmd === 'object' && 'cmd' in cmd) {
        board.queue(cmd as Parameters<BoardHandle['queue']>[0]);
      }
    }
    replayDoneRef.current = true;
    // The engine processes the queue async; clear replayMode after a tick.
    const tid = setTimeout(() => board.setReplayMode(false), 50);
    return () => clearTimeout(tid);
  }, [framesQ.data]);

  const mockState = location.state as MockState | null;

  return (
    <div className="flex flex-col h-full">
      <TopNav />
      <div className="flex flex-1 min-h-0">
        <aside className="w-[300px] shrink-0 border-r border-border bg-bg-surface p-4 flex flex-col">
          <button
            type="button"
            onClick={() => navigate('/home')}
            className="text-xs text-text-muted hover:text-text mb-3 self-start"
          >
            ← Home
          </button>
          {sessionQ.isLoading ? (
            <div className="flex items-center gap-2 text-text-muted text-sm">
              <Spinner /> Loading session...
            </div>
          ) : sessionQ.data ? (
            <>
              <h2 className="text-base font-semibold mb-1" data-testid="session-title">
                {sessionQ.data.topic ?? sessionQ.data.problemTitle ?? 'Session'}
              </h2>
              <p className="text-xs text-text-dim">
                {sessionQ.data.startedAt
                  ? new Date(sessionQ.data.startedAt).toLocaleString()
                  : ''}
              </p>
              {sessionQ.data.sessionMode === 'mock_interview' && (
                <div className="mt-3 px-2 py-1.5 rounded border border-warn/30 bg-warn/5 text-xs text-warn">
                  Mock interview · {sessionQ.data.mockCompany ?? 'Generic'}
                </div>
              )}
              {sessionQ.data.headlines && (
                <div className="mt-4">
                  <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                    Highlights
                  </h3>
                  <ul className="text-xs text-text-muted leading-relaxed list-disc list-inside">
                    {sessionQ.data.headlines.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                </div>
              )}
              {Array.isArray(sessionQ.data.transcript) &&
                sessionQ.data.transcript.length > 0 && (
                  <div className="mt-4 flex-1 min-h-0 overflow-y-auto">
                    <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 sticky top-0 bg-bg-surface">
                      Transcript
                    </h3>
                    <ol className="text-xs text-text-muted leading-relaxed space-y-2">
                      {(sessionQ.data.transcript as { role?: string; text?: string }[]).map(
                        (t, i) => (
                          <li
                            key={i}
                            className={
                              t.role === 'user' ? 'text-text' : 'text-text-muted'
                            }
                          >
                            <span className="text-text-dim mr-1">
                              {t.role === 'user' ? 'You:' : 'Tutor:'}
                            </span>
                            {t.text}
                          </li>
                        ),
                      )}
                    </ol>
                  </div>
                )}
            </>
          ) : sessionQ.isError ? (
            <p className="text-text-muted">Could not load session.</p>
          ) : (
            <p className="text-text-muted">Session not found.</p>
          )}
          {mockState?.problem && (
            <div className="mt-3 text-xs">
              <div className="font-semibold">{mockState.problem.name}</div>
              {mockState.problem.difficulty && (
                <div className="text-text-dim">{mockState.problem.difficulty}</div>
              )}
            </div>
          )}
        </aside>
        <Board ref={boardRef} className="flex-1 min-h-0" />
      </div>
    </div>
  );
}
