import type { ReactNode } from 'react';
import { TopNav } from './TopNav';

interface Props {
  children: ReactNode;
  showNav?: boolean;
}

export function AppShell({ children, showNav = true }: Props) {
  return (
    <div className="flex flex-col h-full">
      {showNav && <TopNav />}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
