# Service Connection Policy required for Memorystore for Valkey
resource "google_network_connectivity_service_connection_policy" "memorystore" {
  name          = "clef-memorystore-${var.environment}"
  location      = var.region
  service_class = "gcp-memorystore"
  description   = "Service Connection Policy for CLEF Memorystore Valkey"
  network       = "projects/${var.project_id}/global/networks/default"
  project       = var.project_id

  psc_config {
    subnetworks = ["projects/${var.project_id}/regions/${var.region}/subnetworks/default"]
  }

  depends_on = [google_project_service.apis]
}

# Memorystore for Valkey (managed service)
resource "google_memorystore_instance" "clef_valkey" {
  instance_id                 = "clef-valkey-${var.environment}"
  location                    = var.region
  shard_count                 = 1
  replica_count               = var.valkey_replica_count
  node_type                   = var.valkey_node_type
  engine_version              = var.valkey_version
  deletion_protection_enabled = var.environment == "prod" ? true : false
  mode                        = "CLUSTER_DISABLED"

  # Persistence - AOF
  persistence_config {
    mode = "AOF"
    aof_config {
      append_fsync = "EVERY_SEC"
    }
  }

  # Maintenance window (4-5 AM Sunday)
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 4
        minutes = 0
      }
    }
  }

  # Zone distribution
  zone_distribution_config {
    mode = var.valkey_zone_mode
  }

  # Network - auto-create endpoints in default VPC
  desired_auto_created_endpoints {
    network    = "projects/${var.project_id}/global/networks/default"
    project_id = var.project_id
  }

  # Labels
  labels = {
    environment = var.environment
    app         = "clef"
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    google_project_service.apis,
    google_network_connectivity_service_connection_policy.memorystore
  ]
}

