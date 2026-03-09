#!/bin/bash
# Secondus — Cloud Run Deployment Script
# One-command deployment for the Gemini Live Agent Challenge

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-platinum-depot-489523-a7}"
REGION="us-central1"
SERVICE_NAME="secondus"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "=== Secondus Deployment ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo ""

# Ensure we're authenticated
echo "Checking authentication..."
gcloud auth print-access-token > /dev/null 2>&1 || {
    echo "Not authenticated. Running gcloud auth login..."
    gcloud auth login
}

# Set project
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    --quiet

# Build and push container
echo "Building container..."
gcloud builds submit \
    --tag ${IMAGE_NAME} \
    --timeout=600s \
    ./backend

# Deploy to Cloud Run
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

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

echo ""
echo "=== Deployment Complete ==="
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Test with: curl ${SERVICE_URL}/health"
