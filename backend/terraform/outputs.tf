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

output "memorystore_host" {
  value = google_redis_instance.clef_cache.host
}

output "memorystore_port" {
  value = google_redis_instance.clef_cache.port
}

