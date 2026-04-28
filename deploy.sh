#!/usr/bin/env bash
set -euo pipefail

# ─── Deploy MyProfessor services to Cloud Run via Cloud Build ──────
#
# Usage:
#   ./deploy.sh                    # deploy all services (backend + worker)
#   ./deploy.sh --tag v1           # deploy with custom tag
#   ./deploy.sh --backend-only     # deploy only the backend API
#   ./deploy.sh --worker-only      # deploy only the BYO worker
#
# Services:
#   myprofessor-stage        — Backend API + Frontend (Cloud Run)
#   myprofessor-byo-stage    — BYO Worker (Cloud Run)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PROJECT_ID="capacity-platform-dev"
REGION="us-central1"

# Parse args
TAG=""
DEPLOY_TARGET="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="${2:?'Missing tag value'}"; shift 2 ;;
    --backend-only) DEPLOY_TARGET="backend"; shift ;;
    --worker-only) DEPLOY_TARGET="worker"; shift ;;
    *) TAG="$1"; shift ;;
  esac
done

if [[ -z "$TAG" ]]; then
  TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d-%H%M%S)"
fi

echo ""
echo "  MyProfessor Deploy"
echo "  ─────────────────────────────"
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Tag:      $TAG"
echo "  Target:   $DEPLOY_TARGET"
echo ""

if [[ "$DEPLOY_TARGET" == "all" ]]; then
  # Full deploy — both services via cloudbuild.yaml
  gcloud builds submit \
    --project="$PROJECT_ID" \
    --config=cloudbuild.yaml \
    --substitutions=SHORT_SHA="$TAG" \
    --region="$REGION" \
    .
elif [[ "$DEPLOY_TARGET" == "backend" ]]; then
  # Backend only — build + deploy
  IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/myprofessor-stage:$TAG"
  echo "  Building backend image..."
  gcloud builds submit \
    --project="$PROJECT_ID" \
    --tag="$IMAGE" \
    --region="$REGION" \
    .
  echo "  Deploying to Cloud Run..."
  gcloud run deploy myprofessor-stage \
    --project="$PROJECT_ID" \
    --image="$IMAGE" \
    --region="$REGION" \
    --platform=managed
elif [[ "$DEPLOY_TARGET" == "worker" ]]; then
  # Worker only — build + deploy
  IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/myprofessor-byo-stage:$TAG"
  echo "  Building worker image..."
  docker build --target worker -t "$IMAGE" .
  docker push "$IMAGE"
  echo "  Deploying to Cloud Run..."
  gcloud run deploy myprofessor-byo-stage \
    --project="$PROJECT_ID" \
    --image="$IMAGE" \
    --region="$REGION" \
    --platform=managed
fi

echo ""
echo "  Deployed successfully!"

if [[ "$DEPLOY_TARGET" != "worker" ]]; then
  BACKEND_URL=$(gcloud run services describe myprofessor-stage --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "pending")
  echo "  Backend:  $BACKEND_URL"
fi
if [[ "$DEPLOY_TARGET" != "backend" ]]; then
  WORKER_URL=$(gcloud run services describe myprofessor-byo-stage --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "pending")
  echo "  Worker:   $WORKER_URL"
fi
echo ""
