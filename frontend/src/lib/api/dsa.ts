import { api } from './base';

export interface DsaProblem {
  slug: string;
  name: string;
  num?: number;
  difficulty?: 'Easy' | 'Medium' | 'Hard';
  topics?: string[];
  description?: string;
  examples?: { input?: string; output?: string; explanation?: string }[];
  constraints?: string[];
  hints?: string[];
  starterCode?: Record<string, string>;
  testCases?: unknown[];
  lists?: string[];
  companies?: string[];
  [key: string]: unknown;
}

export interface DsaTopic {
  topic: string;
  count: number;
}

export interface DsaListResponse {
  problems: DsaProblem[];
  total?: number;
}

export interface SdProblem {
  slug: string;
  name: string;
  description?: string;
  type?: 'hld' | 'lld';
  [key: string]: unknown;
}

export interface SdConcept {
  id: string;
  name: string;
  description?: string;
  [key: string]: unknown;
}

export interface MockStartResponse {
  problem?: DsaProblem;
  config?: Record<string, unknown>;
  // The backend (currently) does not return a sessionId; the client generates one.
  sessionId?: string;
}

export const dsaApi = {
  // Backend returns `{ problems, total }`. Unwrap to a flat array for simpler callers.
  listProblems: async (params?: Record<string, string | number | boolean | undefined>) => {
    const res = await api.get<DsaListResponse | DsaProblem[]>(
      '/api/v1/dsa/problems',
      { query: params },
    );
    if (Array.isArray(res)) return res;
    return res.problems ?? [];
  },
  listProblemsRaw: (params?: Record<string, string | number | boolean | undefined>) =>
    api.get<DsaListResponse>('/api/v1/dsa/problems', { query: params }),
  getProblem: (slug: string) =>
    api.get<DsaProblem>(`/api/v1/dsa/problems/${slug}`),
  topics: () => api.get<DsaTopic[]>('/api/v1/dsa/topics'),
  lists: () => api.get<{ name: string; slugs: string[] }[]>('/api/v1/dsa/lists'),
  random: () => api.get<DsaProblem>('/api/v1/dsa/random'),
  teachingPlan: (topic: string) =>
    api.get<unknown>(`/api/v1/dsa/teaching-plan/${encodeURIComponent(topic)}`),
  progress: (userId: string) =>
    api.get<unknown>('/api/v1/dsa/progress', { query: { user_id: userId } }),

  sdConcepts: () => api.get<SdConcept[]>('/api/v1/sd/concepts'),
  sdProblems: () => api.get<SdProblem[]>('/api/v1/sd/problems'),
  sdProblem: (slug: string) =>
    api.get<SdProblem>(`/api/v1/sd/problems/${slug}`),

  startMock: (params?: Record<string, string | number | boolean | undefined>) =>
    api.post<MockStartResponse>('/api/v1/mock/start', undefined, {
      query: params,
    }),

  classify: (body: Record<string, unknown>) =>
    api.post<{ blueprint: unknown; mode?: string }>('/api/v1/classify', body),
};
