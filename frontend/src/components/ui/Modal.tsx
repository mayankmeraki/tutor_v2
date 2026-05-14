import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from './cn';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children?: ReactNode;
  width?: string;
  className?: string;
  closeOnBackdrop?: boolean;
}

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export function Modal({
  open,
  onClose,
  title,
  children,
  width = '480px',
  className,
  closeOnBackdrop = true,
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const lastFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocusRef.current = document.activeElement as HTMLElement | null;

    // Lock body scroll while open.
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === 'Tab' && dialogRef.current) {
        const items = Array.from(
          dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE),
        ).filter((el) => !el.hasAttribute('disabled') && el.offsetParent !== null);
        if (items.length === 0) return;
        const first = items[0];
        const last = items[items.length - 1];
        const active = document.activeElement;
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);

    // Move focus inside the dialog.
    requestAnimationFrame(() => {
      const items = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (items && items.length > 0) {
        items[0].focus();
      } else {
        dialogRef.current?.focus();
      }
    });

    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      lastFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-sc-fade-in"
      onClick={() => closeOnBackdrop && onClose()}
      role="presentation"
    >
      <div
        ref={dialogRef}
        className={cn(
          'bg-bg-elevated border border-border rounded-[12px] shadow-2xl max-h-[90vh] overflow-auto outline-none',
          className,
        )}
        style={{ width }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        tabIndex={-1}
      >
        {title && (
          <div className="px-5 pt-4 pb-3 border-b border-border flex items-center justify-between">
            <h3 className="text-lg font-semibold">{title}</h3>
            <button
              type="button"
              onClick={onClose}
              className="text-text-muted hover:text-text text-xl leading-none w-7 h-7 flex items-center justify-center rounded hover:bg-bg-hover"
              aria-label="Close"
            >
              ×
            </button>
          </div>
        )}
        <div className="p-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
