import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTtsPlayback } from './useTtsPlayback';
import { useAuthStore } from '@/stores/auth';

const fetchMock = vi.fn();

beforeEach(() => {
  useAuthStore.setState({ token: null, user: null });
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
  // Audio is jsdom-provided but play() rejects by default; stub it.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (HTMLMediaElement.prototype as any).play = vi.fn(() => Promise.resolve());
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (HTMLMediaElement.prototype as any).load = vi.fn();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (HTMLMediaElement.prototype as any).pause = vi.fn();
});

afterEach(() => vi.unstubAllGlobals());

function audioRes(): Response {
  return new Response(new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/mpeg' }), {
    status: 200,
    headers: { 'content-type': 'audio/mpeg' },
  });
}

describe('useTtsPlayback', () => {
  it('starts in non-playing state', () => {
    const { result } = renderHook(() => useTtsPlayback());
    expect(result.current.playing).toBe(false);
  });

  it('play() POSTs to /api/tts and toggles playing=true', async () => {
    fetchMock.mockResolvedValueOnce(audioRes());
    const { result } = renderHook(() => useTtsPlayback());
    await act(async () => {
      await result.current.play('hello');
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/tts');
    expect((init as RequestInit).method).toBe('POST');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ text: 'hello' });
    expect(result.current.playing).toBe(true);
  });

  it('stop() resets playing to false', async () => {
    fetchMock.mockResolvedValueOnce(audioRes());
    const { result } = renderHook(() => useTtsPlayback());
    await act(async () => {
      await result.current.play('hi');
    });
    act(() => result.current.stop());
    expect(result.current.playing).toBe(false);
  });

  it('AbortError during play() is swallowed', async () => {
    fetchMock.mockImplementationOnce(() => {
      const e = new Error('aborted');
      e.name = 'AbortError';
      return Promise.reject(e);
    });
    const { result } = renderHook(() => useTtsPlayback());
    await act(async () => {
      await result.current.play('x');
    });
    expect(result.current.playing).toBe(false);
  });
});
