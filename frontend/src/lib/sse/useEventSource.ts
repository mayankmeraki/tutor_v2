import { useEffect, useRef, useState, useCallback } from 'react';

export type SseReadyState = 'connecting' | 'open' | 'closed' | 'error';

export interface UseEventSourceOptions<T = unknown> {
  url: string;
  token?: string | null;
  enabled?: boolean;
  onMessage?: (data: T, raw: MessageEvent) => void;
  onOpen?: (ev: Event) => void;
  onError?: (ev: Event) => void;
  parseJson?: boolean;
  events?: string[];
}

export function useEventSource<T = unknown>(
  options: UseEventSourceOptions<T>,
): { close: () => void; readyState: SseReadyState } {
  const {
    url,
    token,
    enabled = true,
    onMessage,
    onOpen,
    onError,
    parseJson = true,
    events,
  } = options;

  const [readyState, setReadyState] = useState<SseReadyState>('closed');
  const sourceRef = useRef<EventSource | null>(null);
  const handlersRef = useRef({ onMessage, onOpen, onError });
  handlersRef.current = { onMessage, onOpen, onError };

  useEffect(() => {
    if (!enabled) {
      setReadyState('closed');
      return;
    }

    const finalUrl = token
      ? `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
      : url;

    const es = new EventSource(finalUrl);
    sourceRef.current = es;
    setReadyState('connecting');

    es.onopen = (ev) => {
      setReadyState('open');
      handlersRef.current.onOpen?.(ev);
    };

    const dispatch = (ev: MessageEvent) => {
      let data: T = ev.data as T;
      if (parseJson && typeof ev.data === 'string') {
        try {
          data = JSON.parse(ev.data) as T;
        } catch {
          data = ev.data as T;
        }
      }
      handlersRef.current.onMessage?.(data, ev);
    };

    es.onmessage = dispatch;

    if (events) {
      for (const evt of events) es.addEventListener(evt, dispatch as EventListener);
    }

    es.onerror = (ev) => {
      setReadyState('error');
      handlersRef.current.onError?.(ev);
    };

    return () => {
      es.close();
      sourceRef.current = null;
      setReadyState('closed');
    };
  }, [url, token, enabled, parseJson, events?.join(',')]);

  const close = useCallback(() => {
    sourceRef.current?.close();
    setReadyState('closed');
  }, []);

  return { close, readyState };
}
