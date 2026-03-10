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
| `OKTA_DOMAIN` | Okta domain | `croix-rouge.okta.com` |
| `OKTA_CLIENT_ID` | Okta client ID | Provided by Okta |
| `OKTA_CLIENT_SECRET` | Okta client secret | Provided by Okta |
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
| `OKTA_DOMAIN` | Okta domain | `croix-rouge.okta.com` |
| `OKTA_CLIENT_ID` | Okta client ID | Provided by Okta |
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

## Technology Stack

### Frontend
- Angular 21
- Angular Material
- TypeScript
- SCSS

### Backend
- Python 3.13
- FastAPI
- Pydantic
- Uvicorn
- Redis (optional)
