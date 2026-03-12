resource "google_project_service" "apis" {
  for_each = toset([
    "sheets.googleapis.com",
    "drive.googleapis.com",
    "calendar-json.googleapis.com",
    "gmail.googleapis.com",
    "redis.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])
  
  project = var.project_id
  service = each.key
  
  disable_on_destroy = false
}

