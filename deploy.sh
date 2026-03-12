#!/bin/bash
# Secondus — Cloud Run Deployment Script
set -e

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-platinum-depot-489523-a7}"
REGION="us-central1"
SERVICE_NAME="secondus"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "=== Secondus Deployment ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo ""

# Build frontend
echo "Building frontend..."
(cd frontend && npm ci && npm run build)

# Copy frontend dist into backend so Docker context includes it
echo "Copying frontend build into backend..."
rm -rf backend/frontend-dist
cp -r frontend/dist backend/frontend-dist

# Ensure we're authenticated
echo "Checking authentication..."
gcloud auth print-access-token > /dev/null 2>&1 || {
    echo "Not authenticated. Running gcloud auth login..."
    gcloud auth login
}

gcloud config set project ${PROJECT_ID}

echo "Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    --quiet

echo "Building container..."
gcloud builds submit \
    --tag ${IMAGE_NAME} \
    --timeout=600s \
    ./backend

echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}"

SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

# Cleanup
rm -rf backend/frontend-dist

echo ""
echo "=== Deployment Complete ==="
echo "Service URL: ${SERVICE_URL}"
echo "Test with: curl ${SERVICE_URL}/health"
