import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { TopNav } from '@/components/layout/TopNav';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { dsaApi } from '@/lib/api';
import { SdCanvas, type SdCanvasHandle } from '@/features/sd-canvas/SdCanvas';

export function SDProblemPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const canvasRef = useRef<SdCanvasHandle>(null);

  const problemQ = useQuery({
    queryKey: ['sd', 'problem', slug],
    queryFn: () => dsaApi.sdProblem(slug!),
    enabled: !!slug,
  });

  useEffect(() => {
    if (!problemQ.data || !canvasRef.current) return;
    // Reset canvas when navigating between problems.
    canvasRef.current.clear();
  }, [problemQ.data?.slug]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-full">
      <TopNav />
      <div className="flex flex-1 min-h-0">
        <aside className="w-[380px] shrink-0 overflow-y-auto border-r border-border bg-bg-surface p-5">
          <button
            type="button"
            onClick={() => navigate('/dsa')}
            className="text-xs text-text-muted hover:text-text mb-3"
          >
            ← All problems
          </button>
          {problemQ.isLoading ? (
            <div className="flex items-center gap-2 text-text-muted">
              <Spinner /> Loading...
            </div>
          ) : problemQ.data ? (
            <>
              <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-bg-hover text-accent inline-block mb-2">
                {problemQ.data.type === 'lld' ? 'LLD' : 'HLD'}
              </span>
              <h1 className="text-lg font-bold mb-2">{problemQ.data.name}</h1>
              {problemQ.data.description && (
                <div className="text-sm text-text-muted leading-relaxed whitespace-pre-wrap mb-4">
                  {problemQ.data.description}
                </div>
              )}
              <Button
                variant="accent"
                className="w-full"
                onClick={() =>
                  navigate(
                    `/tutor?q=${encodeURIComponent('Help me design: ' + problemQ.data!.name)}`,
                  )
                }
              >
                Ask the tutor
              </Button>
            </>
          ) : (
            <p className="text-text-muted">Problem not found.</p>
          )}
        </aside>
        <div className="flex-1 min-w-0">
          <SdCanvas ref={canvasRef} />
        </div>
      </div>
    </div>
  );
}
