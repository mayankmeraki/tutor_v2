import { useState, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, TextArea } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs } from '@/components/ui/Tabs';
import { byoApi, type ByoCollection } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';

export function ByoPage() {
  const [active, setActive] = useState<ByoCollection | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const qc = useQueryClient();
  const { toast } = useToast();
  const list = useQuery({
    queryKey: ['byo', 'collections'],
    queryFn: () => byoApi.listCollections(),
  });
  const create = useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      byoApi.createCollection(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['byo', 'collections'] });
      setCreateOpen(false);
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });
  const removeCol = useMutation({
    mutationFn: (id: string) => byoApi.removeCollection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['byo', 'collections'] }),
  });

  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  if (active) {
    return (
      <AppShell>
        <div className="app-screen max-w-[1080px] mx-auto px-6 pt-8 pb-16">
          <button
            type="button"
            onClick={() => setActive(null)}
            className="text-xs text-text-muted hover:text-text mb-4"
          >
            ← All collections
          </button>
          <CollectionDetail collection={active} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="app-screen max-w-[1080px] mx-auto px-6 pt-8 pb-16">
        <div className="flex items-center justify-between mb-1">
          <h1 className="text-[28px] font-extrabold tracking-[-0.5px]">
            My Materials
          </h1>
          <Button variant="accent" onClick={() => setCreateOpen(true)}>
            New collection
          </Button>
        </div>
        <p className="text-sm text-text-muted mb-6">
          Group your study materials into collections.
        </p>
        {list.isLoading ? (
          <div className="flex items-center gap-2 text-text-muted">
            <Spinner /> Loading...
          </div>
        ) : !list.data || list.data.length === 0 ? (
          <Card className="text-center py-10 text-text-muted">
            No collections yet. Click "New collection" to create one.
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {list.data.map((c) => (
              <Card key={c.collection_id} className="hover:border-border-active transition-colors">
                <div className="flex justify-between items-start mb-1.5">
                  <h3
                    className="text-base font-semibold text-white truncate cursor-pointer flex-1"
                    onClick={() => setActive(c)}
                  >
                    {c.name}
                  </h3>
                  <button
                    type="button"
                    className="text-text-dim hover:text-bad text-xs"
                    onClick={() => {
                      if (confirm(`Delete collection "${c.name}"?`)) {
                        removeCol.mutate(c.collection_id);
                      }
                    }}
                  >
                    ✕
                  </button>
                </div>
                <p className="text-xs text-text-muted">
                  {c.resource_count ?? 0} resources
                </p>
                {c.description && (
                  <p className="text-xs text-text-dim mt-2 line-clamp-2">{c.description}</p>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New collection"
      >
        <div className="flex flex-col gap-3">
          <label>
            <span className="text-xs text-text-muted block mb-1">Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            <span className="text-xs text-text-muted block mb-1">Description</span>
            <TextArea
              rows={3}
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
            />
          </label>
          <Button
            variant="accent"
            loading={create.isPending}
            onClick={() => create.mutate({ name, description: desc || undefined })}
          >
            Create
          </Button>
        </div>
      </Modal>
    </AppShell>
  );
}

function CollectionDetail({ collection }: { collection: ByoCollection }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState('');
  const [textInput, setTextInput] = useState('');

  const detailQ = useQuery({
    queryKey: ['byo', 'collection', collection.collection_id],
    queryFn: () => byoApi.getCollection(collection.collection_id),
  });

  const upload = useMutation({
    mutationFn: async (kind: { type: 'file'; file: File } | { type: 'url'; url: string } | { type: 'text'; text: string }) => {
      if (kind.type === 'file') return byoApi.addResourceFile(collection.collection_id, kind.file);
      if (kind.type === 'url') return byoApi.addResourceUrl(collection.collection_id, kind.url);
      return byoApi.addResourceText(collection.collection_id, kind.text);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['byo', 'collection', collection.collection_id] });
      qc.invalidateQueries({ queryKey: ['byo', 'collections'] });
      setUrl('');
      setTextInput('');
      if (fileRef.current) fileRef.current.value = '';
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  const remove = useMutation({
    mutationFn: (resourceId: string) =>
      byoApi.removeResource(collection.collection_id, resourceId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['byo', 'collection', collection.collection_id] }),
  });

  const retry = useMutation({
    mutationFn: (resourceId: string) =>
      byoApi.retryResource(collection.collection_id, resourceId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['byo', 'collection', collection.collection_id] }),
  });

  return (
    <>
      <h2 className="text-2xl font-bold mb-2">{collection.name}</h2>
      {collection.description && (
        <p className="text-sm text-text-muted mb-5">{collection.description}</p>
      )}

      <Tabs
        tabs={[
          {
            id: 'file',
            label: 'Upload file',
            content: (
              <div className="flex gap-2 items-center">
                <input
                  ref={fileRef}
                  type="file"
                  className="text-sm"
                  multiple={false}
                  accept="application/pdf,image/*,audio/*,video/*,.txt,.md"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) upload.mutate({ type: 'file', file: f });
                  }}
                />
                {upload.isPending && <Spinner />}
              </div>
            ),
          },
          {
            id: 'url',
            label: 'Add URL',
            content: (
              <div className="flex gap-2 max-w-[640px]">
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://youtube.com/..."
                />
                <Button
                  variant="accent"
                  loading={upload.isPending}
                  onClick={() => url.trim() && upload.mutate({ type: 'url', url })}
                >
                  Add
                </Button>
              </div>
            ),
          },
          {
            id: 'text',
            label: 'Paste text',
            content: (
              <div className="flex flex-col gap-2 max-w-[640px]">
                <TextArea
                  rows={5}
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Paste notes, transcript, anything..."
                />
                <Button
                  variant="accent"
                  loading={upload.isPending}
                  onClick={() =>
                    textInput.trim() && upload.mutate({ type: 'text', text: textInput })
                  }
                  className="self-start"
                >
                  Add text
                </Button>
              </div>
            ),
          },
        ]}
      />

      <h3 className="text-sm font-semibold mt-7 mb-3">Resources</h3>
      {detailQ.isLoading ? (
        <Spinner />
      ) : !detailQ.data?.resources || detailQ.data.resources.length === 0 ? (
        <p className="text-text-muted text-sm">No resources yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {detailQ.data.resources.map((r) => (
            <Card key={r.resource_id} className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  {r.filename ?? r.url ?? r.resource_id}
                </div>
                <div className="text-xs text-text-dim">
                  {r.kind} · {r.status ?? 'unknown'}
                </div>
              </div>
              {r.status === 'failed' && (
                <Button size="sm" variant="ghost" onClick={() => retry.mutate(r.resource_id)}>
                  Retry
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => remove.mutate(r.resource_id)}>
                Delete
              </Button>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
