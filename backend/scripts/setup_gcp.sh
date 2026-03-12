#!/bin/bash

# CLEF - GCP Setup Script
# Automates GCP project configuration with OpenTofu
# Usage: ./setup_gcp.sh [dev|test|prod]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if environment parameter is provided
if [ -z "$1" ]; then
    print_error "Environment parameter required"
    echo "Usage: $0 [dev|test|prod]"
    exit 1
fi

ENV=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"
CREDS_DIR="$HOME/.cred/CLEF"

# Validate environment
case $ENV in
    dev|test|prod) ;;
    *)
        print_error "Invalid environment: $ENV"
        echo "Valid options: dev, test, prod"
        exit 1
        ;;
esac

print_info "Setting up GCP for environment: $ENV"
echo ""

# Read .env file if exists
ENV_FILE="$SCRIPT_DIR/../.env.${ENV}"
if [ -f "$ENV_FILE" ]; then
    print_info "Loading configuration from $ENV_FILE"
    # Source the env file to get variables
    set -a
    source "$ENV_FILE"
    set +a

    # Unset GOOGLE_APPLICATION_CREDENTIALS to use ADC for Terraform
    # The script will create this file later and update .env
    if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        print_info "Temporarily unsetting GOOGLE_APPLICATION_CREDENTIALS (will be created by Terraform)"
        unset GOOGLE_APPLICATION_CREDENTIALS
    fi
fi

# Default values
VALKEY_MEMORY_GB="${VALKEY_MEMORY_GB:-1}"
VALKEY_NODE_TYPE="${VALKEY_NODE_TYPE:-SHARED_CORE_NANO}"
VALKEY_REPLICA_COUNT="${VALKEY_REPLICA_COUNT:-1}"
VALKEY_VERSION="${VALKEY_VERSION:-VALKEY_8_0}"
VALKEY_ZONE_MODE="${VALKEY_ZONE_MODE:-MULTI_ZONE}"

print_info "Valkey configuration:"
echo "  Memory: ${VALKEY_MEMORY_GB}GB"
echo "  Node Type: ${VALKEY_NODE_TYPE}"
echo "  Replicas: ${VALKEY_REPLICA_COUNT}"
echo "  Version: ${VALKEY_VERSION}"
echo "  Zone Mode: ${VALKEY_ZONE_MODE}"
echo ""

# Check if OpenTofu is installed
if ! command -v tofu &> /dev/null; then
    print_error "OpenTofu not found. Please install it:"
    echo "  brew install opentofu"
    echo "  OR: https://opentofu.org/docs/intro/install/"
    exit 1
fi

print_success "OpenTofu found"

# Check if gcloud is authenticated (needed for Terraform Google provider)
if ! gcloud auth application-default print-access-token &> /dev/null; then
    print_warning "Not authenticated to GCP"
    print_info "Running: gcloud auth application-default login"
    gcloud auth application-default login
fi

print_success "GCP authentication verified"

# Create credentials directory
mkdir -p "$CREDS_DIR"
chmod 700 "$CREDS_DIR"

# Initialize Terraform
print_info "Initializing OpenTofu..."
cd "$TERRAFORM_DIR"
tofu init -upgrade

# Plan
print_info "Planning infrastructure for $ENV..."
tofu plan -var-file="environments/$ENV.tfvars" \
  -var="valkey_memory_gb=${VALKEY_MEMORY_GB}" \
  -var="valkey_node_type=${VALKEY_NODE_TYPE}" \
  -var="valkey_replica_count=${VALKEY_REPLICA_COUNT}" \
  -var="valkey_version=${VALKEY_VERSION}" \
  -var="valkey_zone_mode=${VALKEY_ZONE_MODE}" \
  -out="tfplan-$ENV"

# Confirm
read -p "Apply this plan? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    print_warning "Aborted"
    exit 0
fi

# Apply
print_info "Applying infrastructure..."
tofu apply "tfplan-$ENV"

# Extract service account key
print_info "Extracting service account key..."
KEY_FILE="$CREDS_DIR/clef-backend-${ENV}-key.json"
tofu output -raw service_account_key > "$KEY_FILE"
chmod 600 "$KEY_FILE"
print_success "Key saved to: $KEY_FILE"

# Update .env file with Terraform outputs
print_info "Updating .env.$ENV with Terraform outputs..."

ENV_FILE="$SCRIPT_DIR/../.env.$ENV"

# Function to update or add a variable in .env file
update_env_var() {
    local var_name="$1"
    local var_value="$2"
    local env_file="$3"

    if grep -q "^${var_name}=" "$env_file"; then
        # Variable exists, update it (handle special characters in value)
        sed -i.bak "s|^${var_name}=.*|${var_name}=${var_value}|" "$env_file"
        rm -f "${env_file}.bak"
    else
        # Variable doesn't exist, append it
        echo "${var_name}=${var_value}" >> "$env_file"
    fi
}

# Get Terraform outputs
VALKEY_HOST=$(tofu output -raw valkey_host 2>/dev/null || echo "")
VALKEY_PORT=$(tofu output -raw valkey_port 2>/dev/null || echo "6379")
SA_EMAIL=$(tofu output -raw service_account_email)
PROJECT_ID=$(tofu output -raw project_id)

# Update .env file
if [ -f "$ENV_FILE" ]; then
    # Update existing file
    if [ -n "$VALKEY_HOST" ]; then
        update_env_var "REDIS_URL" "redis://${VALKEY_HOST}:${VALKEY_PORT}/0" "$ENV_FILE"
        print_success "Updated REDIS_URL with Valkey endpoint"
    else
        print_warning "Valkey endpoint not yet available (may still be provisioning)"
        print_info "Run 'cd backend/terraform && tofu output valkey_host' later to get the endpoint"
    fi
    update_env_var "GOOGLE_APPLICATION_CREDENTIALS" "$KEY_FILE" "$ENV_FILE"
    update_env_var "GCP_PROJECT" "$PROJECT_ID" "$ENV_FILE"

    print_success ".env.$ENV updated with Terraform outputs"
else
    # Create new file if doesn't exist
    print_warning ".env.$ENV not found, creating minimal config..."
    cat > "$ENV_FILE" << EOF
# Generated by setup_gcp.sh on $(date)
ENVIRONMENT=$ENV
GCP_PROJECT=$PROJECT_ID
GOOGLE_APPLICATION_CREDENTIALS=$KEY_FILE
REDIS_URL=redis://${VALKEY_HOST}:${VALKEY_PORT}/0

# Google OAuth (to be filled manually)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Application
USE_MOCKS=false
CORS_ORIGINS=http://localhost:4200,http://localhost:4202,http://localhost:8000

# Session
SESSION_SECRET_KEY=$(openssl rand -hex 32)

# QR Code
QR_CODE_SALT=$(openssl rand -hex 16)
EOF
    print_success ".env.$ENV created"
fi

# Summary
echo ""
print_success "==========================================="
print_success "GCP Setup Complete for $ENV!"
print_success "==========================================="
echo ""
print_info "Resources created:"
echo "  • Service Account: $SA_EMAIL"
echo "  • Key File: $KEY_FILE"
if [ -n "$VALKEY_HOST" ]; then
    echo "  • Valkey: redis://${VALKEY_HOST}:${VALKEY_PORT}"
else
    echo "  • Valkey: (provisioning in progress)"
fi
echo ""
print_info "Updated in .env.$ENV:"
echo "  • GOOGLE_APPLICATION_CREDENTIALS"
echo "  • GCP_PROJECT"
if [ -n "$VALKEY_HOST" ]; then
    echo "  • REDIS_URL (Valkey endpoint)"
fi
echo ""
print_info "Next steps:"
echo "  1. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env.$ENV"
echo "  2. Copy .env.$ENV to backend/.env"
echo "  3. Share Google Sheets with: $SA_EMAIL"
