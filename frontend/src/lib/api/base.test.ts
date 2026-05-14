import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiFetch, ApiError, formatApiError } from './base';
import { useAuthStore } from '@/stores/auth';

describe('formatApiError', () => {
  it('handles plain string detail', () => {
    expect(formatApiError(400, { detail: 'Invalid input' })).toBe('Invalid input');
  });

  it('handles array detail (FastAPI 422 validation)', () => {
    const body = {
      detail: [
        { loc: ['body', 'email'], msg: 'field required', type: 'value_error.missing' },
        { loc: ['body', 'password'], msg: 'too short', type: 'value_error' },
      ],
    };
    const msg = formatApiError(422, body);
    expect(msg).toContain('body.email');
    expect(msg).toContain('field required');
    expect(msg).toContain('body.password');
  });

  it('handles object detail with message', () => {
    expect(formatApiError(500, { detail: { message: 'Boom', code: 'X1' } })).toBe('Boom');
  });

  it('handles raw string body', () => {
    expect(formatApiError(502, 'Bad Gateway')).toBe('Bad Gateway');
  });

  it('falls back when body is null', () => {
    expect(formatApiError(503, null)).toBe('Request failed: 503');
  });

  it('uses error/message keys when detail is absent', () => {
    expect(formatApiError(401, { error: 'unauthenticated' })).toBe('unauthenticated');
    expect(formatApiError(429, { message: 'too many' })).toBe('too many');
  });
});

describe('apiFetch', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    useAuthStore.setState({ token: null, user: null });
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function jsonRes(status: number, body: unknown): Response {
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    });
  }

  it('appends Authorization header when a token is set', async () => {
    useAuthStore.setState({ token: 'tk-1', user: null });
    fetchMock.mockResolvedValueOnce(jsonRes(200, { ok: true }));
    await apiFetch<{ ok: true }>('/api/v1/foo');
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer tk-1',
    });
  });

  it('serializes JSON bodies and sets content-type', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { ok: true }));
    await apiFetch('/api/v1/foo', { method: 'POST', body: { hello: 'world' } });
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).body).toBe('{"hello":"world"}');
    expect((init as RequestInit).headers).toMatchObject({
      'Content-Type': 'application/json',
    });
  });

  it('does NOT set content-type for FormData', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, {}));
    const fd = new FormData();
    fd.append('file', new Blob(['x']), 'a.txt');
    await apiFetch('/api/v1/foo', { method: 'POST', body: fd });
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).headers).not.toHaveProperty('Content-Type');
  });

  it('skips null/undefined query params and supports arrays', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, []));
    await apiFetch('/api/v1/x', {
      query: { a: 1, b: undefined, c: null, d: ['x', 'y'] as never },
    });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('a=1');
    expect(url).not.toContain('b=');
    expect(url).not.toContain('c=');
    expect(url).toContain('d=x');
    expect(url).toContain('d=y');
  });

  it('throws ApiError with formatted message on 422 validation', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(422, {
        detail: [{ loc: ['body', 'name'], msg: 'required' }],
      }),
    );
    await expect(apiFetch('/api/v1/x')).rejects.toMatchObject({
      status: 422,
      message: expect.stringContaining('body.name'),
    });
  });

  it('clears auth and redirects on 401', async () => {
    useAuthStore.setState({ token: 'tk', user: { email: 'a' } as never });
    const assignSpy = vi.fn();
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { ...window.location, pathname: '/home', assign: assignSpy },
    });
    fetchMock.mockResolvedValueOnce(jsonRes(401, { detail: 'expired' }));
    await expect(apiFetch('/api/v1/me')).rejects.toBeInstanceOf(ApiError);
    expect(useAuthStore.getState().token).toBeNull();
    expect(assignSpy).toHaveBeenCalledWith('/login');
  });

  it('does NOT redirect when already on /login', async () => {
    const assignSpy = vi.fn();
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { ...window.location, pathname: '/login', assign: assignSpy },
    });
    fetchMock.mockResolvedValueOnce(jsonRes(401, { detail: 'expired' }));
    await expect(apiFetch('/api/v1/x')).rejects.toBeInstanceOf(ApiError);
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it('returns plain text when content-type is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('hello', { status: 200, headers: { 'content-type': 'text/plain' } }),
    );
    const out = await apiFetch<string>('/api/v1/text');
    expect(out).toBe('hello');
  });

  it('returns null on 204 No Content', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const out = await apiFetch('/api/v1/x');
    expect(out).toBeNull();
  });
});
