import { useEffect, useRef, useState, useCallback } from 'react';
import type { WsReadyState } from './types';

export interface UseWebSocketOptions<TIn = unknown> {
  url: string;
  token?: string | null;
  protocols?: string | string[];
  onMessage?: (frame: TIn, raw: MessageEvent) => void;
  onOpen?: (ev: Event) => void;
  onClose?: (ev: CloseEvent) => void;
  onError?: (ev: Event) => void;
  reconnect?: boolean;
  reconnectIntervalMs?: number;
  maxReconnectIntervalMs?: number;
  enabled?: boolean;
  parseJson?: boolean;
}

export interface UseWebSocketReturn<TOut = unknown> {
  send: (frame: TOut) => boolean;
  sendRaw: (data: string | ArrayBufferLike | Blob | ArrayBufferView) => boolean;
  close: () => void;
  readyState: WsReadyState;
  socket: WebSocket | null;
}

const STATE_MAP: Record<number, WsReadyState> = {
  0: 'connecting',
  1: 'open',
  2: 'closing',
  3: 'closed',
};

export function useWebSocket<TIn = unknown, TOut = unknown>(
  options: UseWebSocketOptions<TIn>,
): UseWebSocketReturn<TOut> {
  const {
    url,
    token,
    protocols,
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnect = true,
    reconnectIntervalMs = 1000,
    maxReconnectIntervalMs = 15000,
    enabled = true,
    parseJson = true,
  } = options;

  const [readyState, setReadyState] = useState<WsReadyState>('closed');
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const explicitlyClosed = useRef(false);

  const handlersRef = useRef({ onMessage, onOpen, onClose, onError });
  handlersRef.current = { onMessage, onOpen, onClose, onError };

  const buildUrl = useCallback(() => {
    if (!token) return url;
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}token=${encodeURIComponent(token)}`;
  }, [url, token]);

  const connect = useCallback(() => {
    if (!enabled) return;
    explicitlyClosed.current = false;
    try {
      const ws = new WebSocket(buildUrl(), protocols);
      socketRef.current = ws;
      setReadyState('connecting');

      ws.onopen = (ev) => {
        reconnectAttempts.current = 0;
        setReadyState('open');
        handlersRef.current.onOpen?.(ev);
      };

      ws.onmessage = (ev) => {
        let frame: TIn = ev.data as TIn;
        if (parseJson && typeof ev.data === 'string') {
          try {
            frame = JSON.parse(ev.data) as TIn;
          } catch {
            frame = ev.data as TIn;
          }
        }
        handlersRef.current.onMessage?.(frame, ev);
      };

      ws.onerror = (ev) => {
        setReadyState('error');
        handlersRef.current.onError?.(ev);
      };

      ws.onclose = (ev) => {
        setReadyState('closed');
        handlersRef.current.onClose?.(ev);
        if (reconnect && !explicitlyClosed.current) {
          reconnectAttempts.current += 1;
          const delay = Math.min(
            reconnectIntervalMs * 2 ** (reconnectAttempts.current - 1),
            maxReconnectIntervalMs,
          );
          reconnectTimer.current = setTimeout(connect, delay);
        }
      };
    } catch (err) {
      setReadyState('error');
      handlersRef.current.onError?.(err as unknown as Event);
    }
  }, [
    enabled,
    buildUrl,
    protocols,
    reconnect,
    reconnectIntervalMs,
    maxReconnectIntervalMs,
    parseJson,
  ]);

  useEffect(() => {
    connect();
    return () => {
      explicitlyClosed.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      const ws = socketRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
      socketRef.current = null;
    };
  }, [connect]);

  useEffect(() => {
    const id = setInterval(() => {
      const ws = socketRef.current;
      if (ws) setReadyState(STATE_MAP[ws.readyState] ?? 'closed');
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const send = useCallback((frame: TOut) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(typeof frame === 'string' ? frame : JSON.stringify(frame));
    return true;
  }, []);

  const sendRaw = useCallback(
    (data: string | ArrayBufferLike | Blob | ArrayBufferView) => {
      const ws = socketRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return false;
      ws.send(data);
      return true;
    },
    [],
  );

  const close = useCallback(() => {
    explicitlyClosed.current = true;
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    socketRef.current?.close();
  }, []);

  return { send, sendRaw, close, readyState, socket: socketRef.current };
}
