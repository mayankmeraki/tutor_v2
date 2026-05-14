import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from './useWebSocket';

class MockWS {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;
  static instances: MockWS[] = [];

  url: string;
  protocols: string | string[] | undefined;
  readyState: number = MockWS.CONNECTING;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWS.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  });

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    MockWS.instances.push(this);
    queueMicrotask(() => {
      this.readyState = MockWS.OPEN;
      this.onopen?.(new Event('open'));
    });
  }
}

beforeEach(() => {
  MockWS.instances = [];
  vi.stubGlobal('WebSocket', MockWS);
});
afterEach(() => vi.unstubAllGlobals());

async function flush() {
  await act(async () => {
    await new Promise((r) => queueMicrotask(() => r(undefined)));
  });
}

describe('useWebSocket', () => {
  it('appends `?token=` to the URL when a token is provided', async () => {
    renderHook(() =>
      useWebSocket({ url: 'ws://x/y', token: 'abc def', onMessage: () => {} }),
    );
    await flush();
    expect(MockWS.instances[0].url).toBe('ws://x/y?token=abc%20def');
  });

  it('does not append token when null', async () => {
    renderHook(() => useWebSocket({ url: 'ws://x/y', token: null }));
    await flush();
    expect(MockWS.instances[0].url).toBe('ws://x/y');
  });

  it('uses & separator if URL already has a query string', async () => {
    renderHook(() => useWebSocket({ url: 'ws://x/y?foo=1', token: 't' }));
    await flush();
    expect(MockWS.instances[0].url).toBe('ws://x/y?foo=1&token=t');
  });

  it('parses incoming JSON messages by default', async () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket({ url: 'ws://x', onMessage }));
    await flush();
    act(() => {
      MockWS.instances[0].onmessage?.(
        new MessageEvent('message', { data: JSON.stringify({ type: 'A', n: 1 }) }),
      );
    });
    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage.mock.calls[0][0]).toEqual({ type: 'A', n: 1 });
  });

  it('falls back to raw string when JSON parse fails', async () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket({ url: 'ws://x', onMessage }));
    await flush();
    act(() => {
      MockWS.instances[0].onmessage?.(
        new MessageEvent('message', { data: 'not json' }),
      );
    });
    expect(onMessage.mock.calls[0][0]).toBe('not json');
  });

  it('can disable JSON parsing via parseJson:false', async () => {
    const onMessage = vi.fn();
    renderHook(() =>
      useWebSocket({ url: 'ws://x', parseJson: false, onMessage }),
    );
    await flush();
    act(() => {
      MockWS.instances[0].onmessage?.(
        new MessageEvent('message', { data: '{"ok":true}' }),
      );
    });
    expect(onMessage.mock.calls[0][0]).toBe('{"ok":true}');
  });

  it('send() serializes objects as JSON when socket is OPEN', async () => {
    const { result } = renderHook(() => useWebSocket({ url: 'ws://x' }));
    await flush();
    act(() => {
      const ok = result.current.send({ type: 'X', a: 1 });
      expect(ok).toBe(true);
    });
    expect(MockWS.instances[0].send).toHaveBeenCalledWith('{"type":"X","a":1}');
  });

  it('send() returns false when not OPEN', async () => {
    const { result } = renderHook(() => useWebSocket({ url: 'ws://x' }));
    expect(result.current.send({ type: 'X' })).toBe(false);
  });

  it('does not attempt to connect when enabled=false', async () => {
    renderHook(() => useWebSocket({ url: 'ws://x', enabled: false }));
    await flush();
    expect(MockWS.instances).toHaveLength(0);
  });

  it('explicit close() prevents reconnection', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() =>
      useWebSocket({ url: 'ws://x', reconnect: true, reconnectIntervalMs: 100 }),
    );
    await flush();
    act(() => result.current.close());
    // even after the reconnect window, no new instance should appear
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(MockWS.instances.length).toBe(1);
    vi.useRealTimers();
  });
});
