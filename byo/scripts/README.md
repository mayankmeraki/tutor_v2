# BYO operational scripts

## 1. Atlas indexes

Index definitions live in `byo/processing/_atlas_indexes.json`
(`byo_segments_vector` for vector search + `byo_segments_text` for `$search`).
The default database name baked into the file is `capacity` — matching
`backend/app/core/mongodb.py`. Override with `--database`.

Apply via the Atlas Admin API:

```bash
export ATLAS_PUBLIC_KEY=...
export ATLAS_PRIVATE_KEY=...
export ATLAS_PROJECT_ID=...          # groupId
export ATLAS_CLUSTER_NAME=...
python -m byo.scripts.apply_atlas_indexes
```

No credentials? Run with `--print-only` (or just run without the env vars) —
the script prints the JSON and step-by-step UI instructions. Paste each
`definition` block into Atlas UI -> Atlas Search -> Create Search Index ->
JSON Editor, pick the right database + collection, and name the index to
match the JSON key (e.g. `byo_segments_vector`).

## 2. Backfill legacy chunks into parent+segment shape

```bash
# Preview first
python -m byo.scripts.backfill_segments --dry-run

# Migrate everything
python -m byo.scripts.backfill_segments

# Narrow to one resource
python -m byo.scripts.backfill_segments --resource-id <rid>

# Tune concurrency (default 5)
python -m byo.scripts.backfill_segments --batch-size 10
```

Idempotent: a legacy chunk is anything in `byo_chunks` missing `level` OR
still carrying an inline `embedding`. Already-migrated parents are skipped.
The script writes the new parents + segments FIRST, then deletes the legacy
doc only after the write succeeds — so a crash mid-migration never loses
data (it just leaves more work for the next run).

### Resource has no matching file?

If a resource_id can't be found in `byo_resources`, the script falls back
to the legacy chunk's own `user_id` (or empty string). If extraction
content is empty, the chunk is logged as `skipped_empty` and left alone;
mark its resource as `status=error` manually in `byo_resources` and
re-upload the source file.
