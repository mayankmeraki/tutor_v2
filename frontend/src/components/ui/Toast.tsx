import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import { cn } from './cn';

type ToastKind = 'info' | 'success' | 'warning' | 'error';

interface ToastEntry {
  id: number;
  kind: ToastKind;
  message: ReactNode;
  durationMs: number;
}

interface ToastContextValue {
  toast: (msg: ReactNode, kind?: ToastKind, durationMs?: number) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: ReactNode, kind: ToastKind = 'info', durationMs = 4000) => {
      const id = ++idRef.current;
      setItems((prev) => {
        const next = [...prev, { id, kind, message, durationMs }];
        // Cap stacked toasts so a runaway error path doesn't fill the screen.
        return next.length > 5 ? next.slice(-5) : next;
      });
      if (durationMs > 0) {
        setTimeout(() => dismiss(id), durationMs);
      }
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div className="fixed bottom-4 right-4 z-[2000] flex flex-col gap-2 max-w-md">
          {items.map((t) => (
            <ToastItem key={t.id} entry={t} onClose={() => dismiss(t.id)} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

function ToastItem({ entry, onClose }: { entry: ToastEntry; onClose: () => void }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);
  const colors: Record<ToastKind, string> = {
    info: 'border-border bg-bg-elevated text-text',
    success: 'border-accent/60 bg-bg-elevated text-text',
    warning: 'border-warn/50 bg-bg-elevated text-text',
    error: 'border-bad/50 bg-bg-elevated text-text',
  };
  return (
    <div
      className={cn(
        'border rounded-[10px] px-4 py-3 shadow-lg transition-all duration-200 flex items-start gap-3',
        colors[entry.kind],
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2',
      )}
    >
      <span className="flex-1 text-sm">{entry.message}</span>
      <button
        type="button"
        onClick={onClose}
        className="text-text-muted hover:text-text leading-none"
      >
        ×
      </button>
    </div>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be inside ToastProvider');
  return ctx;
}
