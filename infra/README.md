# CLEF - Infrastructure as Code (Terraform)

This directory contains Terraform configuration for provisioning GCP infrastructure for the CLEF application.

## Prerequisites

1. **Terraform** installed (>= 1.0)
   ```bash
   # macOS
   brew install terraform
   
   # Or download from https://www.terraform.io/downloads
   ```

2. **gcloud CLI** installed and authenticated
   ```bash
   gcloud auth application-default login
   ```

3. **GCP Project** created (rcq-fr-dev, rcq-fr-test, or rcq-fr-prod)

## Quick Start

```bash
cd infra

# Initialize Terraform
terraform init

# Preview changes
terraform plan -var="environment=dev"

# Apply configuration
terraform apply -var="environment=dev"
```

## What Gets Created

This Terraform configuration creates:

1. **Enabled APIs**:
   - Cloud Run
   - Artifact Registry
   - Cloud MemoryStore (Redis)
   - Google Sheets API
   - Google Drive API
   - Google Calendar API
   - Gmail API
   - Secret Manager
   - IAM

2. **Service Account**: `clef-backend@{project-id}.iam.gserviceaccount.com`
   - With roles: Cloud Run Admin, Artifact Registry Writer, Redis Editor, Secret Manager Accessor

3. **Artifact Registry Repository**: `clef-images` (Docker format)

4. **Secret Manager Secrets** (empty, values must be set manually):
   - OKTA_CLIENT_ID
   - OKTA_CLIENT_SECRET
   - QR_CODE_SALT
   - JWT_SECRET_KEY

## Usage

### Deploy to Development

```bash
terraform apply -var="environment=dev"
```

### Deploy to Test

```bash
terraform apply -var="environment=test"
```

### Deploy to Production

```bash
terraform apply -var="environment=prod"
```

### View Outputs

```bash
terraform output
```

### Destroy Infrastructure (⚠️ Use with caution)

```bash
terraform destroy -var="environment=dev"
```

## Post-Deployment Steps

After running Terraform, you still need to:

1. **Generate Service Account Key**:
   ```bash
   gcloud iam service-accounts keys create clef-backend-dev-key.json \
     --iam-account=clef-backend@rcq-fr-dev.iam.gserviceaccount.com \
     --project=rcq-fr-dev
   ```

2. **Set Secret Values**:
   ```bash
   # OKTA_CLIENT_ID
   echo -n "your-okta-client-id" | gcloud secrets versions add OKTA_CLIENT_ID \
     --data-file=- --project=rcq-fr-dev
   
   # OKTA_CLIENT_SECRET
   echo -n "your-okta-client-secret" | gcloud secrets versions add OKTA_CLIENT_SECRET \
     --data-file=- --project=rcq-fr-dev
   
   # QR_CODE_SALT (generate random)
   openssl rand -base64 32 | gcloud secrets versions add QR_CODE_SALT \
     --data-file=- --project=rcq-fr-dev
   
   # JWT_SECRET_KEY (generate random)
   openssl rand -base64 32 | gcloud secrets versions add JWT_SECRET_KEY \
     --data-file=- --project=rcq-fr-dev
   ```

3. **Create MemoryStore Redis Instance** (see DEPLOYMENT.md)

4. **Configure Okta Application** (see DEPLOYMENT.md)

5. **Share Google Sheets** with the service account email

## Alternative: Bash Script

If you prefer a simpler approach without Terraform, use the bash script:

```bash
cd backend
./scripts/setup_gcp.sh dev
```

The bash script is more interactive and includes prompts for key generation and secret creation.

## State Management

For production use, consider using remote state:

```hcl
terraform {
  backend "gcs" {
    bucket = "your-terraform-state-bucket"
    prefix = "clef/terraform/state"
  }
}
```

## Troubleshooting

### Permission Denied

Ensure you have the necessary permissions in the GCP project:
```bash
gcloud projects get-iam-policy rcq-fr-dev
```

### API Not Enabled

If you get API errors, manually enable them:
```bash
gcloud services enable run.googleapis.com --project=rcq-fr-dev
```

### Service Account Already Exists

Terraform will import the existing service account. This is safe.

## More Information

- [DEPLOYMENT.md](../DEPLOYMENT.md) - Full deployment guide
- [SECRETS_SETUP.md](../SECRETS_SETUP.md) - Secrets configuration
- [Terraform Google Provider Docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

