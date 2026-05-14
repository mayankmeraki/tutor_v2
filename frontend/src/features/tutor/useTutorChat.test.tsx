import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTutorChat } from './useTutorChat';
import { useAuthStore } from '@/stores/auth';

class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;

  static instances: MockWebSocket[] = [];
  url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  send = vi.fn();
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    });
  }

  emit(data: string | ArrayBuffer | Blob) {
    this.onmessage?.(new MessageEvent('message', { data }));
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket);
  useAuthStore.setState({ token: 'test-tok', user: { email: 'a' } as never });
  // Stub EventSource (jsdom doesn't ship one) so SSE side-effects don't blow up.
  class StubES {
    onmessage: ((e: MessageEvent) => void) | null = null;
    onerror: ((e: Event) => void) | null = null;
    close = vi.fn();
    constructor(public url: string) {}
  }
  vi.stubGlobal('EventSource', StubES);
});

afterEach(() => {
  vi.unstubAllGlobals();
  useAuthStore.setState({ token: null, user: null });
});

async function flush() {
  await act(async () => {
    await new Promise((r) => queueMicrotask(() => r(undefined)));
  });
}

describe('useTutorChat — frame routing', () => {
  it('routes BOARD frames to onBoardCommand', async () => {
    const onBoardCommand = vi.fn();
    renderHook(() => useTutorChat({ sessionId: 's1', onBoardCommand }));
    await flush();
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.emit(JSON.stringify({ type: 'BOARD', cmd: 'text', text: 'hi' }));
    });
    expect(onBoardCommand).toHaveBeenCalledTimes(1);
    expect(onBoardCommand.mock.calls[0][0].cmd).toBe('text');
  });

  it('appends TUTOR_TEXT messages, accumulates TEXT_DELTA', async () => {
    const { result } = renderHook(() => useTutorChat({ sessionId: 's1' }));
    await flush();
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.emit(JSON.stringify({ type: 'TUTOR_TEXT', text: 'Hello ' }));
      ws.emit(JSON.stringify({ type: 'TEXT_DELTA', text: 'world' }));
    });
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].text).toBe('Hello world');
  });

  it('clears thinking on DONE', async () => {
    const { result } = renderHook(() => useTutorChat({ sessionId: 's1' }));
    await flush();
    const ws = MockWebSocket.instances[0];
    // Simulate user-initiated thinking (via send).
    act(() => {
      result.current.sendMessage('hi');
    });
    expect(result.current.thinking).toBe(true);
    act(() => {
      ws.emit(JSON.stringify({ type: 'DONE' }));
    });
    expect(result.current.thinking).toBe(false);
  });

  it('clears thinking on INTERRUPTED / CANCELLED', async () => {
    const { result } = renderHook(() => useTutorChat({ sessionId: 's1' }));
    await flush();
    const ws = MockWebSocket.instances[0];
    act(() => result.current.sendMessage('x'));
    expect(result.current.thinking).toBe(true);
    act(() => ws.emit(JSON.stringify({ type: 'INTERRUPTED' })));
    expect(result.current.thinking).toBe(false);
  });

  it('appends a system message and clears thinking on RUN_ERROR', async () => {
    const { result } = renderHook(() => useTutorChat({ sessionId: 's1' }));
    await flush();
    const ws = MockWebSocket.instances[0];
    act(() => result.current.sendMessage('x'));
    act(() =>
      ws.emit(JSON.stringify({ type: 'RUN_ERROR', message: 'tool failed' })),
    );
    expect(result.current.thinking).toBe(false);
    const last = result.current.messages.at(-1)!;
    expect(last.role).toBe('system');
    expect(last.text).toContain('tool failed');
  });

  it('safely ignores binary / ArrayBuffer frames', async () => {
    const { result } = renderHook(() => useTutorChat({ sessionId: 's1' }));
    await flush();
    const ws = MockWebSocket.instances[0];
    expect(() => {
      act(() => ws.emit(new ArrayBuffer(8)));
    }).not.toThrow();
    expect(result.current.messages).toHaveLength(0);
  });

  it('PONG / HEARTBEAT do not affect state', async () => {
    const { result } = renderHook(() => useTutorChat({ sessionId: 's1' }));
    await flush();
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.emit(JSON.stringify({ type: 'PONG' }));
      ws.emit(JSON.stringify({ type: 'HEARTBEAT' }));
    });
    expect(result.current.messages).toHaveLength(0);
    expect(result.current.thinking).toBe(false);
  });

  it('TTS_CHUNK invokes onTtsChunk', async () => {
    const onTtsChunk = vi.fn();
    renderHook(() => useTutorChat({ sessionId: 's1', onTtsChunk }));
    await flush();
    const ws = MockWebSocket.instances[0];
    act(() => ws.emit(JSON.stringify({ type: 'TTS_CHUNK', text: 'hello' })));
    expect(onTtsChunk).toHaveBeenCalledWith('hello');
  });

  it('sendMessage appends a user message and sends via socket', async () => {
    const { result } = renderHook(() => useTutorChat({ sessionId: 's1' }));
    await flush();
    const ws = MockWebSocket.instances[0];
    act(() => result.current.sendMessage('Hello'));
    expect(result.current.messages.at(-1)?.role).toBe('user');
    expect(ws.send).toHaveBeenCalled();
    const sent = JSON.parse(ws.send.mock.calls[0][0] as string);
    expect(sent.type).toBe('MESSAGE');
    expect(sent.text).toBe('Hello');
  });
});
