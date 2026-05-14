import { useState } from 'react';
import { cn } from '@/components/ui/cn';
import { useScribeStream } from './useScribeStream';

interface Props {
  onSubmit: (text: string) => void;
  onPartial?: (text: string) => void;
  /** Called when mic starts. Useful to interrupt tutor TTS on legacy parity. */
  onMicStart?: () => void;
  /** If true, auto-submit when scribe yields a final transcript. Legacy default: false. */
  autoSubmit?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function VoiceBar({
  onSubmit,
  onPartial,
  onMicStart,
  autoSubmit = false,
  disabled,
  placeholder = 'Ask anything...',
}: Props) {
  const [text, setText] = useState('');
  const scribe = useScribeStream({
    onPartial: (t) => {
      setText(t);
      onPartial?.(t);
    },
    onFinal: (t) => {
      // Legacy InlineMic: populate field but DO NOT auto-submit. Caller can opt in.
      setText(t);
      if (autoSubmit && t.trim()) {
        onSubmit(t.trim());
        setText('');
      }
    },
  });

  const submit = () => {
    if (!text.trim() || disabled) return;
    onSubmit(text.trim());
    setText('');
  };

  const toggleMic = () => {
    if (scribe.isRecording) scribe.stop();
    else {
      onMicStart?.();
      void scribe.start();
    }
  };

  return (
    <div className="flex items-center gap-2 border border-border rounded-[12px] bg-bg-elevated px-2 py-1.5">
      <button
        type="button"
        onClick={toggleMic}
        disabled={disabled}
        className={cn(
          'w-9 h-9 rounded-full flex items-center justify-center transition-colors',
          scribe.isRecording
            ? 'bg-bad/20 text-bad animate-pulse'
            : 'bg-bg-hover text-text-muted hover:text-text',
        )}
        title={scribe.isRecording ? 'Stop' : 'Start mic'}
      >
        {scribe.isRecording ? '■' : '🎙'}
      </button>
      <input
        className="flex-1 bg-transparent outline-none text-text placeholder:text-text-dim text-sm"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !text.trim()}
        className="bg-accent text-bg px-3 h-9 rounded-[8px] font-semibold disabled:opacity-40 text-sm"
      >
        Send
      </button>
    </div>
  );
}
