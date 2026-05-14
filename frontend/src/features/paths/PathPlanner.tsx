import { useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, TextArea } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { streamingPost } from '@/lib/sse/streamingPost';
import { useToast } from '@/components/ui/Toast';

interface Props {
  onCreated: (pathId: string) => void;
}

interface PlanEvent {
  type?: string;
  message?: string;
  text?: string;
  pathId?: string;
  path?: { pathId?: string };
  tool?: string;
  step?: string;
  done?: boolean;
}

export function PathPlanner({ onCreated }: Props) {
  const { toast } = useToast();
  const [intent, setIntent] = useState('');
  const [goal, setGoal] = useState('');
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<PlanEvent[]>([]);
  const [agentText, setAgentText] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  // Cancel any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  const start = async () => {
    if (!intent.trim()) {
      toast('Tell us what you want to learn first.', 'warning');
      return;
    }
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setRunning(true);
    setEvents([]);
    setAgentText('');
    let createdPathId: string | null = null;

    await streamingPost<PlanEvent>({
      url: '/api/v1/paths/plan',
      body: { intent, goal },
      signal: abortRef.current.signal,
      onEvent: ({ data }) => {
        // `agent_text` events carry incremental tokens — accumulate separately.
        if (data.type === 'agent_text') {
          setAgentText((prev) => prev + (data.text ?? ''));
          return;
        }
        if (data.type === 'path_ready') {
          createdPathId = data.path?.pathId ?? data.pathId ?? createdPathId;
        }
        if (data.pathId && !createdPathId) createdPathId = data.pathId;
        setEvents((prev) => [...prev, data]);
      },
      onError: (err) => toast(err.message, 'error'),
      onComplete: () => {
        setRunning(false);
        if (createdPathId) onCreated(createdPathId);
      },
    });
  };

  const cancel = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <Card>
        <h3 className="text-base font-semibold mb-3">Plan a learning path</h3>
        <label className="block mb-3">
          <span className="text-xs text-text-muted block mb-1">Intent</span>
          <Input
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder="What do you want to learn?"
            data-testid="path-planner-intent"
          />
        </label>
        <label className="block mb-4">
          <span className="text-xs text-text-muted block mb-1">Goal (optional)</span>
          <TextArea
            rows={3}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="By when? Why?"
            data-testid="path-planner-goal"
          />
        </label>
        <div className="flex gap-2">
          <Button
            variant="accent"
            loading={running}
            onClick={start}
            className="flex-1"
            data-testid="path-planner-start"
          >
            {running ? 'Planning...' : 'Plan path'}
          </Button>
          {running && (
            <Button variant="ghost" onClick={cancel}>
              Cancel
            </Button>
          )}
        </div>
      </Card>
      <Card>
        <h3 className="text-base font-semibold mb-2">Stream</h3>
        {!running && events.length === 0 && !agentText && (
          <p className="text-xs text-text-muted">
            Plan a path on the left — steps will appear here as the planner streams.
          </p>
        )}
        {running && events.length === 0 && !agentText && (
          <div className="flex items-center gap-2 text-text-muted text-sm">
            <Spinner /> Thinking...
          </div>
        )}
        <div
          className="space-y-2 max-h-[400px] overflow-y-auto"
          data-testid="path-planner-events"
        >
          {events.map((e, i) => (
            <div
              key={i}
              className="text-xs text-text-muted border-l-2 border-border pl-2"
            >
              {e.type === 'status' && (
                <>
                  <strong className="text-accent">status: </strong>
                  {e.message ?? ''}
                </>
              )}
              {e.type === 'tool_call' && (
                <>
                  <strong className="text-warn">→ </strong>
                  {e.message ?? e.tool ?? 'tool'}
                </>
              )}
              {e.type === 'tool_result' && (
                <>
                  <strong className="text-good">✓ </strong>
                  {e.message ?? e.tool ?? 'done'}
                </>
              )}
              {e.type === 'path_ready' && (
                <>
                  <strong className="text-good">Path ready</strong>
                  {e.path?.pathId ? `: ${String(e.path.pathId)}` : ''}
                </>
              )}
              {e.type === 'stream_reset' && (
                <span className="text-text-dim italic">Restarting…</span>
              )}
            </div>
          ))}
          {agentText && (
            <div className="text-xs text-text whitespace-pre-wrap mt-2 pt-2 border-t border-border">
              {agentText}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
