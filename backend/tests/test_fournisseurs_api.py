"""Tests for fournisseurs (suppliers) API endpoints."""
import os
import pytest

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"

from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.auth.dependencies import require_authenticated_user
from app.auth.models import User
from app.services.valkey_dependencies import get_valkey_service
from app.models.repair_models import Fournisseur, NiveauFournisseur


# --------------- Mock ValkeyService ---------------

class _MockValkeyService:
    """In-memory mock for fournisseur CRUD."""

    def __init__(self):
        self._dt: dict[str, Fournisseur] = {}
        self._ul: dict[str, dict[str, Fournisseur]] = {}

    async def list_fournisseurs_dt(self):
        return list(self._dt.values())

    async def list_fournisseurs_ul(self, ul_id: str):
        return list(self._ul.get(ul_id, {}).values())

    async def list_fournisseurs(self, ul_id=None):
        result = await self.list_fournisseurs_dt()
        if ul_id:
            result = result + await self.list_fournisseurs_ul(ul_id)
        return result

    async def get_fournisseur(self, fournisseur_id, ul_id=None):
        if ul_id:
            return self._ul.get(ul_id, {}).get(fournisseur_id)
        return self._dt.get(fournisseur_id)

    async def set_fournisseur(self, fournisseur: Fournisseur):
        if fournisseur.niveau == NiveauFournisseur.UL and fournisseur.ul_id:
            self._ul.setdefault(fournisseur.ul_id, {})[fournisseur.id] = fournisseur
        else:
            self._dt[fournisseur.id] = fournisseur
        return True


_mock_valkey = _MockValkeyService()


def _override_valkey():
    return _mock_valkey


# --------------- User helpers ---------------

def _dt_manager():
    return User(
        email="thomas.manson@croix-rouge.fr", nom="Manson", prenom="Thomas",
        dt="DT75", ul="DT Paris", role="Gestionnaire DT",
        perimetre="DT Paris", type_perimetre="DT",
    )


def _ul_responsible():
    return User(
        email="claire.rousseau@croix-rouge.fr", nom="Rousseau", prenom="Claire",
        dt="DT75", ul="UL Paris 15", role="Responsable UL",
        perimetre="UL Paris 15", type_perimetre="UL",
    )


def _benevole():
    return User(
        email="jean.dupont@croix-rouge.fr", nom="Dupont", prenom="Jean",
        dt="DT75", ul="UL Paris 15", role="Bénévole",
        perimetre="UL Paris 15", type_perimetre="UL",
    )


# --------------- Fixtures ---------------

@pytest.fixture(autouse=True)
def _setup():
    """Reset mock data and override dependencies for each test."""
    _mock_valkey._dt.clear()
    _mock_valkey._ul.clear()
    app.dependency_overrides[get_valkey_service] = _override_valkey
    yield
    app.dependency_overrides.pop(get_valkey_service, None)
    app.dependency_overrides.pop(require_authenticated_user, None)


client = TestClient(app)



class TestListFournisseurs:
    """GET /api/{dt}/fournisseurs"""

    def test_list_empty(self):
        app.dependency_overrides[require_authenticated_user] = _dt_manager
        resp = client.get("/api/DT75/fournisseurs")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_list_dt_and_ul_combined(self):
        """DT manager sees DT suppliers; UL user sees DT + own UL."""
        app.dependency_overrides[require_authenticated_user] = _dt_manager
        # Create one DT supplier
        client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage DT", "niveau": "dt",
        })
        # Create one UL supplier
        app.dependency_overrides[require_authenticated_user] = _ul_responsible
        client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage UL15", "niveau": "ul", "ul_id": "UL Paris 15",
        })
        resp = client.get("/api/DT75/fournisseurs")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2  # DT + own UL

    def test_list_unauthenticated(self):
        # No auth override → should fail
        app.dependency_overrides.pop(require_authenticated_user, None)
        resp = client.get("/api/DT75/fournisseurs")
        assert resp.status_code == 401


class TestCreateFournisseur:
    """POST /api/{dt}/fournisseurs"""

    def test_create_dt_supplier_as_dt_manager(self):
        app.dependency_overrides[require_authenticated_user] = _dt_manager
        resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage Central", "niveau": "dt",
            "adresse": "1 rue de Paris", "telephone": "01 00 00 00 00",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["nom"] == "Garage Central"
        assert data["niveau"] == "dt"
        assert data["cree_par"] == "thomas.manson@croix-rouge.fr"
        assert "id" in data

    def test_create_dt_supplier_forbidden_for_ul_responsible(self):
        app.dependency_overrides[require_authenticated_user] = _ul_responsible
        resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage X", "niveau": "dt",
        })
        assert resp.status_code == 403

    def test_create_ul_supplier_as_ul_responsible(self):
        app.dependency_overrides[require_authenticated_user] = _ul_responsible
        resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage Local", "niveau": "ul", "ul_id": "UL Paris 15",
        })
        assert resp.status_code == 201
        assert resp.json()["niveau"] == "ul"
        assert resp.json()["ul_id"] == "UL Paris 15"

    def test_create_ul_supplier_missing_ul_id(self):
        app.dependency_overrides[require_authenticated_user] = _ul_responsible
        resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage X", "niveau": "ul",
        })
        assert resp.status_code == 400

    def test_create_ul_supplier_wrong_ul_forbidden(self):
        app.dependency_overrides[require_authenticated_user] = _ul_responsible
        resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage X", "niveau": "ul", "ul_id": "UL Paris 16",
        })
        assert resp.status_code == 403

    def test_create_supplier_as_benevole_forbidden(self):
        app.dependency_overrides[require_authenticated_user] = _benevole
        resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "Garage X", "niveau": "ul", "ul_id": "UL Paris 15",
        })
        assert resp.status_code == 403


class TestUpdateFournisseur:
    """PATCH /api/{dt}/fournisseurs/{id}"""

    def test_update_dt_supplier(self):
        app.dependency_overrides[require_authenticated_user] = _dt_manager
        create_resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "Old Name", "niveau": "dt",
        })
        fid = create_resp.json()["id"]
        resp = client.patch(f"/api/DT75/fournisseurs/{fid}", json={
            "nom": "New Name", "telephone": "09 99 99 99 99",
        })
        assert resp.status_code == 200
        assert resp.json()["nom"] == "New Name"
        assert resp.json()["telephone"] == "09 99 99 99 99"

    def test_update_ul_supplier(self):
        app.dependency_overrides[require_authenticated_user] = _ul_responsible
        create_resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "UL Garage", "niveau": "ul", "ul_id": "UL Paris 15",
        })
        fid = create_resp.json()["id"]
        resp = client.patch(f"/api/DT75/fournisseurs/{fid}", json={
            "adresse": "42 avenue Victor Hugo",
        })
        assert resp.status_code == 200
        assert resp.json()["adresse"] == "42 avenue Victor Hugo"

    def test_update_not_found(self):
        app.dependency_overrides[require_authenticated_user] = _dt_manager
        resp = client.patch("/api/DT75/fournisseurs/nonexistent", json={
            "nom": "X",
        })
        assert resp.status_code == 404

    def test_update_dt_supplier_forbidden_for_benevole(self):
        app.dependency_overrides[require_authenticated_user] = _dt_manager
        create_resp = client.post("/api/DT75/fournisseurs", json={
            "nom": "DT Garage", "niveau": "dt",
        })
        fid = create_resp.json()["id"]
        app.dependency_overrides[require_authenticated_user] = _benevole
        resp = client.patch(f"/api/DT75/fournisseurs/{fid}", json={
            "nom": "Hacked",
        })
        assert resp.status_code == 403
