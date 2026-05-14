import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocket } from '@/lib/ws/useWebSocket';
import { chatFrames, type ChatFrame } from '@/lib/ws/protocol';
import { useEventSource } from '@/lib/sse/useEventSource';
import { useAuthStore } from '@/stores/auth';
import type { BoardCommand } from '@/features/board/engine';

export interface TutorMessage {
  id: string;
  role: 'user' | 'tutor' | 'system';
  text: string;
  timestamp: number;
}

export interface UseTutorChatOptions {
  sessionId: string | null;
  onBoardCommand?: (cmd: BoardCommand) => void;
  onTtsChunk?: (text: string) => void;
}

export function useTutorChat({
  sessionId,
  onBoardCommand,
  onTtsChunk,
}: UseTutorChatOptions) {
  const token = useAuthStore((s) => s.token);
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const handlersRef = useRef({ onBoardCommand, onTtsChunk });
  handlersRef.current = { onBoardCommand, onTtsChunk };

  const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = typeof window !== 'undefined' ? window.location.host : '';

  const ws = useWebSocket<ChatFrame, ChatFrame>({
    url: `${proto}://${host}/ws/chat`,
    token,
    enabled: !!token && !!sessionId,
    onMessage: (frame) => {
      // Binary frames (audio chunks keyed by beat/gen). Legacy decodes them via
      // MediaSource. The simplified TTS path uses HTTP /api/tts; binary audio is
      // safely ignored here.
      if (frame instanceof ArrayBuffer || frame instanceof Blob) return;
      if (!frame || typeof frame !== 'object') return;
      const f = frame as Record<string, unknown>;
      const type = f.type as string | undefined;

      // Heartbeat / keepalive
      if (type === 'PONG' || type === 'HEARTBEAT') return;

      // Board command frames
      if (type === 'BOARD' || f.cmd) {
        const cmd = (f.cmd ? f : f.command) as BoardCommand;
        if (cmd && typeof cmd === 'object' && (cmd as BoardCommand).cmd) {
          handlersRef.current.onBoardCommand?.(cmd);
        }
        return;
      }

      // Tutor text — handle both finalized messages and incremental deltas.
      if (type === 'TUTOR_TEXT' || type === 'MESSAGE' || type === 'TEXT_DELTA') {
        const text = String(f.text ?? f.delta ?? f.payload ?? '');
        const isDelta = type === 'TEXT_DELTA' || !!f.delta;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'tutor' && isDelta) {
            return [...prev.slice(0, -1), { ...last, text: last.text + text }];
          }
          return [
            ...prev,
            {
              id: `m_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
              role: 'tutor',
              text,
              timestamp: Date.now(),
            },
          ];
        });
        return;
      }

      if (type === 'TTS_CHUNK') {
        handlersRef.current.onTtsChunk?.(String(f.text ?? ''));
        return;
      }

      // Generic state updates
      if (type === 'STATE') {
        if (f.thinking !== undefined) setThinking(!!f.thinking);
        return;
      }

      // Turn lifecycle: clear thinking on terminal events.
      if (type === 'DONE' || type === 'INTERRUPTED' || type === 'CANCELLED') {
        setThinking(false);
        return;
      }

      if (type === 'RUN_ERROR' || type === 'ERROR') {
        setThinking(false);
        const msg = String(f.message ?? f.error ?? 'Tutor error');
        setMessages((prev) => [
          ...prev,
          {
            id: `e_${Date.now()}`,
            role: 'system',
            text: msg,
            timestamp: Date.now(),
          },
        ]);
        return;
      }

      // Agent lifecycle (subagents). Surface as system notes.
      if (type === 'AGENT_SPAWNED' || type === 'AGENT_COMPLETE' || type === 'AGENT_ERROR') {
        // Optional: could push lightweight system messages; suppressed by default
        // to match legacy behavior of not showing agent chrome to users.
        return;
      }
    },
  });

  useEventSource({
    url: `/api/events/${sessionId ?? ''}`,
    token,
    enabled: !!sessionId && !!token,
    onMessage: (data) => {
      if (data && typeof data === 'object') {
        const evt = data as Record<string, unknown>;
        const type = evt.type as string | undefined;
        if (type === 'HEARTBEAT' || type === 'EVENTS_CONNECTED') return;
        if (evt.cmd) handlersRef.current.onBoardCommand?.(evt as BoardCommand);
        if (evt.thinking !== undefined) setThinking(!!evt.thinking);
        if (
          type === 'DONE' ||
          type === 'AGENT_COMPLETE' ||
          type === 'INTERRUPTED' ||
          type === 'CANCELLED'
        ) {
          setThinking(false);
        }
      }
    },
  });

  // Heartbeat
  useEffect(() => {
    if (ws.readyState !== 'open') return;
    const id = setInterval(() => ws.send(chatFrames.ping()), 25_000);
    return () => clearInterval(id);
  }, [ws.readyState, ws.send, ws]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      setMessages((prev) => [
        ...prev,
        {
          id: `u_${Date.now()}`,
          role: 'user',
          text,
          timestamp: Date.now(),
        },
      ]);
      setThinking(true);
      ws.send(chatFrames.message(text, { sessionId }));
    },
    [ws, sessionId],
  );

  const interrupt = useCallback(() => {
    ws.send(chatFrames.interrupt());
  }, [ws]);

  const cancel = useCallback(() => {
    ws.send(chatFrames.cancel());
    setThinking(false);
  }, [ws]);

  return {
    messages,
    thinking,
    sendMessage,
    interrupt,
    cancel,
    readyState: ws.readyState,
  };
}
