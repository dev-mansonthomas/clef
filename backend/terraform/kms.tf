# Keyring pour CLEF
resource "google_kms_key_ring" "clef" {
  name     = "clef-${var.environment}-keyring"
  location = var.region
  
  depends_on = [google_project_service.apis]
}

# Clé pour chiffrer les tokens OAuth
resource "google_kms_crypto_key" "oauth_tokens" {
  name            = "oauth-tokens-key"
  key_ring        = google_kms_key_ring.clef.id
  rotation_period = "7776000s"  # 90 jours
  
  purpose = "ENCRYPT_DECRYPT"
  
  version_template {
    algorithm = "GOOGLE_SYMMETRIC_ENCRYPTION"
  }
  
  lifecycle {
    prevent_destroy = true
  }
}

