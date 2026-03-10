# CLEF - Deployment Guide

This document describes the CI/CD pipeline and deployment process for the CLEF Fleet Management application.

## Overview

The application uses GitHub Actions for CI/CD with automatic deployment to Google Cloud Run.

### Pipeline Stages

1. **Pull Request**: Build frontend apps + Run backend tests
2. **Main Branch Merge**: Deploy to Cloud Run (dev environment)

## Architecture

- **Backend**: FastAPI application deployed to Cloud Run (`clef-api`)
- **Frontend**: Nginx serving Angular apps deployed to Cloud Run (`clef-frontend`)
- **Cache**: Google Cloud MemoryStore for Redis (`clef-cache`)
- **Container Registry**: Artifact Registry (`clef-images`)

## Prerequisites

### 1. GCP Project Setup

Create or use existing GCP projects:
- `rcq-fr-dev` (development)
- `rcq-fr-test` (testing)
- `rcq-fr-prod` (production)

### 2. Automated GCP Setup (Recommended)

We provide two options for automating the GCP infrastructure setup:

#### Option A: Bash Script (Interactive)

The bash script provides an interactive setup experience with prompts and confirmations:

```bash
cd backend
./scripts/setup_gcp.sh dev
```

This script will:
- ✅ Set the active GCP project
- ✅ Enable all required APIs (Sheets, Drive, Calendar, Gmail, Cloud Run, Artifact Registry, Redis, Secret Manager)
- ✅ Create the `clef-backend` service account
- ✅ Assign necessary IAM roles
- ✅ Generate a service account JSON key (with confirmation)
- ✅ Create Artifact Registry repository
- ✅ Optionally create Secret Manager secrets
- ✅ Generate a partial `.env.{env}` file with configuration

**Usage for different environments:**
```bash
./scripts/setup_gcp.sh dev   # For development
./scripts/setup_gcp.sh test  # For testing
./scripts/setup_gcp.sh prod  # For production
```

#### Option B: Terraform (Infrastructure as Code)

For teams preferring Infrastructure as Code:

```bash
cd infra

# Initialize Terraform
terraform init

# Preview changes
terraform plan -var="environment=dev"

# Apply configuration
terraform apply -var="environment=dev"
```

See [infra/README.md](infra/README.md) for detailed Terraform usage.

**Both options create the same infrastructure.** Choose based on your preference:
- **Bash script**: Simpler, interactive, good for one-time setup
- **Terraform**: Better for version control, reproducibility, and team collaboration

### 3. Manual Setup (Alternative)

If you prefer manual setup or need to troubleshoot, here are the individual commands:

#### Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  redis.googleapis.com \
  sheets.googleapis.com \
  drive.googleapis.com \
  calendar.googleapis.com \
  gmail.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  --project=rcq-fr-dev
```

#### Create Artifact Registry Repository

```bash
gcloud artifacts repositories create clef-images \
  --repository-format=docker \
  --location=europe-west1 \
  --description="CLEF container images" \
  --project=rcq-fr-dev
```

#### Create Service Account

```bash
# Create service account
gcloud iam service-accounts create clef-backend \
  --display-name="CLEF Backend Service Account" \
  --project=rcq-fr-dev

# Grant necessary roles
gcloud projects add-iam-policy-binding rcq-fr-dev \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding rcq-fr-dev \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding rcq-fr-dev \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/redis.editor"

gcloud projects add-iam-policy-binding rcq-fr-dev \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding rcq-fr-dev \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Generate key for GitHub Actions
gcloud iam service-accounts keys create key.json \
  --iam-account=clef-backend@rcq-fr-dev.iam.gserviceaccount.com \
  --project=rcq-fr-dev
```

### 4. Create MemoryStore Redis Instance

**Note:** This step is NOT automated by the setup scripts and must be done manually.

```bash
gcloud redis instances create clef-cache \
  --size=1 \
  --region=europe-west1 \
  --redis-version=redis_7_0 \
  --enable-auth \
  --persistence-mode=rdb \
  --project=rcq-fr-dev

# Get the Redis instance IP for your .env file
gcloud redis instances describe clef-cache \
  --region=europe-west1 \
  --project=rcq-fr-dev \
  --format="value(host)"
```

## GitHub Secrets Configuration

Configure the following secrets in your GitHub repository (Settings → Secrets and variables → Actions):

### Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `GCP_SERVICE_ACCOUNT_KEY` | Service account JSON key | Contents of `key.json` |
| `GCP_PROJECT_DEV` | GCP project ID for dev | `rcq-fr-dev` |
| `GCP_PROJECT_TEST` | GCP project ID for test | `rcq-fr-test` |
| `GCP_PROJECT_PROD` | GCP project ID for prod | `rcq-fr-prod` |

### GCP Secret Manager Secrets

Store sensitive configuration in GCP Secret Manager:

```bash
# Okta credentials
echo -n "your-okta-client-id" | gcloud secrets create OKTA_CLIENT_ID \
  --data-file=- \
  --replication-policy="automatic" \
  --project=rcq-fr-dev

echo -n "your-okta-client-secret" | gcloud secrets create OKTA_CLIENT_SECRET \
  --data-file=- \
  --replication-policy="automatic" \
  --project=rcq-fr-dev

# QR Code salt (generate random string)
openssl rand -base64 32 | gcloud secrets create QR_CODE_SALT \
  --data-file=- \
  --replication-policy="automatic" \
  --project=rcq-fr-dev

# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding OKTA_CLIENT_ID \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=rcq-fr-dev

gcloud secrets add-iam-policy-binding OKTA_CLIENT_SECRET \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=rcq-fr-dev

gcloud secrets add-iam-policy-binding QR_CODE_SALT \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=rcq-fr-dev
```

## CI/CD Workflow

### On Pull Request

The workflow runs automatically when a PR is opened or updated:

1. **Backend Tests**: Runs pytest with mocked Google APIs
2. **Frontend Build**: Builds both admin and form apps in parallel

### On Main Branch Merge

The workflow deploys to the dev environment:

1. **Build Images**: Creates Docker images for backend and frontend
2. **Push to Registry**: Uploads images to Artifact Registry
3. **Deploy to Cloud Run**: Updates Cloud Run services
4. **Output URLs**: Displays deployed service URLs

## Manual Deployment

### Deploy Backend

```bash
# Build and push image
cd backend
docker build -t europe-west1-docker.pkg.dev/rcq-fr-dev/clef-images/clef-api:latest .
docker push europe-west1-docker.pkg.dev/rcq-fr-dev/clef-images/clef-api:latest

# Deploy to Cloud Run
gcloud run deploy clef-api \
  --image europe-west1-docker.pkg.dev/rcq-fr-dev/clef-images/clef-api:latest \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --project rcq-fr-dev
```

### Deploy Frontend

```bash
# Build and push image
cd frontend
docker build -t europe-west1-docker.pkg.dev/rcq-fr-dev/clef-images/clef-frontend:latest .
docker push europe-west1-docker.pkg.dev/rcq-fr-dev/clef-images/clef-frontend:latest

# Deploy to Cloud Run
gcloud run deploy clef-frontend \
  --image europe-west1-docker.pkg.dev/rcq-fr-dev/clef-images/clef-frontend:latest \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --port 80 \
  --project rcq-fr-dev
```

## Monitoring and Logs

### View Logs

```bash
# Backend logs
gcloud run logs read clef-api --region europe-west1 --project rcq-fr-dev

# Frontend logs
gcloud run logs read clef-frontend --region europe-west1 --project rcq-fr-dev
```

### View Service Status

```bash
# List services
gcloud run services list --region europe-west1 --project rcq-fr-dev

# Describe service
gcloud run services describe clef-api --region europe-west1 --project rcq-fr-dev
```

## Rollback

Cloud Run keeps previous revisions for easy rollback:

```bash
# List revisions
gcloud run revisions list --service clef-api --region europe-west1 --project rcq-fr-dev

# Rollback to previous revision
gcloud run services update-traffic clef-api \
  --to-revisions=clef-api-00001-abc=100 \
  --region europe-west1 \
  --project rcq-fr-dev
```

## Environment-Specific Deployment

To deploy to test or production environments:

1. Create a new branch protection rule for the target branch
2. Add environment-specific secrets in GitHub
3. Update the workflow to trigger on the appropriate branch
4. Ensure all environment variables are configured correctly

## Troubleshooting

### Build Fails

- Check Docker build logs in GitHub Actions
- Verify all dependencies are in requirements.txt / package.json
- Test build locally: `docker build -t test .`

### Deployment Fails

- Verify GCP credentials are valid
- Check service account permissions
- Ensure all required APIs are enabled
- Review Cloud Run logs for errors

### Service Not Responding

- Check Cloud Run service status
- Review application logs
- Verify environment variables are set correctly
- Check MemoryStore Redis connectivity

## Security Best Practices

1. **Never commit secrets** to the repository
2. **Use Secret Manager** for sensitive configuration
3. **Rotate credentials** regularly
4. **Enable VPC** for production deployments
5. **Use least privilege** for service accounts
6. **Enable Cloud Armor** for DDoS protection
7. **Set up monitoring** and alerting

## Next Steps

- [ ] Configure custom domain with Cloud Load Balancer
- [ ] Set up Cloud CDN for frontend assets
- [ ] Enable Cloud Armor for security
- [ ] Configure VPC connector for MemoryStore
- [ ] Set up monitoring and alerting
- [ ] Configure backup and disaster recovery
- [ ] Implement blue-green deployment strategy

