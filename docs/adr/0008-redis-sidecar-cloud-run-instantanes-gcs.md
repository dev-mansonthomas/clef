# ADR 0008 — Redis en sidecar Cloud Run, instantanés sur GCS

**Statut :** accepté
**Date de la décision :** 2026-08-26
**Complète :** [ADR 0006 — Redis 8.10 remplace Valkey 8](0006-redis-8-10-remplace-valkey.md)

## Contexte

L'[ADR 0006](0006-redis-8-10-remplace-valkey.md) actait Redis 8.10 comme datastore mais
laissait la cible de production ouverte. L'infrastructure existante provisionnait un
**Memorystore for Valkey** en `europe-west9`, réellement déployé et facturé.

Deux éléments ont tranché :

1. **Memorystore ne sait pas chercher dans le JSON**, y compris dans ses versions
   Valkey les plus récentes (constat du propriétaire, Redis Solution Architect). CLEF
   n'utilise aujourd'hui que `JSON.SET`/`JSON.GET` — aucun `FT.CREATE` dans le code
   (constat M25) — mais s'enfermer dans un service incapable de recherche JSON était
   un cul-de-sac.
2. Redis est ici la **base de données principale** (ADR 0002), pas un cache. Les
   dossiers de réparation, devis, factures, réservations et le carnet de bord n'existent
   **que** dans Redis.

## Décision

**Redis 8.10 tourne en conteneur sidecar du service Cloud Run du backend**, avec
instantanés RDB toutes les 10 minutes sur un bucket GCS monté par Cloud Storage FUSE.

### Pourquoi un sidecar et pas un service

Cloud Run ne route que du HTTP et du gRPC : les ports d'un service se déclarent `http1`
ou `h2c`. Redis parle RESP, un protocole TCP brut — il **ne peut pas** être exposé comme
un service Cloud Run distinct. La seule topologie possible est deux conteneurs dans le
même service, communiquant par `localhost`.

### Pourquoi GCS et pas Filestore

La décision « pas d'AOF » découle du support : les appends sur un système de fichiers
objet n'offrent pas les garanties de `fsync` qu'exige un journal. Les seules écritures
sont donc des **dumps RDB complets** — précisément le motif d'accès que FUSE gère
correctement. Et Filestore facture un minimum de **1 TiB** là où ce jeu de données pèse
quelques mégaoctets.

## Conséquences

### Trois contraintes structurelles, non négociables

**`maxScale = 1`.** Chaque instance a son propre Redis. Deux instances, ce sont deux
jeux de données qui divergent **sans aucun signal** — pas d'erreur, pas de log, juste
des utilisateurs qui voient des données différentes selon l'instance qui les sert.
C'est plus grave que la perte de données, parce qu'invisible. `01-gcp-deploy.sh` refuse
toute autre valeur.

**CPU allouée en permanence** (`run.googleapis.com/cpu-throttling: "false"`). Cloud Run
bride le CPU entre deux requêtes ; l'instantané périodique étant une tâche de fond, il
ne s'exécuterait **jamais** avec le réglage par défaut. Snapshots configurés, bucket
vide : la durabilité annoncée serait fictive.

**`gen2`**, requis pour monter un volume GCS.

### Le RPO passe de 1 seconde à 10 minutes

C'est la contrepartie assumée, et elle mérite d'être écrite en clair. Memorystore était
configuré en AOF `EVERY_SEC` : perte maximale d'une seconde. Avec des instantanés toutes
les 10 minutes, une panne peut coûter **jusqu'à 10 minutes de saisie** sur des données
qui n'existent nulle part ailleurs.

Ce qui atténue, sans l'annuler :

- Redis fait un **dernier instantané sur SIGTERM**. Lors d'un arrêt propre — un
  redéploiement, une mise en veille — la perte réelle est nulle. Les 10 minutes sont le
  pire cas : un crash ou une interruption brutale.
- Une seconde fenêtre `save 120 100` capture plus vite les rafales d'écritures.
- Le bucket est **versionné** : un instantané corrompu n'écrase pas définitivement le
  dernier bon état.

À l'échelle d'une délégation — quelques dizaines de véhicules et de bénévoles — c'est
un arbitrage défendable. Il ne le resterait pas à une autre échelle.

### `minInstances = 1` en dev depuis le 2026-08-29 — et pas pour le RPO

Ce paragraphe disait : « `minInstances = 0` : chaque réveil repart du dernier
instantané, donc perd jusqu'à 10 minutes à **chaque mise en veille** ». C'était en
contradiction avec le paragraphe ci-dessus, et c'est le paragraphe ci-dessus qui a
raison : Redis écrit son instantané final sur SIGTERM, une mise en veille ne perd
**rien**. Mesuré le 2026-08-28 — `Saving the final RDB snapshot before exiting`,
`BGSAVE done, 21 keys saved`, `DB saved on disk` — en 400 ms.

La décision de passer à `minInstances = 1` a donc une **autre** cause, découverte le
même jour : **le montage du volume GCS est une dépendance dure du démarrage, et il
peut échouer.**

```
23:20:30  Starting new instance. Reason: AUTOSCALING
23:20:30  GetStorageLayout for "…/clef-redis-snapshots/storageLayout" failed:
          rpc error: code = Unimplemented desc = this function is not implemented
23:20:32  terminated: Application failed to run:
          volume (type: gcs, name: snapshots): mount operation failed
```

L'appelant — la synchronisation Apps Script du référentiel bénévoles — a reçu un 503
après 9,8 s. La même révision avait monté ce volume sans problème 50 minutes plus tôt,
et l'a remonté sans problème ensuite : le montage est **intermittent**, et chaque
réveil rejoue le tirage. Avec une instance permanente, il n'a lieu qu'au déploiement.

Contrepartie assumée : facturation continue d'une instance. À l'échelle d'un dev de
délégation, c'est quelques euros par mois contre une synchronisation horaire fiable.

Deux mesures complémentaires, côté appelant : l'Apps Script réveille l'API sur
`/health` avant d'envoyer son lot, et réessaie les 5xx. Un 503 de démarrage à froid est
un état normal d'un service en scale-to-zero — il doit être réessayé, pas rapporté.

⚠️ Le vrai correctif de fond reste à trouver : le bucket est à espace de noms **plat**
(`hierarchicalNamespace.enabled` vide), et l'appel qui échoue sert à détecter le
contraire. Une option de montage devrait pouvoir le court-circuiter — à vérifier dans
la documentation gcsfuse plutôt qu'à supposer.

### Ce que la décision a permis de fermer

- **H6** — plus aucune `google_service_account_key`. Cloud Run s'exécute **sous** le
  service account ; `app/services/google_credentials.py` récupère l'identité par ADC.
  La clé privée ne traîne plus en clair dans le state.
- **H7** — une racine Terraform unique et valide (`deploy/terraform`), fusion de
  `backend/terraform` et `infra/` qui étaient complémentaires et se disputaient le même
  service account.
- **M12** — l'incohérence de région devient un écart **documenté** : Cloud Run, bucket
  et registre en `europe-west1` avec le reste du projet ; le keyring KMS reste en
  `europe-west9`, où il existe déjà et d'où il ne peut pas être déplacé.

### Ce que la décision impose de savoir

Le projet `rcq-fr-dev` est **partagé** avec une autre application entière (`rcq-api`,
`rcq-frontend`, `dev-export-*`, `ul-queteur-*`). Conséquences :

- Les secrets sont préfixés `CLEF_` : Secret Manager est un espace de noms au niveau du
  projet, et un `GOOGLE_CLIENT_ID` nu serait entré en collision. C'est d'ailleurs la
  convention du projet — tout y est préfixé (`rcq_`, `lc-`, `dev-`).
- `disable_on_destroy = false` sur les APIs : un `destroy` de CLEF ne doit pas désactiver
  une API dont l'application voisine dépend.
- Les liaisons IAM sont additives, jamais autoritatives.

### Un piège de syntaxe qui échoue en silence

L'ordre de démarrage des conteneurs se déclare par l'**annotation**
`run.googleapis.com/container-dependencies: '{"backend":["redis"]}'`, et il exige un
`startupProbe` sur le conteneur dont on dépend — c'est la sonde qui permet à Cloud Run
de constater qu'il est prêt.

Le champ `depends_on` au niveau du conteneur, que l'on trouve dans presque tous les
exemples, appartient au **provider Terraform**. L'API v1 utilisée par
`gcloud run services replace` ne le connaît pas : elle l'ignore, sans erreur. Le
gabarit l'a d'abord porté ainsi ; le déploiement aurait « réussi » avec un backend
démarrant avant sa base, et des 500 intermittents au démarrage pour seul symptôme.
`backend/tests/test_cloudrun_template.py` garde ce point.

## Alternatives écartées

- **Memorystore managé** : durable, AOF à la seconde, mais incapable de recherche JSON —
  cul-de-sac fonctionnel. Instance détruite le 2026-08-26.
- **Redis dans Cloud Run sans persistance** : les référentiels véhicules et bénévoles
  seraient reconstructibles par la synchronisation Apps Script, mais les dossiers de
  réparation, devis, factures, réservations et le carnet de bord seraient **définitivement
  perdus** à chaque redémarrage.
- **VM Compute Engine avec disque persistant** : garanties de `fsync` réelles et coût
  modeste — c'est d'ailleurs ce qui avait été tenté puis abandonné, comme en témoigne le
  `google_compute_instance.valkey` mort qui subsistait dans `outputs.tf`. Écarté pour ne
  pas avoir de VM à administrer et patcher, mais **c'est l'option à reconsidérer pour la
  production** : elle lève à la fois la contrainte d'instance unique et le RPO de
  10 minutes.
