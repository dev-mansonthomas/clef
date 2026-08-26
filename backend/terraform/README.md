# ⚠️ Ancienne racine Terraform — PÉRIMÉE, ne pas utiliser

Remplacée le **2026-08-26** par **[`deploy/terraform/`](../../deploy/terraform/)** :
racine unique, qui valide, avec un state distant dans un bucket GCS versionné.

- Conception : [ADR 0008](../../docs/adr/0008-redis-sidecar-cloud-run-instantanes-gcs.md)
- Procédure : [`DEPLOYMENT.md`](../../DEPLOYMENT.md)
- Suppression prévue : constat **N12** de [`docs/TODO.md`](../../docs/TODO.md)

## Pourquoi ce dossier survit encore

1. Son `terraform.tfstate` **local** (gitignoré) porte les ressources réellement
   provisionnées — keyring KMS, service account. `00-infra.sh` l'**adopte** au
   premier lancement, sans quoi la nouvelle racine tenterait de recréer un keyring
   déjà en place et échouerait. Ne pas le supprimer avant cette adoption.
2. Il a servi le `tofu destroy` du Memorystore le 2026-08-26 ; ses fichiers ont été
   réparés pour cela (4 variables déclarées, 2 outputs morts retirés,
   `prevent_destroy` levé sur la seule instance Memorystore).

⚠️ Le state local **contient une clé privée de service account en clair**. Il est
gitignoré ; ne jamais le committer, ne jamais le copier hors de la machine.

`prevent_destroy` reste **volontairement** posé sur `kms.tf` et
`service_account.tf` : ces ressources sont adoptées par la nouvelle racine, les
détruire serait une perte sèche.
