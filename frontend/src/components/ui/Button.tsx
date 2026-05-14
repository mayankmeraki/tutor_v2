import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from './cn';

type Variant = 'primary' | 'accent' | 'ghost' | 'outline' | 'danger';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-text text-bg hover:bg-white border border-transparent',
  accent:
    'bg-accent text-bg hover:bg-accent-bright border border-transparent font-semibold',
  ghost:
    'bg-transparent text-text hover:bg-bg-hover border border-transparent',
  outline:
    'bg-transparent text-text hover:bg-bg-hover border border-border hover:border-border-active',
  danger:
    'bg-bad text-bg hover:opacity-90 border border-transparent',
};

const sizeClasses: Record<Size, string> = {
  sm: 'h-8 px-3 text-sm rounded-[8px]',
  md: 'h-10 px-4 text-sm rounded-[8px]',
  lg: 'h-12 px-6 text-base rounded-[10px]',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'outline', size = 'md', loading, disabled, className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 transition-colors duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed select-none',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...rest}
    >
      {loading && (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      )}
      {children}
    </button>
  );
});
