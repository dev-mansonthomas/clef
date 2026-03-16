# Clef

Monorepo project with Angular 21 frontend and Python 3.13/FastAPI backend.

## Project Structure

```
clef/
├── frontend/          # Angular 21 workspace
│   ├── projects/
│   │   ├── admin/    # Admin application (admin.{DOMAIN})
│   │   └── form/     # Form application ({DOMAIN})
│   └── src/          # Default application
├── backend/           # FastAPI backend
│   └── app/          # Application modules
└── README.md
```

## Requirements

### Frontend
- Node.js 18+ (tested with v22.22.0)
- npm 9+ (tested with 10.9.4)

### Backend
- Python 3.13+
- pip

## Environment Configuration

The project supports three environments: **dev**, **test**, and **prod**.

### Backend Environment Variables

Copy the example file and configure:

```bash
cd backend
cp .env.example .env
# Edit .env with your values
```

Key variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Current environment | `dev`, `test`, or `prod` |
| `GCP_PROJECT` | GCP project | `rcq-fr-dev`, `rcq-fr-test`, `rcq-fr-prod` |
| `GCP_RESOURCE_PREFIX` | GCP resource prefix | `clef-` (required) |
| `DOMAIN` | Main domain | `clef.example.com` |
| `REDIS_URL` | MemoryStore URL | `redis://localhost:6379/0` |
| `SHEETS_URL_VEHICULES` | Vehicles registry | Google Sheets URL |
| `SHEETS_URL_BENEVOLES` | Volunteers registry | Google Sheets URL |
| `SHEETS_URL_RESPONSABLES` | Managers registry | Google Sheets URL |
| `GOOGLE_DOMAIN` | Google OAuth domain | `croix-rouge.okta.com` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Provided by Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Provided by Google OAuth |
| `EMAIL_GESTIONNAIRE_DT` | DT manager email | `thomas.manson@croix-rouge.fr` |
| `QR_CODE_SALT` | QR code salt | Unique random string |

**⚠️ Important**:
- All GCP resources must be prefixed with `clef-`
- There are 3 copies of each Google Sheets registry (DEV, TEST, PROD)
- `QR_CODE_SALT` must be unique per environment

Validate configuration:

```bash
cd backend
python validate_env.py
```

### Frontend Environment Variables

Copy the example file and configure:

```bash
cd frontend
cp .env.example .env
# Edit .env with your values
```

Key variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Current environment | `dev`, `test`, or `prod` |
| `API_URL` | Backend API URL | `http://localhost:8000` (dev) |
| `DOMAIN` | Main domain | `clef.example.com` |
| `GCP_PROJECT` | GCP project | `rcq-fr-dev`, `rcq-fr-test`, `rcq-fr-prod` |
| `GOOGLE_DOMAIN` | Google OAuth domain | `croix-rouge.okta.com` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Provided by Google OAuth |
| `THEME_COLOR` | Theme color | `#E30613` (Red Cross red) |

Validate configuration:

```bash
cd frontend
node validate-env.js
```

### GCP Projects by Environment

| Environment | GCP Project | Domain |
|-------------|-------------|--------|
| **dev** | `rcq-fr-dev` | `dev.clef.example.com` |
| **test** | `rcq-fr-test` | `test.clef.example.com` |
| **prod** | `rcq-fr-prod` | `clef.croix-rouge.fr` |

All GCP resources (Cloud Run, MemoryStore, etc.) are prefixed with `clef-` as projects are shared.

## Getting Started

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Serve the default app (development)
npm start
# Available at http://localhost:4200

# Serve the admin app
npx ng serve admin
# Available at http://localhost:4200

# Serve the form app
npx ng serve form
# Available at http://localhost:4200

# Build all apps
npm run build           # Default app
npx ng build admin      # Admin app
npx ng build form       # Form app
```

### Backend Setup

```bash
cd backend

# Install dependencies
pip install -e .

# Install dev dependencies (optional)
pip install -e ".[dev]"

# Run the server
uvicorn app.main:app --reload
# Available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Development

### Frontend Applications

- **Default App**: General purpose application
- **Admin App**: Administration interface (admin.{DOMAIN})
  - Configured with Angular Material
  - Located in `frontend/projects/admin/`
- **Form App**: Public form interface ({DOMAIN})
  - Configured with Angular Material
  - Located in `frontend/projects/form/`

### Backend API

- **FastAPI**: Modern Python web framework
- **CORS**: Configured for local development (localhost:4200)
- **Endpoints**:
  - `GET /` - Root endpoint
  - `GET /health` - Health check
  - `GET /docs` - Swagger UI documentation
  - `GET /redoc` - ReDoc documentation

## Testing

### Frontend E2E Tests

End-to-end tests using Playwright:

```bash
cd frontend

# Run all E2E tests
npm run e2e

# Run in UI mode (interactive)
npm run e2e:ui

# Run in headed mode (see browser)
npm run e2e:headed
```

**Test Coverage**:
- Admin vehicle management flow
- Form vehicle prise submission
- Reservation and calendar management
- 13 test scenarios across 3 critical user journeys

See `frontend/e2e/README.md` for detailed documentation.

### Backend Unit Tests

```bash
cd backend
pytest
```

## Accès à Valkey (Cache)

L'application utilise **Memorystore for Valkey** (service managé Google Cloud) pour le cache.

### Configuration

| Environnement | Instance | Région |
|---------------|----------|--------|
| dev | clef-valkey-dev | europe-west9 |
| test | clef-valkey-test | europe-west9 |
| prod | clef-valkey-prod | europe-west9 |

### Connexion depuis le backend

Le backend se connecte automatiquement via le réseau VPC interne. La variable d'environnement `REDIS_URL` est configurée par Terraform.

### Connexion depuis votre machine locale (Redis Insight)

Memorystore for Valkey n'est accessible que depuis le réseau VPC Google Cloud. Pour vous connecter localement avec Redis Insight ou redis-cli :

#### 1. Via IAP Tunnel (recommandé)

```bash
# Créer un tunnel SSH via IAP vers une VM bastion
gcloud compute ssh BASTION_VM \
  --zone=europe-west9-b \
  --tunnel-through-iap \
  -- -N -L 6379:VALKEY_INTERNAL_IP:6379
```

Remplacez :
- `BASTION_VM` : nom d'une VM dans le même VPC
- `VALKEY_INTERNAL_IP` : IP interne de Valkey (visible dans la console GCP ou via `tofu output`)

#### 2. Via Cloud Shell

Cloud Shell est dans le même réseau que Memorystore :

```bash
# Depuis Cloud Shell
redis-cli -h VALKEY_INTERNAL_IP -p 6379
```

#### 3. Connexion avec Redis Insight

1. Créer le tunnel IAP (voir ci-dessus)
2. Ouvrir Redis Insight
3. Ajouter une connexion :
   - **Host** : `localhost`
   - **Port** : `6379`
   - **Name** : `CLEF Dev` (ou Test/Prod)

### Authentification

Memorystore for Valkey utilise **IAM** pour l'authentification. Le Service Account `clef-backend@{project}.iam.gserviceaccount.com` a le rôle `roles/memorystore.dbConnectionUser`.

### Commandes utiles

```bash
# Voir les endpoints Valkey
cd backend/terraform
tofu output valkey_endpoints

# Vérifier la connexion (depuis Cloud Shell ou via tunnel)
redis-cli -h VALKEY_IP ping
# Réponse attendue: PONG
```

## Technology Stack

### Frontend
- Angular 21
- Angular Material
- TypeScript
- SCSS
- Playwright (E2E testing)

### Backend
- Python 3.13
- FastAPI
- Pydantic
- Uvicorn
- Memorystore for Valkey (cache)
- pytest (testing)
