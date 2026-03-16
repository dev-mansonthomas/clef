# Valkey 8 on Compute Engine with Container-Optimized OS
resource "google_compute_instance" "valkey" {
  name         = "clef-valkey-${var.environment}"
  machine_type = var.valkey_machine_type
  zone         = "${var.region}-b"
  project      = var.project_id

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 20
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }

  metadata = {
    gce-container-declaration = yamlencode({
      spec = {
        containers = [{
          image = "valkey/valkey:8"
          name  = "valkey"
          ports = [{ containerPort = 6379 }]
          volumeMounts = [{
            name      = "valkey-data"
            mountPath = "/data"
          }]
          args = [
            "--appendonly", "yes",
            "--appendfsync", "everysec",
            "--save", "3600", "1",
            "--save", "300", "100"
          ]
        }]
        volumes = [{
          name = "valkey-data"
          hostPath = { path = "/var/valkey-data" }
        }]
        restartPolicy = "Always"
      }
    })
  }

  service_account {
    email  = google_service_account.clef_backend.email
    scopes = ["cloud-platform"]
  }

  tags = ["valkey", "clef"]

  lifecycle {
    prevent_destroy = true
  }

  labels = {
    environment = var.environment
    app         = "clef"
  }

  depends_on = [google_project_service.apis]
}

# Firewall rule for Valkey
resource "google_compute_firewall" "valkey" {
  name    = "clef-valkey-${var.environment}"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["6379"]
  }

  # Dev: Allow all. Prod: Internal only
  source_ranges = var.environment == "prod" ? ["10.0.0.0/8"] : ["0.0.0.0/0"]
  target_tags   = ["valkey"]
}

