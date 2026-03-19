#!/usr/bin/env bash
set -euo pipefail

# ─── Deploy tutor-v2-stage to Cloud Run via Cloud Build ──────────
#
# Usage:
#   ./deploy.sh          # deploy current working tree
#   ./deploy.sh --tag v1 # deploy with custom tag (default: git short SHA)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PROJECT_ID="capacity-platform-dev"
SERVICE="tutor-v2-stage"
REGION="us-central1"

# Resolve tag
TAG="${1:-}"
if [[ "$TAG" == "--tag" ]]; then
  TAG="${2:?'Missing tag value after --tag'}"
elif [[ -z "$TAG" ]]; then
  TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d-%H%M%S)"
fi

echo ""
echo "  Deploying $SERVICE"
echo "  ─────────────────────────────"
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Tag:      $TAG"
echo ""

# Submit build to Cloud Build
gcloud builds submit \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions=SHORT_SHA="$TAG" \
  --region="$REGION" \
  .

echo ""
echo "  Deployed successfully!"
SERVICE_URL=$(gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "https://$SERVICE.$REGION.run.app")
echo "  Service URL: $SERVICE_URL"
echo ""
