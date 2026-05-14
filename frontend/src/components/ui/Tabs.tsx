import { useState, type ReactNode } from 'react';
import { cn } from './cn';

interface Tab {
  id: string;
  label: ReactNode;
  content: ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  defaultId?: string;
  className?: string;
  onChange?: (id: string) => void;
}

export function Tabs({ tabs, defaultId, className, onChange }: TabsProps) {
  const [active, setActive] = useState(defaultId ?? tabs[0]?.id);
  return (
    <div className={cn('flex flex-col', className)}>
      <div className="flex border-b border-border">
        {tabs.map((t) => {
          const on = t.id === active;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setActive(t.id);
                onChange?.(t.id);
              }}
              className={cn(
                'px-4 h-10 text-sm font-medium transition-colors border-b-2 -mb-px',
                on
                  ? 'border-accent text-text'
                  : 'border-transparent text-text-muted hover:text-text',
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div className="pt-4">
        {tabs.find((t) => t.id === active)?.content}
      </div>
    </div>
  );
}
