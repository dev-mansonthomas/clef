# Bucket des instantanés Redis.
#
# Redis 8.10 tourne en sidecar du service Cloud Run et écrit son dump RDB ici, monté
# par Cloud Storage FUSE. C'est ce qui rend la donnée durable alors que l'instance
# Cloud Run est éphémère.
#
# Pourquoi GCS plutôt que Filestore : la décision « pas d'AOF » fait que les seules
# écritures sont des dumps complets — le motif d'accès que FUSE gère correctement,
# contrairement aux appends. Et Filestore facture un minimum de 1 TiB là où ce jeu de
# données pèse quelques mégaoctets.
#
# ⚠️ Le RPO est de 10 minutes. Voir l'ADR 0008 : les dossiers de réparation, devis,
# factures, réservations et le carnet de bord n'existent QUE dans Redis.
resource "google_storage_bucket" "redis_snapshots" {
  name     = "${var.project_id}-clef-redis-snapshots"
  location = var.region
  project  = var.project_id

  # Le dump porte toujours le même nom : sans versionnement, un instantané corrompu
  # écraserait le dernier bon état sans recours.
  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      days_since_noncurrent_time = var.snapshot_retention_days
    }
    action {
      type = "Delete"
    }
  }

  # Ces instantanés contiennent des données personnelles de bénévoles : jamais public,
  # et accès uniformément géré par IAM.
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle {
    # Détruire ce bucket, c'est perdre la totalité des données de CLEF.
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}
