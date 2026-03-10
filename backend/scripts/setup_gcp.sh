#!/bin/bash

# CLEF - GCP Setup Script
# Automates GCP project configuration with gcloud CLI
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

print_info "Setting up GCP for environment: $ENV"
print_info "GCP Project: $PROJECT_ID"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI not found. Please install it first:"
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    print_error "Not authenticated with gcloud. Please run:"
    echo "gcloud auth login"
    exit 1
fi

print_success "gcloud CLI found and authenticated"

# Step 1: Set active project
print_info "Step 1/7: Setting active GCP project..."
gcloud config set project $PROJECT_ID
print_success "Active project set to $PROJECT_ID"
echo ""

# Step 2: Enable required APIs
print_info "Step 2/7: Enabling required APIs..."
APIS=(
    "run.googleapis.com"
    "artifactregistry.googleapis.com"
    "redis.googleapis.com"
    "sheets.googleapis.com"
    "drive.googleapis.com"
    "calendar.googleapis.com"
    "gmail.googleapis.com"
    "secretmanager.googleapis.com"
    "iam.googleapis.com"
)

for API in "${APIS[@]}"; do
    print_info "  Enabling $API..."
    gcloud services enable $API --project=$PROJECT_ID
done
print_success "All APIs enabled"
echo ""

# Step 3: Create Service Account
SERVICE_ACCOUNT_NAME="clef-backend"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

print_info "Step 3/7: Creating Service Account..."
if gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID &> /dev/null; then
    print_warning "Service Account $SERVICE_ACCOUNT_EMAIL already exists"
else
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="CLEF Backend Service Account" \
        --description="Service account for CLEF application backend" \
        --project=$PROJECT_ID
    print_success "Service Account created: $SERVICE_ACCOUNT_EMAIL"
fi
echo ""

# Step 4: Assign IAM roles
print_info "Step 4/7: Assigning IAM roles to Service Account..."
ROLES=(
    "roles/run.admin"
    "roles/artifactregistry.writer"
    "roles/redis.editor"
    "roles/secretmanager.secretAccessor"
    "roles/iam.serviceAccountUser"
)

for ROLE in "${ROLES[@]}"; do
    print_info "  Assigning $ROLE..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$ROLE" \
        --condition=None \
        --quiet
done
print_success "IAM roles assigned"
echo ""

# Step 5: Generate Service Account Key
print_info "Step 5/7: Generating Service Account JSON key..."
KEY_FILE="clef-backend-${ENV}-key.json"

if [ -f "$KEY_FILE" ]; then
    print_warning "Key file $KEY_FILE already exists"
    read -p "Do you want to generate a new key? This will overwrite the existing file. (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping key generation"
    else
        gcloud iam service-accounts keys create $KEY_FILE \
            --iam-account=$SERVICE_ACCOUNT_EMAIL \
            --project=$PROJECT_ID
        print_success "New key generated: $KEY_FILE"
        print_warning "IMPORTANT: Store this key securely and never commit it to version control!"
    fi
else
    read -p "Generate Service Account JSON key? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        gcloud iam service-accounts keys create $KEY_FILE \
            --iam-account=$SERVICE_ACCOUNT_EMAIL \
            --project=$PROJECT_ID
        print_success "Key generated: $KEY_FILE"
        print_warning "IMPORTANT: Store this key securely and never commit it to version control!"
    else
        print_info "Skipping key generation"
    fi
fi
echo ""

# Step 6: Create Artifact Registry repository
print_info "Step 6/7: Creating Artifact Registry repository..."
REPO_NAME="clef-images"
REGION="europe-west1"

if gcloud artifacts repositories describe $REPO_NAME \
    --location=$REGION \
    --project=$PROJECT_ID &> /dev/null; then
    print_warning "Artifact Registry repository $REPO_NAME already exists"
else
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="CLEF container images" \
        --project=$PROJECT_ID
    print_success "Artifact Registry repository created: $REPO_NAME"
fi
echo ""

# Step 7: Optional - Create Secret Manager secrets
print_info "Step 7/7: Secret Manager setup (optional)..."
read -p "Do you want to create Secret Manager secrets now? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Creating Secret Manager secrets..."

    # List of secrets to create
    SECRETS=(
        "OKTA_CLIENT_ID"
        "OKTA_CLIENT_SECRET"
        "QR_CODE_SALT"
        "JWT_SECRET_KEY"
    )

    for SECRET in "${SECRETS[@]}"; do
        if gcloud secrets describe $SECRET --project=$PROJECT_ID &> /dev/null; then
            print_warning "  Secret $SECRET already exists"
        else
            print_info "  Creating secret: $SECRET"
            echo -n "Enter value for $SECRET: "
            read -s SECRET_VALUE
            echo
            echo -n "$SECRET_VALUE" | gcloud secrets create $SECRET \
                --data-file=- \
                --replication-policy="automatic" \
                --project=$PROJECT_ID

            # Grant access to service account
            gcloud secrets add-iam-policy-binding $SECRET \
                --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
                --role="roles/secretmanager.secretAccessor" \
                --project=$PROJECT_ID \
                --quiet

            print_success "  Secret $SECRET created and access granted"
        fi
    done
else
    print_info "Skipping Secret Manager setup"
    print_info "You can create secrets later using the commands in SECRETS_SETUP.md"
fi
echo ""

# Generate partial .env file
print_info "Generating partial .env.$ENV file..."
ENV_FILE=".env.$ENV"

cat > $ENV_FILE << EOF
# CLEF - Environment Configuration for $ENV
# Generated by setup_gcp.sh on $(date)

# GCP Configuration
GCP_PROJECT_ID=$PROJECT_ID
GCP_REGION=europe-west1
GCP_SERVICE_ACCOUNT_EMAIL=$SERVICE_ACCOUNT_EMAIL

# Service Account Key Path (update with actual path)
GOOGLE_APPLICATION_CREDENTIALS=./clef-backend-${ENV}-key.json

# Redis (MemoryStore)
# Update with actual MemoryStore instance IP after creation
REDIS_URL=redis://localhost:6379/0

# Okta Configuration (update with actual values)
OKTA_DOMAIN=your-domain.okta.com
OKTA_CLIENT_ID=your-client-id
OKTA_CLIENT_SECRET=your-client-secret
OKTA_REDIRECT_URI=https://admin.clef.example.com/auth/callback

# Email Configuration
EMAIL_GESTIONNAIRE_DT=thomas.manson@croix-rouge.fr
EMAIL_DESTINATAIRE_ALERTES=Magalie.WERNER@s2hgroup.com

# Google Sheets URLs (update with actual URLs)
SHEETS_URL_VEHICULES=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID
SHEETS_URL_BENEVOLES=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID
SHEETS_URL_RESPONSABLES=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID

# Application Configuration
ENVIRONMENT=$ENV
DOMAIN=clef.example.com
USE_MOCKS=false
EOF

print_success "Environment file created: $ENV_FILE"
print_warning "Please update the placeholder values in $ENV_FILE"
echo ""

# Summary
print_success "========================================="
print_success "GCP Setup Complete for $ENV environment!"
print_success "========================================="
echo ""
print_info "Summary:"
echo "  • Project: $PROJECT_ID"
echo "  • Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "  • Artifact Registry: $REGION/$REPO_NAME"
if [ -f "$KEY_FILE" ]; then
    echo "  • Key File: $KEY_FILE"
fi
echo "  • Environment File: $ENV_FILE"
echo ""
print_info "Next steps:"
echo "  1. Review and update $ENV_FILE with actual values"
echo "  2. Store the service account key securely"
echo "  3. Create MemoryStore Redis instance (see DEPLOYMENT.md)"
echo "  4. Configure Okta application (see DEPLOYMENT.md)"
echo "  5. Share Google Sheets with the service account"
echo ""
print_info "For more information, see DEPLOYMENT.md and SECRETS_SETUP.md"

