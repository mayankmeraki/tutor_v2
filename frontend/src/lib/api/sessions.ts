import { api } from './base';

export interface SessionDoc {
  sessionId: string;
  studentName?: string;
  email?: string;
  topic?: string;
  startedAt?: string;
  endedAt?: string;
  durationMs?: number;
  transcript?: unknown[];
  headlines?: string[];
  sessionMode?: string;
  mockPhase?: string;
  mockCompany?: string;
  problemTitle?: string;
  problemSlug?: string;
  problemDifficulty?: string;
  [key: string]: unknown;
}

export interface BoardFrame {
  ts: number;
  command: Record<string, unknown>;
  [key: string]: unknown;
}

export const sessionsApi = {
  create: (body: Partial<SessionDoc>) =>
    api.post<SessionDoc>('/api/v1/sessions', body),
  patch: (sessionId: string, body: Partial<SessionDoc>) =>
    api.patch<SessionDoc>(`/api/v1/sessions/${sessionId}`, body),
  get: (sessionId: string) =>
    api.get<SessionDoc>(`/api/v1/sessions/${sessionId}`),
  listMine: () => api.get<SessionDoc[]>('/api/v1/sessions/me/all'),
  listMineWithHeadlines: (courseId = 'default') =>
    api.get<SessionDoc[]>(`/api/v1/sessions/me/${courseId}/with-headlines`),
  searchAll: (q: string) =>
    api.get<SessionDoc[]>('/api/v1/sessions/search/all', { query: { q } }),
  searchInCourse: (courseId: string, q: string) =>
    api.get<SessionDoc[]>(`/api/v1/sessions/search/${courseId}`, { query: { q } }),
  byStudent: (courseId: string, name: string) =>
    api.get<SessionDoc[]>(`/api/v1/sessions/student/${courseId}/${encodeURIComponent(name)}`),
  byStudentWithHeadlines: (courseId: string, name: string) =>
    api.get<SessionDoc[]>(
      `/api/v1/sessions/student/${courseId}/${encodeURIComponent(name)}/with-headlines`,
    ),
  boardFrames: (sessionId: string) =>
    api.get<BoardFrame[]>(`/api/v1/sessions/${sessionId}/board-frames`),
  summarizeSection: (sessionId: string, body: Record<string, unknown>) =>
    api.post<{ summary: string }>(
      `/api/v1/sessions/${sessionId}/summarize-section`,
      body,
    ),
};
