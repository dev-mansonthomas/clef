resource "google_project_service" "apis" {
  for_each = toset([
    "sheets.googleapis.com",
    "drive.googleapis.com",
    "calendar-json.googleapis.com",
    "gmail.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
    "memorystore.googleapis.com",
    "networkconnectivity.googleapis.com",
  ])
  
  project = var.project_id
  service = each.key
  
  disable_on_destroy = false
}

