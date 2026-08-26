resource "google_artifact_registry_repository" "clef_images" {
  location      = var.region
  repository_id = "clef-images"
  description   = "Images de conteneurs CLEF (backend, frontend)"
  format        = "DOCKER"
  project       = var.project_id

  # Les images de révisions anciennes n'ont plus d'usage passé quelques semaines, et
  # Artifact Registry est facturé au stockage.
  cleanup_policies {
    id     = "supprimer-les-anciennes-versions"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 jours
    }
  }

  cleanup_policies {
    id     = "garder-les-cinq-dernieres"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }

  depends_on = [google_project_service.apis]
}
