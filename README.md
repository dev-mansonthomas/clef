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
- **Backend**: Python 3.13 / FastAPI (async), port 8000
- **Database**: Valkey 8 (Redis-compatible) with native JSON module — single source of truth, no SQL
- **Google APIs**: Drive (documents), Calendar (reservations), Gmail (alerts), Sheets (referentials via Apps Script)
- **Auth**: Google OAuth 2.0 SSO restricted to `@croix-rouge.fr`
- **Infrastructure**: GCP Cloud Run, Memorystore for Valkey 8, Cloud KMS
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
│   │   └── cache/              # Valkey connection layer
│   ├── tests/                  # pytest tests
│   └── terraform/              # Infrastructure as Code
├── google-apps-scripts/        # Apps Script for Spreadsheet ↔ API sync
├── docker/                     # Docker configuration (Valkey)
├── infra/                      # Terraform/OpenTofu GCP setup
└── docker-compose.yml          # Local dev environment
```

## Quick Start (Docker Compose — recommended)

```bash
# Clone and start all services
docker compose up

# Services:
# - Admin app:  http://localhost:4200
# - Form app:   http://localhost:4202
# - Backend:    http://localhost:8000 (API docs at /docs)
# - Valkey:     localhost:6379
```

## Manual Setup

### Backend

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
# Requires Valkey on localhost:6379
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
| `REDIS_URL` | Valkey connection URL (primary database) | `redis://localhost:6379/0` |
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
# Backend — nécessite Python 3.13. `python3 -m venv` est cassé dans la VM
# (ensurepip absent) : utiliser uv.
cd backend
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
export USE_MOCKS=true
.venv/bin/python -m pytest tests/ -q
#   → 12 failed, 356 passed, 1 skipped

# Idem avec un vrai Valkey (fait tomber 4 échecs sur 12) :
docker run -d --rm -p 6379:6379 valkey/valkey-bundle:8
export REDIS_URL="redis://localhost:6379/0"
.venv/bin/python -m pytest tests/ -q
#   → 8 failed, 360 passed, 1 skipped
#   Les 8 restants : fixture CSV perdue, voir docs/TODO.md (H2).

# Frontend — tests unitaires : NE COMPILENT PAS
cd frontend && npx ng test admin --watch=false
#   → TS2304: Cannot find name 'spyOn'  (specs Jasmine sur runner Vitest)
#   Aucun test unitaire frontend n'est actuellement exécutable.

# E2E (Playwright) — 6 specs, jamais exécutées par la CI
cd frontend && npx playwright test
```

Ne pas utiliser `pytest -x` : le premier échec masquerait l'état réel de la suite.

⚠️ Le module **JSON** de Valkey est obligatoire : d'où l'image `valkey-bundle:8`
(et non `valkey:8`) et l'extra `fakeredis[json]` dans `requirements.txt`.

See [`frontend/e2e/README.md`](frontend/e2e/README.md) for detailed E2E test documentation.

## Infrastructure (GCP)

| Environment | GCP Project | Services |
|-------------|-------------|----------|
| dev | `rcq-fr-dev` | Cloud Run, Memorystore for Valkey 8, Cloud KMS |
| test | `rcq-fr-test` | Cloud Run, Memorystore for Valkey 8, Cloud KMS |
| prod | `rcq-fr-prod` | Cloud Run, Memorystore for Valkey 8, Cloud KMS |

- All resources prefixed with `clef-` (shared GCP projects)
- IaC: OpenTofu/Terraform in [`infra/main.tf`](infra/main.tf) and [`backend/terraform/`](backend/terraform/)

## Connecting to Remote Valkey

Memorystore for Valkey is the **primary database** and is only accessible from the GCP VPC network. The backend connects automatically via the internal VPC; the `REDIS_URL` variable is configured by Terraform.

### Valkey Instances

| Environment | Instance | Region |
|-------------|----------|--------|
| dev | clef-valkey-dev | europe-west9 |
| test | clef-valkey-test | europe-west9 |
| prod | clef-valkey-prod | europe-west9 |

### Via IAP Tunnel (recommended)

```bash
gcloud compute ssh BASTION_VM \
  --zone=europe-west9-b \
  --tunnel-through-iap \
  -- -N -L 6379:VALKEY_INTERNAL_IP:6379
```

Replace `BASTION_VM` with a VM in the same VPC, and `VALKEY_INTERNAL_IP` with the Valkey internal IP (from GCP console or `tofu output`).

### Via Cloud Shell

Cloud Shell has access to the Memorystore network:

```bash
redis-cli -h VALKEY_INTERNAL_IP -p 6379
```

### Via Redis Insight

1. Create the IAP tunnel (see above)
2. Open Redis Insight → Add connection: **Host** `localhost`, **Port** `6379`

### Authentication

Memorystore for Valkey uses **IAM** authentication.

> ⚠️ **Écart vérifié le 2026-08-13 — cette section décrit une intention, pas la réalité.**
> `roles/memorystore.dbConnectionUser` n'est accordé **nulle part** dans le dépôt.
> Les seuls rôles réellement attribués au service account `clef-backend` par
> `backend/terraform/service_account.tf` sont :
>
> - `roles/cloudkms.cryptoKeyEncrypterDecrypter`
> - `roles/compute.instanceAdmin.v1`
>
> Le rôle nécessaire à la connexion IAM à Memorystore doit donc être ajouté avant
> tout déploiement, sinon le backend ne pourra pas s'authentifier auprès de
> l'instance Valkey. Voir `docs/TODO.md` (M23) et
> `docs/adr/0005-deux-arbres-terraform-et-deploiement-imperatif.md`.

### Useful Commands

```bash
# View Valkey endpoints
cd backend/terraform && tofu output valkey_endpoints

# Test connection (from Cloud Shell or via tunnel)
redis-cli -h VALKEY_IP ping
# Expected response: PONG
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Angular 21, Angular Material, TypeScript, PWA |
| Backend | Python 3.13, FastAPI, Pydantic v2 |
| Database | Valkey 8 (JSON module) |
| Auth | Google OAuth 2.0, Cloud KMS |
| Cloud | GCP Cloud Run, Memorystore |
| Testing | pytest, Vitest, Playwright |
| IaC | OpenTofu/Terraform |
| CI/CD | GitHub Actions |
