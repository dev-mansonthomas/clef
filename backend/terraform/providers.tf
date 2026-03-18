terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.23.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "2.7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

