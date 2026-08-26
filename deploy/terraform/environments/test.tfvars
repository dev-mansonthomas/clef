# Environnement test
project_id  = "rcq-fr-test"
environment = "test"

# Cloud Run, bucket d'instantanés et registre : alignés sur le reste du projet.
region = "europe-west1"

# Le keyring KMS existe en europe-west9 et ne peut pas être déplacé.
kms_region = "europe-west9"
