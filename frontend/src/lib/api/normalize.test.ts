import { describe, it, expect, vi, beforeEach } from 'vitest';
import { dsaApi } from './dsa';
import { artifactsApi } from './artifacts';
import { pathsApi } from './paths';
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

describe('dsa.listProblems', () => {
  it('unwraps `{ problems, total }`', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, {
        problems: [{ slug: 'two-sum', name: 'Two Sum' }],
        total: 1,
      }),
    );
    const out = await dsaApi.listProblems();
    expect(Array.isArray(out)).toBe(true);
    expect(out[0].slug).toBe('two-sum');
  });

  it('passes through array responses unchanged', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, [{ slug: 'a', name: 'A' }]));
    const out = await dsaApi.listProblems();
    expect(out).toHaveLength(1);
    expect(out[0].slug).toBe('a');
  });
});

describe('artifactsApi.list', () => {
  it('mirrors snake_case ids onto camelCase aliases', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, [
        {
          artifact_id: 'a-1',
          type: 'flashcards',
          title: 'Trees',
          sr_stats: { due_now: 2 },
        },
      ]),
    );
    const out = await artifactsApi.list();
    expect(out[0].artifactId).toBe('a-1');
    expect(out[0].artifact_id).toBe('a-1');
    expect(out[0].sr_stats?.due_now).toBe(2);
  });
});

describe('pathsApi.get', () => {
  it('mirrors nodeId/id and studentNote/note', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonRes(200, {
        pathId: 'p-1',
        title: 'Graphs',
        nodes: [
          { nodeId: 'n-1', title: 'BFS', studentNote: 'remember queue', status: 'active' },
          { nodeId: 'n-2', title: 'DFS', status: 'pending' },
        ],
      }),
    );
    const path = await pathsApi.get('p-1');
    expect(path.nodes![0].id).toBe('n-1');
    expect(path.nodes![0].nodeId).toBe('n-1');
    expect(path.nodes![0].note).toBe('remember queue');
    expect(path.nodes![0].status).toBe('active');
  });
});

describe('pathsApi.reorderNodes', () => {
  it('sends `nodeIds` body matching the backend contract', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { pathId: 'p', nodes: [] }));
    await pathsApi.reorderNodes('p', ['n-2', 'n-1']);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/paths/p/nodes/reorder');
    expect((init as RequestInit).body).toBe('{"nodeIds":["n-2","n-1"]}');
  });
});

describe('pathsApi.applyPivot', () => {
  it('sends `{ nodes }` body', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { pathId: 'p', nodes: [] }));
    await pathsApi.applyPivot('p', 0, [{ title: 'New step' }]);
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      nodes: [{ title: 'New step' }],
    });
  });
});

describe('pathsApi.noteNode', () => {
  it('PATCHes with `studentNote` field (not `note`)', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { ok: true }));
    await pathsApi.noteNode('p', 'n', 'remember the invariant');
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      studentNote: 'remember the invariant',
    });
    expect((init as RequestInit).method).toBe('PATCH');
  });
});

describe('artifactsApi.spacedRepetition', () => {
  it('sends `{ rating }` enum (not numeric quality)', async () => {
    fetchMock.mockResolvedValueOnce(jsonRes(200, { artifact_id: 'a' }));
    await artifactsApi.spacedRepetition('a-1', { rating: 'good' });
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ rating: 'good' });
  });
});
