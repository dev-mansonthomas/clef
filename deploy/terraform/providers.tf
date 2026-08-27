# Racine Terraform UNIQUE de CLEF.
#
# Elle remplace deux racines qui coexistaient sans se recouvrir tout à fait :
#
#   backend/terraform/  → Memorystore, KMS, service account (+ CLÉ statique), APIs
#   infra/              → Artifact Registry, secrets, APIs Cloud Run
#
# Aucune des deux ne suffisait, et toutes deux déclaraient le même service account et
# les mêmes APIs : les appliquer ensemble se battait pour les mêmes ressources. Voir le
# constat H7 de docs/TODO.md.
#
# Ce qui a changé au passage :
#   • Memorystore disparaît — Redis 8.10 passe en sidecar Cloud Run (ADR 0008).
#   • Plus aucune `google_service_account_key` : Cloud Run s'exécute SOUS le service
#     account, sans clé (constat H6).
#   • Le state vit sur GCS, versionné et verrouillé, au lieu d'un fichier local
#     contenant une clé privée en clair.

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.23.0"
    }
  }

  # Le bucket est créé par 00-infra.sh avant le premier `init` : un backend ne peut pas
  # se provisionner lui-même. Le préfixe sépare les environnements dans un seul bucket.
  backend "gcs" {
    # bucket et prefix sont fournis par 00-infra.sh via -backend-config,
    # pour qu'un même code serve dev, test et prod.
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
