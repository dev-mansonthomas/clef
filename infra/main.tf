# CLEF - Terraform Configuration for GCP Infrastructure
# This is an alternative to the setup_gcp.sh script for those who prefer Infrastructure as Code
# Usage: terraform init && terraform apply -var="environment=dev"

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, test, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be dev, test, or prod."
  }
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"
}

# Local variables
locals {
  project_map = {
    dev  = "rcq-fr-dev"
    test = "rcq-fr-test"
    prod = "rcq-fr-prod"
  }

  project_id            = local.project_map[var.environment]
  service_account_name  = "clef-backend"
  service_account_email = "${local.service_account_name}@${local.project_id}.iam.gserviceaccount.com"

  # APIs to enable
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "redis.googleapis.com",
    "sheets.googleapis.com",
    "drive.googleapis.com",
    "calendar.googleapis.com",
    "gmail.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
  ]

  # IAM roles for service account
  service_account_roles = [
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/redis.editor",
    "roles/secretmanager.secretAccessor",
    "roles/iam.serviceAccountUser",
  ]
}

# Provider configuration
provider "google" {
  project = local.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset(local.apis)

  project = local.project_id
  service = each.value

  disable_on_destroy = false
}

# Create Service Account
resource "google_service_account" "clef_backend" {
  account_id   = local.service_account_name
  display_name = "CLEF Backend Service Account"
  description  = "Service account for CLEF application backend"
  project      = local.project_id

  depends_on = [google_project_service.apis]
}

# Assign IAM roles to Service Account
resource "google_project_iam_member" "service_account_roles" {
  for_each = toset(local.service_account_roles)

  project = local.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.clef_backend.email}"
}

# Create Artifact Registry repository
resource "google_artifact_registry_repository" "clef_images" {
  location      = var.region
  repository_id = "clef-images"
  description   = "CLEF container images"
  format        = "DOCKER"
  project       = local.project_id

  depends_on = [google_project_service.apis]
}

# Create Secret Manager secrets (optional - values must be set manually)
resource "google_secret_manager_secret" "okta_client_id" {
  secret_id = "OKTA_CLIENT_ID"
  project   = local.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "okta_client_secret" {
  secret_id = "OKTA_CLIENT_SECRET"
  project   = local.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "qr_code_salt" {
  secret_id = "QR_CODE_SALT"
  project   = local.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "jwt_secret_key" {
  secret_id = "JWT_SECRET_KEY"
  project   = local.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# Grant Service Account access to secrets
resource "google_secret_manager_secret_iam_member" "okta_client_id_access" {
  secret_id = google_secret_manager_secret.okta_client_id.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.clef_backend.email}"
  project   = local.project_id
}

resource "google_secret_manager_secret_iam_member" "okta_client_secret_access" {
  secret_id = google_secret_manager_secret.okta_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.clef_backend.email}"
  project   = local.project_id
}

resource "google_secret_manager_secret_iam_member" "qr_code_salt_access" {
  secret_id = google_secret_manager_secret.qr_code_salt.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.clef_backend.email}"
  project   = local.project_id
}

resource "google_secret_manager_secret_iam_member" "jwt_secret_key_access" {
  secret_id = google_secret_manager_secret.jwt_secret_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.clef_backend.email}"
  project   = local.project_id
}

# Outputs
output "project_id" {
  description = "GCP Project ID"
  value       = local.project_id
}

output "service_account_email" {
  description = "Service Account email"
  value       = google_service_account.clef_backend.email
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${local.project_id}/${google_artifact_registry_repository.clef_images.repository_id}"
}

output "next_steps" {
  description = "Next steps after Terraform apply"
  value       = <<-EOT

    ========================================
    GCP Setup Complete for ${var.environment} environment!
    ========================================

    Summary:
      • Project: ${local.project_id}
      • Service Account: ${google_service_account.clef_backend.email}
      • Artifact Registry: ${var.region}/${google_artifact_registry_repository.clef_images.repository_id}

    Next steps:
      1. Generate service account key:
         gcloud iam service-accounts keys create clef-backend-${var.environment}-key.json \
           --iam-account=${google_service_account.clef_backend.email} \
           --project=${local.project_id}

      2. Set secret values in Secret Manager:
         gcloud secrets versions add OKTA_CLIENT_ID --data-file=- --project=${local.project_id}
         gcloud secrets versions add OKTA_CLIENT_SECRET --data-file=- --project=${local.project_id}
         gcloud secrets versions add QR_CODE_SALT --data-file=- --project=${local.project_id}
         gcloud secrets versions add JWT_SECRET_KEY --data-file=- --project=${local.project_id}

      3. Create MemoryStore Redis instance (see DEPLOYMENT.md)
      4. Configure Okta application (see DEPLOYMENT.md)
      5. Share Google Sheets with the service account

    For more information, see DEPLOYMENT.md and SECRETS_SETUP.md
  EOT
}

