# CLEF - GCP Infrastructure with OpenTofu
# Main configuration file
#
# This file serves as the entry point for the Terraform configuration.
# The actual resources are defined in separate files:
# - providers.tf: Provider configuration
# - variables.tf: Input variables
# - outputs.tf: Output values
# - apis.tf: GCP API enablement
# - service_account.tf: Service account and IAM
# - valkey.tf: Valkey 8 instance on Compute Engine
#
# Usage:
#   tofu init
#   tofu plan -var-file=environments/dev.tfvars
#   tofu apply -var-file=environments/dev.tfvars

