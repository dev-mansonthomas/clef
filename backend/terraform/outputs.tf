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

output "valkey_host" {
  description = "Valkey VM external IP"
  value       = google_compute_instance.valkey.network_interface[0].access_config[0].nat_ip
}

output "valkey_internal_ip" {
  description = "Valkey VM internal IP (for use within GCP)"
  value       = google_compute_instance.valkey.network_interface[0].network_ip
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

