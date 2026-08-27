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

# Droit d'écriture sur CE bucket, et sur lui seul.
#
# ⚠️ Ce rôle était d'abord accordé au niveau **projet**, dans iam.tf. Le projet
# `rcq-fr-dev` étant partagé avec une autre application entière, cela donnait au
# backend CLEF le droit de lire, écrire et **supprimer** les objets de tous ses
# buckets. Le besoin réel est ce seul bucket : la liaison est donc portée par la
# ressource, pas par le projet.
#
# `objectAdmin` et non `objectCreator` : gcsfuse doit lister, lire, écrire et
# remplacer `dump.rdb` — Redis écrit un fichier temporaire puis le renomme, ce qui
# sur un stockage objet est un copier-supprimer.
resource "google_storage_bucket_iam_member" "backend_snapshots" {
  bucket = google_storage_bucket.redis_snapshots.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.clef_backend.email}"
}
