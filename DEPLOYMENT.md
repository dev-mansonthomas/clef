# CLEF — déploiement sur GCP

> **Réécrit le 2026-08-26.** La version précédente décrivait un déploiement par
> GitHub Actions **qui n'a jamais fonctionné** (le job `deploy-dev` échouait à
> l'authentification GCP à chaque exécution, sans que personne le voie), et un
> Memorystore for Redis **détruit depuis**. Elle est remplacée par deux scripts
> lancés à la main depuis l'hôte.
>
> La conception du datastore est justifiée dans
> [ADR 0008](docs/adr/0008-redis-sidecar-cloud-run-instantanes-gcs.md).
> Le déploiement automatique depuis GitHub reviendra quand le projet aura mûri —
> voir constat H12 dans [docs/TODO.md](docs/TODO.md).

## En deux commandes

Depuis la racine du dépôt, **sur l'hôte** (pas dans la VM de développement) :

```sh
./00-infra.sh dev          # provisionne l'infrastructure — une seule fois par env
./01-gcp-deploy.sh dev     # construit les images et déploie — à chaque livraison
```

Les deux acceptent `dev`, `test` ou `prod`, sont idempotents, et refusent de
démarrer en nommant ce qui manque plutôt que d'échouer à mi-parcours.

**Pourquoi depuis l'hôte ?** La VM de développement ne détient, par construction,
aucune credential sortante : c'est elle la frontière de sécurité. Les scripts
détectent l'absence de `gcloud` et s'arrêtent avec le message
« Ce script se lance depuis l'HÔTE ». **Relisez-les avant de les lancer** — ils
agissent avec vos droits GCP.

## Architecture déployée

```
                    ┌─────────────────────── Cloud Run ────────────────────────┐
   navigateur ──────┤ clef-frontend  (nginx + Angular admin & form)            │
                    └──────────────────────────┬───────────────────────────────┘
                                               │ /api
                    ┌──────────────────────────▼───────────────────────────────┐
                    │ clef-api — DEUX conteneurs dans la même instance         │
                    │                                                          │
                    │   backend  (FastAPI)  ──localhost:6379──►  redis  8.10   │
                    │                                             │            │
                    └─────────────────────────────────────────────┼────────────┘
                                                                  │ RDB, 10 min
                                                    ┌─────────────▼──────────┐
                                                    │ gs://…-clef-redis-     │
                                                    │ snapshots  (GCS FUSE)  │
                                                    └────────────────────────┘
```

| Composant | Nom | Détail |
|---|---|---|
| API | `clef-api` | FastAPI, **avec Redis en conteneur adjoint** |
| Datastore | conteneur `redis` | Redis 8.10 officiel (embarque ReJSON et Search) |
| Persistance | bucket GCS | instantanés RDB, monté par Cloud Storage FUSE |
| Frontend | `clef-frontend` | nginx servant `admin` et `form` |
| Images | Artifact Registry `clef-images` | construites par **Cloud Build**, pas localement |
| Secrets | Secret Manager, préfixe `CLEF_` | 3 secrets |
| Chiffrement | KMS `clef-keyring` | en `europe-west9` — voir « Deux régions » |

### Trois conséquences à connaître

1. **`maxScale = 1`, obligatoirement.** Chaque instance Cloud Run a son propre
   conteneur Redis, donc son propre jeu de données. Deux instances, deux bases qui
   divergent en silence. `01-gcp-deploy.sh` **refuse** de déployer si
   `MAX_INSTANCES` vaut autre chose que 1.
2. **La perte de données maximale est de 10 minutes** (RPO). Redis écrit un
   instantané toutes les 10 minutes, ou après 100 écritures en 2 minutes. Ce qui
   suit le dernier instantané disparaît si l'instance meurt.
3. **`minInstances = 0` fait perdre des écritures.** Avec le scale-to-zero, chaque
   mise en veille redémarre depuis le dernier instantané. Acceptable en `dev`,
   à trancher en `prod` (constat N11).

### Deux régions, et c'est voulu

Cloud Run, le bucket et le registre sont en **`europe-west1`**, avec le reste du
projet. Le **keyring KMS reste en `europe-west9`** : il y existait déjà, et un
keyring ne se déplace pas — Terraform l'adopte là où il est. L'écart est sans
conséquence : KMS n'est appelé qu'à l'ouverture de session. Il est porté par la
variable `kms_region` de `deploy/terraform/variables.tf`.

### Une policy d'organisation interdit `global`

`constraints/gcp.resourceLocations` est appliquée sur ce projet par l'organisation :
toute ressource créée dans l'emplacement `global` est refusée. Constaté au premier
apply, sur les quatre secrets.

Conséquence pratique : **ne jamais utiliser `replication { auto {} }`** pour un
`google_secret_manager_secret`, qui place le secret dans `global`. La configuration
déclare une réplication explicite en `europe-west1`. Le message d'erreur parle
d'emplacement mais ne nomme jamais `auto` : la cause n'est pas lisible dans l'erreur.

`europe-west1` est autorisée — le bucket et le registre y ont été créés sans
difficulté au même apply. Pour lire la liste exacte :

```sh
gcloud resource-manager org-policies describe gcp.resourceLocations \
  --project=rcq-fr-dev --effective
```

### ⚠️ Le projet GCP est partagé

`rcq-fr-dev` héberge **une autre application entière** (15 services Cloud Run :
`rcq-api`, `rcq-frontend`, `dev-export-*`, `ul-queteur-*`). D'où trois règles à
ne pas relâcher :

- **les secrets CLEF sont préfixés `CLEF_`** — Secret Manager est un espace de noms
  de projet, et un `JWT_SECRET` du voisin y vit déjà ;
- **`disable_on_destroy = false`** sur les APIs — un `tofu destroy` ne doit pas
  couper Cloud Run pour l'application voisine ;
- **les liaisons IAM sont additives** (`google_project_iam_member`, jamais
  `_policy`), sous peine d'effacer les droits du voisin.

Ne détruisez jamais une ressource de ce projet sans avoir vérifié à qui elle
appartient.

## Prérequis, une seule fois

### 1. Projets GCP

- `rcq-fr-dev` (développement) — le seul utilisé à ce jour
- `rcq-fr-test`, `rcq-fr-prod` (à créer le jour où ils serviront)

### 2. Outils sur l'hôte

| Outil | Pourquoi | Vérifier |
|---|---|---|
| `gcloud` authentifié | tout le reste | `gcloud auth list` |
| `tofu` (ou `terraform`) | `00-infra.sh` | `tofu version` |
| `envsubst` (paquet gettext) | rendu du gabarit Cloud Run | `envsubst --version` |

Docker n'est **pas** nécessaire : les images sont construites par Cloud Build.

### 3. Configuration OAuth Google

L'authentification passe par Google OAuth. À configurer dans la console GCP.

**Écran de consentement** — *APIs & Services → OAuth consent screen* : choisir
**Internal** (utilisateurs Google Workspace uniquement), renseigner le nom
« CLEF Fleet Management » et un email de contact, puis ajouter les portées
`openid`, `.../auth/userinfo.email` et `.../auth/userinfo.profile`.

**Client OAuth 2.0** — *APIs & Services → Credentials → Create Credentials →
OAuth 2.0 Client ID*, type **Web application** :

| Champ | Valeur |
|---|---|
| Origines JavaScript autorisées | `http://localhost:8000` (dev local), `https://<url-cloud-run>` |
| URI de redirection autorisés | `http://localhost:8000/auth/callback`, `https://<url-cloud-run>/auth/callback` |

Conservez le **Client ID** et le **Client Secret** : ils alimentent les secrets
`CLEF_GOOGLE_CLIENT_ID` et `CLEF_GOOGLE_CLIENT_SECRET` à l'étape suivante.

L'URL Cloud Run n'est connue qu'après le premier déploiement : lancez d'abord les
deux scripts, puis revenez ajouter l'URI de redirection.

**Seules les adresses `@croix-rouge.fr` sont autorisées à s'authentifier.**

## Étape 1 — `./00-infra.sh <env>`

```sh
./00-infra.sh dev                 # affiche le plan, demande confirmation
./00-infra.sh dev --auto-approve  # sans confirmation, pour une réexécution déjà relue
```

Ce que le script fait, dans l'ordre :

1. vérifie `gcloud`, `tofu`, et que vous êtes authentifié ;
2. crée le **bucket de state Terraform** `${PROJECT_ID}-clef-tfstate`, versionné.
   C'est le seul geste posé hors Terraform : un backend ne peut pas se
   provisionner lui-même ;
3. **adopte le state local** de l'ancienne racine `backend/terraform`, s'il existe
   et si le nouveau est vide. Sans cela, Terraform tenterait de recréer un keyring
   KMS déjà en place — et échouerait ;
4. `init`, `plan`, puis `apply` après que vous avez lu le plan ;
5. liste les **secrets encore vides** et la commande pour les remplir.

Ressources créées : 12 APIs, le service account `clef-backend` avec 3 rôles,
le registre `clef-images`, le bucket d'instantanés, 3 secrets (sans valeur), et
le keyring KMS.

**Aucune clé de service account n'est générée** (constat H6 clos) : sur Cloud Run,
le backend s'authentifie par *Application Default Credentials*, résolues par
`backend/app/services/google_credentials.py`. Rien à télécharger, rien à faire
tourner.

### Renseigner les 3 secrets

`00-infra.sh` crée les secrets vides — une valeur de secret n'a pas sa place dans
du code Terraform. À faire une fois, à la main :

```sh
printf '%s' 'votre-client-id.apps.googleusercontent.com' \
  | gcloud secrets versions add CLEF_GOOGLE_CLIENT_ID --data-file=- --project=rcq-fr-dev
printf '%s' 'GOCSPX-votre-secret' \
  | gcloud secrets versions add CLEF_GOOGLE_CLIENT_SECRET --data-file=- --project=rcq-fr-dev
openssl rand -base64 32 \
  | gcloud secrets versions add CLEF_QR_CODE_SALT --data-file=- --project=rcq-fr-dev
```

Il n'y a **pas** de secret de signature de jetons, et ce n'est pas un oubli : le
cookie de session porte l'id_token de Google, vérifié contre les clés publiques de
Google. L'application ne signe aucun jeton.

⚠️ **`CLEF_QR_CODE_SALT` ne doit jamais changer** une fois des QR codes imprimés :
les codes déjà collés sur les véhicules deviendraient invalides.

`printf` plutôt que `echo -n` : ce dernier écrit `-n` littéralement dans certains
shells, et le secret serait silencieusement faux.

## Étape 2 — `./01-gcp-deploy.sh <env>`

```sh
cp deploy/deploy.env.example deploy/deploy.dev.env   # une fois
$EDITOR deploy/deploy.dev.env                        # PROJECT_ID, emails, sheet IDs
./01-gcp-deploy.sh dev
```

`deploy/deploy.*.env` est **gitignoré**. Il ne porte pas de secret — identifiants
de classeurs et adresses email seulement ; les secrets vivent dans Secret Manager.

Options :

```sh
./01-gcp-deploy.sh dev --components=api        # backend seul
./01-gcp-deploy.sh dev --skip-build            # redéploie la dernière image
```

### Le préflight

Le script refuse de déployer, en nommant le manque, si : `gcloud` est absent ou
non authentifié ; `MAX_INSTANCES != 1` ; le service account, le bucket
d'instantanés ou le registre n'existent pas ; un secret n'a **aucune version**
(cas fourbe — la révision serait créée puis mourrait au démarrage, avec un
message opaque) ; ou si un service du même nom existe **dans une autre région**
(vous auriez deux services vivants, deux URLs, et des utilisateurs répartis entre
les deux sans le savoir). Les identifiants de classeurs manquants ne bloquent pas
mais déclenchent un avertissement explicite.

### Pourquoi `services replace` et non `gcloud run deploy`

`gcloud run deploy` ne sait décrire ni plusieurs conteneurs, ni un volume GCS.
Le backend passe donc par un descripteur complet,
`deploy/cloudrun-api.yaml.tpl`, rendu par `envsubst`. Le frontend, lui, est un
conteneur simple : `gcloud run deploy` suffit.

Trois réglages du gabarit qui ne sont pas cosmétiques :

- `run.googleapis.com/cpu-throttling: "false"` — sans cela, le CPU est bridé hors
  requête et **les instantanés en tâche de fond ne se déclenchent jamais** ;
- `execution-environment: gen2` — requis pour monter un volume GCS ;
- `run.googleapis.com/container-dependencies: '{"backend":["redis"]}'` — Redis
  démarre d'abord, avec un `startupProbe` TCP sur le port 6379 **sans lequel
  l'annotation ne garantit rien**. C'est bien une annotation : le champ
  `depends_on` au niveau du conteneur est la syntaxe du provider Terraform, et
  l'API v1 de `services replace` l'ignorerait en silence.

`USE_MOCKS` et `GOOGLE_APPLICATION_CREDENTIALS` sont **délibérément absents** du
gabarit : le premier ferait servir des données fictives en production (le backend
refuse d'ailleurs de démarrer dans ce cas, garde-fou S1), le second forcerait la
recherche d'un fichier de clé qui n'existe pas.

## Amorçage du premier accès

Enchaînement à respecter, sinon personne ne peut se connecter :

1. `EMAIL_GESTIONNAIRE_DT` (dans `deploy.<env>.env`) est le **seul compte** dont
   l'authentification ne consulte pas le référentiel Redis. C'est l'unique porte
   d'entrée avant la première synchronisation.
2. Connectez-vous avec ce compte, puis créez une **clé API de synchronisation**
   depuis l'écran de configuration.
3. Installez cette clé dans le script Apps Script du classeur « CLEF Benevoles »
   (onglet « Bénévoles ») — voir
   [docs/specs/synchronisation-referentiel-benevoles.md](docs/specs/synchronisation-referentiel-benevoles.md).
4. Lancez la synchronisation. Le référentiel se peuple, et les autres bénévoles
   peuvent se connecter.

## Vérifier, observer, revenir en arrière

```sh
# santé — ce que le script vérifie déjà en fin de course
curl -s "$(gcloud run services describe clef-api --region europe-west1 \
  --project rcq-fr-dev --format='value(status.url)')/health"
#  → {"status":"healthy","redis":"connected"}

# les instantanés RDB arrivent-ils vraiment ? (à vérifier au premier déploiement)
gcloud storage ls -l gs://rcq-fr-dev-clef-redis-snapshots/

# logs, par conteneur
gcloud run services logs read clef-api --region europe-west1 --project rcq-fr-dev

# revenir à la révision précédente
gcloud run revisions list --service clef-api --region europe-west1 --project rcq-fr-dev
gcloud run services update-traffic clef-api --to-revisions=<révision>=100 \
  --region europe-west1 --project rcq-fr-dev
```

⚠️ **Un rollback ne restaure pas les données** : la nouvelle instance repart du
dernier instantané, quelle que soit la révision.

## Ce qui monte vers Cloud Build finit dans l'image

`gcloud builds submit backend` ne lit que **`backend/.gcloudignore`** — ou, à défaut,
`backend/.gitignore`. **Jamais** ceux de la racine. Et `backend/Dockerfile` fait
`COPY . .`.

Autrement dit : tout fichier présent dans `backend/` et non exclu par
`backend/.gcloudignore` se retrouve **dans l'image de conteneur**, poussée sur un
registre lisible par quiconque a accès au projet partagé.

Les deux fichiers `.gcloudignore` existent et excluent les secrets (`​.env`,
`.env.*`, `credentials/`) et les dépendances locales (`.venv/`, `node_modules/`) —
0,7 Mo et 4,2 Mo envoyés, au lieu de 388 et 406. `backend/tests/test_gcloudignore.py`
échoue si un de ces motifs disparaît.

Pour vérifier avant de construire :

```sh
gcloud meta list-files-for-upload backend | grep -E '\.env|\.venv' && echo "⚠️ STOP"
```

⚠️ **Ne jamais ajouter un secret dans `backend/`** en comptant sur le `.gitignore` de
la racine : il ne protège que git, pas Cloud Build.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| « Ce script se lance depuis l'HÔTE » | vous êtes dans la VM — c'est voulu |
| La révision est créée puis meurt aussitôt | un secret sans version, ou `USE_MOCKS` fixé en production (garde-fou S1) |
| `/health` répond `"redis":"disconnected"` | le conteneur `redis` n'a pas démarré : regarder ses logs, pas ceux du backend |
| Le bucket d'instantanés reste vide après 15 min | `cpu-throttling` remis à `true`, ou l'écriture RDB échoue sur GCS FUSE (constat N9) |
| Tout le monde est « Bénévole » sans UL | référentiel vide, ou identifiants de classeurs absents (M9/M10, M31) |
| `tofu` : « permission denied » à l'extraction du provider | vous êtes dans la VM, sur le montage partagé. Pointer `TF_DATA_DIR` ailleurs — et de toute façon, pas d'`apply` dans la VM |
| Redirection OAuth refusée | l'URL Cloud Run n'est pas dans les URI autorisés du client OAuth |
| `Constraint constraints/gcp.resourceLocations violated ... in [global]` | une ressource est créée dans `global`, interdit par la policy d'organisation. Pour Secret Manager, c'est `replication { auto {} }` — le message ne nomme jamais `auto`. Utiliser une réplication explicite en `europe-west1` |

## Ce qui n'est pas fait

- **Rien n'a encore été déployé.** Les scripts sont écrits, `shellcheck` est muet,
  tous les chemins d'arguments sont testés — mais **aucun n'a tourné contre GCP**
  (constat N7). Relisez les plans à la première exécution.
- **Le montage GCS FUSE n'est pas éprouvé** pour des écritures RDB (constat N9).
  C'est le point à surveiller au premier déploiement ; le repli est un RDB local
  recopié périodiquement.
- **Deux clés de service account utilisateur restent à révoquer** (constat N8).
- **`backend/scripts/setup_gcp.sh` et `backend/scripts/setup_github_secrets.sh`
  sont périmés** : ils visaient Memorystore, l'ancienne racine Terraform et des
  clés statiques. Ne pas les utiliser (constat N10).
- **`backend/terraform/` et `infra/` subsistent** le temps de valider la nouvelle
  racine, puis seront supprimés (constat N12). La seule racine à utiliser est
  **`deploy/terraform/`**.
- **Domaine personnalisé, Cloud Armor, CDN, alerting, sauvegarde testée** : rien
  de tout cela n'est en place.
