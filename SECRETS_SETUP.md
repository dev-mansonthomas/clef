# CLEF - Secrets Configuration Guide

Quick reference for setting up all required secrets for CI/CD deployment.

## GitHub Repository Secrets

Navigate to: **Settings → Secrets and variables → Actions → New repository secret**

### Required Secrets

```bash
# 1. GCP Service Account Key
# Create and download the key, then paste the entire JSON content
Name: GCP_SERVICE_ACCOUNT_KEY
Value: {
  "type": "service_account",
  "project_id": "rcq-fr-dev",
  ...
}

# 2. GCP Project IDs
Name: GCP_PROJECT_DEV
Value: rcq-fr-dev

Name: GCP_PROJECT_TEST
Value: rcq-fr-test

Name: GCP_PROJECT_PROD
Value: rcq-fr-prod
```

## GCP Secret Manager Secrets

These secrets are accessed by Cloud Run services at runtime.

### Create Secrets

```bash
# Set project
export PROJECT_ID=rcq-fr-dev

# 1. Okta Client ID
echo -n "YOUR_OKTA_CLIENT_ID" | gcloud secrets create OKTA_CLIENT_ID \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# 2. Okta Client Secret
echo -n "YOUR_OKTA_CLIENT_SECRET" | gcloud secrets create OKTA_CLIENT_SECRET \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# 3. QR Code Salt (generate random)
openssl rand -base64 32 | gcloud secrets create QR_CODE_SALT \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# 4. JWT Secret Key (generate random)
openssl rand -base64 64 | gcloud secrets create JWT_SECRET_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# 5. Redis URL (from MemoryStore)
REDIS_HOST=$(gcloud redis instances describe clef-cache \
  --region=europe-west1 \
  --format='value(host)' \
  --project=$PROJECT_ID)
echo -n "redis://${REDIS_HOST}:6379/0" | gcloud secrets create REDIS_URL \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# 6. Google Sheets URLs (configure with your actual URLs)
echo -n "https://docs.google.com/spreadsheets/d/YOUR_VEHICULES_SHEET_ID" | \
  gcloud secrets create SHEETS_URL_VEHICULES \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

echo -n "https://docs.google.com/spreadsheets/d/YOUR_BENEVOLES_SHEET_ID" | \
  gcloud secrets create SHEETS_URL_BENEVOLES \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

echo -n "https://docs.google.com/spreadsheets/d/YOUR_RESPONSABLES_SHEET_ID" | \
  gcloud secrets create SHEETS_URL_RESPONSABLES \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# 7. Email Configuration
echo -n "thomas.manson@croix-rouge.fr" | gcloud secrets create EMAIL_GESTIONNAIRE_DT \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

echo -n "Magalie.WERNER@s2hgroup.com" | gcloud secrets create EMAIL_DESTINATAIRE_ALERTES \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID
```

### Grant Access to Service Account

```bash
export PROJECT_ID=rcq-fr-dev
export SERVICE_ACCOUNT=clef-backend@rcq-fr-dev.iam.gserviceaccount.com

# Grant access to all secrets
for SECRET in OKTA_CLIENT_ID OKTA_CLIENT_SECRET QR_CODE_SALT JWT_SECRET_KEY \
              REDIS_URL SHEETS_URL_VEHICULES SHEETS_URL_BENEVOLES \
              SHEETS_URL_RESPONSABLES EMAIL_GESTIONNAIRE_DT EMAIL_DESTINATAIRE_ALERTES
do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID
done
```

## Environment Variables (Non-Secret)

These are set directly in the Cloud Run deployment:

```yaml
ENVIRONMENT: dev
GCP_PROJECT: rcq-fr-dev
GCP_REGION: europe-west1
GCP_RESOURCE_PREFIX: clef-
DOMAIN: clef.example.com
OKTA_DOMAIN: croix-rouge.okta.com
OKTA_ISSUER: https://croix-rouge.okta.com/oauth2/default
OKTA_REDIRECT_URI: https://clef.example.com/auth/callback
SERVICE_ACCOUNT_EMAIL: clef-backend@rcq-fr-dev.iam.gserviceaccount.com
CORS_ORIGINS: https://clef.example.com,https://admin.clef.example.com
```

## Verification

### Check GitHub Secrets

1. Go to repository Settings → Secrets and variables → Actions
2. Verify all 4 secrets are present
3. Secrets cannot be viewed after creation (only updated)

### Check GCP Secrets

```bash
# List all secrets
gcloud secrets list --project=rcq-fr-dev

# View secret metadata (not the value)
gcloud secrets describe OKTA_CLIENT_ID --project=rcq-fr-dev

# Access a secret value (for testing)
gcloud secrets versions access latest --secret=OKTA_CLIENT_ID --project=rcq-fr-dev
```

### Test Secret Access from Cloud Run

```bash
# Deploy a test service
gcloud run deploy test-secrets \
  --image=gcr.io/cloudrun/hello \
  --set-secrets="OKTA_CLIENT_ID=OKTA_CLIENT_ID:latest" \
  --region=europe-west1 \
  --project=rcq-fr-dev

# Check if secret is accessible
gcloud run services describe test-secrets \
  --region=europe-west1 \
  --project=rcq-fr-dev
```

## Security Best Practices

1. **Rotate secrets regularly** (every 90 days recommended)
2. **Use different secrets** for each environment (dev/test/prod)
3. **Never log secret values** in application code
4. **Audit secret access** using Cloud Audit Logs
5. **Use automatic replication** for high availability
6. **Enable Secret Manager API** before creating secrets
7. **Grant least privilege** access to secrets

## Troubleshooting

### Secret Not Found

```bash
# Verify secret exists
gcloud secrets list --project=rcq-fr-dev | grep OKTA_CLIENT_ID

# Check IAM permissions
gcloud secrets get-iam-policy OKTA_CLIENT_ID --project=rcq-fr-dev
```

### Access Denied

```bash
# Grant access to service account
gcloud secrets add-iam-policy-binding OKTA_CLIENT_ID \
  --member="serviceAccount:clef-backend@rcq-fr-dev.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=rcq-fr-dev
```

### Update Secret Value

```bash
# Add new version
echo -n "NEW_VALUE" | gcloud secrets versions add OKTA_CLIENT_ID \
  --data-file=- \
  --project=rcq-fr-dev

# Cloud Run will automatically use the latest version
```

## Quick Setup Script

Save this as `setup-secrets.sh`:

```bash
#!/bin/bash
set -e

PROJECT_ID=${1:-rcq-fr-dev}
echo "Setting up secrets for project: $PROJECT_ID"

# Check if gcloud is authenticated
gcloud auth list

# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID

# Create secrets (you'll be prompted for values)
read -p "Enter OKTA_CLIENT_ID: " OKTA_CLIENT_ID
echo -n "$OKTA_CLIENT_ID" | gcloud secrets create OKTA_CLIENT_ID \
  --data-file=- --replication-policy="automatic" --project=$PROJECT_ID

read -sp "Enter OKTA_CLIENT_SECRET: " OKTA_CLIENT_SECRET
echo
echo -n "$OKTA_CLIENT_SECRET" | gcloud secrets create OKTA_CLIENT_SECRET \
  --data-file=- --replication-policy="automatic" --project=$PROJECT_ID

# Generate random secrets
openssl rand -base64 32 | gcloud secrets create QR_CODE_SALT \
  --data-file=- --replication-policy="automatic" --project=$PROJECT_ID

openssl rand -base64 64 | gcloud secrets create JWT_SECRET_KEY \
  --data-file=- --replication-policy="automatic" --project=$PROJECT_ID

echo "✅ Secrets created successfully!"
```

Usage:
```bash
chmod +x setup-secrets.sh
./setup-secrets.sh rcq-fr-dev
```

