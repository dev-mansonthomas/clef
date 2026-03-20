# CLEF Backend — API de gestion des véhicules Croix-Rouge

Python 3.13 + FastAPI (async natif)

## Architecture

```
backend/
├── app/
│   ├── main.py              # FastAPI application, startup/shutdown
│   ├── scheduler.py          # Scheduled tasks (alerts, CT checks)
│   ├── auth/                 # Google OAuth 2.0 SSO (@croix-rouge.fr)
│   │   ├── config.py         # AuthSettings (scopes, OAuth URLs)
│   │   ├── dependencies.py   # Auth dependencies (require_authenticated_user, etc.)
│   │   ├── google_oauth.py   # OAuth flow implementation
│   │   ├── models.py         # User model
│   │   ├── routes.py         # /auth/* endpoints
│   │   └── service.py        # Auth service (token management)
│   ├── admin/                # Super admin routes
│   ├── cache/                # Redis/Valkey cache layer
│   ├── models/               # Pydantic models
│   │   ├── valkey_models.py  # VehicleData, BenevoleData, DTConfiguration, etc.
│   │   ├── vehicle.py        # Vehicle API response models
│   │   ├── reservation.py    # Reservation models
│   │   ├── calendar.py       # Calendar models
│   │   ├── carnet_bord.py    # Carnet de bord (vehicle logbook) models
│   │   ├── config.py         # DT Configuration models
│   │   ├── import_models.py  # CSV import models
│   │   └── qr_code.py        # QR code models
│   ├── routers/              # API endpoints
│   │   ├── vehicles.py       # /api/vehicles/* — CRUD, Drive documents, photos
│   │   ├── reservations.py   # /api/reservations/* — Reservation management
│   │   ├── calendar.py       # /api/calendar/* — Google Calendar integration
│   │   ├── carnet_bord.py    # /api/carnet-bord/* — Vehicle logbook entries
│   │   ├── config.py         # /api/config/* — DT configuration
│   │   ├── sync.py           # /api/sync/* — Google Apps Script sync endpoints
│   │   ├── alerts.py         # /api/alerts/* — Email alerts (CT, assurance)
│   │   ├── benevoles.py      # /api/benevoles/* — Volunteer data
│   │   ├── stats.py          # /api/stats/* — Dashboard statistics
│   │   ├── api_keys.py       # /api/api-keys/* — API key management
│   │   ├── ical.py           # /api/ical/* — iCal feed
│   │   ├── import_vehicles.py # /api/import/* — CSV vehicle import
│   │   ├── ul_config.py      # /api/ul-config/* — UL configuration
│   │   ├── unites_locales.py # /api/unites-locales/* — UL listing
│   │   └── upload.py         # /api/upload/* — File uploads
│   ├── services/             # Business logic
│   │   ├── valkey_service.py          # Multi-tenant Valkey (JSON.SET/GET)
│   │   ├── vehicle_service.py         # Vehicle enrichment & status
│   │   ├── vehicle_document_service.py # Google Drive document management
│   │   ├── vehicle_photo_service.py   # Vehicle photos (prise/retour)
│   │   ├── drive_service.py           # Google Drive API wrapper
│   │   ├── calendar_service.py        # Google Calendar API wrapper
│   │   ├── gmail_service.py           # Gmail API for alerts
│   │   ├── config_service.py          # DT configuration service
│   │   ├── alert_service.py           # Alert scheduling & sending
│   │   ├── carnet_bord_service.py     # Logbook entries
│   │   ├── dt_token_service.py        # DT Manager OAuth token management
│   │   ├── kms_service.py             # Cloud KMS encryption for tokens
│   │   ├── stats_service.py           # Statistics computation
│   │   ├── qr_code_service.py         # QR code generation
│   │   └── upload_service.py          # File upload handling
│   └── mocks/                # Mock services for dev/testing
├── tests/                    # pytest test suite
├── pyproject.toml            # Dependencies & project config
└── Dockerfile / Dockerfile.dev
```

## Key APIs

- **Auth**: `/auth/*` — Google OAuth 2.0 SSO, DT Manager authorization
- **Vehicles**: `/api/vehicles/*` — CRUD, Drive documents, photos
- **Reservations**: `/api/reservations/*` — Calendar-backed reservations
- **Sync**: `/api/sync/*` — Google Apps Script ↔ Valkey sync (API Key auth)
- **Config**: `/api/config/*` — DT configuration, Drive folder management
- **Alerts**: `/api/alerts/*` — Email alerts for CT/assurance deadlines

API documentation is auto-generated at:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Data Storage

- **Valkey 8** (Redis-compatible) as primary database
- Multi-tenant with DT prefix: `DTXX:vehicules:*`, `DTXX:benevoles:*`, etc.
- JSON module for native JSON operations (`JSON.SET`, `JSON.GET`)
- No SQL database — Valkey is the single source of truth

## Google APIs Integration

| API | Scope | Usage |
| --- | --- | --- |
| Drive | drive | Vehicle documents (Carte Grise, Assurance, CT, etc.) |
| Calendar | — | Reservations synced as calendar events |
| Gmail | — | Alert emails (CT expiring, insurance) |
| Sheets | — | Read-only referential (via Google Apps Script sync) |

Auth: DT Manager's OAuth tokens, encrypted via Cloud KMS, stored in Valkey.

## Dev Setup

```bash
# Via Docker Compose (recommended)
docker compose up

# Manual
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
# Requires Valkey running on localhost:6379
```

## Testing

```bash
cd backend && python -m pytest tests/ -x -q
```

## Environment Variables

| Variable | Description |
| --- | --- |
| GOOGLE_CLIENT_ID | Google OAuth client ID |
| GOOGLE_CLIENT_SECRET | Google OAuth client secret |
| REDIS_URL | Valkey/Redis connection URL |
| USE_MOCKS | Enable mock services for dev/testing |
| SESSION_SECRET_KEY | Secret key for session encryption |