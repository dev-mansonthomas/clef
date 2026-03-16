#!/bin/bash

# CLEF - GitHub Secrets Setup Script
# Automates GitHub Actions secrets configuration with gh CLI
# Usage: ./setup_github_secrets.sh [dev|test|prod]

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

# Map environment to GCP project
case $ENV in
    dev)
        PROJECT_ID="rcq-fr-dev"
        ;;
    test)
        PROJECT_ID="rcq-fr-test"
        ;;
    prod)
        PROJECT_ID="rcq-fr-prod"
        ;;
    *)
        print_error "Invalid environment: $ENV"
        echo "Valid options: dev, test, prod"
        exit 1
        ;;
esac

print_info "Setting up GitHub Secrets for environment: $ENV"
print_info "GCP Project: $PROJECT_ID"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    print_error "gh CLI not found. Please install it first:"
    echo "https://cli.github.com/"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    print_error "Not authenticated with gh CLI. Please run:"
    echo "gh auth login"
    exit 1
fi

print_success "gh CLI found and authenticated"
echo ""

# Load values from .env file if it exists
ENV_FILE="backend/.env.$ENV"
if [ -f "$ENV_FILE" ]; then
    print_info "Loading values from $ENV_FILE..."
    source "$ENV_FILE"
    print_success "Environment file loaded"
else
    print_warning "Environment file $ENV_FILE not found"
    print_info "Values will be requested interactively"
fi
echo ""

# Function to get or prompt for value
get_value() {
    local var_name=$1
    local prompt_text=$2
    local current_value=${!var_name}
    
    if [ -n "$current_value" ]; then
        echo "$current_value"
    else
        read -p "$prompt_text: " value
        echo "$value"
    fi
}

# Function to get or prompt for secret value
get_secret_value() {
    local var_name=$1
    local prompt_text=$2
    local current_value=${!var_name}
    
    if [ -n "$current_value" ]; then
        echo "$current_value"
    else
        read -sp "$prompt_text: " value
        echo >&2
        echo "$value"
    fi
}

# Function to generate random secret
generate_secret() {
    openssl rand -base64 32
}

print_info "Collecting secret values..."
echo ""

# 1. GCP_PROJECT_ID
print_info "1/6: GCP_PROJECT_ID"
GCP_PROJECT_ID=$(get_value "GCP_PROJECT_ID" "Enter GCP Project ID")
if [ -z "$GCP_PROJECT_ID" ]; then
    GCP_PROJECT_ID=$PROJECT_ID
fi
print_success "GCP_PROJECT_ID: $GCP_PROJECT_ID"
echo ""

# 2. GCP_SA_KEY (Service Account Key - JSON file)
print_info "2/6: GCP_SA_KEY (Service Account JSON Key)"
KEY_FILE=$(get_value "GOOGLE_APPLICATION_CREDENTIALS" "Enter path to service account JSON key file")
if [ -z "$KEY_FILE" ]; then
    KEY_FILE="backend/clef-backend-${ENV}-key.json"
fi

if [ ! -f "$KEY_FILE" ]; then
    print_error "Service account key file not found: $KEY_FILE"
    read -p "Enter path to service account JSON key file: " KEY_FILE
    if [ ! -f "$KEY_FILE" ]; then
        print_error "File not found: $KEY_FILE"
        exit 1
    fi
fi

# Encode JSON key as base64
GCP_SA_KEY=$(base64 -i "$KEY_FILE")
print_success "GCP_SA_KEY loaded and encoded from $KEY_FILE"
echo ""

# 3. GOOGLE_CLIENT_ID (Google OAuth)
print_info "3/6: GOOGLE_CLIENT_ID (Google OAuth Client ID)"
GOOGLE_CLIENT_ID=$(get_value "GOOGLE_CLIENT_ID" "Enter Google OAuth Client ID")
print_success "GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID:0:10}..."
echo ""

# 4. GOOGLE_CLIENT_SECRET (Google OAuth)
print_info "4/6: GOOGLE_CLIENT_SECRET (Google OAuth Client Secret)"
GOOGLE_CLIENT_SECRET=$(get_secret_value "GOOGLE_CLIENT_SECRET" "Enter Google OAuth Client Secret")
print_success "GOOGLE_CLIENT_SECRET: [hidden]"
echo ""

# 5. QR_CODE_SALT
print_info "5/6: QR_CODE_SALT"
QR_CODE_SALT=$(get_secret_value "QR_CODE_SALT" "Enter QR Code Salt (leave empty to auto-generate)")
if [ -z "$QR_CODE_SALT" ]; then
    QR_CODE_SALT=$(generate_secret)
    print_success "QR_CODE_SALT: [auto-generated]"
else
    print_success "QR_CODE_SALT: [provided]"
fi
echo ""

# 6. JWT_SECRET_KEY
print_info "6/6: JWT_SECRET_KEY"
JWT_SECRET_KEY=$(get_secret_value "JWT_SECRET_KEY" "Enter JWT Secret Key (leave empty to auto-generate)")
if [ -z "$JWT_SECRET_KEY" ]; then
    JWT_SECRET_KEY=$(generate_secret)
    print_success "JWT_SECRET_KEY: [auto-generated]"
else
    print_success "JWT_SECRET_KEY: [provided]"
fi
echo ""

# Configure GitHub Secrets
print_info "Configuring GitHub Secrets..."
echo ""

# Set each secret
print_info "Setting GCP_PROJECT_ID..."
echo -n "$GCP_PROJECT_ID" | gh secret set GCP_PROJECT_ID
print_success "GCP_PROJECT_ID configured"

print_info "Setting GCP_SA_KEY..."
echo -n "$GCP_SA_KEY" | gh secret set GCP_SA_KEY
print_success "GCP_SA_KEY configured"

print_info "Setting GOOGLE_CLIENT_ID..."
echo -n "$GOOGLE_CLIENT_ID" | gh secret set GOOGLE_CLIENT_ID
print_success "GOOGLE_CLIENT_ID configured"

print_info "Setting GOOGLE_CLIENT_SECRET..."
echo -n "$GOOGLE_CLIENT_SECRET" | gh secret set GOOGLE_CLIENT_SECRET
print_success "GOOGLE_CLIENT_SECRET configured"

print_info "Setting QR_CODE_SALT..."
echo -n "$QR_CODE_SALT" | gh secret set QR_CODE_SALT
print_success "QR_CODE_SALT configured"

print_info "Setting JWT_SECRET_KEY..."
echo -n "$JWT_SECRET_KEY" | gh secret set JWT_SECRET_KEY
print_success "JWT_SECRET_KEY configured"

echo ""

# Verify secrets
print_info "Verifying configured secrets..."
gh secret list
echo ""

# Summary
print_success "========================================="
print_success "GitHub Secrets Setup Complete!"
print_success "========================================="
echo ""
print_info "Summary:"
echo "  • Environment: $ENV"
echo "  • GCP Project: $GCP_PROJECT_ID"
echo "  • Secrets configured: 6"
echo ""
print_info "Configured secrets:"
echo "  ✓ GCP_PROJECT_ID"
echo "  ✓ GCP_SA_KEY (base64 encoded)"
echo "  ✓ GOOGLE_CLIENT_ID"
echo "  ✓ GOOGLE_CLIENT_SECRET"
echo "  ✓ QR_CODE_SALT"
echo "  ✓ JWT_SECRET_KEY"
echo ""
print_info "Next steps:"
echo "  1. Verify secrets in GitHub repository settings"
echo "  2. Update GitHub Actions workflows to use these secrets"
echo "  3. Test the CI/CD pipeline"
echo ""
print_success "Done!"

