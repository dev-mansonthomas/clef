# Secrets injectés dans Cloud Run.
#
# Terraform déclare les **conteneurs** de secrets, pas leurs valeurs : une valeur écrite
# ici finirait dans le state. Les versions sont poussées à la main ou par 00-infra.sh,
# qui signale les secrets encore vides.
#
# ⚠️ Les liaisons IAM d'infra/ référençaient `google_secret_manager_secret.okta_client_secret`,
# jamais déclaré — vestige de la migration Okta → Google OAuth. C'était la cause des
# 2 erreurs de `tofu validate` sur cette racine (constat H7).
# ⚠️ Les noms sont préfixés `CLEF_`, et ce n'est pas cosmétique.
#
# Le projet `rcq-fr-dev` est **partagé** : il héberge une autre application entière
# (rcq-api, rcq-frontend, dev-export-*, ul-queteur-*). Secret Manager étant un espace
# de noms au niveau du projet, un secret nommé `GOOGLE_CLIENT_ID` entrerait en
# collision avec celui du voisin — au mieux Terraform échouerait, au pire il
# adopterait et écraserait un secret qui ne lui appartient pas.
#
# Le nom de la **variable d'environnement** dans le conteneur reste `GOOGLE_CLIENT_ID`
# (c'est ce que lit `app/auth/config.py`) : seul le nom de la ressource change, et le
# gabarit Cloud Run fait la correspondance.
locals {
  secrets = {
    # OAuth Google, pour l'authentification des utilisateurs
    "CLEF_GOOGLE_CLIENT_ID"     = "CLEF — Client ID OAuth"
    "CLEF_GOOGLE_CLIENT_SECRET" = "CLEF — Client secret OAuth"
    # Sel du HMAC des QR codes véhicule. Le changer invalide tous les QR déjà imprimés.
    "CLEF_QR_CODE_SALT" = "CLEF — Sel HMAC de signature des QR codes véhicule"
    # ⚠️ Constat M11 : ce secret était déclaré et stocké, mais n'était PAS transmis au
    # service Cloud Run. 01-gcp-deploy.sh le passe désormais.
    "CLEF_JWT_SECRET_KEY" = "CLEF — Clé de signature des jetons applicatifs"
  }
}

resource "google_secret_manager_secret" "clef" {
  for_each = local.secrets

  secret_id = each.key
  project   = var.project_id

  # ⚠️ Réplication **explicite**, et non `auto {}`.
  #
  # `auto {}` place le secret dans l'emplacement `global`, que la policy
  # d'organisation `constraints/gcp.resourceLocations` interdit sur ce projet. Le
  # premier apply a échoué là-dessus, avec un message qui parle d'emplacement sans
  # jamais nommer `auto` — la cause n'est pas lisible dans l'erreur.
  #
  # Un seul réplica, dans la région du service : le secret n'est lu qu'au démarrage
  # du conteneur, et ce conteneur est lui-même mono-région. Un second réplica
  # n'ajouterait aucune disponibilité au chemin réel.
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    app         = "clef"
    environment = var.environment
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "backend_access" {
  for_each = local.secrets

  project   = var.project_id
  secret_id = google_secret_manager_secret.clef[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.clef_backend.email}"
}
