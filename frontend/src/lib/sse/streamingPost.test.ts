import { describe, it, expect, vi, beforeEach } from 'vitest';
import { streamingPost } from './streamingPost';
import { useAuthStore } from '@/stores/auth';

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
  useAuthStore.setState({ token: null, user: null });
});

function streamRes(body: string): Response {
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(enc.encode(body));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { 'content-type': 'text/event-stream' },
  });
}

describe('streamingPost', () => {
  it('parses single data: lines as JSON', async () => {
    fetchMock.mockResolvedValueOnce(streamRes('data: {"type":"status","message":"hi"}\n\n'));
    const events: unknown[] = [];
    await streamingPost({
      url: '/foo',
      body: {},
      onEvent: ({ data }) => events.push(data),
    });
    expect(events).toHaveLength(1);
    expect((events[0] as Record<string, string>).type).toBe('status');
  });

  it('joins multi-line data: payloads', async () => {
    const body = 'data: {"type":\ndata: "x"}\n\n';
    fetchMock.mockResolvedValueOnce(streamRes(body));
    const events: unknown[] = [];
    await streamingPost({
      url: '/foo',
      body: {},
      onEvent: ({ data }) => events.push(data),
    });
    expect((events[0] as Record<string, string>).type).toBe('x');
  });

  it('passes through `event:` field when present', async () => {
    fetchMock.mockResolvedValueOnce(
      streamRes('event: error\ndata: {"detail":"boom"}\n\n'),
    );
    const events: { event?: string; data: unknown }[] = [];
    await streamingPost({
      url: '/foo',
      body: {},
      onEvent: (e) => events.push(e),
    });
    expect(events[0].event).toBe('error');
  });

  it('ignores comment lines (e.g., `:keep-alive`)', async () => {
    const body = ':keep-alive\n\ndata: {"type":"ok"}\n\n';
    fetchMock.mockResolvedValueOnce(streamRes(body));
    const events: unknown[] = [];
    await streamingPost({
      url: '/foo',
      body: {},
      onEvent: ({ data }) => events.push(data),
    });
    expect(events).toHaveLength(1);
  });

  it('forwards multiple events in order', async () => {
    const body =
      'data: {"i":1}\n\ndata: {"i":2}\n\ndata: {"i":3}\n\n';
    fetchMock.mockResolvedValueOnce(streamRes(body));
    const seen: number[] = [];
    await streamingPost({
      url: '/foo',
      body: {},
      onEvent: ({ data }) => seen.push((data as { i: number }).i),
    });
    expect(seen).toEqual([1, 2, 3]);
  });

  it('calls onError when fetch rejects', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network fail'));
    const onError = vi.fn();
    await streamingPost({ url: '/foo', body: {}, onError });
    expect(onError).toHaveBeenCalledWith(expect.any(Error));
  });

  it('does not call onError when aborted', async () => {
    const ctrl = new AbortController();
    fetchMock.mockRejectedValueOnce(
      Object.assign(new Error('aborted'), { name: 'AbortError' }),
    );
    const onError = vi.fn();
    await streamingPost({
      url: '/foo',
      body: {},
      signal: ctrl.signal,
      onError,
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it('attaches Authorization header when token is set', async () => {
    useAuthStore.setState({ token: 'tk', user: null });
    fetchMock.mockResolvedValueOnce(streamRes('data: {}\n\n'));
    await streamingPost({ url: '/foo', body: {} });
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer tk',
    });
  });

  it('throws no callback when stream errors with non-OK', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('nope', { status: 500, headers: {} }),
    );
    const onError = vi.fn();
    await streamingPost({ url: '/foo', body: {}, onError });
    expect(onError).toHaveBeenCalled();
  });
});
