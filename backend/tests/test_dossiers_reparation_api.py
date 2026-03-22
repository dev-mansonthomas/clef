"""Tests for dossiers réparation API endpoints."""
import os
import json
import pytest

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"

# Import and configure auth settings BEFORE importing app
from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.auth import routes as auth_routes
from app.auth.config import auth_settings
from app.services.valkey_dependencies import get_valkey_service

# Load mock vehicle data
_mock_data_path = os.path.join(os.path.dirname(__file__), "..", "app", "mocks", "data", "vehicules.json")
with open(_mock_data_path) as _f:
    MOCK_VEHICLES = json.load(_f)
for _v in MOCK_VEHICLES:
    _v["dt"] = "DT75"

from app.models.valkey_models import VehicleData as _VehicleData
_MOCK_VEHICLE_DATA = {v["immat"]: _VehicleData(**v) for v in MOCK_VEHICLES}

# In-memory stores for dossier data
_dossier_store: dict = {}  # key -> dossier dict
_dossier_index: dict = {}  # immat -> set of numeros
_dossier_counters: dict = {}  # immat -> int
_historique_store: dict = {}  # key -> list of entries


class _MockValkeyService:
    """Mock ValkeyService for dossier tests."""
    dt = "DT75"

    async def list_vehicles(self):
        return list(_MOCK_VEHICLE_DATA.keys())

    async def get_vehicle(self, immat: str):
        return _MOCK_VEHICLE_DATA.get(immat)

    async def set_vehicle(self, vehicle_data):
        _MOCK_VEHICLE_DATA[vehicle_data.immat] = vehicle_data
        return True

    async def get_configuration(self):
        return None

    def _key(self, *parts: str) -> str:
        return f"{self.dt}:{':'.join(parts)}"

    async def create_dossier_reparation(self, immat: str, description, cree_par: str, commentaire=None, titre=None):
        from datetime import datetime
        from app.models.repair_models import DossierReparation, HistoriqueEntry, ActionHistorique

        _dossier_counters[immat] = _dossier_counters.get(immat, 0) + 1
        counter = _dossier_counters[immat]
        year = datetime.utcnow().year
        numero = f"REP-{year}-{counter:03d}"

        # Support both list and legacy string description
        if isinstance(description, str):
            description = [description]

        dossier = DossierReparation(
            numero=numero, immat=immat, dt=self.dt,
            titre=titre, description=description, commentaire=commentaire,
            cree_par=cree_par, cree_le=datetime.utcnow(),
        )
        key = self._key("vehicules", immat, "travaux", numero)
        _dossier_store[key] = dossier.model_dump(mode="json")
        _dossier_index.setdefault(immat, set()).add(numero)

        await self.add_historique_entry(immat, numero, HistoriqueEntry(
            auteur=cree_par, action=ActionHistorique.CREATION, details="Dossier créé", ref=key,
        ))
        return dossier

    async def get_dossier_reparation(self, immat: str, numero: str):
        from app.models.repair_models import DossierReparation
        key = self._key("vehicules", immat, "travaux", numero)
        data = _dossier_store.get(key)
        if not data:
            return None
        return DossierReparation(**data)

    async def list_dossiers_reparation(self, immat: str):
        from app.models.repair_models import DossierReparation
        numeros = _dossier_index.get(immat, set())
        dossiers = []
        for numero in numeros:
            d = await self.get_dossier_reparation(immat, numero)
            if d:
                dossiers.append(d)
        dossiers.sort(key=lambda d: d.cree_le, reverse=True)
        return dossiers

    async def update_dossier_reparation(self, immat: str, numero: str, dossier):
        key = self._key("vehicules", immat, "travaux", numero)
        _dossier_store[key] = dossier.model_dump(mode="json")
        return True

    async def add_historique_entry(self, immat: str, numero: str, entry):
        key = self._key("vehicules", immat, "travaux", numero, "historique")
        _historique_store.setdefault(key, []).append(entry.model_dump(mode="json"))
        return True


def _override_valkey():
    return _MockValkeyService()


@pytest.fixture(autouse=True)
def _mock_valkey_and_cleanup():
    """Override ValkeyService and clean up dossier stores after each test."""
    app.dependency_overrides[get_valkey_service] = _override_valkey
    yield
    app.dependency_overrides.pop(get_valkey_service, None)
    _dossier_store.clear()
    _dossier_index.clear()
    _dossier_counters.clear()
    _historique_store.clear()


def get_authenticated_client(email: str = "thomas.manson@croix-rouge.fr") -> TestClient:
    """Helper to get an authenticated test client."""
    okta_mock = auth_routes.okta_mock
    if not okta_mock:
        raise RuntimeError("okta_mock is None - ensure USE_MOCKS=true is set")
    test_client = TestClient(app)
    code = okta_mock.create_mock_authorization_code(email)
    response = test_client.get(f"/auth/callback?code={code}&state=test-state", follow_redirects=False)
    assert response.status_code == 307
    session_cookie = response.cookies.get(auth_settings.session_cookie_name)
    if session_cookie:
        test_client.cookies.set(auth_settings.session_cookie_name, session_cookie)
    return test_client


IMMAT = "AB-123-CD"
DT = "DT75"
BASE = f"/api/{DT}/vehicles/{IMMAT}/dossiers-reparation"


class TestCreateDossier:
    """Test POST /api/{dt}/vehicles/{immat}/dossiers-reparation."""

    def test_create_dossier_success(self):
        client = get_authenticated_client()
        response = client.post(BASE, json={"description": ["Brake repair"]})
        assert response.status_code == 201
        data = response.json()
        assert data["numero"].startswith("REP-")
        assert data["immat"] == IMMAT
        assert data["description"] == ["Brake repair"]
        assert data["statut"] == "ouvert"
        assert data["dt"] == DT

    def test_create_dossier_vehicle_not_found(self):
        client = get_authenticated_client()
        response = client.post(
            f"/api/{DT}/vehicles/NONEXISTENT/dossiers-reparation",
            json={"description": ["Test"]},
        )
        assert response.status_code == 404

    def test_create_dossier_empty_description(self):
        client = get_authenticated_client()
        response = client.post(BASE, json={"description": []})
        assert response.status_code == 422

    def test_create_dossier_unauthorized(self):
        client = TestClient(app)
        response = client.post(BASE, json={"description": ["Test"]})
        assert response.status_code == 401


class TestListDossiers:
    """Test GET /api/{dt}/vehicles/{immat}/dossiers-reparation."""

    def test_list_dossiers_empty(self):
        client = get_authenticated_client()
        response = client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["dossiers"] == []

    def test_list_dossiers_with_data(self):
        client = get_authenticated_client()
        client.post(BASE, json={"description": ["First"]})
        client.post(BASE, json={"description": ["Second"]})
        response = client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_list_dossiers_vehicle_not_found(self):
        client = get_authenticated_client()
        response = client.get(f"/api/{DT}/vehicles/NONEXISTENT/dossiers-reparation")
        assert response.status_code == 404


class TestGetDossier:
    """Test GET /api/{dt}/vehicles/{immat}/dossiers-reparation/{numero}."""

    def test_get_dossier_success(self):
        client = get_authenticated_client()
        create_resp = client.post(BASE, json={"description": ["Test"]})
        numero = create_resp.json()["numero"]
        response = client.get(f"{BASE}/{numero}")
        assert response.status_code == 200
        assert response.json()["numero"] == numero

    def test_get_dossier_not_found(self):
        client = get_authenticated_client()
        response = client.get(f"{BASE}/REP-2026-999")
        assert response.status_code == 404


class TestUpdateDossier:
    """Test PATCH /api/{dt}/vehicles/{immat}/dossiers-reparation/{numero}."""

    def test_update_description(self):
        client = get_authenticated_client()
        create_resp = client.post(BASE, json={"description": ["Original"]})
        numero = create_resp.json()["numero"]
        response = client.patch(f"{BASE}/{numero}", json={"description": ["Updated"]})
        assert response.status_code == 200
        assert response.json()["description"] == ["Updated"]

    def test_close_dossier(self):
        client = get_authenticated_client()
        create_resp = client.post(BASE, json={"description": ["Test"]})
        numero = create_resp.json()["numero"]
        response = client.patch(f"{BASE}/{numero}", json={"statut": "cloture"})
        assert response.status_code == 200
        data = response.json()
        assert data["statut"] == "cloture"
        assert data["cloture_le"] is not None

    def test_reopen_dossier(self):
        client = get_authenticated_client()
        create_resp = client.post(BASE, json={"description": ["Test"]})
        numero = create_resp.json()["numero"]
        client.patch(f"{BASE}/{numero}", json={"statut": "cloture"})
        response = client.patch(f"{BASE}/{numero}", json={"statut": "ouvert"})
        assert response.status_code == 200
        data = response.json()
        assert data["statut"] == "ouvert"
        assert data["cloture_le"] is None

    def test_cancel_dossier(self):
        client = get_authenticated_client()
        create_resp = client.post(BASE, json={"description": ["Test"]})
        numero = create_resp.json()["numero"]
        response = client.patch(f"{BASE}/{numero}", json={"statut": "annule"})
        assert response.status_code == 200
        assert response.json()["statut"] == "annule"

    def test_update_not_found(self):
        client = get_authenticated_client()
        response = client.patch(f"{BASE}/REP-2026-999", json={"description": ["X"]})
        assert response.status_code == 404

    def test_no_change_returns_current(self):
        client = get_authenticated_client()
        create_resp = client.post(BASE, json={"description": ["Test"]})
        numero = create_resp.json()["numero"]
        response = client.patch(f"{BASE}/{numero}", json={})
        assert response.status_code == 200
        assert response.json()["description"] == ["Test"]

