# CLEF — carte d'entrée pour agents

> Ce fichier est la carte du dépôt. Le modèle de sécurité, la boucle de travail
> (Qualify → Spec → Plan → Implement → Review → Ship → Document) et les règles
> git/VM sont définis dans `~/.claude/CLAUDE.md` et **ne sont pas répétés ici**.
>
> **Reconstruit le 2026-08-13 depuis le code seul.** L'agent qui a construit ce
> projet a perdu ses notes : il n'existe aucun dossier de reprise. Tout ce qui
> suit est soit **vérifié par exécution**, soit explicitement marqué
> `(inferred — verify)`. Les décisions et leur *pourquoi* sont largement perdus —
> voir `docs/migration-status.md`.

## Ce que c'est

Application de **gestion de flotte de véhicules** pour la **Croix-Rouge française**,
délégation territoriale **DT75 (Paris)**. Le domaine, le code et l'historique git
sont en français ; les identifiants techniques sont en anglais.

Deux applications utilisateur distinctes, un seul backend :

| Application | Public | Usage |
|---|---|---|
| `admin` | Gestionnaires DT, Responsables UL | Back-office : référentiel véhicules, dossiers de réparation, devis/factures, réservations, configuration |
| `form` | Bénévoles sur le terrain | Prise et retour de véhicule (km, carburant, état, photos, signature), réservations |

Un troisième projet Angular, `frontend`, est un **squelette CLI vide et non déployé**
(`app.routes.ts` = `[]`) — ne pas y travailler.

## Stack (versions vérifiées)

| Couche | Techno | Version |
|---|---|---|
| Backend | FastAPI + Pydantic v2, Uvicorn | fastapi 0.141.1, pydantic 2.13.4, starlette 1.6.0 |
| Runtime backend | Python | **3.14** requis (`backend/pyproject.toml` `requires-python = ">=3.14"`) |
| Datastore | **Redis 8.10** (modules **JSON**, Search, TimeSeries, Bloom inclus dans l'image officielle) | image `redis:8.10` |
| Client datastore | `redis` (asyncio) | 5.2.0 (inchangé : fonctionne tel quel contre Redis 8.10) |
| Frontend | Angular standalone + Angular Material | **21.2.4**, TypeScript 5.9 |
| Runtime frontend | Node | **24** partout : VM, CI et Docker |
| Tests backend | pytest + `fakeredis[json]` | 9.1.1 / 2.37.0 |
| Tests frontend | **Vitest** via `@angular/build:unit-test` | 4.0.8 |
| E2E | Playwright (chromium) | 1.62.1 |
| IaC | OpenTofu / Terraform, provider google | `>= 1.0`, google 7.23.0 |
| Cible de déploiement | GCP Cloud Run + Secret Manager + KMS ; **datastore de prod non tranché** (voir ADR 0006) | — |

## Commandes réelles (toutes exécutées le 2026-08-13, sorties authentiques)

### Backend — installation

⚠️ **La VM n'a pas de Python 3.14 dans le `PATH`** : `python3 -V` → `3.12.3`. Utiliser
`uv`, qui télécharge et gère un CPython 3.14.6 :

```sh
cd backend
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

`python3 -m venv` fonctionne désormais (`ensurepip` est réparé), mais donnerait un
venv 3.12 — insuffisant pour `requires-python = ">=3.14"`, ce que
`tests/test_runtime.py` fait échouer explicitement.

### Backend — tests

Démarrer le datastore, puis lancer la suite :

```sh
docker compose up -d redis
cd backend
USE_MOCKS=true REDIS_URL="redis://localhost:6379/0" .venv/bin/python -m pytest tests/ -q
```

```
410 passed, 1 skipped in 3.06s
```

Sans aucun Redis joignable, les tests qui traversent le vrai chemin de données sont
**ignorés, pas mis en échec** :

```sh
USE_MOCKS=true .venv/bin/python -m pytest tests/ -q
#  → 394 passed, 17 skipped
```

**La suite est verte.** C'est nouveau : la référence historique était de 8 à 12
échecs (voir `docs/TODO.md`). Le module JSON reste indispensable — c'est pourquoi
`requirements.txt` épingle `fakeredis[json]`, et pourquoi `tests/test_datastore.py`
garde sa présence sur le serveur réel.

### Backend — démarrage

```sh
cd backend
export USE_MOCKS=true REDIS_URL="redis://localhost:6379/0"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Vérifié :

```
GET /health   → 200  {"status":"healthy","redis":"connected"}
GET /docs     → 200  (Swagger UI)
GET /auth/me  → 401  (sans cookie de session — comportement attendu)
openapi.json  → 86 routes, titre "CLEF API 0.1.0"
```

### Frontend — installation et build

```sh
cd frontend
npm ci
npx ng build admin --configuration production      # exit 0
npx ng build form  --configuration production      # exit 0
```

Tailles réelles : `admin` ≈ 1,5 Mo initial (566 kB pour le chunk `vehicle-edit`),
`form` 1,36 Mo initial / 290 kB transféré.

### Frontend — tests unitaires

```sh
cd frontend
npx ng test admin --watch=false     # → 19 passed (6 fichiers)
npx ng test form  --watch=false     # →  3 passed (1 fichier)
```

Les specs sont en **Vitest** (`vi.fn()`, `vi.spyOn`), pas en Jasmine. `tsconfig.spec.json`
déclare `types: ["vitest/globals"]` : `describe`/`it`/`expect`/`vi` sont globaux, aucun
import à ajouter. Deux membres testés sont `protected` — y accéder par indexation
(`component['error']()`) plutôt qu'élargir la visibilité du composant.

### E2E

```sh
cd frontend && npx playwright test --reporter=line     # → 30 passed
```

6 specs dans `frontend/e2e/`, backend mocké via `e2e/helpers/mock-api.ts`. Playwright
démarre lui-même les deux serveurs Angular (`webServer` de `playwright.config.ts`).

⚠️ **Les motifs de route du mock doivent correspondre aux URL réelles**, segment
`{dt}` compris. Trois d'entre eux ne correspondaient à rien — l'app partait alors
vers le proxy du serveur de dev et échouait en `ENOTFOUND backend`, ce que les tests
interprétaient en erreur d'assertion. Vérifier le service Angular avant d'écrire un
motif.

⚠️ Les lignes `[WebServer] Error: getaddrinfo ENOTFOUND backend` dans la sortie sont
**normales** hors docker compose : `proxy.conf` cible l'hôte `backend`. Elles ne
concernent que les requêtes non interceptées par les mocks.

### Environnement complet en local

```sh
./run_local.sh          # docker compose down puis up --build ; exige docker + docker compose
```

Services compose : `redis`, `backend`, `frontend`, `frontend-form`.

**Deux modes**, le mock étant le défaut :

```sh
./run_local.sh          # mock : aucune credential, fonctionne dans la VM
./run_local.sh --real   # intégration réelle : hôte uniquement
```

Vérifié en mode mock : `/health` → `{"status":"healthy","redis":"connected"}`, `4200`
et `4202` → 200.

`--real` exécute un **préflight** qui échoue avant tout démarrage si le service
account (`~/.cred/CLEF/…`) ou les trois `*_SPREADSHEET_ID` de `backend/.env` manquent.
Dans cette VM il échoue donc toujours, et c'est le comportement voulu.

⚠️ Le backend **annonce son mode au démarrage** (`WARNING` en mock). Ne pas diagnostiquer
un comportement bizarre sans avoir lu cette ligne :
`docker compose logs backend | grep USE_MOCKS`.

### Terraform — racine unique `deploy/terraform` ✅

**Validation seule dans la VM, jamais d'`apply`** : la VM ne détient aucune
credential sortante. `TF_DATA_DIR` doit pointer hors du montage partagé, sinon
l'extraction du provider échoue en « permission denied ».

```sh
export TF_DATA_DIR=/tmp/clef-tf
tofu -chdir=deploy/terraform init -backend=false -upgrade && \
tofu -chdir=deploy/terraform validate && \
tofu -chdir=deploy/terraform fmt -check
# → Success! The configuration is valid.
```

`backend/terraform/` et `infra/` sont les **anciennes** racines : conservées le
temps de valider la nouvelle, elles seront supprimées (`docs/TODO.md` N12). Ne pas
y travailler.

### Déploiement — deux scripts, lancés depuis l'HÔTE

```sh
./00-infra.sh dev          # provisionne l'infrastructure GCP
./01-gcp-deploy.sh dev     # Cloud Build puis déploiement Cloud Run
```

**Ne jamais les lancer depuis la VM** : ils échouent proprement (« Ce script se
lance depuis l'HÔTE »), et c'est le modèle de sécurité qui le veut. Documentation
complète dans `DEPLOYMENT.md`, conception dans
`docs/adr/0008-redis-sidecar-cloud-run-instantanes-gcs.md`.

Pour diagnostiquer, **`./02-logs.sh <env>`** (hôte) collecte dans `debug/logs/` les
conditions du service, les journaux **par conteneur** — le nom du conteneur est un
label, pas un champ — la spécification déployée et les journaux Cloud Build. Une
révision qui échoue au démarrage n'apparaît pas dans `gcloud run services logs read` :
c'est pour ça que l'outil interroge Cloud Logging par nom de révision.

Les deux scripts écrivent dans **`debug/deploy/`** (gitignoré, montage partagé) :
transcription et rapport JSON pour `01-gcp-deploy.sh`, plan Terraform en clair et
rapport pour `00-infra.sh`. Les rapports sont posés par un `trap EXIT`, donc présents
même sur un arrêt en cours de route. **Les lire plutôt que demander une sortie
collée.**

⚠️ **Aucun déploiement n'a encore été exécuté** (`docs/TODO.md` N7).

## Carte des modules

### `backend/`

| Chemin | Responsabilité |
|---|---|
| `app/main.py` | Point d'entrée FastAPI, monte 21 routers. ⚠️ contient aussi des routes inline **sans authentification** — voir Pièges |
| `app/routers/` | Un router par domaine métier (véhicules, dossiers de réparation, réservations, config, sync, iCal…) |
| `app/services/` | Logique métier et adaptateurs externes. `redis_service.py` (1849 lignes) est la couche d'accès aux données de tout le domaine |
| `app/models/` | Modèles Pydantic. `repair_models.py` porte le domaine réparation/sinistre/franchise |
| `app/auth/` | Session par cookie, OAuth Google, guards de rôle, mock OIDC |
| `app/cache/` | Client Redis async partagé (`redis_cache.py`) ; `cache_service.py` est marqué déprécié |
| `app/mocks/` | Doubles de Google Sheets/Drive/Gmail/Calendar + Okta, activés par `USE_MOCKS=true` |
| `app/admin/` | Routes de debug réservées au super admin |
| `app/scheduler.py` | Tâches de fond APScheduler (alertes CT/pollution, rappels de devis) |
| `scripts/` | Scripts ponctuels d'ops et de migration |
| `terraform/` | ⚠️ **ancienne** racine IaC, périmée. La racine à jour est `deploy/terraform/` |
| `tests/` | ~40 fichiers pytest, un par domaine |

### `frontend/`

| Chemin | Responsabilité |
|---|---|
| `projects/admin/` | Back-office. Routes **lazy** (`loadComponent`), guards par rôle |
| `projects/admin/src/app/vehicles/dossier-reparation/` | Cœur du domaine réparation/sinistre/franchise. `dossier-detail.component.ts` fait **1028 lignes** — le point chaud |
| `projects/admin/src/app/services/` | 17 services HTTP. `repair.service.ts` porte 20+ appels |
| `projects/form/` | App terrain. Routes **eager**, aucun lazy loading |
| `projects/frontend/` (racine `src/`) | Squelette vide, non déployé — ignorer |
| `e2e/` | Playwright, backend mocké |

### Autres

| Chemin | Responsabilité |
|---|---|
| `google-apps-scripts/` | Scripts Apps Script poussant les données référentiel vers l'API via clé API |
| `deploy/` | 👉 IaC à jour (`terraform/`) et descripteur Cloud Run à 2 conteneurs (`cloudrun-api.yaml.tpl`) |
| `00-infra.sh`, `01-gcp-deploy.sh` | Déploiement GCP, **à lancer depuis l'hôte** |
| `infra/` | ⚠️ **ancienne** seconde racine Terraform, périmée |
| `docs/` | Docs agent (ce chantier) + `specs-gestion-factures.md`, antérieur et conservé |

## Conventions

- **Langue** : domaine, commentaires et messages de commit en **français** ;
  identifiants de code en anglais. Conserver cette séparation.
- **Commits** : Conventional Commits. Les PR sont **squash-mergées** — voir Pièges.
- **Clés Redis** : `RedisService._key()` produit toujours
  `f"{dt}:{...}"`. **Le code DT est le premier segment de toute clé** ; c'est le
  *seul* mécanisme d'isolation multi-tenant, appliqué par l'application et non par
  le datastore.
- **Aucun `KEYS`** dans le code — un seul `SCAN` (`routers/approbation.py:60`).
  Ne pas introduire de `KEYS`.
- **Mocks** : `USE_MOCKS=true` bascule tous les services Google et l'OIDC sur des
  doubles en mémoire. Aucun appel réseau, aucune credential nécessaire.
- **Marqueur `integration`** : les tests qui traversent le vrai chemin de données le
  portent. `pytest_runtest_setup` (`tests/conftest.py`) les **ignore** si `REDIS_URL`
  n'est pas joignable — jamais d'échec pour une dépendance d'environnement absente.
- **L'authentification dépend de Redis** depuis la tâche N2 : le référentiel des
  bénévoles y est lu via l'index `{dt}:benevoles:by_email`. Sans serveur, la suite se
  replie sur `fakeredis` (`conftest.py` remplace `cache.connect()`) et reste verte.
  Après un déploiement, lancer **une fois**
  `python backend/scripts/backfill_benevole_email_index.py` : les bénévoles écrits
  avant l'index seraient sinon introuvables, donc ramenés à « Bénévole » sans périmètre.
- **Référentiel bénévoles : deux propriétaires.** La feuille « CLEF Benevoles » possède
  l'identité (`nivol`, `nom`, `prenom`, `ul`, `email`, `telephone`) ; CLEF possède
  l'organisation (`statut`, `responsable_ul`, `fonctions_dt`). Deux points d'entrée
  disjoints — `upsert_benevole_identite` et `set_benevole_organisation` — rendent
  l'écrasement de l'un par l'autre structurellement impossible. Le rôle applicatif
  n'est **pas stocké** : il est dérivé (`app/auth/service.py`). Voir ADR 0007.
- **Parité mock / réel** : `tests/test_mock_parity.py` compare les méthodes appelées sur
  les services fournis par `service_factory` à celles réellement définies. Quatre dettes
  connues y sont listées (M16, M32) ; toute **nouvelle** occurrence fait échouer la
  suite. C'est la classe de bug qui a produit M16, M31 et M32 — invisible autrement,
  puisque les tests tournent en `USE_MOCKS=true`.
- **Aucune fixture `.csv` versionnée** : la règle `.gitignore` `*.csv` en a déjà fait
  disparaître deux définitivement. Les CSV de test sont **générés** — `conftest.py`
  côté backend, `e2e/helpers/vehicles-csv.ts` côté e2e. Seule exception, strictement
  scopée : `docs/examples/*.csv`, de la documentation, pas des fixtures.
- **Angular** : composants standalone, nouveau control flow (`@if`/`@for`),
  signals partiellement adoptés. `OnPush` n'est utilisé que dans **un** fichier —
  ne pas en déduire une convention établie.

## Pièges

1. **Les quatre suites sont vertes depuis le 2026-08-13** — c'est la référence à
   tenir : backend `410 passed, 1 skipped` (avec `docker compose up -d redis`),
   `ng test admin` 19, `ng test form` 3, Playwright 30. Un échec est désormais un
   **signal**, plus du bruit hérité. Historique : la suite a longtemps été à 8 ou 12
   échecs, et l'e2e n'avait jamais tourné.

2. **Le fuseau horaire cassait 86 tests.** `datetime.utcnow()` renvoie un datetime
   *naïf* : `.timestamp()` l'interprète en heure locale. Corrigé dans
   `app/mocks/okta_mock.py`, mais **23 autres `datetime.utcnow()` subsistent** dans
   le code de production. Ils comparent du naïf à du naïf, donc restent cohérents,
   mais `datetime.utcnow()` est déprécié depuis Python 3.12.

3. **`main.py` n'a aucun `Depends` : toute route y est publique par construction.**
   Les trois routes de référentiel qui y exposaient les données personnelles des
   bénévoles ont été retirées le 2026-08-20 (C1 clos). Ne **jamais** y déclarer de
   route : passer par un router avec un guard. `tests/test_referentiel_directory.py`
   contient une garde structurelle qui échoue si l'une d'elles réapparaît.
   ⚠️ `GET /api/alerts/status` reste non authentifié (H4 voisin), toujours ouvert.

4. **La CI garde désormais le déploiement.** `deploy-dev` déclare
   `needs: [backend-test, frontend-build, frontend-test, e2e]`, et les jobs de test
   tournent sur `pull_request` **et** sur `push`. `tests/test_ci_workflow.py` relit
   `ci.yml` et fait échouer la suite si ce garde-fou disparaît — ne pas le retirer
   sans retirer aussi ce test, ce qui rendra la régression visible en revue.

5. **Les PR sont squash-mergées.** Une branche vivante affiche « ahead de N
   commits » alors que leur contenu est déjà dans `main`. Ne jamais réutiliser un
   nom de branche déjà associé à une PR mergée : les outils qui cherchent « la PR
   de cette branche » retombent sur l'ancienne et concluent à tort « déjà mergée ».

6. **Le filet unitaire frontend est mince : 22 tests pour ~100 composants.** Il
   compile et passe, mais ne couvre que `App`, `LayoutComponent`, le générateur de
   QR codes, `QrCodeService`, `superAdminGuard` et `ConfigurationUlComponent`. Ne
   pas confondre « vert » et « couvert ».

7. **Le champ « Montant de la franchise » de l'écran Configuration est décoratif.**
   L'UI l'envoie, mais `ConfigUpdate` (`app/models/config.py`) ne le déclare pas :
   `model_dump(exclude_none=True)` le jette. La valeur reste à 350 €.

8. **4 services admin codent `dt = 'DT75'` en dur** (`api-keys`, `stats`,
   `unite-locale`, `vehicle-import`). L'application est mono-DT en pratique, malgré
   un backend conçu multi-tenant.

9. **L'app `form` envoie une identité bénévole factice** (`'user@example.com'`,
   `'Nom'`, `'Prénom'`) au lieu de l'utilisateur authentifié : les prises et retours
   sont mal attribués. Voir les TODO dans `prise-form.component.ts:178` et
   `retour-form.component.ts:147`.

10. **`*.csv` est gitignoré** (protection des données personnelles des bénévoles).
    Cette règle a avalé une fixture de test : `backend/tests/fixtures/vehicles_import_sample.csv`
    n'a **jamais** été committée et est perdue — 8 tests d'import échouent de ce fait.

11. **La VM n'a pas de Python 3.14 dans le `PATH`** (`python3 -V` → 3.12.3) alors
    que le projet exige `>=3.14`. Passer par `uv venv --python 3.14`.
    `tests/test_runtime.py` échoue explicitement si le venv est trop ancien. Node,
    lui, est aligné en 24 partout.

12. **Trois motifs de route des mocks e2e ne correspondaient à aucune URL réelle**
    (`/api/vehicles/import`, `/api/calendar/reservations`, `/api/carnet-bord/*`).
    Corrigés. Symptôme à reconnaître : `ENOTFOUND backend` dans la sortie Playwright
    plus une assertion qui échoue « sans raison » — la requête a fui vers le proxy.

13. **Deux jeux de données mock e2e ne respectaient pas le contrat de l'API** :
    `status_ct` était une chaîne au lieu de `{value, color}`, et les réservations
    portaient l'ancien modèle Google Calendar (`vehicule_id`, `date_debut`) au lieu
    du modèle Redis (`vehicule_immat`, `debut`). Vérifier le modèle avant d'ajouter
    une fixture.

14. **Un flake de timing subsiste** dans
    `tests/test_carnet_de_bord.py::test_get_historique_carnet` : il trie l'historique
    sur `timestamp.isoformat()` et a échoué une fois sur ~10 exécutions. Observé, non
    corrigé — voir `docs/TODO.md` M27.

## Où commencer selon la tâche

| Tâche | Point d'entrée |
|---|---|
| Domaine réparation / sinistre / franchise | `backend/app/models/repair_models.py`, `backend/app/routers/dossiers_reparation.py`, `frontend/.../dossier-reparation/dossier-detail.component.ts` |
| Accès aux données, nouvelle entité | `backend/app/services/redis_service.py` |
| Authentification, rôles | `backend/app/auth/dependencies.py`, `auth/service.py` (référentiel lu dans **Redis** via `benevoles:by_email`) |
| Nouvel écran admin | `frontend/projects/admin/src/app/app.routes.ts` (lazy + guard) |
| Écran terrain bénévole | `frontend/projects/form/src/app/` |
| Infra GCP, déploiement | `deploy/terraform/`, `00-infra.sh`, `01-gcp-deploy.sh`, `DEPLOYMENT.md` |
