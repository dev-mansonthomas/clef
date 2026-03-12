resource "google_redis_instance" "clef_cache" {
  name           = "clef-cache-${var.environment}"
  project        = var.project_id
  region         = var.region  # europe-west9
  
  # STANDARD_HA = Multi-zone with replica
  tier           = "STANDARD_HA"
  
  # Shared core / small instance
  memory_size_gb = var.memorystore_memory_gb
  
  # Replica configuration (1 replica per shard)
  replica_count      = 1
  read_replicas_mode = "READ_REPLICAS_ENABLED"
  
  # Redis version (closest to Valkey)
  redis_version = "REDIS_7_0"
  
  # RDB persistence - hourly snapshots
  persistence_config {
    persistence_mode    = "RDB"
    rdb_snapshot_period = "ONE_HOUR"
  }
  
  # Maintenance window for backups (4-5 AM Sunday)
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 4
        minutes = 0
      }
    }
  }
  
  # Labels
  labels = {
    environment = var.environment
    app         = "clef"
  }
  
  depends_on = [google_project_service.apis]
}

