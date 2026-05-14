import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { pathsApi } from '@/lib/api';
import { PathPlanner } from '@/features/paths/PathPlanner';
import { PathDetail } from '@/features/paths/PathDetail';

export function PathsPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const list = useQuery({
    queryKey: ['paths'],
    queryFn: () => pathsApi.list(),
  });

  if (activeId) {
    return (
      <AppShell>
        <div className="app-screen max-w-[1080px] mx-auto px-6 pt-8 pb-16">
          <PathDetail pathId={activeId} onBack={() => setActiveId(null)} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="app-screen max-w-[1080px] mx-auto px-6 pt-8 pb-16">
        <h1 className="text-[28px] font-extrabold tracking-[-0.5px] mb-1">
          Learning Paths
        </h1>
        <p className="text-sm text-text-muted mb-6">
          Multi-step paths to master a topic — each step is a tutor session.
        </p>
        <div className="mb-8">
          <PathPlanner
            onCreated={(id) => {
              setActiveId(id);
              qc.invalidateQueries({ queryKey: ['paths'] });
            }}
          />
        </div>
        <h2 className="text-base font-semibold mb-3">Your paths</h2>
        {list.isLoading ? (
          <div className="flex items-center gap-2 text-text-muted">
            <Spinner /> Loading...
          </div>
        ) : !list.data || list.data.length === 0 ? (
          <Card className="text-center py-10 text-text-muted">No paths yet.</Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {list.data.map((p) => (
              <Card
                key={p.pathId}
                className="cursor-pointer hover:border-border-active transition-colors"
                onClick={() => setActiveId(p.pathId)}
              >
                <div className="text-xs text-text-dim mb-1">
                  {p.status ?? 'in_progress'}
                </div>
                <h3 className="text-base font-semibold text-white">
                  {p.title ?? p.intent ?? 'Untitled path'}
                </h3>
                <p className="text-xs text-text-muted mt-1">
                  {p.nodes?.length ?? 0} steps
                </p>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
