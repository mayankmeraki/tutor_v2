import { describe, it, expect, vi, beforeEach } from 'vitest';
import { judgeApi } from './judge';
import { dsaApi } from './dsa';
import { byoApi } from './byo';
import { sessionsApi } from './sessions';
import { authApi } from './auth';
import { useAuthStore } from '@/stores/auth';

const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
  useAuthStore.setState({ token: null, user: null });
});

function jsonRes(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('judgeApi', () => {
  it('run posts code + test_cases body shape backend expects', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, {
        status: 'ok',
        passed: true,
        cases: [{ passed: true }],
      }),
    );
    const out = await judgeApi.run({
      code: 'print(1)',
      language: 'python',
      test_cases: [{ input: '', expected_output: '1' }],
    });
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.code).toBe('print(1)');
    expect(body.language).toBe('python');
    expect(body.test_cases).toHaveLength(1);
    expect(out.passed).toBe(true);
  });

  it('submit accepts problem_slug for backend hydration', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { status: 'ok' }));
    await judgeApi.submit({
      code: 'def f(): pass',
      language: 'python',
      problem_slug: 'two-sum',
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/judge/submit');
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.problem_slug).toBe('two-sum');
  });
});

describe('dsaApi', () => {
  it('listProblemsRaw returns the unwrapped envelope', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, { problems: [{ slug: 'a', name: 'A' }], total: 1 }),
    );
    const raw = await dsaApi.listProblemsRaw();
    expect(raw.total).toBe(1);
    expect(raw.problems).toHaveLength(1);
  });

  it('topics() returns DsaTopic[]', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, [
        { topic: 'arrays', count: 12 },
        { topic: 'graphs', count: 7 },
      ]),
    );
    const topics = await dsaApi.topics();
    expect(topics).toHaveLength(2);
    expect(topics[0].topic).toBe('arrays');
    expect(topics[1].count).toBe(7);
  });

  it('startMock POSTs to /api/v1/mock/start with query params', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, {
        problem: { slug: 'two-sum', name: 'Two Sum' },
        config: { difficulty: 'Easy', company: 'Google' },
      }),
    );
    const res = await dsaApi.startMock({
      difficulty: 'Easy',
      company: 'Google',
      type: 'dsa',
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/mock/start');
    expect(url).toContain('difficulty=Easy');
    expect(url).toContain('company=Google');
    expect(url).toContain('type=dsa');
    expect((init as RequestInit).method).toBe('POST');
    expect(res.problem?.slug).toBe('two-sum');
  });

  it('sdProblem fetches a single SD problem by slug', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, { slug: 'url-shortener', name: 'URL Shortener', type: 'hld' }),
    );
    const p = await dsaApi.sdProblem('url-shortener');
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/sd/problems/url-shortener');
    expect(p.type).toBe('hld');
  });
});

describe('byoApi.addResource* — uses FormData (no Content-Type override)', () => {
  it('addResourceUrl sends a FormData body with `url`', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, { resource: { resource_id: 'r1', collection_id: 'c1', kind: 'url' } }),
    );
    await byoApi.addResourceUrl('c1', 'https://x.com/y');
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).body).toBeInstanceOf(FormData);
    const fd = (init as RequestInit).body as FormData;
    expect(fd.get('url')).toBe('https://x.com/y');
    expect((init as RequestInit).headers).not.toHaveProperty('Content-Type');
  });

  it('addResourceText accepts extras', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, { resource: { resource_id: 'r2', collection_id: 'c1', kind: 'text' } }),
    );
    await byoApi.addResourceText('c1', 'hello', { tag: 'note' });
    const [, init] = fetchMock.mock.calls[0];
    const fd = (init as RequestInit).body as FormData;
    expect(fd.get('text')).toBe('hello');
    expect(fd.get('tag')).toBe('note');
  });

  it('moveResource POSTs JSON', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { ok: true }));
    await byoApi.moveResource('c1', {
      resource_id: 'r1',
      target_collection_id: 'c2',
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/byo/collections/c1/move-resource');
    expect((init as RequestInit).method).toBe('POST');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      resource_id: 'r1',
      target_collection_id: 'c2',
    });
  });

  it('searchCollections passes the q query param', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, []));
    await byoApi.searchCollections('graphs');
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/byo/collections/search');
    expect(url).toContain('q=graphs');
  });

  it('resourceTranscript supports timestamp + windowMs', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { lines: [] }));
    await byoApi.resourceTranscript('r1', 12.5, 4000);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/byo/resources/r1/transcript');
    expect(url).toContain('timestamp=12.5');
    expect(url).toContain('window=4000');
  });
});

describe('sessionsApi', () => {
  it('searchAll passes q in the query string', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, []));
    await sessionsApi.searchAll('binary tree');
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/sessions/search/all');
    expect(url).toContain('q=binary+tree');
  });

  it('boardFrames fetches /board-frames', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, [{ ts: 0, command: { cmd: 'h1' } }]));
    const frames = await sessionsApi.boardFrames('s1');
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/sessions/s1/board-frames');
    expect(frames).toHaveLength(1);
  });
});

describe('authApi', () => {
  it('login posts {email,password}', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, { token: 't', user: { email: 'a@b.com' } }),
    );
    const out = await authApi.login('a@b.com', 'pw');
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      email: 'a@b.com',
      password: 'pw',
    });
    expect(out.token).toBe('t');
  });

  it('google posts {credential}', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, { token: 'g', user: { email: 'b@c.com' } }),
    );
    await authApi.google('jwt-credential');
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      credential: 'jwt-credential',
    });
  });

  it('me() GETs /api/v1/auth/me', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { email: 'a@b.com' }));
    await authApi.me();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/auth/me');
    expect((init as RequestInit).method).toBe('GET');
  });
});
