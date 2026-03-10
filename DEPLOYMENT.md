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

### Automated Setup (Recommended)

We provide a script to automate the GitHub secrets configuration using `gh` CLI:

```bash
cd backend
./scripts/setup_github_secrets.sh dev
```

This script will:
- ✅ Read values from `.env.{env}` file if available
- ✅ Prompt interactively for missing values
- ✅ Auto-generate `QR_CODE_SALT` and `JWT_SECRET_KEY` if not provided
- ✅ Encode the service account JSON key as base64
- ✅ Configure all required GitHub secrets
- ✅ Verify the configuration with `gh secret list`

**Prerequisites:**
- Install `gh` CLI: https://cli.github.com/
- Authenticate: `gh auth login`
- Have the service account JSON key file ready

**Usage for different environments:**
```bash
./scripts/setup_github_secrets.sh dev   # For development
./scripts/setup_github_secrets.sh test  # For testing
./scripts/setup_github_secrets.sh prod  # For production
```

### Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `GCP_PROJECT_ID` | GCP project ID | `rcq-fr-dev` |
| `GCP_SA_KEY` | Service account JSON key (base64 encoded) | Base64 of `key.json` |
| `GOOGLE_CLIENT_ID` | Okta client ID | `0oa...` |
| `GOOGLE_CLIENT_SECRET` | Okta client secret | `secret...` |
| `QR_CODE_SALT` | Salt for QR code generation | Random 32-byte string |
| `JWT_SECRET_KEY` | JWT signing key | Random 32-byte string |

### Manual Setup (Alternative)

If you prefer to configure secrets manually, use the GitHub web interface:

1. Go to your repository → Settings → Secrets and variables → Actions
2. Click "New repository secret" for each secret
3. For `GCP_SA_KEY`, encode the JSON key file: `base64 -i key.json`
4. For `QR_CODE_SALT` and `JWT_SECRET_KEY`, generate random values: `openssl rand -base64 32`

### GCP Secret Manager Secrets (Optional)

Alternatively, you can store sensitive configuration in GCP Secret Manager and reference them in Cloud Run:

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

# JWT Secret Key
openssl rand -base64 32 | gcloud secrets create JWT_SECRET_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project=rcq-fr-dev

# Grant Cloud Run access to secrets
for SECRET in OKTA_CLIENT_ID OKTA_CLIENT_SECRET QR_CODE_SALT JWT_SECRET_KEY; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=rcq-fr-dev
done
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

