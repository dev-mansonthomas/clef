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

  # `prevent_destroy` a été retiré le 2026-08-26, délibérément.
  #
  # C'était un garde-fou légitime tant que Memorystore était le datastore principal.
  # Il ne l'est plus : Memorystore ne sait pas chercher dans le JSON, et CLEF passe à
  # Redis 8.10 en sidecar Cloud Run avec instantanés sur GCS (voir l'ADR sur le
  # datastore). Cette instance est donc mise hors service, et cette racine entière est
  # remplacée par deploy/terraform.
  #
  # ⚠️ Ne pas réintroduire ce bloc ici : reposer un garde-fou sur une ressource qu'on
  # veut détruire ne protège plus rien, il masque juste l'intention.

  depends_on = [
    google_project_service.apis,
    google_network_connectivity_service_connection_policy.memorystore
  ]
}

