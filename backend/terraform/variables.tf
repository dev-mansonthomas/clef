variable "environment" {
  description = "Environment name (dev, test, prod)"
  type        = string
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west9"
}

variable "valkey_machine_type" {
  description = "Machine type for Valkey VM"
  type        = string
  default     = "e2-micro"
}

