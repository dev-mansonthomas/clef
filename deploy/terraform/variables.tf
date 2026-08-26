variable "project_id" {
  description = "Identifiant du projet GCP (ex. rcq-fr-dev)"
  type        = string
}

variable "environment" {
  description = "Nom de l'environnement : dev, test ou prod"
  type        = string

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment doit valoir dev, test ou prod."
  }
}

variable "region" {
  description = <<-EOT
    Région de Cloud Run, du bucket d'instantanés et du registre d'images.

    `europe-west1` : c'est là que vit tout le reste du projet `rcq-fr-dev`, partagé
    avec une autre application (rcq-api, rcq-frontend, dev-export-*). Un opérateur
    trouve ainsi toutes les ressources au même endroit.

    Le bucket d'instantanés doit impérativement partager cette région : il est monté
    par le service Cloud Run et lu ou écrit en permanence.
  EOT
  type        = string
  default     = "europe-west1"
}

variable "kms_region" {
  description = <<-EOT
    Région du keyring KMS — **différente** de `region`, volontairement.

    Le keyring `clef-<env>-keyring` existe déjà en europe-west9, et un keyring KMS ne
    peut ni se déplacer ni se supprimer. Le déclarer ailleurs ferait planifier la
    création d'un second keyring, et l'ancien resterait à vie.

    L'écart est sans conséquence pratique : KMS n'est appelé que pour déchiffrer les
    refresh tokens OAuth des gestionnaires DT, jamais sur le chemin des requêtes. Le
    surcoût est de quelques millisecondes, à l'ouverture de session seulement.

    C'est la résolution assumée du constat M12 : une incohérence subie devient un
    écart documenté.
  EOT
  type        = string
  default     = "europe-west9"
}

variable "service_name" {
  description = "Nom du service Cloud Run portant le backend et son sidecar Redis"
  type        = string
  default     = "clef-api"
}

variable "frontend_service_name" {
  description = "Nom du service Cloud Run portant les deux applications Angular"
  type        = string
  default     = "clef-frontend"
}

variable "snapshot_retention_days" {
  description = <<-EOT
    Rétention des instantanés Redis dans le bucket, en jours.

    Les instantanés sont écrasés toutes les 10 minutes ; le versionnement du bucket
    conserve les précédents. Cette durée borne cet historique — c'est la profondeur de
    retour arrière disponible en cas de corruption non détectée immédiatement.
  EOT
  type        = number
  default     = 30
}
