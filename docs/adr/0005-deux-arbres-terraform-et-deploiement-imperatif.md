# ADR 0005 — Deux arbres Terraform divergents, déploiement Cloud Run impératif

**Statut :** 🗄️ **remplacé le 2026-08-26 par
[ADR 0008](0008-redis-sidecar-cloud-run-instantanes-gcs.md)** — **(reconstructed — verify)**

> Le constat de cet ADR était juste et reste utile comme archive : deux racines,
> aucune valide, un service Cloud Run créé impérativement. Ce qui a changé :
> **une racine unique** `deploy/terraform` qui valide, un **state distant** dans un
> bucket GCS versionné, et le service Cloud Run **déclaré** dans
> `deploy/cloudrun-api.yaml.tpl`. Une nuance a émergé à la fusion : les deux racines
> n'étaient pas *concurrentes* mais **complémentaires** — elles se disputaient
> seulement le même service account et les mêmes APIs.
**Date :** `infra/` daté du 2026-03-16, `backend/terraform/` du 2026-08-13

## Contexte

Reconstruit depuis le code. Le dépôt contient **deux racines Terraform
indépendantes, incompatibles, et aucune des deux ne valide.**

| | `infra/` | `backend/terraform/` |
|---|---|---|
| Outil | Terraform | OpenTofu |
| Provider google | `~> 5.0` (lock 5.45.2) | `7.23.0` exact (lock **6.50.0** — dérive) |
| Région | `europe-west1` | `europe-west9` |
| Provisionne | Cloud Run API, Artifact Registry, Memorystore **Redis** legacy, Secret Manager | KMS, Memorystore **for Valkey**, IAM Compute |
| État | local | local |
| Valide ? | ❌ non | ❌ non |

Les deux échouent à `tofu validate`, vérifié par exécution :

- `backend/terraform/outputs.tf:16,21` référence `google_compute_instance.valkey`,
  **ressource qui n'existe pas** — vestige d'un Valkey auto-hébergé sur Compute
  Engine remplacé par Memorystore, sans mise à jour des outputs.
- `infra/main.tf:167` référence `google_secret_manager_secret.okta_client_secret`,
  **jamais déclarée** — vestige de l'authentification Okta abandonnée
  (voir [ADR 0003](0003-session-sans-etat-token-google.md)).
- `backend/terraform/variables.tf` ne déclare pas `valkey_replica_count`,
  `valkey_node_type`, `valkey_version`, `valkey_zone_mode`, pourtant utilisées par
  `memorystore_valkey.tf`.

Et surtout : **le service Cloud Run n'est déclaré dans aucun des deux arbres.** Il
est créé impérativement par `gcloud run deploy` dans `.github/workflows/ci.yml`.
L'IaC ne décrit donc pas ce qui tourne.

## Décision (telle que constatée, non telle qu'elle devrait être)

`infra/` a été écrit d'abord, aligné avec `DEPLOYMENT.md` et `SECRETS_SETUP.md`.
`backend/terraform/` l'a ensuite partiellement remplacé pour la partie données et
chiffrement, sans que `infra/` soit supprimé ni que la documentation suive. Le
déploiement applicatif est resté impératif dans la CI.

`(inferred — verify)` — cette lecture repose uniquement sur les dates de fichiers,
les versions de provider et le fait que `backend/terraform/` corresponde au code qui
tourne (nommage KMS identique à `kms_service.py`). Aucun commit ne l'explique.

## Conséquences

- **Aucun `apply` n'est possible aujourd'hui** sans corriger les références mortes.
- **L'état est local** : pas de verrouillage, pas de partage, et il contient la clé
  privée du service account en clair (`outputs.tf` expose
  `base64decode(google_service_account_key.clef_backend.private_key)`).
  `infra/README.md` reconnaît lui-même le problème : *« For production use, consider
  using remote state »*.
- **Incohérence de région** entre le calcul (`europe-west1`) et sa base de données
  (`europe-west9`) : latence et coût de sortie inter-région.
- **`JWT_SECRET_KEY`** est documenté, déclaré dans `infra/main.tf`, et **absent** de
  la liste `--set-secrets` du déploiement Cloud Run : le service ne le reçoit jamais.
- La documentation de déploiement décrit le monde de `infra/` (`clef-cache`,
  `redis_7_0`), qui n'est **pas** ce qui tourne.

## Ce qu'il faut décider

1. Quel arbre est autoritaire ? Supprimer ou archiver l'autre.
2. Déclarer le service Cloud Run en IaC, ou assumer explicitement le déploiement
   impératif et le documenter comme tel.
3. Migrer l'état vers un backend GCS avec verrouillage.
4. Remplacer la clé de service account à longue durée par une fédération d'identité
   (Workload Identity Federation) — voir `docs/TODO.md`, sévérité élevée.
