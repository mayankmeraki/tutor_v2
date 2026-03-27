#!/bin/bash
# Reindex search embeddings for courses and lessons
# Usage:
#   ./scripts/reindex.sh --course-id 2
#   ./scripts/reindex.sh --all
#   ./scripts/reindex.sh --all --force
#   ./scripts/reindex.sh --all --dry-run

cd "$(dirname "$0")/.."
python -m scripts.build_search_index "$@"
