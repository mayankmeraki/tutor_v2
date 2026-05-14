import { useAuthStore } from '@/stores/auth';

export interface StreamingPostOptions<T = unknown> {
  url: string;
  body: unknown;
  signal?: AbortSignal;
  onEvent?: (event: { event?: string; data: T }, raw: string) => void;
  onError?: (err: Error) => void;
  onComplete?: () => void;
  parseJson?: boolean;
  headers?: Record<string, string>;
}

/**
 * Stream a server-sent-events response from a POST. The backend returns
 * `StreamingResponse(media_type="text/event-stream")` for paths/plan and
 * paths/{id}/refine, so we manually parse the SSE wire format chunk-by-chunk.
 */
export async function streamingPost<T = unknown>(
  options: StreamingPostOptions<T>,
): Promise<void> {
  const {
    url,
    body,
    signal,
    onEvent,
    onError,
    onComplete,
    parseJson = true,
    headers = {},
  } = options;

  const token = useAuthStore.getState().token;
  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
    ...headers,
  };
  if (token) finalHeaders.Authorization = `Bearer ${token}`;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: finalHeaders,
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) {
      const txt = await res.text().catch(() => '');
      throw new Error(`Stream failed (${res.status}): ${txt.slice(0, 200)}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIdx: number;
      while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
        const chunk = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        if (!chunk.trim()) continue;

        let evt: string | undefined;
        const dataLines: string[] = [];
        for (const line of chunk.split('\n')) {
          if (line.startsWith('event:')) {
            evt = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim());
          }
        }
        const dataStr = dataLines.join('\n');
        if (!dataStr) continue;
        let data: T = dataStr as T;
        if (parseJson) {
          try {
            data = JSON.parse(dataStr) as T;
          } catch {
            data = dataStr as T;
          }
        }
        onEvent?.({ event: evt, data }, dataStr);
      }
    }
    onComplete?.();
  } catch (err) {
    if ((err as Error).name === 'AbortError') return;
    onError?.(err as Error);
  }
}
