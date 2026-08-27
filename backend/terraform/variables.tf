variable "environment" {
  description = "Environment name (dev, test, prod)"
  type        = string
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west9"
}

variable "valkey_machine_type" {
  description = "Machine type for Valkey VM"
  type        = string
  default     = "e2-micro"
}


# ---------------------------------------------------------------------------
# Variables de l'instance Memorystore
# ---------------------------------------------------------------------------
# Elles étaient utilisées par memorystore_redis.tf sans avoir jamais été déclarées :
# c'est l'une des deux causes de l'échec de `tofu validate` (constat H7). Déclarées ici
# pour que cette racine redevienne valide, ce qui est nécessaire à un `tofu destroy`.
#
# ⚠️ Cette racine est en voie de retrait : Redis passe en sidecar Cloud Run et la
# racine unique vit désormais dans deploy/terraform. Ne rien ajouter ici.

variable "valkey_replica_count" {
  description = "Nombre de répliques par shard"
  type        = number
  default     = 1
}

variable "valkey_node_type" {
  description = "Type de nœud Memorystore"
  type        = string
  default     = "SHARED_CORE_NANO"
}

variable "valkey_version" {
  description = "Version du moteur Memorystore"
  type        = string
  default     = "VALKEY_8_0"
}

variable "valkey_zone_mode" {
  description = "Distribution zonale : MULTI_ZONE ou SINGLE_ZONE"
  type        = string
  default     = "MULTI_ZONE"
}
