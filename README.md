# CLEF — Croix-Rouge Fleet Management

Web application for managing vehicles of the Croix-Rouge Française (French Red Cross) Délégation Territoriale: vehicle checkout/return by volunteers, administrative tracking (CT, insurance), reservations, and alerts.

## Documentation

| Pour | Où |
|---|---|
| **Démarrer, installer, lancer, tester** | ce README |
| **Carte d'entrée pour agents IA** | [`CLAUDE.md`](CLAUDE.md) — stack, commandes vérifiées, carte des modules, pièges |
| Besoin, utilisateurs, périmètre | [`docs/product/PRD.md`](docs/product/PRD.md) |
| Architecture, flux, modèle de données | [`docs/architecture/overview.md`](docs/architecture/overview.md) |
| Contrats par fonctionnalité | [`docs/specs/`](docs/specs/) — et [`docs/specs-gestion-factures.md`](docs/specs-gestion-factures.md), spec fonctionnel d'origine |
| Décisions techniques et leurs conséquences | [`docs/adr/`](docs/adr/) |
| **Défauts connus, par sévérité** | [`docs/TODO.md`](docs/TODO.md) |
| Ce qui a été reconstruit, ce qui est perdu | [`docs/migration-status.md`](docs/migration-status.md) |

> Les documents de `docs/` ont été **reconstruits depuis le code le 2026-08-13**,
> les notes de l'agent qui a construit le projet ayant été perdues. Toute affirmation
> non vérifiable y est marquée `(inferred — verify)`. Les documents
> `DEPLOYMENT.md`, `DOCKER_SETUP.md` et `SECRETS_SETUP.md` sont **obsolètes** sur
> plusieurs points (Redis vs Valkey, Okta vs Google OAuth, noms de secrets) — voir
> `docs/TODO.md` (M23) avant de s'y fier.

## Architecture Overview

- **Frontend**: Angular 21 monorepo with 2 PWA apps
  - **Admin** (`projects/admin/`, port 4200): Vehicle management, reservations calendar, Drive documents, configuration
  - **Form** (`projects/form/`, port 4202): Vehicle checkout/return forms, QR code scanning, reservations
- **Backend**: Python 3.14 / FastAPI (async), port 8000
- **Database**: Redis 8.10 with the native JSON module — single source of truth, no SQL
- **Google APIs**: Drive (documents), Calendar (reservations), Gmail (alerts), Sheets (referentials via Apps Script)
- **Auth**: Google OAuth 2.0 SSO restricted to `@croix-rouge.fr`
- **Infrastructure**: GCP Cloud Run (Redis 8.10 en **conteneur adjoint**, instantanés RDB sur Cloud Storage), Cloud KMS — voir [ADR 0008](docs/adr/0008-redis-sidecar-cloud-run-instantanes-gcs.md) et [`DEPLOYMENT.md`](DEPLOYMENT.md)
- **Sync**: Google Apps Scripts in the referential Spreadsheet push data to the API

## Project Structure

```
clef/
├── frontend/                   # Angular 21 workspace
│   └── projects/
│       ├── admin/              # Admin PWA (port 4200)
│       └── form/               # Volunteer form PWA (port 4202)
├── backend/                    # FastAPI backend (port 8000)
│   ├── app/
│   │   ├── auth/               # Google OAuth 2.0
│   │   ├── routers/            # API endpoints
│   │   ├── services/           # Business logic + Google API integrations
│   │   ├── models/             # Pydantic models
│   │   └── cache/              # Redis connection layer
│   ├── tests/                  # pytest tests
│   └── terraform/              # ⚠️ ancienne racine IaC, périmée (docs/TODO.md N12)
├── deploy/                     # 👉 IaC et gabarit Cloud Run — la seule racine à jour
│   ├── terraform/              # OpenTofu : APIs, IAM, registre, secrets, KMS, bucket
│   └── cloudrun-api.yaml.tpl   # descripteur du service à 2 conteneurs
├── 00-infra.sh                 # provisionnement GCP    — à lancer depuis l'HÔTE
├── 01-gcp-deploy.sh            # build + déploiement    — à lancer depuis l'HÔTE
├── google-apps-scripts/        # Apps Script for Spreadsheet ↔ API sync
├── docker/                     # Docker configuration (Redis)
├── infra/                      # ⚠️ seconde racine IaC, périmée (docs/TODO.md N12)
└── docker-compose.yml          # Local dev environment
```

## Quick Start (Docker Compose — recommended)

```bash
# Mode mock — aucune credential requise, fonctionne partout
./run_local.sh

# Intégration réelle — vrais services Google, À LANCER DEPUIS L'HÔTE
./run_local.sh --real
```

Le mode par défaut est le **mock** : services Google et OIDC simulés, données
fictives, aucune credential nécessaire. Le backend annonce son mode au démarrage
(`docker compose logs backend | grep USE_MOCKS`), donc aucun doute possible.

`--real` bascule sur les vrais services Google. Le script **vérifie les prérequis
avant de démarrer quoi que ce soit** et s'arrête net en les nommant s'il en manque :
le service account sous `~/.cred/CLEF/`, et les trois identifiants de feuilles
`*_SPREADSHEET_ID` dans `backend/.env`. Ce mode n'a de sens que sur l'hôte — la VM de
développement ne détient aucune credential sortante.

```bash
# Équivalent direct, sans le script
docker compose up                      # mock
USE_MOCKS=false docker compose up      # réel

# Services:
# - Admin app:  http://localhost:4200
# - Form app:   http://localhost:4202
# - Backend:    http://localhost:8000 (API docs at /docs)
# - Redis:      localhost:6379
```

## Manual Setup

### Backend

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
# Requires Redis 8.10 on localhost:6379 (docker compose up -d redis)
# API available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npx ng serve admin              # Admin on port 4200
npx ng serve form --port 4202   # Form on port 4202
```

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for detailed setup instructions.

## Environment Configuration

### Backend Environment Variables

```bash
cd backend
cp .env.example .env
# Edit .env with your values
```

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Current environment | `dev`, `test`, or `prod` |
| `GCP_PROJECT` | GCP project | `rcq-fr-dev` |
| `GCP_RESOURCE_PREFIX` | GCP resource prefix | `clef-` (required) |
| `DOMAIN` | Main domain | `clef.example.com` |
| `REDIS_URL` | Redis connection URL (primary database) | `redis://localhost:6379/0` |
| `USE_MOCKS` | Enable mock Google APIs for dev without credentials | `true` or `false` |
| `SESSION_SECRET_KEY` | Secret key for session encryption | Unique random string |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Provided by Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Provided by Google OAuth |
| `EMAIL_GESTIONNAIRE_DT` | DT manager email | `manager@croix-rouge.fr` |
| `QR_CODE_SALT` | QR code salt (unique per environment) | Unique random string |
| `SHEETS_URL_VEHICULES` | Vehicles registry | Google Sheets URL |
| `SHEETS_URL_BENEVOLES` | Volunteers registry | Google Sheets URL |
| `SHEETS_URL_RESPONSABLES` | Managers registry | Google Sheets URL |

### Frontend Environment Variables

```bash
cd frontend
cp .env.example .env
```

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Current environment | `dev`, `test`, or `prod` |
| `API_URL` | Backend API URL | `http://localhost:8000` |
| `DOMAIN` | Main domain | `clef.example.com` |
| `GCP_PROJECT` | GCP project | `rcq-fr-dev` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Provided by Google OAuth |
| `THEME_COLOR` | Theme color | `#E30613` (Red Cross red) |

### Validate Configuration

```bash
cd backend && python validate_env.py
cd frontend && node validate-env.js
```

## Google APIs Integration

| API | Scope | Purpose |
|-----|-------|---------|
| **Drive** | `drive` | Vehicle documents organized in folders per vehicle |
| **Calendar** | `calendar` | Reservations synced as calendar events |
| **Gmail** | `gmail.send` | Automated alerts for expiring CT/insurance |
| **Sheets** | Read-only | Referential data (synced via Google Apps Script triggers) |

The DT Manager authorizes via OAuth; tokens are encrypted with Cloud KMS.

## Google Apps Script Sync

Scripts in [`google-apps-scripts/`](google-apps-scripts/) are installed in the referential Spreadsheet. Automatic triggers sync data to the backend API:

| Data | Sync Frequency | Method | Endpoint |
|------|---------------|--------|----------|
| Vehicles | Every 1 minute | `GET` | `/api/sync/{DT}/vehicules` |
| Responsables | Every hour | `GET` | `/api/sync/{DT}/responsables` |
| Bénévoles | Every hour | `POST` | `/api/sync/{DT}/benevoles` |

`{DT}` is the délégation code (e.g. `DT75`), supplied by the Apps Script `CLEF_DT`
script property. It is **not** optional — see `backend/app/routers/sync.py` and
`google-apps-scripts/api.gs`.

Uses API Key authentication (`X-API-Key` header, checked against the `SYNC_API_KEY`
environment variable). See [`google-apps-scripts/README.md`](google-apps-scripts/README.md) for installation guide.

## Testing

> ⚠️ **État réel mesuré le 2026-08-13.** La suite n'est pas verte. Les chiffres
> ci-dessous sont des sorties d'exécution, pas des objectifs. Détail des causes
> racines dans [`docs/TODO.md`](docs/TODO.md).

```bash
# Datastore : l'image officielle redis:8.10 embarque RedisJSON, dépendance dure.
docker compose up -d redis

# Backend — nécessite Python 3.14. La VM n'en a pas dans le PATH : utiliser uv.
cd backend
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
USE_MOCKS=true REDIS_URL="redis://localhost:6379/0" .venv/bin/python -m pytest tests/ -q
#   → 410 passed, 1 skipped

# Sans serveur Redis, les tests d'intégration sont IGNORÉS, pas en échec :
USE_MOCKS=true .venv/bin/python -m pytest tests/ -q
#   → 394 passed, 17 skipped

# Frontend — tests unitaires (Vitest)
cd ../frontend
npx ng test admin --watch=false   # → 19 passed
npx ng test form  --watch=false   # →  3 passed

# E2E (Playwright) — démarre lui-même les 2 serveurs Angular
npx playwright test --reporter=line   # → 30 passed
```

Ne pas utiliser `pytest -x` : le premier échec masquerait l'état réel de la suite.

⚠️ Le module **JSON** est obligatoire : d'où l'extra `fakeredis[json]` dans
`requirements.txt`, et le test `backend/tests/test_datastore.py` qui vérifie sa
présence sur le serveur réel.

See [`frontend/e2e/README.md`](frontend/e2e/README.md) for detailed E2E test documentation.

## Infrastructure (GCP)

Le déploiement complet — prérequis, OAuth, secrets, amorçage, dépannage — est
documenté dans **[`DEPLOYMENT.md`](DEPLOYMENT.md)**. En résumé, deux commandes,
**depuis l'hôte** :

```sh
./00-infra.sh dev          # provisionne l'infrastructure — une fois par environnement
./01-gcp-deploy.sh dev     # construit les images et déploie — à chaque livraison
```

| Environnement | Projet GCP | Services |
|---|---|---|
| dev | `rcq-fr-dev` | Cloud Run (`clef-api` + `clef-frontend`), Cloud Storage, Secret Manager, Cloud KMS |
| test | `rcq-fr-test` | idem — projet à créer |
| prod | `rcq-fr-prod` | idem — projet à créer |

- Toutes les ressources sont préfixées `clef-`, et les secrets `CLEF_` : **les
  projets GCP sont partagés** avec une autre application.
- IaC : OpenTofu dans **[`deploy/terraform/`](deploy/terraform/)** — seule racine
  valide. `backend/terraform/` et `infra/` sont périmées (`docs/TODO.md` N12).
- **Rien n'est déployé à ce jour** : les scripts sont écrits et vérifiés, mais
  n'ont jamais tourné contre GCP (`docs/TODO.md` N7).

### Le datastore n'est pas un service managé

Redis 8.10 tourne en **conteneur adjoint** du backend, dans la même instance Cloud
Run, joignable sur `localhost:6379`. Memorystore a été écarté : il ne sait pas
indexer ni chercher dans le JSON, ce dont CLEF dépend. L'instance Memorystore
`clef-valkey-dev` a été **détruite le 2026-08-26**. Raisonnement complet dans
[ADR 0008](docs/adr/0008-redis-sidecar-cloud-run-instantanes-gcs.md).

Trois conséquences :

| | |
|---|---|
| `maxScale = 1` **obligatoire** | une instance = un Redis. Deux instances, deux jeux de données qui divergent en silence. Le script refuse toute autre valeur |
| RPO **10 minutes** | la persistance repose sur des instantanés RDB écrits vers un bucket GCS monté en FUSE |
| Pas d'accès direct | plus de tunnel IAP ni de bastion : le datastore ne vit que dans l'instance. Pour l'inspecter, passer par les logs ou une route d'administration |

### En local

Le Redis local est celui de `docker-compose.yml`, lancé par `./run_local.sh`. Il
n'y a **aucun datastore distant auquel se connecter**.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Angular 21, Angular Material, TypeScript, PWA |
| Backend | Python 3.14, FastAPI, Pydantic v2 |
| Database | Redis 8.10 (JSON module) |
| Auth | Google OAuth 2.0, Cloud KMS |
| Cloud | GCP Cloud Run (Redis en sidecar), Cloud Storage, Secret Manager |
| Testing | pytest, Vitest, Playwright |
| IaC | OpenTofu/Terraform |
| CI/CD | GitHub Actions (tests et builds ; le **déploiement est manuel** — `docs/TODO.md` H12) |
