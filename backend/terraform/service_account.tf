resource "google_service_account" "clef_backend" {
  account_id   = "clef-backend"
  display_name = "CLEF Backend Service Account"
  project      = var.project_id

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_service_account_key" "clef_backend" {
  service_account_id = google_service_account.clef_backend.name
}

# IAM roles for the service account
resource "google_project_iam_member" "service_account_roles" {
  for_each = toset([
    "roles/redis.editor",
  ])
  
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.clef_backend.email}"
}

