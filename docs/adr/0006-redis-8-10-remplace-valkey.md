# ADR 0006 — Redis 8.10 remplace Valkey 8 comme datastore

**Statut :** accepté
**Date de la décision :** 2026-08-13
**Remplace :** [ADR 0001 — Valkey 8 (bundle JSON) comme datastore principal](0001-valkey-8-comme-datastore-principal.md)

## Contexte

L'[ADR 0001](0001-valkey-8-comme-datastore-principal.md) actait `valkey/valkey-bundle:8`
comme datastore, en remplacement de Redis, le 2026-03-13. Le *pourquoi* n'avait pas
été consigné ; l'hypothèse la plus plausible relevée à l'époque était le changement
de licence de Redis 7.4 (RSALv2/SSPL), qui avait motivé la création du fork Valkey.

Deux faits ont changé depuis :

1. **Redis 8.0 est publié sous AGPLv3**, une licence open source approuvée par l'OSI.
   La raison de licence qui justifiait le fork ne s'applique plus à ce projet.
2. **L'image officielle `redis:8.10` embarque les modules** dont CLEF dépend. Vérifié
   par exécution le 2026-08-13 :

   ```
   redis_version:8.10.0
   MODULE LIST → ReJSON 81000, search 81000, timeseries 81000, bf 81000, vectorset 1
   JSON.SET / JSON.GET / FT.CREATE ON JSON → OK
   ```

   Il n'y a donc pas d'équivalent à chercher du côté d'un « bundle » : le module JSON,
   dépendance dure de `RedisService`, est fourni par l'image de base.

## Décision

Le datastore de CLEF est **Redis 8.10**, via l'image officielle `redis:8.10`.

Le remplacement porte aussi sur le **vocabulaire du code** : `ValkeyService` devient
`RedisService`, `valkey_service.py` → `redis_service.py`, `valkey_models.py` →
`redis_models.py`, `valkey_dependencies.py` → `redis_dependencies.py`,
`reservations_valkey.py` → `reservations_store.py`, `ValkeyReservation*` →
`RedisReservation*`. Un nom de datastore inexact dans 600+ identifiants est un coût
de compréhension permanent pour tout agent ou humain qui arrive sur le dépôt.

## Conséquences

**Acquis, vérifiés par exécution :**

- Le client Python `redis==5.2.0` fonctionne **inchangé** contre Redis 8.10 : aucune
  adaptation du code d'accès aux données.
- La suite backend donne **exactement le même résultat** qu'avec Valkey. Mesuré à
  périmètre de tests constant, avant les ajouts du chantier : `8 failed, 360 passed`
  dans les deux cas — les 8 échecs étant les fixtures CSV perdues (H2), sans rapport
  avec le datastore. L'état final de la suite est `410 passed, 1 skipped`.
- Le healthcheck passe de `valkey-cli ping` à `redis-cli ping` ; `redis-cli` est
  présent dans l'image.
- `test_datastore.py` garde la décision : il assert `redis_version` en `8.x`, ce qui
  **échoue** contre `valkey/valkey-bundle:8` (lequel annonce `redis_version:7.2.4`
  et `valkey_version:8.1.9`).

**Différence de nommage à connaître :** le module JSON s'appelle `ReJSON` chez Redis
et `json` chez Valkey. `test_datastore_loads_json_module` accepte les deux noms : la
garde « Redis et non Valkey » est portée par le test de version, pas par celui du
module.

**Reste ouvert — hors périmètre de cette décision :**

- **Le déploiement GCP.** `backend/terraform/memorystore_redis.tf` (renommé, contenu
  inchangé) provisionne toujours un `google_memorystore_instance` en mode **Valkey**.
  Le choix de la cible de production — Memorystore for Redis, Redis dans Cloud Run,
  ou autre — n'est pas tranché ici. Voir [ADR 0005](0005-deux-arbres-terraform-et-deploiement-imperatif.md)
  et `docs/TODO.md` H7/N1.
- **`backend/scripts/setup_gcp.sh`** lit encore des sorties Terraform nommées
  `valkey_host` / `valkey_port`. Ces noms appartiennent à l'arbre Terraform, non
  touché : les renommer sans lui casserait le script.
- **Le module Search reste inutilisé** (`docs/TODO.md` M25) : aucun `FT.CREATE` dans
  le code. L'image le fournit sans coût ; rien à décider.
- **La montée du client `redis` en 7.x** n'a pas été mesurée et fait l'objet d'un
  chantier séparé.

## Alternatives écartées

- **Rester sur Valkey.** Fonctionne, mais impose de suivre un fork dont la raison
  d'être — la licence — ne s'applique plus, et laisse le nommage du code désaligné de
  la cible de déploiement la plus probable (Memorystore for Redis).
- **Swap runtime sans renommer le code.** Diff minimal, mais le dépôt aurait continué
  de désigner son datastore par un nom faux dans plus de 600 identifiants. La revue de
  ce renommage est aisée : il est mécanique, isolé, et les quatre suites de tests
  encadrent le changement.
