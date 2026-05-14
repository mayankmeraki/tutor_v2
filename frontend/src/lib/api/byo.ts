import { api } from './base';

export interface ByoCollection {
  collection_id: string;
  name: string;
  description?: string;
  resource_count?: number;
  created_at?: string;
  [key: string]: unknown;
}

export interface ByoResource {
  resource_id: string;
  collection_id: string;
  kind: 'file' | 'url' | 'text';
  filename?: string;
  url?: string;
  status?: 'pending' | 'processing' | 'ready' | 'failed';
  error?: string;
  [key: string]: unknown;
}

export interface ByoJob {
  job_id: string;
  resource_id?: string;
  status: string;
  progress?: number;
  error?: string;
}

export const byoApi = {
  listCollections: () =>
    api.get<ByoCollection[]>('/api/v1/byo/collections'),
  createCollection: (body: { name: string; description?: string }) =>
    api.post<ByoCollection>('/api/v1/byo/collections', body),
  getCollection: (id: string) =>
    api.get<ByoCollection & { resources?: ByoResource[] }>(
      `/api/v1/byo/collections/${id}`,
    ),
  patchCollection: (id: string, body: Partial<ByoCollection>) =>
    api.patch<ByoCollection>(`/api/v1/byo/collections/${id}`, body),
  removeCollection: (id: string) =>
    api.del<{ ok: boolean }>(`/api/v1/byo/collections/${id}`),
  searchCollections: (q: string) =>
    api.get<unknown[]>('/api/v1/byo/collections/search', { query: { q } }),
  moveResource: (
    id: string,
    body: { resource_id: string; target_collection_id: string },
  ) =>
    api.post<{ ok: boolean }>(
      `/api/v1/byo/collections/${id}/move-resource`,
      body,
    ),

  listResources: (collectionId: string) =>
    api.get<ByoResource[]>(`/api/v1/byo/collections/${collectionId}/resources`),
  addResourceFile: (collectionId: string, file: File, extra?: Record<string, string>) => {
    const fd = new FormData();
    fd.append('file', file);
    if (extra) for (const [k, v] of Object.entries(extra)) fd.append(k, v);
    return api.post<{ resource: ByoResource; job?: ByoJob }>(
      `/api/v1/byo/collections/${collectionId}/resources`,
      fd,
    );
  },
  addResourceUrl: (collectionId: string, url: string, extra?: Record<string, string>) => {
    const fd = new FormData();
    fd.append('url', url);
    if (extra) for (const [k, v] of Object.entries(extra)) fd.append(k, v);
    return api.post<{ resource: ByoResource; job?: ByoJob }>(
      `/api/v1/byo/collections/${collectionId}/resources`,
      fd,
    );
  },
  addResourceText: (collectionId: string, text: string, extra?: Record<string, string>) => {
    const fd = new FormData();
    fd.append('text', text);
    if (extra) for (const [k, v] of Object.entries(extra)) fd.append(k, v);
    return api.post<{ resource: ByoResource; job?: ByoJob }>(
      `/api/v1/byo/collections/${collectionId}/resources`,
      fd,
    );
  },
  retryResource: (collectionId: string, resourceId: string) =>
    api.post<ByoJob>(
      `/api/v1/byo/collections/${collectionId}/resources/${resourceId}/retry`,
    ),
  removeResource: (collectionId: string, resourceId: string) =>
    api.del<{ ok: boolean }>(
      `/api/v1/byo/collections/${collectionId}/resources/${resourceId}`,
    ),
  getJob: (jobId: string) =>
    api.get<ByoJob>(`/api/v1/byo/jobs/${jobId}`),
  resourceTranscript: (
    resourceId: string,
    timestamp?: number,
    windowMs?: number,
  ) =>
    api.get<unknown>(`/api/v1/byo/resources/${resourceId}/transcript`, {
      query: { timestamp, window: windowMs },
    }),
  resourceInfo: (resourceId: string) =>
    api.get<unknown>(`/api/v1/byo/resources/${resourceId}/info`),
};

export const byoUrls = {
  media: (alias: string) => `/api/v1/byo/media/${alias}`,
  audio: (audioId: string) => `/api/v1/byo/audio/${audioId}`,
  resourceFile: (resourceId: string) => `/api/v1/byo/resources/${resourceId}/file`,
};
