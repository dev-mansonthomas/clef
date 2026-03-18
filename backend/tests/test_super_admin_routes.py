"""Tests for super admin backend routes."""
import copy
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import routes as auth_routes
from app.auth.config import auth_settings
from app.models.valkey_models import DTConfiguration, VehicleData
from app.services.valkey_dependencies import get_valkey_service


okta_mock = auth_routes.okta_mock


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Ensure dependency overrides are cleared between tests."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    auth_settings.use_mocks = True
    return TestClient(app)


@pytest.fixture
def super_admin_email():
    """Configure the super admin email for the duration of the test."""
    original = auth_settings.super_admin_email
    auth_settings.super_admin_email = "thomas.manson@croix-rouge.fr"
    yield auth_settings.super_admin_email
    auth_settings.super_admin_email = original


class FakeRedisJSON:
    def __init__(self, json_store: dict[str, dict]):
        self._json_store = json_store

    async def get(self, key: str):
        value = self._json_store.get(key)
        return copy.deepcopy(value) if value is not None else None

    async def set(self, key: str, path: str, value: dict):
        assert path == "$"
        self._json_store[key] = copy.deepcopy(value)
        return True


class FakeRedis:
    def __init__(self, set_store: dict[str, set[str]], json_store: dict[str, dict]):
        self._set_store = set_store
        self._json = FakeRedisJSON(json_store)

    async def smembers(self, key: str):
        return set(self._set_store.get(key, set()))

    def json(self):
        return self._json


class FakeValkeyService:
    def __init__(self):
        self.dt = "DT75"
        self._config = DTConfiguration(
            dt="DT75",
            nom="Délégation Territoriale de Paris",
            gestionnaire_email="thomas.manson@croix-rouge.fr",
            drive_folder_id="root-folder",
            drive_folder_url="https://drive/root-folder",
            drive_vehicles_folder_id="vehicles-folder",
            drive_vehicles_folder_url="https://drive/vehicles-folder",
            drive_dt_folder_id="dt-folder",
            drive_dt_folder_url="https://drive/dt-folder",
        )
        self._ul_json_store = {
            "DT75:unite_locale:81": {
                "id": "81",
                "nom": "UL 01-02",
                "dt": "DT75",
                "created_at": "2026-03-18T00:00:00Z",
                "drive_folder_id": "ul-folder-81",
                "drive_folder_url": "https://drive/ul-folder-81",
            }
        }
        self.redis = FakeRedis(
            {"DT75:unite_locales:index": {"81"}},
            self._ul_json_store,
        )
        self._vehicles = {
            "AB-123-CD": VehicleData(
                immat="AB-123-CD",
                dt="DT75",
                dt_ul="UL 01-02",
                indicatif="VPSU 81",
                operationnel_mecanique="Dispo",
                raison_indispo="",
                prochain_controle_technique=None,
                prochain_controle_pollution=None,
                marque="Renault",
                modele="Master",
                type="VSAV",
                date_mec=None,
                nom_synthetique="VSAV-UL0102-01",
                carte_grise="CG123",
                nb_places="3",
                commentaires="",
                lieu_stationnement="Garage UL",
                instructions_recuperation="",
                assurance_2026="",
                numero_serie_baus="",
                drive_folders={
                    "vehicles_root": {
                        "folder_id": "vehicles-folder",
                        "folder_name": "Véhicules",
                        "folder_url": "https://drive/vehicles-folder",
                    },
                    "perimeter_folder": {
                        "folder_id": "ul-folder-81",
                        "folder_name": "UL 01-02",
                        "folder_url": "https://drive/ul-folder-81",
                    },
                    "vehicle_folder": {
                        "folder_id": "vehicle-folder-1",
                        "folder_name": "VSAV-UL0102-01",
                        "folder_url": "https://drive/vehicle-folder-1",
                    },
                    "documents": {},
                },
            )
        }

    async def get_configuration(self):
        return self._config.model_copy(deep=True)

    async def set_configuration(self, config: DTConfiguration):
        self._config = config.model_copy(deep=True)

    async def list_vehicles(self):
        return list(self._vehicles.keys())

    async def get_vehicle(self, immat: str):
        vehicle = self._vehicles.get(immat)
        return vehicle.model_copy(deep=True) if vehicle else None

    async def set_vehicle(self, vehicle: VehicleData):
        self._vehicles[vehicle.immat] = vehicle.model_copy(deep=True)


@pytest.fixture
def valkey_dt75():
    """Valkey-like service with cached Drive data."""
    return FakeValkeyService()


def get_authenticated_client(email: str) -> TestClient:
    """Authenticate a test client through the mock OAuth flow."""
    test_client = TestClient(app)
    code = okta_mock.create_mock_authorization_code(email)
    response = test_client.get(f"/auth/callback?code={code}&state=test-state", follow_redirects=False)
    session_token = response.cookies[auth_settings.session_cookie_name]
    test_client.cookies.set(auth_settings.session_cookie_name, session_token)
    return test_client


class TestSuperAdminStatusRoute:
    def test_status_requires_authentication(self, client: TestClient):
        response = client.get("/admin/super/status")
        assert response.status_code == 401

    def test_status_returns_true_for_super_admin(self, super_admin_email):
        auth_client = get_authenticated_client(super_admin_email)
        response = auth_client.get("/admin/super/status")
        assert response.status_code == 200
        assert response.json() == {"is_super_admin": True}

    def test_status_returns_false_for_non_super_admin(self, super_admin_email):
        auth_client = get_authenticated_client("jean.dupont@croix-rouge.fr")
        response = auth_client.get("/admin/super/status")
        assert response.status_code == 200
        assert response.json() == {"is_super_admin": False}


class TestSuperAdminDriveCacheRoutes:
    def test_get_drive_cache_forbidden_for_non_super_admin(self, super_admin_email, valkey_dt75):
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75
        auth_client = get_authenticated_client("jean.dupont@croix-rouge.fr")

        response = auth_client.get("/admin/super/cache/drive-folders")
        assert response.status_code == 403
        assert response.json()["detail"] == "Super admin access required"

    def test_get_drive_cache_returns_cached_entries(self, super_admin_email, valkey_dt75):
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75
        auth_client = get_authenticated_client(super_admin_email)

        response = auth_client.get("/admin/super/cache/drive-folders")
        assert response.status_code == 200

        data = response.json()
        assert data["dt_config"]["drive_folder_id"] == "root-folder"
        assert data["dt_config"]["drive_vehicles_folder_id"] == "vehicles-folder"
        assert data["dt_config"]["drive_dt_folder_id"] == "dt-folder"
        assert data["unites_locales"] == [{
            "id": "81",
            "nom": "UL 01-02",
            "drive_folder_id": "ul-folder-81",
            "drive_folder_url": "https://drive/ul-folder-81",
        }]
        assert data["vehicles_count"] == 1
        assert data["vehicles"] == [{
            "immat": "AB-123-CD",
            "nom_synthetique": "VSAV-UL0102-01",
            "drive_folder_id": "vehicle-folder-1",
            "drive_folder_url": "https://drive/vehicle-folder-1",
        }]

    @pytest.mark.asyncio
    async def test_clear_drive_cache_clears_dt_ul_and_vehicle_cache(self, super_admin_email, valkey_dt75):
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75
        auth_client = get_authenticated_client(super_admin_email)

        response = auth_client.delete("/admin/super/cache/drive-folders")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["cleared"] == {
            "dt_config": True,
            "unites_locales": 1,
            "vehicles": 1,
        }

        config = await valkey_dt75.get_configuration()
        assert config is not None
        assert config.drive_folder_id is None
        assert config.drive_folder_url is None
        assert config.drive_vehicles_folder_id is None
        assert config.drive_vehicles_folder_url is None
        assert config.drive_dt_folder_id is None
        assert config.drive_dt_folder_url is None

        ul_data = await valkey_dt75.redis.json().get("DT75:unite_locale:81")
        assert ul_data["drive_folder_id"] is None
        assert ul_data["drive_folder_url"] is None

        vehicle = await valkey_dt75.get_vehicle("AB-123-CD")
        assert vehicle is not None
        assert vehicle.drive_folders == {}