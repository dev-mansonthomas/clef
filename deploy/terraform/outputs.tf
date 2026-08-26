# ⚠️ Aucun output ne porte de secret.
#
# L'ancienne racine exposait `service_account_key` en base64 décodé — donc une clé
# privée en clair, dans le state comme dans la sortie de `tofu output` (constat H6).
# Il n'y a plus de clé du tout : Cloud Run s'exécute sous le service account.

output "project_id" {
  description = "Projet GCP"
  value       = var.project_id
}

output "region" {
  description = "Région de toutes les ressources"
  value       = var.region
}

output "service_account_email" {
  description = <<-EOT
    Adresse du service account d'exécution.

    C'est cette adresse qui doit avoir accès aux feuilles Google et aux dossiers Drive :
    les partager avec elle, comme avec un utilisateur.
  EOT
  value       = google_service_account.clef_backend.email
}

output "artifact_registry" {
  description = "Dépôt d'images, à préfixer aux tags poussés"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.clef_images.repository_id}"
}

output "redis_snapshots_bucket" {
  description = "Bucket des instantanés Redis, monté par le sidecar"
  value       = google_storage_bucket.redis_snapshots.name
}

output "kms_crypto_key_id" {
  description = "Clé KMS de chiffrement des refresh tokens OAuth"
  value       = google_kms_crypto_key.oauth_tokens.id
}

output "secrets_a_renseigner" {
  description = <<-EOT
    Secrets déclarés sans valeur.

    Terraform crée les conteneurs, jamais les valeurs — une valeur passée ici finirait
    dans le state. 00-infra.sh signale ceux qui sont encore vides.
  EOT
  value       = keys(google_secret_manager_secret.clef)
}
