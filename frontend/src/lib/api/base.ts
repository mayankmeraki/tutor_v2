import { useAuthStore } from '@/stores/auth';

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export interface ApiRequestOptions extends Omit<RequestInit, 'body' | 'headers'> {
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  raw?: boolean;
}

function buildUrl(path: string, query?: ApiRequestOptions['query']): string {
  if (!query) return path;
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      for (const item of v) {
        if (item === undefined || item === null) continue;
        usp.append(k, String(item));
      }
      continue;
    }
    usp.append(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `${path}?${qs}` : path;
}

/**
 * FastAPI returns errors in several shapes:
 *   { detail: "string" }                                 - HTTPException(detail="...")
 *   { detail: [{ loc, msg, type, ... }] }                - 422 validation
 *   { detail: { ... } }                                  - structured detail
 *   raw text / HTML                                       - upstream / proxy errors
 */
export function formatApiError(status: number, body: unknown): string {
  const fallback = `Request failed: ${status}`;
  if (body == null) return fallback;
  if (typeof body === 'string') return body.slice(0, 300) || fallback;
  if (typeof body !== 'object') return fallback;
  const obj = body as Record<string, unknown>;
  const detail = obj.detail ?? obj.message ?? obj.error;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const lines = detail
      .map((d) => {
        if (typeof d === 'string') return d;
        if (d && typeof d === 'object') {
          const dd = d as Record<string, unknown>;
          const loc = Array.isArray(dd.loc) ? dd.loc.join('.') : '';
          const msg = (dd.msg ?? dd.message ?? '') as string;
          return loc ? `${loc}: ${msg}` : msg;
        }
        return '';
      })
      .filter(Boolean);
    if (lines.length) return lines.slice(0, 5).join('; ');
  }
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    if (typeof d.message === 'string') return d.message;
    try {
      return JSON.stringify(d).slice(0, 300);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  opts: ApiRequestOptions = {},
): Promise<T> {
  const token = useAuthStore.getState().token;
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(opts.headers ?? {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json';
    body = JSON.stringify(opts.body);
  }

  const url = buildUrl(path, opts.query);
  const res = await fetch(url, { ...opts, headers, body });

  if (res.status === 401) {
    useAuthStore.getState().clear();
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.assign('/login');
    }
    throw new ApiError(401, 'Unauthorized');
  }

  if (!res.ok) {
    let errBody: unknown = null;
    try {
      errBody = await res.json();
    } catch {
      errBody = await res.text().catch(() => null);
    }
    const msg = formatApiError(res.status, errBody);
    throw new ApiError(res.status, msg, errBody);
  }

  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return null as T;

  const contentType = res.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

export const api = {
  get: <T>(path: string, opts?: ApiRequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts?: ApiRequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, opts?: ApiRequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'PATCH', body }),
  del: <T>(path: string, opts?: ApiRequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'DELETE' }),
};
