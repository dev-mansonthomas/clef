# Union des APIs des deux anciennes racines, moins celles devenues inutiles.
#
# Retirées : memorystore.googleapis.com et networkconnectivity.googleapis.com — Redis
# passe en sidecar Cloud Run, il n'y a plus d'instance managée ni de Private Service
# Connect à provisionner. redis.googleapis.com, que déclarait infra/, n'a jamais servi.
resource "google_project_service" "apis" {
  for_each = toset([
    # Exécution
    "run.googleapis.com",
    # ⚠️ Requise par le load balancer : adresse globale, NEG, url map, proxies,
    # certificat managé sont tous des ressources Compute. Elle avait été retirée
    # avec Memorystore — elle est de retour pour cette raison, pas par inadvertance.
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "storage.googleapis.com",

    # Google Workspace, consommé par le backend
    "sheets.googleapis.com",
    "drive.googleapis.com",
    "calendar-json.googleapis.com",
    "gmail.googleapis.com",

    # Sécurité et plateforme
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  project = var.project_id
  service = each.key

  # Ne pas désactiver l'API à la destruction : d'autres ressources du projet peuvent en
  # dépendre, et une désactivation est bien plus large qu'un `terraform destroy`.
  disable_on_destroy = false
}
