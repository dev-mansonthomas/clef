# ⚠️ Racine en voie de retrait. Les outputs `valkey_host` et `valkey_internal_ip`
# ont été supprimés : ils référençaient un `google_compute_instance.valkey`
# inexistant — vestige d'une tentative Redis sur Compute Engine abandonnée au
# profit de Memorystore. C'est l'autre cause de l'échec de `tofu validate` (H7).

output "project_id" {
  value = var.project_id
}

output "service_account_email" {
  value = google_service_account.clef_backend.email
}

output "service_account_key" {
  value     = base64decode(google_service_account_key.clef_backend.private_key)
  sensitive = true
}

output "valkey_port" {
  description = "Valkey port"
  value       = 6379
}

output "kms_keyring_id" {
  value       = google_kms_key_ring.clef.id
  description = "KMS Keyring ID"
}

output "kms_crypto_key_id" {
  value       = google_kms_crypto_key.oauth_tokens.id
  description = "KMS Crypto Key ID for OAuth tokens"
}

