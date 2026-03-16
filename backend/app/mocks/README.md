# Google API Mocks

Mock implementations of Google APIs (Sheets, Drive, Calendar, Gmail) for local development and testing.

## Usage

Set the `USE_MOCKS` environment variable to `true` to use mock services instead of real Google APIs:

```bash
export USE_MOCKS=true
```

Or in your `.env` file:

```
USE_MOCKS=true
```

## Services

### Google Sheets Mock

Mock implementation of Google Sheets API with pre-loaded test data:

- **Référentiel Véhicules**: 4 test vehicles with all 19 columns
- **Référentiel Bénévoles**: 5 test volunteers
- **Référentiel Responsables**: 4 test managers

```python
from backend.app.mocks.service_factory import get_sheets_service

service = get_sheets_service()
vehicules = service.get_vehicules()
benevole = service.get_benevole_by_email("jean.dupont@croix-rouge.fr")
```

### Google Drive Mock

Mock implementation for file and folder operations:

```python
from backend.app.mocks.service_factory import get_drive_service

service = get_drive_service()
folder = service.create_folder("Test Folder")
file = service.upload_file("test.jpg", file_content, "image/jpeg", folder["id"])
```

### Google Calendar Mock

Mock implementation for calendar and event management:

```python
from backend.app.mocks.service_factory import get_calendar_service

service = get_calendar_service()
calendar = service.create_calendar("Test Calendar")
event = service.create_event(
    calendar_id=calendar["id"],
    summary="Réservation VSAV",
    start=datetime.now(),
    end=datetime.now() + timedelta(hours=2)
)
```

### Gmail Mock

Mock implementation for sending emails:

```python
from backend.app.mocks.service_factory import get_gmail_service

service = get_gmail_service()
message = service.send_email(
    to="recipient@example.com",
    subject="Test",
    body="Test message"
)

# Or use the alert helper
alert = service.send_alert_email(
    to="manager@croix-rouge.fr",
    vehicle_name="VSAV-PARIS15-01",
    alert_type="Contrôle Technique",
    expiry_date="2026-03-15"
)
```

## Test Data

### Vehicles (vehicules.json)

4 test vehicles covering different scenarios:
- VSAV-PARIS15-01: Available, CT valid until 2026-08
- VL-PARIS15-02: Available, CT expiring soon (2026-03)
- VPSP-PARIS16-01: Unavailable (under maintenance), CT expired
- VL-DT-PARIS-01: DT vehicle, available

### Volunteers (benevoles.json)

5 test volunteers from different ULs:
- Jean Dupont (UL Paris 15)
- Marie Martin (UL Paris 15)
- Pierre Bernard (UL Paris 16)
- Sophie Dubois (UL Paris 16)
- Thomas Manson (DT Paris - Gestionnaire DT)

### Managers (responsables.json)

4 test managers covering different scopes:
- Thomas Manson: Gestionnaire DT (full access)
- Claire Rousseau: Responsable UL Paris 15
- Laurent Petit: Responsable UL Paris 16
- Isabelle Moreau: Responsable Activité Spécialisée

## Testing

Run tests with mocks enabled:

```bash
USE_MOCKS=true pytest backend/tests/
```

Or run the specific mock tests:

```bash
USE_MOCKS=true pytest backend/tests/test_mocks.py -v
```

## Adding New Mock Data

To add more test data, edit the JSON files in `backend/app/mocks/data/`:

- `vehicules.json`: Add vehicles following the 19-column structure
- `benevoles.json`: Add volunteers with email, nom, prenom, ul, role
- `responsables.json`: Add managers with perimetre and type_perimetre

## Interface Compatibility

Mock services implement the same interface as real Google API services. When real services are implemented, they should match these method signatures to ensure seamless switching between mock and production modes.

