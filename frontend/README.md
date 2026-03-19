# CLEF Frontend

Angular 21 apps for Croix-Rouge vehicle fleet management. Two separate Angular projects in a monorepo workspace.

## Architecture — Two Apps

### App Admin (`projects/admin/`) — Port 4200

For DT managers and UL vehicle responsables:

- **Dashboard**: Statistics, alerts overview
- **Vehicle List**: Sortable/filterable table, status indicators (CT, pollution, disponibilité)
- **Vehicle Edit**: Full vehicle form, Google Drive document management (Carte Grise, Assurance, CT, Carte Total, Plan d'Entretien, Factures, Sinistres), photo management
- **Reservations**: Calendar view (FullCalendar), create/edit/cancel reservations
- **Import**: CSV vehicle import
- **Configuration DT**: Google Drive folder setup, document folder types, DT Manager OAuth authorization
- **Configuration UL**: UL-level settings
- **Super Admin**: Multi-DT management
- **QR Code Generator**: Generate QR codes for vehicles
- **API Key Management**: For Google Apps Script sync

Key components:

```
projects/admin/src/app/
├── components/
│   ├── vehicle-list/          # Main vehicle table
│   ├── calendar-view/         # FullCalendar reservation view
│   ├── reservation-form/      # Create/edit reservations
│   ├── dt-admin/              # DT administration
│   ├── qr-code-generator/     # QR code generation
│   └── api-keys-manager/      # API key CRUD
├── vehicles/
│   └── vehicle-edit/          # Vehicle detail/edit form
├── features/
│   ├── auth/                  # Login page
│   ├── dashboard/             # Stats dashboard
│   └── import-vehicles/       # CSV import
├── pages/
│   ├── config/                # DT Configuration page
│   ├── configuration-ul/      # UL Configuration page
│   └── super-admin/           # Super admin panel
├── services/                  # HTTP services (vehicle, reservation, calendar, etc.)
├── guards/                    # Route guards (dt-manager, super-admin, ul-responsable)
├── models/                    # TypeScript interfaces
└── shared/                    # Layout, dialogs
```

### App Form (`projects/form/`) — Port 4202

For field volunteers (bénévoles):

- **Vehicle Selector**: Select vehicle from list or scan QR code
- **Prise Form**: Vehicle checkout form (kilomètres, photos, état)
- **Retour Form**: Vehicle return form (kilomètres, photos, anomalies)
- **Reservations**: View/create reservations

Key components:

```
projects/form/src/app/
├── components/
│   ├── vehicle-selector/      # Vehicle picker (list + QR code scan)
│   ├── prise-form/            # Vehicle checkout form
│   └── retour-form/           # Vehicle return form
├── features/
│   ├── auth/                  # Login
│   ├── prise/                 # Prise feature wrapper
│   ├── retour/                # Retour feature wrapper
│   ├── reservations/          # Reservation list/form/detail
│   └── vehicle-selection/     # Vehicle selection feature
├── services/                  # HTTP services
├── models/                    # TypeScript interfaces
└── shared/                    # Layout
```

## Tech Stack

- Angular 21 (standalone components, signals)
- Angular Material (UI components)
- PWA support (both apps)
- TypeScript strict mode

## Dev Setup

```bash
# Via Docker Compose (recommended)
docker compose up
# Admin: http://localhost:4200
# Form:  http://localhost:4202

# Manual
cd frontend
npm install
npx ng serve admin          # Admin app on port 4200
npx ng serve form --port 4202  # Form app on port 4202
```

## Building

```bash
npx ng build admin    # Production build of admin app
npx ng build form     # Production build of form app
```

## Testing

```bash
npx ng test admin     # Vitest unit tests for admin
npx ng test form      # Vitest unit tests for form
npx playwright test   # E2E tests
```

## API Proxy

Both apps proxy `/api/*` and `/auth/*` to the backend (port 8000) via `proxy.conf.json`.

## Authentication

- Google OAuth 2.0 SSO (restricted to @croix-rouge.fr domain)
- Session cookie-based auth
- Route guards for role-based access (DT Manager, UL Responsable, Super Admin)
