import { useCallback, useEffect, useRef, useState } from 'react';
import { scribeApi } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

export interface UseScribeStreamOptions {
  enabled?: boolean;
  onPartial?: (text: string) => void;
  onFinal?: (text: string) => void;
}

interface ScribeStream {
  start: () => Promise<void>;
  stop: () => void;
  isRecording: boolean;
  error: Error | null;
  liveText: string;
}

export function useScribeStream(options: UseScribeStreamOptions = {}): ScribeStream {
  const { onPartial, onFinal } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [liveText, setLiveText] = useState('');

  const handlersRef = useRef({ onPartial, onFinal });
  handlersRef.current = { onPartial, onFinal };

  const stop = useCallback(() => {
    try {
      mediaRef.current?.stop();
    } catch {
      /* ignore */
    }
    mediaRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    wsRef.current = null;
    setIsRecording(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const tokenResp = await scribeApi.getRealtimeToken().catch(() => null);
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const jwt = useAuthStore.getState().token ?? '';
      const url = `${proto}://${window.location.host}/ws/scribe?token=${encodeURIComponent(jwt)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.text || data.transcript) {
            const text = data.text ?? data.transcript;
            setLiveText(text);
            if (data.is_final || data.final) {
              handlersRef.current.onFinal?.(text);
              setLiveText('');
            } else {
              handlersRef.current.onPartial?.(text);
            }
          }
        } catch {
          /* ignore */
        }
      };
      ws.onerror = () => setError(new Error('Scribe connection error'));
      ws.onclose = () => {
        setIsRecording(false);
      };

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      recorder.ondataavailable = (e) => {
        if (e.data.size && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };
      recorder.start(250);
      mediaRef.current = recorder;

      if (tokenResp?.token && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'INIT', token: tokenResp.token }));
      }
      setIsRecording(true);
    } catch (err) {
      setError(err as Error);
      stop();
    }
  }, [stop]);

  useEffect(() => () => stop(), [stop]);

  return { start, stop, isRecording, error, liveText };
}
