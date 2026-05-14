import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { pathsApi, type PathDoc, type PathNode } from '@/lib/api';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, TextArea } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { useToast } from '@/components/ui/Toast';
import { streamingPost } from '@/lib/sse/streamingPost';
import { cn } from '@/components/ui/cn';

interface Props {
  pathId: string;
  onBack: () => void;
}

export function PathDetail({ pathId, onBack }: Props) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { toast } = useToast();
  const refineAbort = useRef<AbortController | null>(null);
  const [refining, setRefining] = useState(false);
  const [refineEvents, setRefineEvents] = useState<string[]>([]);
  const [refineMessage, setRefineMessage] = useState('');
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState('');
  const [addingNode, setAddingNode] = useState(false);
  const [newNodeTitle, setNewNodeTitle] = useState('');

  const pathQ = useQuery({
    queryKey: ['path', pathId],
    queryFn: () => pathsApi.get(pathId),
  });

  // Cancel any in-flight refine stream when the component unmounts.
  useEffect(() => () => refineAbort.current?.abort(), []);

  const startNode = useMutation({
    mutationFn: (nodeId: string) => pathsApi.startNode(pathId, nodeId),
    onSuccess: (_, nodeId) => {
      // Backend returns `{ ok: true }`; navigate to /tutor with both ids so the
      // tutor page can pick up where the node left off and create a session.
      navigate(`/tutor?pathId=${pathId}&nodeId=${nodeId}`);
    },
    onError: (err) => toast((err as Error).message, 'error'),
  });

  const completeNode = useMutation({
    mutationFn: (nodeId: string) => pathsApi.completeNode(pathId, nodeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['path', pathId] }),
  });

  const skipNode = useMutation({
    mutationFn: (nodeId: string) => pathsApi.skipNode(pathId, nodeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['path', pathId] }),
  });

  const removeNode = useMutation({
    mutationFn: (nodeId: string) => pathsApi.removeNode(pathId, nodeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['path', pathId] }),
  });

  const noteNode = useMutation({
    mutationFn: ({ nodeId, note }: { nodeId: string; note: string }) =>
      pathsApi.noteNode(pathId, nodeId, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['path', pathId] });
      setEditingNoteId(null);
    },
  });

  const reorder = useMutation({
    mutationFn: (nodeIds: string[]) => pathsApi.reorderNodes(pathId, nodeIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['path', pathId] }),
  });

  const addNode = useMutation({
    mutationFn: (title: string) => pathsApi.addNode(pathId, { title }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['path', pathId] });
      setAddingNode(false);
      setNewNodeTitle('');
    },
  });

  const moveNode = (idx: number, dir: -1 | 1) => {
    const nodes = pathQ.data?.nodes ?? [];
    const target = idx + dir;
    if (target < 0 || target >= nodes.length) return;
    const order = nodes.map((n) => n.id);
    [order[idx], order[target]] = [order[target], order[idx]];
    reorder.mutate(order);
  };

  const refine = async () => {
    if (!refineMessage.trim()) {
      toast('Tell the planner what to change.', 'warning');
      return;
    }
    setRefining(true);
    setRefineEvents([]);
    refineAbort.current?.abort();
    refineAbort.current = new AbortController();
    await streamingPost<Record<string, unknown>>({
      url: `/api/v1/paths/${pathId}/refine`,
      body: { message: refineMessage },
      signal: refineAbort.current.signal,
      onEvent: ({ data }) => {
        const type = data.type as string | undefined;
        if (type === 'status') {
          setRefineEvents((prev) => [...prev, String(data.message ?? '')]);
        } else if (type === 'tool_call') {
          setRefineEvents((prev) => [
            ...prev,
            `→ ${String(data.message ?? data.tool ?? 'tool')}`,
          ]);
        } else if (type === 'agent_text') {
          setRefineEvents((prev) => {
            const last = prev[prev.length - 1] ?? '';
            return [...prev.slice(0, -1), last + String(data.text ?? '')];
          });
        } else if (type === 'artifact_refresh' || type === 'refine_ready') {
          qc.invalidateQueries({ queryKey: ['path', pathId] });
        }
      },
      onError: (err) => toast(err.message, 'error'),
      onComplete: () => qc.invalidateQueries({ queryKey: ['path', pathId] }),
    });
    setRefining(false);
    setRefineMessage('');
  };

  if (pathQ.isLoading) {
    return (
      <div className="flex items-center gap-2 text-text-muted">
        <Spinner /> Loading path...
      </div>
    );
  }
  const path: PathDoc | undefined = pathQ.data;
  if (!path) return <p className="text-text-muted">Path not found.</p>;

  return (
    <div className="max-w-[800px]">
      <button
        type="button"
        onClick={onBack}
        className="text-xs text-text-muted hover:text-text mb-4"
      >
        ← Back
      </button>
      <h2 className="text-2xl font-bold mb-1">{path.title ?? path.intent ?? 'Path'}</h2>
      <p className="text-sm text-text-muted mb-4">
        {path.status ?? 'in_progress'} · {path.nodes?.length ?? 0} steps
      </p>

      <div className="flex flex-col gap-3 mb-5" data-testid="path-nodes">
        {(path.nodes ?? []).map((n: PathNode, i: number) => (
          <Card
            key={n.id}
            className={cn(
              'flex items-start gap-3',
              n.status === 'completed' && 'opacity-60',
            )}
            data-testid="path-node"
          >
            <div className="flex flex-col items-center gap-1 flex-shrink-0">
              <div className="text-xs font-mono text-text-dim w-6 text-center pt-0.5">
                {String(i + 1).padStart(2, '0')}
              </div>
              <button
                type="button"
                onClick={() => moveNode(i, -1)}
                disabled={i === 0}
                className="text-text-dim hover:text-text disabled:opacity-30 text-xs"
                title="Move up"
                data-testid="path-node-up"
              >
                ▲
              </button>
              <button
                type="button"
                onClick={() => moveNode(i, 1)}
                disabled={i === (path.nodes?.length ?? 0) - 1}
                className="text-text-dim hover:text-text disabled:opacity-30 text-xs"
                title="Move down"
                data-testid="path-node-down"
              >
                ▼
              </button>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <h3 className="text-sm font-semibold truncate">{n.title ?? 'Untitled'}</h3>
                <span
                  className={cn(
                    'text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full',
                    n.status === 'completed' && 'bg-good/15 text-good',
                    n.status === 'active' && 'bg-warn/15 text-warn',
                    n.status === 'skipped' && 'bg-bg-hover text-text-dim',
                    (!n.status || n.status === 'pending') && 'bg-bg-hover text-text-muted',
                  )}
                  data-testid="path-node-status"
                >
                  {n.status ?? 'pending'}
                </span>
                {n.targetMin && (
                  <span className="text-[10px] text-text-dim">
                    {n.targetMin}m
                  </span>
                )}
              </div>
              {n.topics && n.topics.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1">
                  {n.topics.map((t) => (
                    <span
                      key={t}
                      className="text-[10px] text-text-muted bg-bg-hover rounded-full px-1.5 py-0.5"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
              {editingNoteId === n.id ? (
                <div className="flex flex-col gap-2 mt-2">
                  <TextArea
                    rows={2}
                    value={noteDraft}
                    onChange={(e) => setNoteDraft(e.target.value)}
                    data-testid="path-node-note-input"
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="accent"
                      onClick={() =>
                        noteNode.mutate({ nodeId: n.id, note: noteDraft })
                      }
                      loading={noteNode.isPending}
                    >
                      Save note
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingNoteId(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div
                  className="text-xs text-text-muted cursor-pointer hover:text-text"
                  onClick={() => {
                    setEditingNoteId(n.id);
                    setNoteDraft(n.studentNote ?? n.note ?? '');
                  }}
                  data-testid="path-node-note"
                >
                  {n.studentNote ?? n.note ?? (
                    <span className="text-text-dim italic">Add a note...</span>
                  )}
                </div>
              )}
            </div>
            <div className="flex flex-col gap-1.5 flex-shrink-0">
              {n.status !== 'completed' && (
                <Button
                  size="sm"
                  variant="accent"
                  onClick={() => startNode.mutate(n.id)}
                  loading={startNode.isPending}
                  data-testid="path-node-start"
                >
                  Start
                </Button>
              )}
              {n.status !== 'completed' && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => completeNode.mutate(n.id)}
                  data-testid="path-node-complete"
                >
                  Mark done
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                onClick={() => skipNode.mutate(n.id)}
                data-testid="path-node-skip"
              >
                Skip
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => removeNode.mutate(n.id)}
                data-testid="path-node-remove"
              >
                Remove
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {addingNode ? (
        <Card className="mb-5 flex gap-2">
          <Input
            value={newNodeTitle}
            onChange={(e) => setNewNodeTitle(e.target.value)}
            placeholder="New node title"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newNodeTitle.trim()) addNode.mutate(newNodeTitle);
            }}
            data-testid="path-add-node-input"
          />
          <Button
            variant="accent"
            onClick={() => addNode.mutate(newNodeTitle)}
            disabled={!newNodeTitle.trim()}
            loading={addNode.isPending}
          >
            Add
          </Button>
          <Button variant="ghost" onClick={() => setAddingNode(false)}>
            Cancel
          </Button>
        </Card>
      ) : (
        <Button
          variant="ghost"
          className="mb-5 w-full"
          onClick={() => setAddingNode(true)}
          data-testid="path-add-node"
        >
          + Add node
        </Button>
      )}

      <Card className="mb-5">
        <h3 className="text-sm font-semibold mb-2">Refine path</h3>
        <p className="text-xs text-text-muted mb-2">
          Tell the planner what to change — e.g. "shorter", "more practice on graphs",
          or "add a final review beat".
        </p>
        <div className="flex gap-2 mb-2">
          <Input
            value={refineMessage}
            onChange={(e) => setRefineMessage(e.target.value)}
            placeholder="What should change?"
            data-testid="path-refine-input"
          />
          <Button
            variant="outline"
            loading={refining}
            onClick={refine}
            data-testid="path-refine-btn"
          >
            Refine
          </Button>
        </div>
        {refineEvents.length > 0 && (
          <div
            className="border-l-2 border-border pl-3 mt-3 space-y-1"
            data-testid="path-refine-events"
          >
            {refineEvents.map((e, i) => (
              <div key={i} className="text-xs text-text-muted">
                {e}
              </div>
            ))}
          </div>
        )}
      </Card>

      {(path.pivots?.length ?? 0) > 0 && (
        <Card className="mb-5">
          <h3 className="text-sm font-semibold mb-2">Suggested pivots</h3>
          <div className="space-y-2">
            {path.pivots!.map((p, i) => (
              <div key={i} className="flex items-start justify-between gap-2 text-xs">
                <div className="flex-1">
                  <div className="text-text-muted">{String(p.reason ?? 'Alternative path')}</div>
                  {p.proposedNodes && p.proposedNodes.length > 0 && (
                    <div className="text-text-dim mt-1">
                      {p.proposedNodes.length} proposed nodes
                    </div>
                  )}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    pathsApi
                      .applyPivot(pathId, p.pivotIndex ?? i, p.proposedNodes ?? [])
                      .then(() =>
                        qc.invalidateQueries({ queryKey: ['path', pathId] }),
                      )
                      .catch((err) => toast((err as Error).message, 'error'))
                  }
                >
                  Apply
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
