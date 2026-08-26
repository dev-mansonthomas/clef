# Chiffrement des refresh tokens OAuth des gestionnaires DT
# (app/services/kms_service.py, consommé par dt_token_service).
#
# ⚠️ Les adresses de ces deux ressources sont **identiques** à celles de l'ancienne
# racine backend/terraform. C'est volontaire : 00-infra.sh adopte l'ancien state, et
# Terraform reconnaît alors le keyring et la clé déjà en place plutôt que de tenter
# d'en créer de nouveaux — ce qui échouerait, les noms étant pris.
resource "google_kms_key_ring" "clef" {
  name = "clef-${var.environment}-keyring"
  # ⚠️ `kms_region`, pas `region` : le keyring existe en europe-west9 et un keyring KMS
  # ne se déplace pas. Utiliser `region` ici ferait planifier un second keyring en
  # europe-west1, et le premier resterait à vie.
  location = var.kms_region
  project  = var.project_id

  lifecycle {
    # Un keyring KMS ne se supprime pas vraiment, et détruire la clé rendrait les
    # refresh tokens chiffrés **définitivement illisibles** : les gestionnaires DT
    # devraient tous reconsentir aux scopes Calendar, Drive et Gmail.
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_kms_crypto_key" "oauth_tokens" {
  name            = "oauth-tokens-key"
  key_ring        = google_kms_key_ring.clef.id
  rotation_period = "7776000s" # 90 jours

  purpose = "ENCRYPT_DECRYPT"

  version_template {
    algorithm = "GOOGLE_SYMMETRIC_ENCRYPTION"
  }

  lifecycle {
    prevent_destroy = true
  }
}
