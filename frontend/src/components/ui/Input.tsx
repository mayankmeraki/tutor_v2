import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { cn } from './cn';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        'w-full h-10 px-3 bg-bg-surface border rounded-[8px] text-text placeholder:text-text-dim outline-none transition-colors',
        invalid ? 'border-bad' : 'border-border focus:border-border-active',
        className,
      )}
      {...rest}
    />
  );
});

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { className, invalid, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      className={cn(
        'w-full px-3 py-2 bg-bg-surface border rounded-[8px] text-text placeholder:text-text-dim outline-none transition-colors resize-none',
        invalid ? 'border-bad' : 'border-border focus:border-border-active',
        className,
      )}
      {...rest}
    />
  );
});
