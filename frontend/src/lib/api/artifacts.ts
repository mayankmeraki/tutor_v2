import { api } from './base';

/** Spaced-repetition rating accepted by `/api/v1/artifacts/{id}/sr`. */
export type SrRating = 'again' | 'hard' | 'good' | 'easy';

export interface SrStats {
  due_now?: number;
  next_due_at?: string | null;
  total_cards?: number;
  reviewed?: number;
}

/**
 * Backend returns artifacts using snake_case keys for IDs and SR fields.
 * We mirror those alongside camelCase aliases so React code can use either.
 */
export interface Artifact {
  artifact_id: string;
  artifactId: string;
  type?: string;
  title?: string;
  preview?: string;
  content?: string;
  tags?: string[];
  ownerEmail?: string;
  createdAt?: string;
  updatedAt?: string;
  sr_stats?: SrStats;
  sr?: {
    interval?: number;
    repetitions?: number;
    easeFactor?: number;
    nextReviewAt?: string;
    lastReviewedAt?: string;
  };
  cards?: unknown[];
  [key: string]: unknown;
}

function normalizeArtifact(raw: Record<string, unknown>): Artifact {
  const id = (raw.artifact_id ?? raw.artifactId ?? '') as string;
  return {
    ...raw,
    artifact_id: id,
    artifactId: id,
    sr_stats: (raw.sr_stats ?? raw.srStats) as SrStats | undefined,
  } as Artifact;
}

export const artifactsApi = {
  list: async () => {
    const list = await api.get<Record<string, unknown>[]>('/api/v1/artifacts');
    return list.map(normalizeArtifact);
  },
  get: async (id: string) => {
    const raw = await api.get<Record<string, unknown>>(`/api/v1/artifacts/${id}`);
    return normalizeArtifact(raw);
  },
  create: async (body: Partial<Artifact>) => {
    const raw = await api.post<Record<string, unknown>>('/api/v1/artifacts', body);
    return normalizeArtifact(raw);
  },
  patch: async (id: string, body: Partial<Artifact>) => {
    const raw = await api.patch<Record<string, unknown>>(`/api/v1/artifacts/${id}`, body);
    return normalizeArtifact(raw);
  },
  remove: (id: string) =>
    api.del<{ ok: boolean }>(`/api/v1/artifacts/${id}`),
  /** Backend expects `{ rating: 'again'|'hard'|'good'|'easy', card_index?: number }`. */
  spacedRepetition: (
    id: string,
    body: { rating: SrRating; card_index?: number },
  ) => api.post<Artifact>(`/api/v1/artifacts/${id}/sr`, body),
};
