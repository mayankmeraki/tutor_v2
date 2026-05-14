import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Board, type BoardHandle } from '@/features/board/Board';
import { VoiceBar } from '@/features/voice/VoiceBar';
import { TopNav } from '@/components/layout/TopNav';
import { useTutorChat } from '@/features/tutor/useTutorChat';
import { useTtsPlayback } from '@/features/voice/useTtsPlayback';
import { sessionsApi } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';

function newSessionId(): string {
  return 's_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export function TutorPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { toast } = useToast();
  const boardRef = useRef<BoardHandle>(null);
  const tts = useTtsPlayback();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const initialPrompt = useMemo(
    () => params.get('q') ?? sessionStorage.getItem('lp_prompt'),
    [params],
  );

  useEffect(() => {
    const id = newSessionId();
    void sessionsApi
      .create({ sessionId: id, startedAt: new Date().toISOString() })
      .then(() => setSessionId(id))
      .catch((err) => {
        toast(`Failed to start session: ${(err as Error).message}`, 'error');
        setSessionId(id);
      });
    return () => {
      sessionStorage.removeItem('lp_prompt');
    };
  }, [toast]);

  const { messages, thinking, sendMessage, cancel, interrupt } = useTutorChat({
    sessionId,
    onBoardCommand: (cmd) => boardRef.current?.queue(cmd),
    onTtsChunk: (text) => {
      if (text) void tts.play(text);
    },
  });

  const onSubmit = useCallback(
    (text: string) => {
      if (!sessionId) return;
      // Interrupt any in-flight tutor turn + audio before sending a new message (legacy parity)
      tts.stop();
      interrupt();
      sendMessage(text);
    },
    [sessionId, sendMessage, interrupt, tts],
  );

  const onStop = useCallback(() => {
    tts.stop();
    cancel();
    boardRef.current?.cancel();
  }, [tts, cancel]);

  useEffect(() => {
    if (initialPrompt && sessionId) {
      sendMessage(initialPrompt);
      sessionStorage.removeItem('lp_prompt');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return (
    <div className="flex flex-col h-full">
      <TopNav />
      <div className="flex flex-1 min-h-0">
        <aside className="w-[300px] shrink-0 border-r border-border flex flex-col bg-bg-surface">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-sm font-semibold">Conversation</h2>
            <p className="text-xs text-text-dim mt-1">
              {sessionId ? `Session ${sessionId.slice(0, 8)}…` : 'Connecting...'}
            </p>
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-2">
            {messages.length === 0 && (
              <div className="text-xs text-text-dim italic px-1">
                Ask anything — the tutor will draw and explain on the board.
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`text-sm rounded-[8px] px-3 py-2 ${
                  m.role === 'user'
                    ? 'bg-bg-hover text-text self-end max-w-[90%]'
                    : 'text-text-muted'
                }`}
              >
                {m.text}
              </div>
            ))}
            {thinking && (
              <div className="text-xs text-accent italic flex items-center gap-1.5 px-1">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                tutor is thinking...
              </div>
            )}
          </div>
          <div className="p-3 border-t border-border flex items-center gap-2">
            <button
              type="button"
              onClick={onStop}
              className="text-xs text-text-muted hover:text-text underline"
            >
              Stop
            </button>
            <button
              type="button"
              onClick={() => navigate('/home')}
              className="text-xs text-text-muted hover:text-text ml-auto"
            >
              ← Home
            </button>
          </div>
        </aside>
        <div className="flex-1 flex flex-col min-w-0">
          <Board ref={boardRef} className="flex-1 min-h-0" />
          <div className="px-4 py-3 border-t border-border bg-bg-surface">
            <VoiceBar
              onSubmit={onSubmit}
              onMicStart={() => {
                tts.stop();
                interrupt();
              }}
              disabled={!sessionId}
              placeholder="Ask Euler anything..."
            />
          </div>
        </div>
      </div>
    </div>
  );
}
