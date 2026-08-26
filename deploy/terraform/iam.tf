# Identité d'exécution du backend.
#
# ⚠️ Aucune `google_service_account_key` ici, délibérément. Cloud Run s'exécute **sous**
# ce service account : les credentials viennent du serveur de métadonnées, et
# `app/services/google_credentials.py` les récupère par ADC. Une clé statique à longue
# durée était le mauvais patron pointé par le constat H6, et sa clé privée finissait en
# clair dans le fichier de state.
#
# Les feuilles Google et les dossiers Drive doivent être partagés avec l'adresse de ce
# service account — c'était déjà le cas avec une clé, l'identité étant la même.
resource "google_service_account" "clef_backend" {
  account_id   = "clef-backend"
  display_name = "CLEF Backend (${var.environment})"
  description  = "Identité d'exécution du backend CLEF sur Cloud Run"
  project      = var.project_id

  lifecycle {
    # Le détruire invaliderait tous les partages Drive et Sheets faits à son adresse,
    # et il faudrait les refaire un par un à la main.
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "backend_roles" {
  for_each = toset([
    # Déchiffrer les refresh tokens OAuth des gestionnaires DT (KMS).
    "roles/cloudkms.cryptoKeyEncrypterDecrypter",
    # Lire les secrets injectés dans Cloud Run.
    #
    # ⚠️ Reste au niveau projet, à dessein : `secretmanager.secretAccessor` ne donne
    # accès qu'aux secrets sur lesquels une liaison existe, et secrets.tf en pose une
    # par secret CLEF. C'est cette liaison par secret qui borne réellement la portée.
    "roles/secretmanager.secretAccessor",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.clef_backend.email}"
}

# L'ancienne racine nommait cette ressource `service_account_roles`. Sans ce bloc,
# Terraform verrait deux ressources distinctes et planifierait, pour le rôle commun
# `roles/cloudkms.cryptoKeyEncrypterDecrypter`, un destroy ET un create — sans
# dépendance entre les deux, donc dans un ordre arbitraire. Le create passant en
# premier serait un no-op (le membre est déjà lié), et le destroy qui suit retirerait
# la liaison : le backend perdrait l'accès à KMS, sans qu'aucune erreur ne le dise.
#
# `moved` fait reprendre les instances existantes sous la nouvelle adresse. Le rôle
# `roles/compute.instanceAdmin.v1`, absent du `for_each`, est alors simplement détruit
# — une seule opération, voulue : il n'a jamais servi (moindre privilège).
moved {
  from = google_project_iam_member.service_account_roles
  to   = google_project_iam_member.backend_roles
}
