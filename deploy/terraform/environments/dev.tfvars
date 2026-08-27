# Environnement dev
project_id  = "rcq-fr-dev"
environment = "dev"

# Cloud Run, bucket d'instantanés et registre : alignés sur le reste du projet.
region = "europe-west1"

# Le keyring KMS existe en europe-west9 et ne peut pas être déplacé.
kms_region = "europe-west9"
