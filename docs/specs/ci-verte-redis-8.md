# Spec — CI au vert, Redis 8.10, Python 3.14, Node 24

> Établi le 2026-08-13. Toutes les valeurs de ce document sont **mesurées par
> exécution** dans la VM ce jour-là, ou explicitement marquées
> `(inferred — verify)`. Les commandes exactes sont reproduites en annexe.

## Objet

Amener les quatre suites de tests du dépôt à **zéro échec**, faire garder le
déploiement par ces tests, et remplacer **Valkey par Redis 8.10** comme datastore.

Le périmètre est **strictement local** : la stack doit tourner via `./run_local.sh`
et la CI doit être verte. Le déploiement GCP (Cloud Run, Memorystore, Terraform)
est **hors périmètre** — voir *Non-objectifs*.

## Motivation

1. **La CI n'a jamais été verte.** Référence documentée dans `docs/TODO.md` :
   12 échecs backend sans serveur, 8 avec. `ng test` ne compile pas. Les e2e n'ont
   jamais tourné. Aucun de ces échecs n'est une régression : c'est l'état hérité.
2. **Le déploiement n'est gardé par aucun test** (`docs/TODO.md` H1) : `deploy-dev`
   n'a pas de `needs:` et les jobs de test sont conditionnés `pull_request`. Un
   merge sur `main` déploie sans qu'aucun test ne s'exécute.
3. **Redis 8.0 est passé sous AGPLv3**, ce qui retire la raison d'être du fork
   Valkey pour ce projet (`docs/TODO.md` N5). Redis 8.10.0 est GA.
4. **La VM a évolué** : Node 24, `ensurepip` réparé, Python 3.14 disponible via
   `uv`. Les épinglages du dépôt (Python 3.13, Node 22) ont divergé.

## Décisions actées (propriétaire, 2026-08-13)

| # | Décision |
|---|---|
| **D-A** | **Fixtures CSV : les deux approches.** Une fixture pytest génère le CSV en `tmp_path` (aucun `.csv` dans `backend/`), **et** un CSV d'exemple documenté est versionné hors tests, sous `docs/examples/`, avec une exception `.gitignore` strictement scopée. |
| **D-B** | **Renommage complet.** Le swap runtime *et* le renommage des identifiants `Valkey*` → `Redis*` dans le code sont livrés. Le renommage arrive en dernier, en commits séparés, une fois les suites vertes. |
| **D-C** | **Périmètre CI : les quatre suites.** backend pytest (avec service `redis:8.10`), gating du déploiement, `ng test`, et Playwright e2e. |
| **D-D** | **Dépendances backend au dernier stable**, à une exception près : `redis` (le client Python) **reste en 5.2.0**. Sa montée en 7.x n'a pas été mesurée et fera l'objet d'un chantier séparé. |

## État de départ mesuré

| Suite | Commande | Résultat mesuré |
|---|---|---|
| Backend, py3.13 + `fakeredis` (= CI actuelle) | `pytest tests/ -q` | `12 failed, 356 passed, 1 skipped` |
| Backend, py3.13 + `redis:8.10` réel | idem + `REDIS_URL` | `8 failed, 360 passed, 1 skipped` |
| Backend, py3.14.6 + pins à jour + `redis:8.10` | idem | `8 failed, 360 passed, 1 skipped` |
| Backend, py3.14.6 + pins **actuels** | idem | `25 errors during collection` |
| Frontend unitaire `admin` | `ng test admin --watch=false` | **ne compile pas** — 10 erreurs TS dans **2** fichiers |
| Frontend unitaire `form` | `ng test form --watch=false` | `1 failed, 1 passed` |
| E2E | `playwright test` | `30 failed` — navigateur introuvable |
| Builds | `ng build {admin,form} --configuration production` | exit 0 |

Les 12 échecs backend se décomposent en **8** fixtures CSV perdues (`docs/TODO.md`
H2) et **4** tests qui exigent un vrai serveur (`fakeredis` ne les couvre pas, même
en 2.37.0) : `test_reservations_api` ×2, `test_sync_api::test_valid_api_key`,
`test_config_api::test_patch_config_as_non_dt_manager`.

## Matrice de compatibilité mesurée

### Redis 8.10 remplace `valkey-bundle:8` sans perte

`docker run redis:8.10` → `redis_version:8.10.0`, `MODULE LIST` :

| Module | Version |
|---|---|
| `ReJSON` | 81000 |
| `search` | 81000 |
| `timeseries` | 81000 |
| `bf` | 81000 |
| `vectorset` | 1 |

`JSON.SET` / `JSON.GET` / `FT.CREATE ON JSON` vérifiés OK. Le module **JSON est
indispensable** (tout `valkey_service.py` repose dessus) : c'est acquis. Le module
**Search reste inutilisé** (`docs/TODO.md` M25, aucun `FT.CREATE` dans le code) mais
il est fourni par l'image, sans coût.

`redis-cli` est présent dans l'image → le healthcheck `valkey-cli ping` devient
`redis-cli ping`.

Le client Python `redis==5.2.0` fonctionne inchangé contre Redis 8.10.

### Python 3.14 — deux blocages réels, tous deux levés par un bump

| Paquet | Version épinglée | Symptôme sur 3.14 | Version retenue |
|---|---|---|---|
| `Pillow` | 11.0.0 | aucune wheel `cp314` → build source → `RequiredDependencyException: The headers or library files could not be found for jpeg` | **12.3.0** |
| `google-cloud-kms` → `protobuf` | 2.21.0 → 4.25.9 | `TypeError: Metaclasses with custom tp_new are not supported` → **25 erreurs de collecte** | **3.16.0** → protobuf 7.35.1 |

Versions retenues, mesurées vertes ensemble :

```
fastapi 0.141.1        starlette 1.6.0 (transitif)   uvicorn[standard] 0.52.3
pydantic 2.13.4        pydantic-core 2.46.4          pydantic-settings 2.15.0
Pillow 12.3.0          google-cloud-kms 3.16.0       protobuf 7.35.1
google-api-python-client 2.198.0                     google-auth 2.56.3
authlib 1.7.2          PyJWT 2.13.0                  pytest 9.1.1
fakeredis[json] 2.37.0                               redis 5.2.0 (inchangé, D-D)
```

### Starlette 1.0 a supprimé `on_event()`

Starlette 1.0.0rc1 retire `on_event()`, `on_startup`, `on_shutdown`,
`add_event_handler()` (PR encode/starlette#3117). `app/main.py:88,148` les utilise.

**Vérifié en exécution** : FastAPI 0.141.1 conserve son propre shim
`FastAPI.on_event` — le startup s'exécute bien sous Starlette 1.6.0
(`Redis connection established`, `Scheduler started`), alors que
`starlette.routing.Router.on_event` n'existe plus. Ce n'est donc **pas bloquant**,
mais le code dépend d'une API dépréciée dont le socle a disparu : la migration vers
`lifespan` est intégrée à ce chantier (clôt `docs/TODO.md` F13).

### Node 24 est officiellement supporté

`@angular/core`, `@angular/build` et `@angular/cli` 21.2.x déclarent
`engines.node = "^20.19.0 || ^22.12.0 || >=24.0.0"`. La VM a Node 24.18.0 et les
trois builds passent déjà. L'alignement des `Dockerfile` et de la CI sur Node 24 ne
présente pas de risque connu.

### Playwright : version épinglée plus ancienne que le cache de la VM

Le cache de la VM contient `chromium-1234` et `chromium_headless_shell-1234`.
`@playwright/test@1.58.2` réclame le build `1208` → `browserType.launch: Executable
doesn't exist` sur les 30 tests.

`npx playwright install --dry-run chromium` sur **1.62.1** (dernier stable) annonce
exactement `chromium-1234` et `chromium_headless_shell-1234` : le bump de pin rend
les e2e exécutables **sans aucun téléchargement**.

### La VM n'a pas de Python 3.14 système

`python3 -V` → `3.12.3` ; aucun binaire `python3.14` dans le `PATH` ni sous `/usr`.
En revanche `python3 -c "import ensurepip"` réussit désormais : le `venv` cassé
documenté dans `CLAUDE.md` est **réparé**.

Conséquence : le parcours d'installation reste **`uv venv --python 3.14`**, qui
télécharge et gère un CPython 3.14.6. Un Python 3.14 dans le `PATH` demanderait une
ligne dans `scripts/vm-provision.sh` — hors périmètre de ce chantier.

## Entrées / sorties

Ce chantier ne modifie **aucun contrat d'API**. Ses « entrées » sont des fichiers de
configuration et de test ; sa sortie est l'état des suites.

### Fichiers créés

| Chemin | Rôle |
|---|---|
| `docs/specs/ci-verte-redis-8.md` | ce document |
| `backend/tests/test_datastore.py` | garde : le datastore est un Redis 8 avec RedisJSON |
| `backend/tests/test_runtime.py` | garde : le runtime satisfait `requires-python` |
| `backend/tests/test_ci_workflow.py` | garde : le workflow CI gate le déploiement et épingle les bonnes versions |
| `docs/examples/referentiel-vehicules-exemple.csv` | exemple documenté du format d'import (D-A), 100 % fictif |

### Fichiers modifiés

| Chemin | Nature |
|---|---|
| `docker-compose.yml` | service `valkey` → `redis`, image `redis:8.10`, healthcheck `redis-cli` |
| `run_local.sh` | attente et libellés sur le service `redis` |
| `backend/.env.example` | retrait des variables `VALKEY_*` propres à Memorystore-for-Valkey |
| `backend/pyproject.toml` | `requires-python = ">=3.14"` |
| `backend/requirements.txt` | pins ci-dessus |
| `backend/Dockerfile`, `backend/Dockerfile.dev` | `python:3.13-slim` → `python:3.14-slim` |
| `frontend/Dockerfile`, `frontend/Dockerfile.dev` | `node:22-alpine` → `node:24-alpine` |
| `frontend/package.json` | `@playwright/test` → `^1.62.1` |
| `backend/app/main.py` | `on_event` → `lifespan` |
| `backend/tests/conftest.py` | fixtures génératrices de CSV |
| `backend/tests/test_import_vehicles.py` | 8 tests consommant les fixtures |
| `.github/workflows/ci.yml` | service redis, versions, `needs:`, jobs `frontend-test` et `e2e` |
| `.gitignore` | exception scopée `!docs/examples/*.csv` |
| specs frontend | port Jasmine → Vitest |
| `docs/TODO.md`, `CLAUDE.md`, `README.md`, `docs/migration-status.md`, `DOCKER_SETUP.md` | mise à jour documentaire |

### Fichiers renommés (D-B, en dernier)

`app/services/valkey_service.py`, `app/models/valkey_models.py`,
`app/services/valkey_dependencies.py`, `app/routers/reservations_valkey.py`,
`tests/test_valkey_service.py`, `tests/test_reservations_valkey.py`,
`backend/terraform/memorystore_valkey.tf`.

Inventaire des identifiants concernés : `valkey_service` ×319, `valkey` ×262,
`ValkeyService` ×206, `get_valkey_service` ×120, `valkey_models` ×27,
`valkey_dependencies` ×23, `get_valkey_for_dt` ×14, `reservations_valkey` ×2 ;
côté frontend `ValkeyReservation` ×22, `ValkeyReservationCreate` ×7,
`ValkeyReservationListResponse` ×7.

⚠️ `app/cache/redis_cache.py` porte **déjà** un nom `redis_*` : le renommage doit
éviter la collision `RedisService` / `RedisCache`.

## Forme exigée des fixtures CSV

Reprise de `docs/specs/import-vehicules-csv.md`, à respecter par la fixture pytest :

| Contrainte | Valeur |
|---|---|
| Lignes totales | 12 |
| Lignes de métadonnées à ignorer | 4 |
| Ligne d'en-têtes | ligne 5 |
| Colonnes | 19 |
| En-tête colonne 0 | contient `DT 75 / UL` |
| Lignes de données | ≥ 5 |
| Dont invalides | 1, `immat = N/A`, en ligne 9 |
| Véhicules créés ou mis à jour | ≥ 4 |

Les fautes d'orthographe du référentiel source — `Nom Syntéthique`,
`Instructions pour récuperer le véhicule` — **doivent être reproduites à
l'identique** : la détection d'en-tête s'appuie dessus.

Deux fixtures sont nécessaires : le cas nominal, et une variante sans colonne
`indicatif` (`test_import_csv_without_indicatif`).

## Critères d'acceptation

| # | Critère | Vérification |
|---|---|---|
| A1 | Le datastore local est un Redis 8.x exposant RedisJSON | `test_datastore.py` (marqué `integration`, `skip` sans serveur) |
| A2 | Le runtime satisfait `requires-python` du `pyproject` | `test_runtime.py` |
| A3 | La suite backend est à **zéro échec** avec un `redis:8.10` joignable | `pytest tests/ -q` |
| A4 | La suite backend ne régresse pas sans serveur réel (les 4 tests dépendants sont `skip`, pas `fail`) | `pytest tests/ -q` sans `REDIS_URL` |
| A5 | `ng test admin` et `ng test form` compilent et sont à zéro échec | `ng test <app> --watch=false` |
| A6 | Les e2e s'exécutent et les specs retenues sont vertes ; toute spec écartée est tracée et justifiée | `playwright test --reporter=line` |
| A7 | Les deux builds de production passent | `ng build {admin,form} --configuration production` |
| A8 | `deploy-dev` est gardé par les jobs de test, qui tournent aussi sur `push` | `test_ci_workflow.py` |
| A9 | La CI épingle Python 3.14 et Node 24, et fournit un service `redis:8.10` | `test_ci_workflow.py` |
| A10 | `./run_local.sh` démarre la stack sur `redis:8.10` et `/health` répond `{"status":"healthy","redis":"connected"}` | manuel |
| A11 | Aucun identifiant `Valkey`/`valkey` résiduel dans le code | `grep -ril valkey backend/app backend/tests frontend/projects frontend/e2e` |
| A11bis | Les mentions restantes sont limitées à : `backend/terraform/` (hors périmètre), `backend/scripts/setup_gcp.sh` (lit des sorties Terraform, F18), les sections GCP du `README.md` (bannière d'avertissement posée), et les citations historiques des ADR | lecture |
| A12 | La règle `*.csv` du `.gitignore` reste en vigueur partout sauf `docs/examples/` | lecture du `.gitignore` |

## Cas limites et pièges

1. **Les 4 tests qui exigent un vrai serveur.** `fakeredis` 2.37.0 ne les couvre
   toujours pas. Ils ne doivent pas devenir des `fail` silencieux quand aucun
   serveur n'est disponible : critère **A4**. Le choix retenu est un `skip`
   conditionnel, pas un contournement de la logique testée.
2. **`import-wizard.spec.ts:58` contredit le backend.** La spec e2e attend
   `default skip lines = 6` ; le backend détecte **4**
   (`test_import_vehicles.py:74`, `docs/specs/import-vehicules-csv.md` §Règles 2).
   L'un des deux a tort — arbitrage requis, pas un ajustement d'assertion.
3. **`admin-reservation-calendar.spec.ts` ne teste rien** (`docs/TODO.md` M24) :
   toutes ses assertions sont sous `if (await createButton.isVisible())` et il est
   écrit contre un formulaire inexistant. Le rendre « vert » serait un faux
   positif : il doit être réécrit ou retiré, explicitement.
4. **Les deux `app.spec.ts` sont des restes de `ng new`** (`toContain('Hello,
   admin')` / `('Hello, form')`). Celui de `form` échoue déjà ; celui d'`admin`
   échouera dès que le projet compilera.
5. **`HttpClientTestingModule` est déprécié** en Angular 21 au profit de
   `provideHttpClient()` + `provideHttpClientTesting()`.
6. **`qr-code.service.spec.ts:26-34`** souscrit sans jamais `flush()` la requête
   HTTP : `afterEach(httpMock.verify)` le fera échouer une fois le `done()` retiré.
7. **Deux membres testés sont `protected`** (`error`, `printQrCodes`) : accès par
   indexation dans le test plutôt qu'élargissement de la visibilité du composant
   pour les besoins du test.
8. **`starlette.testclient` avertit** : `Using httpx with starlette.testclient is
   deprecated; install httpx2 instead`. Non bloquant ; noté pour un chantier
   ultérieur.

## Non-objectifs

Explicitement **hors périmètre** de ce chantier, et donc toujours ouverts après lui :

- **Terraform** (`docs/TODO.md` H7). Les deux racines continueront d'échouer à
  `tofu validate`. `backend/terraform/memorystore_valkey.tf` est renommé mais son
  contenu — un `google_memorystore_instance` en mode Valkey — n'est **pas** porté
  vers un équivalent Redis 8.
- **Le déploiement GCP** : Cloud Run, Memorystore, `gcp-deploy.sh` (`docs/TODO.md`
  N1, D3). La consigne est explicite : « on regardera le déploiement dans GCP plus
  tard ».
- **Les constats de sécurité** C1, C3, S1–S12 et les bugs R1–R7 de `docs/TODO.md`.
  Ce chantier ne corrige **aucun** d'entre eux ; il ne doit pas non plus les
  aggraver. En particulier, rendre `ng test` et les e2e exécutables peut révéler
  des échecs qui *documentent* ces bugs : ils seront remontés, pas masqués.
- **La montée du client `redis` en 7.x** (D-D).
- **L'ajout d'un Python 3.14 système** à `scripts/vm-provision.sh`.

## Annexe — commandes de vérification

```sh
# Datastore
docker run -d --rm --name clef-redis -p 6379:6379 redis:8.10

# Backend (venv Python 3.14 via uv)
cd backend
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
USE_MOCKS=true REDIS_URL=redis://localhost:6379/0 .venv/bin/python -m pytest tests/ -q

# Frontend unitaire
cd frontend && npx ng test admin --watch=false && npx ng test form --watch=false

# E2E
cd frontend && npx playwright test --reporter=line

# Builds
cd frontend && npx ng build admin --configuration production \
            && npx ng build form  --configuration production

# Stack complète
./run_local.sh && curl -s localhost:8000/health
```


---

## Résultat — chantier terminé le 2026-08-13

Les 9 waves du plan ont été exécutées. Sorties authentiques, dernière mesure :

| Critère | Commande | Résultat |
|---|---|---|
| A1, A3 | `pytest tests/ -q` avec `redis:8.10` | ✅ `410 passed, 1 skipped` |
| A4 | `pytest tests/ -q` sans serveur | ✅ `394 passed, 17 skipped` — **aucun échec** |
| A2 | `test_runtime.py` sur CPython 3.14.6 | ✅ |
| A5 | `ng test admin` / `ng test form` | ✅ `19 passed` / `3 passed` |
| A6 | `playwright test --reporter=line` | ✅ `30 passed` |
| A7 | `ng build {admin,form} --configuration production` | ✅ exit 0 |
| A8, A9 | `test_ci_workflow.py` | ✅ 8 assertions |
| A12 | `git check-ignore` | ✅ `docs/examples/*.csv` réinclus, `backend/tests/*.csv` toujours ignoré |

**A6 — aucune spec e2e n'a été écartée.** Les 30 tests passent. Le plan prévoyait la
possibilité d'en mettre de côté ; ce n'a pas été nécessaire. Une réserve subsiste,
tracée en M24 : dans `admin-reservation-calendar.spec.ts`, le bloc gardé par
`if (await createButton.isVisible())` reste **inerte** — le bouton « Nouvelle
réservation » n'existe pas, donc la création de réservation n'est pas couverte, même si
le fichier est vert.

**A10 — vérifié, sous une condition.** Les trois images se reconstruisent sans erreur
sur leurs nouvelles bases (`python:3.14-slim`, `node:24-alpine`) et la stack complète
démarre :

```
GET  localhost:8000/health  → {"status":"healthy","redis":"connected"}
redis-cli INFO server       → redis_version:8.10.0
GET  localhost:4200         → 200   (admin, écran de connexion rendu)
GET  localhost:4202         → 200   (form)
GET  localhost:8000/docs    → 200
GET  localhost:8000/auth/me → 401   (sans session — attendu)
```

⚠️ **Mais `./run_local.sh` échoue tel quel dans cette VM** :

```
Container clef-backend  Error  dependency backend failed to start
dependency failed to start: container clef-backend is unhealthy
```

Cause, lue dans les logs du conteneur : `backend/.env` porte `USE_MOCKS=false`, donc
l'app instancie le vrai `GoogleSheetsService`, qui exige
`/credentials/clef-backend-dev-key.json` — monté depuis `~/.cred/CLEF`, **vide par
construction** dans cette VM (le modèle de sécurité veut qu'elle ne détienne aucune
credential sortante). Le healthcheck échoue, et les deux frontends ne démarrent donc
jamais.

**Ce n'est pas une régression de ce chantier** : la trace pointe
`app/services/sheets_real.py:39`, sans rapport avec Redis, Python 3.14 ou Node 24. Le
même `.env` aurait produit le même échec avant. Les mesures ci-dessus ont été obtenues
avec un fichier d'override éphémère posant `USE_MOCKS=true` sur le seul service
`backend` — **aucun fichier du dépôt n'a été modifié pour cela**. Voir le constat H11
de `docs/TODO.md` : décision requise.

### Écarts au plan, assumés

1. **M26 non corrigé.** Le plan prévoyait de réordonner les dépendances de
   `update_config` pour que le 403 précède l'ouverture de la connexion. À l'examen, le
   motif est systématique sur **8 routes** de `config.py` : réordonner une chaîne
   d'autorisation dépassait le périmètre d'un chantier de mise au vert. Le test
   concerné est marqué `integration` et le constat est consigné.
2. **Deux corrections applicatives faites**, au-delà du strict test : les liens de
   navigation manquants (H9) et l'`aria-label` du bouton d'aide (H10). Dans les deux
   cas, les specs frontend décrivaient déjà le comportement attendu, tout était en
   place côté service et guards, et affaiblir les tests aurait été le seul autre choix.
3. **`backend/test_output.txt` supprimé et gitignoré** (M30) — artefact de run
   versionné, non prévu au plan.
