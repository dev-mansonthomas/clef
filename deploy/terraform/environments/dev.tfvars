# Environnement dev
project_id  = "rcq-fr-dev"
environment = "dev"

# Cloud Run, bucket d'instantanés et registre : alignés sur le reste du projet.
region = "europe-west1"

# Le keyring KMS existe en europe-west9 et ne peut pas être déplacé.
kms_region = "europe-west9"

# Domaine public. Vide en test et prod tant qu'ils n'en ont pas.
# En production ce sera vraisemblablement clef.croix-rouge.fr.
public_domain = "clef.paquerette.com"
