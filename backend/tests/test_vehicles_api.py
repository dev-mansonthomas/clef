"""Tests for vehicle API endpoints."""
import os
import json
import pytest
import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"

# Import and configure auth settings BEFORE importing app
from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.models.vehicle import StatusColor, VehicleDocumentType
from app.models.vehicle import VehicleDocumentSelectRequest
from app.routers.vehicles import get_vehicle_drive_documents, select_vehicle_drive_document
from app.auth import routes as auth_routes
from app.auth.config import auth_settings

# Load mock vehicle data
_mock_data_path = os.path.join(os.path.dirname(__file__), "..", "app", "mocks", "data", "vehicules.json")
with open(_mock_data_path) as _f:
    MOCK_VEHICLES = json.load(_f)
for _v in MOCK_VEHICLES:
    _v["dt"] = "DT75"

# Build a mock ValkeyService that returns only the 4 mock vehicles
from app.models.valkey_models import VehicleData as _VehicleData
_MOCK_VEHICLE_DATA = {v["immat"]: _VehicleData(**v) for v in MOCK_VEHICLES}


class _MockValkeyService:
    """Mock ValkeyService that returns only the 4 test vehicles."""
    async def list_vehicles(self):
        return list(_MOCK_VEHICLE_DATA.keys())

    async def get_vehicle(self, immat: str):
        return _MOCK_VEHICLE_DATA.get(immat)

    async def set_vehicle(self, vehicle_data):
        _MOCK_VEHICLE_DATA[vehicle_data.immat] = vehicle_data
        return True

    async def get_configuration(self):
        return None


def _override_valkey():
    return _MockValkeyService()


from app.routers.vehicles import get_valkey_service


@pytest.fixture(autouse=True)
def _mock_valkey_dependency():
    """Override ValkeyService dependency for all tests in this module."""
    app.dependency_overrides[get_valkey_service] = _override_valkey
    yield
    app.dependency_overrides.pop(get_valkey_service, None)


client = TestClient(app)


def get_authenticated_client(email: str) -> TestClient:
    """Helper to get an authenticated test client via OAuth flow."""
    # Use the same okta_mock instance that auth routes uses
    okta_mock = auth_routes.okta_mock
    if not okta_mock:
        raise RuntimeError("okta_mock is None - ensure USE_MOCKS=true is set")

    # Create a new client for this test
    test_client = TestClient(app)

    # Go through OAuth flow
    code = okta_mock.create_mock_authorization_code(email)
    response = test_client.get(
        f"/auth/callback?code={code}&state=test-state",
        follow_redirects=False
    )

    # The callback should set a cookie and redirect
    assert response.status_code == 307, f"Callback failed: {response.status_code} - {response.json() if response.status_code != 307 else ''}"

    # Extract and set the session cookie on the client
    session_cookie = response.cookies.get(auth_settings.session_cookie_name)
    if session_cookie:
        test_client.cookies.set(auth_settings.session_cookie_name, session_cookie)

    return test_client


class TestVehicleStatusCalculation:
    """Test status calculation logic."""
    
    def test_status_expired(self):
        """Test that expired dates show red status."""
        from app.services.vehicle_service import VehicleService
        
        # Date in the past
        past_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        status = VehicleService.calculate_status(past_date)
        
        assert status.color == StatusColor.RED
        assert status.days_until_expiry < 0
    
    def test_status_expiring_soon(self):
        """Test that dates < 60 days show orange status."""
        from app.services.vehicle_service import VehicleService
        
        # Date in 30 days (< 60 days threshold)
        soon_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        status = VehicleService.calculate_status(soon_date)
        
        assert status.color == StatusColor.ORANGE
        assert 0 <= status.days_until_expiry < 60
    
    def test_status_ok(self):
        """Test that dates > 60 days show green status."""
        from app.services.vehicle_service import VehicleService
        
        # Date in 100 days (> 60 days threshold)
        future_date = (date.today() + timedelta(days=100)).strftime("%Y-%m-%d")
        status = VehicleService.calculate_status(future_date)
        
        assert status.color == StatusColor.GREEN
        assert status.days_until_expiry >= 60
    
    def test_status_missing_date(self):
        """Test that missing dates show red status."""
        from app.services.vehicle_service import VehicleService
        
        status = VehicleService.calculate_status(None)
        
        assert status.color == StatusColor.RED
        assert status.value == "N/A"
        assert status.days_until_expiry is None


class TestVehicleListEndpoint:
    """Test GET /api/vehicles endpoint."""
    
    def test_list_vehicles_gestionnaire_dt(self):
        """Test that Gestionnaire DT sees all vehicles."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.get("/api/vehicles")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 4  # All 4 mock vehicles
        assert len(data["vehicles"]) == 4

        # Check that status fields are present
        vehicle = data["vehicles"][0]
        assert "status_ct" in vehicle
        assert "status_pollution" in vehicle
        assert "status_disponibilite" in vehicle
        assert "color" in vehicle["status_ct"]

    def test_list_vehicles_responsable_ul(self):
        """Test that Responsable UL sees only their UL vehicles."""
        auth_client = get_authenticated_client("claire.rousseau@croix-rouge.fr")
        response = auth_client.get("/api/vehicles")

        assert response.status_code == 200
        data = response.json()
        # Claire is Responsable UL Paris 15, should see 2 vehicles
        assert data["count"] == 2
        assert all(v["dt_ul"] == "UL Paris 15" for v in data["vehicles"])

    def test_list_vehicles_benevole(self):
        """Test that Bénévole sees only their UL vehicles."""
        auth_client = get_authenticated_client("jean.dupont@croix-rouge.fr")
        response = auth_client.get("/api/vehicles")

        assert response.status_code == 200
        data = response.json()
        # Jean is from UL Paris 15, should see 2 vehicles
        assert data["count"] == 2
        assert all(v["dt_ul"] == "UL Paris 15" for v in data["vehicles"])

    def test_list_vehicles_unauthorized(self):
        """Test that missing auth returns 401."""
        response = client.get("/api/vehicles")

        assert response.status_code == 401


class TestVehicleDetailEndpoint:
    """Test GET /api/vehicles/{immat} endpoint."""

    def test_get_vehicle_success(self):
        """Test getting a specific vehicle by immat."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.get("/api/vehicles/AB-123-CD")

        assert response.status_code == 200
        vehicle = response.json()
        assert vehicle["nom_synthetique"] == "VSAV-PARIS15-01"
        assert vehicle["immat"] == "AB-123-CD"
        assert "status_ct" in vehicle
        assert "status_pollution" in vehicle

    def test_get_vehicle_not_found(self):
        """Test getting a non-existent vehicle."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.get("/api/vehicles/NON-EXISTENT")

        assert response.status_code == 404

    def test_get_vehicle_forbidden(self):
        """Test that user cannot access vehicle from another UL."""
        # Jean is from UL Paris 15, trying to access UL Paris 16 vehicle (IJ-789-KL)
        auth_client = get_authenticated_client("jean.dupont@croix-rouge.fr")
        response = auth_client.get("/api/vehicles/IJ-789-KL")

        assert response.status_code == 403


class TestVehicleDriveDocumentsEndpoints:
    """Test Drive-backed vehicle document endpoints."""

    @pytest.mark.asyncio
    async def test_get_vehicle_drive_documents_success(self):
        mock_vehicle = MagicMock()
        mock_valkey = MagicMock()
        mock_user = MagicMock()

        with patch(
            "app.routers.vehicles.get_accessible_vehicle_data",
            new=AsyncMock(return_value=("VSAV-PARIS15-01", mock_vehicle, {})),
        ), patch(
            "app.routers.vehicles.vehicle_document_service.get_documents_overview",
            new=AsyncMock(return_value={
                "configured": True,
                "root_folder_id": "root-folder-123",
                "root_folder_url": "https://drive.google.com/drive/folders/root-folder-123",
                "vehicle_folder_name": "VSAV-PARIS15-01",
                "vehicle_folder_id": "vehicle-folder-123",
                "vehicle_folder_url": "https://drive.google.com/drive/folders/vehicle-folder-123",
                "documents": {
                    VehicleDocumentType.CARTE_GRISE.value: {
                        "key": VehicleDocumentType.CARTE_GRISE.value,
                        "label": "Carte grise",
                        "folder_name": "Carte Grise",
                        "managed": True,
                        "folder_id": "folder-cg",
                        "folder_url": "https://drive.google.com/drive/folders/folder-cg",
                        "file_count": 1,
                        "current_file": {
                            "file_id": "file-cg-1",
                            "name": "carte-grise.pdf"
                        }
                    }
                }
            }),
        ):
            result = await get_vehicle_drive_documents(
                "VSAV-PARIS15-01",
                current_user=mock_user,
                valkey_service=mock_valkey,
            )

        assert result["configured"] is True
        assert result["documents"]["carte_grise"]["current_file"]["file_id"] == "file-cg-1"

    @pytest.mark.asyncio
    async def test_select_vehicle_drive_document_success(self):
        mock_vehicle = MagicMock()
        mock_valkey = MagicMock()
        mock_user = MagicMock()

        with patch(
            "app.routers.vehicles.get_accessible_vehicle_data",
            new=AsyncMock(return_value=("VSAV-PARIS15-01", mock_vehicle, {})),
        ), patch(
            "app.routers.vehicles.vehicle_document_service.associate_existing_file",
            new=AsyncMock(return_value={
                "key": VehicleDocumentType.CARTE_TOTAL.value,
                "label": "Carte Total",
                "folder_name": "Carte Total",
                "managed": True,
                "folder_id": "folder-total",
                "folder_url": "https://drive.google.com/drive/folders/folder-total",
                "file_count": 2,
                "current_file": {
                    "file_id": "file-total-1",
                    "name": "carte-total.pdf"
                }
            }),
        ):
            result = await select_vehicle_drive_document(
                "VSAV-PARIS15-01",
                VehicleDocumentType.CARTE_TOTAL,
                VehicleDocumentSelectRequest(file_id="file-total-1"),
                current_user=mock_user,
                valkey_service=mock_valkey,
            )

        assert result["current_file"]["file_id"] == "file-total-1"


class TestVehicleUpdateEndpoint:
    """Test PATCH /api/vehicles/{immat} endpoint."""

    def test_update_vehicle_success(self):
        """Test updating vehicle metadata."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.patch(
            "/api/vehicles/AB-123-CD",
            json={
                "commentaires": "Updated comment",
                "couleur_calendrier": "#FF5733"
            }
        )

        assert response.status_code == 200
        vehicle = response.json()
        assert vehicle["commentaires"] == "Updated comment"

    def test_update_vehicle_not_found(self):
        """Test updating a non-existent vehicle."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.patch(
            "/api/vehicles/NON-EXISTENT",
            json={"commentaires": "Test"}
        )

        assert response.status_code == 404

    def test_update_vehicle_forbidden(self):
        """Test that user cannot update vehicle from another UL."""
        # Jean is from UL Paris 15, trying to update UL Paris 16 vehicle (IJ-789-KL)
        auth_client = get_authenticated_client("jean.dupont@croix-rouge.fr")
        response = auth_client.patch(
            "/api/vehicles/IJ-789-KL",
            json={"commentaires": "Test"}
        )

        assert response.status_code == 403


class TestVehicleFiltering:
    """Test UL-based filtering logic via API endpoints."""

    def test_filter_gestionnaire_dt_sees_all(self):
        """Test that Gestionnaire DT sees all vehicles via API."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.get("/api/vehicles")

        assert response.status_code == 200
        data = response.json()
        # DT manager should see all 4 vehicles
        assert data["count"] == 4

    def test_filter_responsable_ul_sees_only_their_ul(self):
        """Test that Responsable UL sees only their UL via API."""
        auth_client = get_authenticated_client("claire.rousseau@croix-rouge.fr")
        response = auth_client.get("/api/vehicles")

        assert response.status_code == 200
        data = response.json()
        # UL Paris 15 responsible should see only their vehicles
        assert data["count"] == 2
        for vehicle in data["vehicles"]:
            assert "Paris 15" in vehicle["dt_ul"]


class TestVehicleUppercaseFields:
    """Test that immat and indicatif are forced to uppercase."""

    def test_vehicle_create_model_uppercase(self):
        """Test that VehicleCreate model forces uppercase on immat and indicatif."""
        from app.models.vehicle import VehicleCreate, DisponibiliteStatus

        # Create vehicle with lowercase immat and indicatif
        vehicle = VehicleCreate(
            dt_ul="UL Paris 15",
            immat="ab-123-cd",  # lowercase
            indicatif="paris-15-01",  # lowercase
            nom_synthetique="test-vehicle",
            marque="Renault",
            modele="Master",
            type="VSAV",
            nb_places="3",
            carte_grise="CG123456",
            operationnel_mecanique=DisponibiliteStatus.DISPO
        )

        # Verify fields are uppercased
        assert vehicle.immat == "AB-123-CD"
        assert vehicle.indicatif == "PARIS-15-01"

    def test_vehicle_data_model_uppercase(self):
        """Test that VehicleData model forces uppercase on immat and indicatif."""
        from app.models.valkey_models import VehicleData

        # Create vehicle data with lowercase immat and indicatif
        vehicle_data = VehicleData(
            immat="ef-456-gh",  # lowercase
            dt="DT75",
            dt_ul="UL Paris 16",
            indicatif="paris-16-02",  # lowercase
            marque="Peugeot",
            modele="Partner",
            nom_synthetique="test-vehicle-2",
            operationnel_mecanique="Dispo",
            type="VL",
            carte_grise="CG789",
            nb_places="5",
            lieu_stationnement="Garage"
        )

        # Verify fields are uppercased
        assert vehicle_data.immat == "EF-456-GH"
        assert vehicle_data.indicatif == "PARIS-16-02"

