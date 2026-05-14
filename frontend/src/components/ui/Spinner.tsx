import { cn } from './cn';

interface SpinnerProps {
  size?: number;
  className?: string;
}

export function Spinner({ size = 20, className }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        'inline-block border-2 border-current border-t-transparent rounded-full animate-spin',
        className,
      )}
      style={{ width: size, height: size }}
    />
  );
}
