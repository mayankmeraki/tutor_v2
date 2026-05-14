import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Input, TextArea } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { artifactsApi, type Artifact, type SrRating } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { cn } from '@/components/ui/cn';

const RATINGS: { id: SrRating; label: string; help: string; color: string }[] = [
  { id: 'again', label: 'Again', help: 'Forgot completely', color: 'text-bad' },
  { id: 'hard', label: 'Hard', help: 'Took effort', color: 'text-warn' },
  { id: 'good', label: 'Good', help: 'Got it', color: 'text-good' },
  { id: 'easy', label: 'Easy', help: 'Trivial', color: 'text-accent' },
];

export function ArtifactsPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [active, setActive] = useState<Artifact | null>(null);
  const [search, setSearch] = useState('');
  const [showDueOnly, setShowDueOnly] = useState(false);

  const list = useQuery({
    queryKey: ['artifacts'],
    queryFn: () => artifactsApi.list(),
  });

  const remove = useMutation({
    mutationFn: (id: string) => artifactsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['artifacts'] });
      toast('Artifact deleted', 'success');
    },
    onError: (err) => toast((err as Error).message, 'error'),
  });

  const review = useMutation({
    mutationFn: ({ id, rating }: { id: string; rating: SrRating }) =>
      artifactsApi.spacedRepetition(id, { rating }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['artifacts'] });
      setActive(null);
      toast('Review recorded', 'success');
    },
    onError: (err) => toast((err as Error).message, 'error'),
  });

  const filtered = useMemo(() => {
    let items = list.data ?? [];
    if (showDueOnly) {
      const now = Date.now();
      items = items.filter((a) => {
        const due = a.sr?.nextReviewAt ? Date.parse(a.sr.nextReviewAt) : 0;
        return due && due <= now;
      });
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(
        (a) =>
          (a.title ?? '').toLowerCase().includes(q) ||
          (a.preview ?? '').toLowerCase().includes(q) ||
          (a.tags ?? []).some((t) => t.toLowerCase().includes(q)),
      );
    }
    return items;
  }, [list.data, search, showDueOnly]);

  return (
    <AppShell>
      <div className="app-screen max-w-[1080px] mx-auto px-6 pt-8 pb-16">
        <h1 className="text-[28px] font-extrabold tracking-[-0.5px] mb-1">
          Knowledge artifacts
        </h1>
        <p className="text-sm text-text-muted mb-6">
          Saved snippets, summaries, and notes — review them via spaced repetition.
        </p>
        <div className="flex flex-wrap items-center gap-3 mb-5">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search artifacts..."
            className="max-w-[360px]"
            data-testid="artifacts-search"
          />
          <button
            type="button"
            onClick={() => setShowDueOnly((v) => !v)}
            className={cn(
              'text-xs px-3 py-1.5 rounded-full border transition-colors',
              showDueOnly
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-muted hover:text-text',
            )}
            data-testid="artifacts-due-toggle"
          >
            Due today only
          </button>
          <span className="text-xs text-text-dim ml-auto" data-testid="artifacts-count">
            {filtered.length} of {list.data?.length ?? 0}
          </span>
        </div>
        {list.isLoading ? (
          <div className="flex items-center gap-2 text-text-muted">
            <Spinner /> Loading...
          </div>
        ) : !list.data || list.data.length === 0 ? (
          <Card className="text-center py-10 text-text-muted">No artifacts yet.</Card>
        ) : filtered.length === 0 ? (
          <Card className="text-center py-10 text-text-muted">
            No artifacts match your filter.
          </Card>
        ) : (
          <div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
            data-testid="artifacts-grid"
          >
            {filtered.map((a) => (
              <Card
                key={a.artifactId}
                className="hover:border-border-active transition-colors"
                data-testid="artifact-card"
              >
                <div className="flex justify-between items-start mb-1.5 gap-2">
                  <h3
                    className="text-base font-semibold text-white cursor-pointer flex-1 min-w-0 break-words"
                    onClick={() => setActive(a)}
                  >
                    {a.title ?? 'Untitled artifact'}
                  </h3>
                  <button
                    type="button"
                    className="text-text-dim hover:text-bad text-xs flex-shrink-0"
                    onClick={() => {
                      if (confirm(`Delete "${a.title ?? 'artifact'}"?`)) {
                        remove.mutate(a.artifactId);
                      }
                    }}
                    data-testid="artifact-delete"
                  >
                    ✕
                  </button>
                </div>
                {a.type && (
                  <span className="text-[10px] text-text-dim uppercase tracking-wider mb-1 inline-block">
                    {a.type}
                  </span>
                )}
                {a.preview && (
                  <p className="text-xs text-text-muted line-clamp-2 mb-2">
                    {a.preview}
                  </p>
                )}
                {a.tags && a.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {a.tags.slice(0, 3).map((t) => (
                      <span
                        key={t}
                        className="text-[10px] text-text-muted bg-bg-hover rounded-full px-2 py-0.5"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}
                {a.sr_stats?.due_now && a.sr_stats.due_now > 0 && (
                  <div className="text-xs text-warn">
                    {a.sr_stats.due_now} card{a.sr_stats.due_now > 1 ? 's' : ''} due
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={!!active}
        onClose={() => setActive(null)}
        title={active?.title ?? 'Artifact'}
        width="640px"
      >
        {active && (
          <ArtifactDetail
            artifact={active}
            onReview={(rating) =>
              review.mutate({ id: active.artifactId, rating })
            }
          />
        )}
      </Modal>
    </AppShell>
  );
}

function ArtifactDetail({
  artifact,
  onReview,
}: {
  artifact: Artifact;
  onReview: (rating: SrRating) => void;
}) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(artifact.title ?? '');
  const [content, setContent] = useState(artifact.content ?? '');
  const [tags, setTags] = useState((artifact.tags ?? []).join(', '));

  const patch = useMutation({
    mutationFn: () =>
      artifactsApi.patch(artifact.artifactId, {
        title,
        content,
        tags: tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['artifacts'] });
      setEditing(false);
      toast('Saved', 'success');
    },
    onError: (err) => toast((err as Error).message, 'error'),
  });

  if (editing) {
    return (
      <div className="flex flex-col gap-3">
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          data-testid="artifact-edit-title"
        />
        <TextArea
          rows={10}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          data-testid="artifact-edit-content"
        />
        <Input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="Tags (comma-separated)"
          data-testid="artifact-edit-tags"
        />
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
          <Button
            variant="accent"
            onClick={() => patch.mutate()}
            loading={patch.isPending}
            data-testid="artifact-save"
          >
            Save
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        className="text-sm text-text-muted whitespace-pre-wrap mb-5 max-h-[40vh] overflow-y-auto"
        data-testid="artifact-content"
      >
        {artifact.content ?? artifact.preview ?? ''}
      </div>
      {artifact.tags && artifact.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {artifact.tags.map((t) => (
            <span
              key={t}
              className="text-[10px] text-text-muted bg-bg-hover rounded-full px-2 py-0.5"
            >
              {t}
            </span>
          ))}
        </div>
      )}
      <div className="flex justify-between items-center border-t border-border pt-4 gap-3 flex-wrap">
        <Button variant="ghost" onClick={() => setEditing(true)} data-testid="artifact-edit">
          Edit
        </Button>
        <div
          className="flex gap-1.5 items-center flex-wrap"
          data-testid="artifact-review-buttons"
        >
          <span className="text-xs text-text-muted mr-1">Review:</span>
          {RATINGS.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => onReview(r.id)}
              className={cn(
                'px-3 h-8 rounded-full border border-border text-xs hover:border-accent transition-colors',
                r.color,
              )}
              title={r.help}
              data-testid={`artifact-review-${r.id}`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
