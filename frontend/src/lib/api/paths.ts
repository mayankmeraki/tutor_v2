import { api } from './base';

export type PathNodeStatus = 'pending' | 'active' | 'completed' | 'skipped';

export interface PathNode {
  /** Backend uses `nodeId`. We mirror it as `id` for React keys. */
  nodeId: string;
  id: string;
  title?: string;
  status?: PathNodeStatus;
  kind?: string;
  type?: string;
  studentNote?: string;
  /** Convenience alias of `studentNote`. */
  note?: string;
  sessionId?: string;
  topics?: string[];
  prerequisites?: string[];
  targetMin?: number;
  [key: string]: unknown;
}

export interface PathPivot {
  pivotIndex?: number;
  reason?: string;
  proposedNodes?: Partial<PathNode>[];
  [key: string]: unknown;
}

export interface PathDoc {
  pathId: string;
  title?: string;
  intent?: string;
  status?: string;
  nodes?: PathNode[];
  pivots?: PathPivot[];
  chatHistory?: unknown[];
  [key: string]: unknown;
}

function normalizeNode(n: Record<string, unknown>): PathNode {
  const id = (n.nodeId ?? n.id ?? '') as string;
  const note = (n.studentNote ?? n.note ?? '') as string;
  return {
    ...n,
    nodeId: id,
    id,
    studentNote: note || undefined,
    note: note || undefined,
  } as PathNode;
}

function normalizePath(p: Record<string, unknown>): PathDoc {
  const nodes = Array.isArray(p.nodes)
    ? (p.nodes as Record<string, unknown>[]).map(normalizeNode)
    : undefined;
  return { ...p, nodes } as PathDoc;
}

export const pathsApi = {
  list: async (status?: string) => {
    const list = await api.get<Record<string, unknown>[]>('/api/v1/paths', {
      query: { status },
    });
    return list.map(normalizePath);
  },
  create: async (body: Partial<PathDoc>) => {
    const raw = await api.post<Record<string, unknown>>('/api/v1/paths', body);
    return normalizePath(raw);
  },
  get: async (pathId: string) => {
    const raw = await api.get<Record<string, unknown>>(`/api/v1/paths/${pathId}`);
    return normalizePath(raw);
  },
  patch: async (pathId: string, body: Partial<PathDoc>) => {
    const raw = await api.patch<Record<string, unknown>>(
      `/api/v1/paths/${pathId}`,
      body,
    );
    return normalizePath(raw);
  },
  remove: (pathId: string) =>
    api.del<{ ok: boolean }>(`/api/v1/paths/${pathId}`),
  wizard: (body: Record<string, unknown>) =>
    api.post<{ questions: { key: string; question: string; chips?: string[]; freeText?: boolean }[] }>(
      '/api/v1/paths/wizard',
      body,
    ),
  next: (pathId: string) =>
    api.get<PathNode | null>(`/api/v1/paths/${pathId}/next`),
  /**
   * Backend route returns `{ ok: true }` only — caller should NOT read `sessionId`
   * from the response. Pass an explicit `sessionId` in the body if linking the
   * node to a session.
   */
  startNode: (pathId: string, nodeId: string, body?: Record<string, unknown>) =>
    api.post<{ ok: boolean }>(
      `/api/v1/paths/${pathId}/nodes/${nodeId}/start`,
      body ?? {},
    ),
  completeNode: (pathId: string, nodeId: string, body?: Record<string, unknown>) =>
    api.post<{ ok: boolean }>(
      `/api/v1/paths/${pathId}/nodes/${nodeId}/complete`,
      body ?? {},
    ),
  skipNode: (pathId: string, nodeId: string) =>
    api.post<{ ok: boolean }>(`/api/v1/paths/${pathId}/nodes/${nodeId}/skip`),
  /** Backend field is `studentNote`. */
  noteNode: (pathId: string, nodeId: string, studentNote: string) =>
    api.patch<{ ok: boolean }>(
      `/api/v1/paths/${pathId}/nodes/${nodeId}/note`,
      { studentNote },
    ),
  removeNode: (pathId: string, nodeId: string) =>
    api.del<{ ok: boolean }>(`/api/v1/paths/${pathId}/nodes/${nodeId}`),
  /** Backend expects `{ nodeIds: [...] }`. */
  reorderNodes: (pathId: string, nodeIds: string[]) =>
    api.post<PathDoc>(`/api/v1/paths/${pathId}/nodes/reorder`, { nodeIds }),
  addNode: (pathId: string, body: Partial<PathNode>) =>
    api.post<PathNode>(`/api/v1/paths/${pathId}/nodes/add`, body),
  reflect: (pathId: string, body: Record<string, unknown>) =>
    api.post<{
      strengths?: string[];
      gaps?: string[];
      pivot?: PathPivot;
      reflection?: string;
    }>(`/api/v1/paths/${pathId}/reflect`, body),
  /** Backend expects `{ nodes: [...] }` body. */
  applyPivot: (pathId: string, pivotIndex: number, nodes: Partial<PathNode>[]) =>
    api.post<PathDoc>(
      `/api/v1/paths/${pathId}/pivots/${pivotIndex}/apply`,
      { nodes },
    ),
  complete: (pathId: string, retrospective?: Record<string, unknown>) =>
    api.post<PathDoc>(`/api/v1/paths/${pathId}/complete`, retrospective ?? {}),
  chat: (pathId: string, body: Record<string, unknown>) =>
    api.post<{ ok: boolean }>(`/api/v1/paths/${pathId}/chat`, body),
};
