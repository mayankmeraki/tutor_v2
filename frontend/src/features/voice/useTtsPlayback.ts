import { useCallback, useRef, useState } from 'react';
import { tutorApi } from '@/lib/api';

export function useTtsPlayback() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [playing, setPlaying] = useState(false);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    audioRef.current?.pause();
    audioRef.current?.removeAttribute('src');
    audioRef.current?.load();
    audioRef.current = null;
    setPlaying(false);
  }, []);

  const play = useCallback(
    async (text: string, voice?: string) => {
      stop();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        const res = (await tutorApi.ttsStream(
          { text, voice },
          ctrl.signal,
        )) as unknown as Response;
        if (!res.body) throw new Error('No audio stream');
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => {
          URL.revokeObjectURL(url);
          setPlaying(false);
        };
        audio.onerror = () => setPlaying(false);
        await audio.play();
        setPlaying(true);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        setPlaying(false);
      }
    },
    [stop],
  );

  return { play, stop, playing };
}
