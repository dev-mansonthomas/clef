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

variable "memorystore_memory_gb" {
  description = "Memorystore memory size in GB"
  type        = number
  default     = 1
}

