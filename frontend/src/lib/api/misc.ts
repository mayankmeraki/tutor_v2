import { api, apiFetch } from './base';

export interface AppConfig {
  tts_enabled: boolean;
  googleClientId?: string;
  [key: string]: unknown;
}

export const configApi = {
  get: () => api.get<AppConfig>('/api/config'),
};

export const feedbackApi = {
  send: (body: {
    type?: string;
    message: string;
    email?: string;
    context?: Record<string, unknown>;
  }) => api.post<{ ok: boolean }>('/api/v1/feedback', body),
  sessionFeedback: (body: {
    sessionId: string;
    rating: number;
    comments?: string;
    [key: string]: unknown;
  }) => api.post<{ ok: boolean }>('/api/v1/session-feedback', body),
};

export const scribeApi = {
  getRealtimeToken: () =>
    api.get<{ token: string; expires_at?: string }>('/api/v1/scribe-token'),
  batch: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<{ text: string }>('/api/v1/scribe-batch', fd);
  },
};

export const tutorApi = {
  fixAnimation: (body: { source: string; error?: string; engine?: 'p5' | 'three' }) =>
    api.post<{ source: string }>('/api/fix-animation', body),
  ttsStream: async (body: { text: string; voice?: string }, signal?: AbortSignal) =>
    apiFetch<Response>('/api/tts', { method: 'POST', body, signal, raw: true }),
};

export const documentsApi = {
  url: (id: string) => `/api/v1/documents/${id}`,
};
