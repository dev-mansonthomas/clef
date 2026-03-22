"""Tests for devis and factures API endpoints."""
import os
import json
import pytest

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"

from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.auth import routes as auth_routes
from app.services.valkey_dependencies import get_valkey_service

# Load mock vehicle data
_mock_data_path = os.path.join(os.path.dirname(__file__), "..", "app", "mocks", "data", "vehicules.json")
with open(_mock_data_path) as _f:
    MOCK_VEHICLES = json.load(_f)
for _v in MOCK_VEHICLES:
    _v["dt"] = "DT75"

from app.models.valkey_models import VehicleData as _VehicleData
_MOCK_VEHICLE_DATA = {v["immat"]: _VehicleData(**v) for v in MOCK_VEHICLES}

# In-memory stores
_dossier_store: dict = {}
_dossier_index: dict = {}
_dossier_counters: dict = {}
_historique_store: dict = {}
_devis_store: dict = {}
_devis_counters: dict = {}
_facture_store: dict = {}
_facture_counters: dict = {}


class _MockValkeyService:
    """Mock ValkeyService for devis/facture tests."""
    dt = "DT75"

    async def get_vehicle(self, immat: str):
        return _MOCK_VEHICLE_DATA.get(immat)

    async def get_configuration(self):
        return None

    def _key(self, *parts: str) -> str:
        return f"{self.dt}:{':'.join(parts)}"

    async def create_dossier_reparation(self, immat, description, cree_par, commentaire=None, titre=None):
        from datetime import datetime
        from app.models.repair_models import DossierReparation, HistoriqueEntry, ActionHistorique
        _dossier_counters[immat] = _dossier_counters.get(immat, 0) + 1
        counter = _dossier_counters[immat]
        year = datetime.utcnow().year
        numero = f"REP-{year}-{counter:03d}"
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

    async def get_dossier_reparation(self, immat, numero):
        from app.models.repair_models import DossierReparation
        key = self._key("vehicules", immat, "travaux", numero)
        data = _dossier_store.get(key)
        if not data:
            return None
        return DossierReparation(**data)

    async def update_dossier_reparation(self, immat, numero, dossier):
        key = self._key("vehicules", immat, "travaux", numero)
        _dossier_store[key] = dossier.model_dump(mode="json")
        return True

    async def add_historique_entry(self, immat, numero, entry):
        key = self._key("vehicules", immat, "travaux", numero, "historique")
        _historique_store.setdefault(key, []).append(entry.model_dump(mode="json"))
        return True

    async def add_devis(self, immat, numero_dossier, devis_data):
        from datetime import datetime
        from app.models.repair_models import Devis, FournisseurSnapshot, StatutDevis, HistoriqueEntry, ActionHistorique
        ckey = f"{immat}:{numero_dossier}:devis"
        _devis_counters[ckey] = _devis_counters.get(ckey, 0) + 1
        devis_id = str(_devis_counters[ckey])
        fournisseur = FournisseurSnapshot(id=devis_data["fournisseur_id"], nom=devis_data["fournisseur_nom"])
        devis = Devis(
            id=devis_id, date_devis=devis_data["date_devis"], fournisseur=fournisseur,
            description=devis_data.get("description_travaux"), montant=devis_data["montant"],
            statut=StatutDevis.EN_ATTENTE, cree_par=devis_data["cree_par"], cree_le=datetime.utcnow(),
        )
        dk = self._key("vehicules", immat, "travaux", numero_dossier, "devis", devis_id)
        _devis_store[dk] = devis.model_dump(mode="json")
        # Update dossier devis list
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            dossier.devis.append(devis)
            await self.update_dossier_reparation(immat, numero_dossier, dossier)
        await self.add_historique_entry(immat, numero_dossier, HistoriqueEntry(
            auteur=devis_data["cree_par"], action=ActionHistorique.DEVIS_AJOUTE,
            details=f"Devis #{devis_id}", ref=dk,
        ))
        return devis

    async def get_devis(self, immat, numero_dossier, devis_id):
        from app.models.repair_models import Devis
        dk = self._key("vehicules", immat, "travaux", numero_dossier, "devis", devis_id)
        data = _devis_store.get(dk)
        if not data:
            return None
        return Devis(**data)

    async def update_devis(self, immat, numero_dossier, devis_id, data):
        devis = await self.get_devis(immat, numero_dossier, devis_id)
        if not devis:
            return None
        for field, value in data.items():
            if hasattr(devis, field):
                setattr(devis, field, value)
        dk = self._key("vehicules", immat, "travaux", numero_dossier, "devis", devis_id)
        _devis_store[dk] = devis.model_dump(mode="json")
        # Update in dossier too
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            for i, d in enumerate(dossier.devis):
                if d.id == devis_id:
                    dossier.devis[i] = devis
                    break
            await self.update_dossier_reparation(immat, numero_dossier, dossier)
        return devis

    async def add_facture(self, immat, numero_dossier, facture_data):
        from datetime import datetime
        from app.models.repair_models import Facture, FournisseurSnapshot, HistoriqueEntry, ActionHistorique
        ckey = f"{immat}:{numero_dossier}:facture"
        _facture_counters[ckey] = _facture_counters.get(ckey, 0) + 1
        facture_id = str(_facture_counters[ckey])
        fournisseur = FournisseurSnapshot(id=facture_data["fournisseur_id"], nom=facture_data["fournisseur_nom"])
        facture = Facture(
            id=facture_id, date_facture=facture_data["date_facture"], fournisseur=fournisseur,
            classification=facture_data["classification"],
            description=facture_data.get("description_travaux"),
            montant_total=facture_data["montant_total"], montant_crf=facture_data["montant_crf"],
            devis_id=facture_data.get("devis_id"), cree_par=facture_data["cree_par"],
            cree_le=datetime.utcnow(),
        )
        fk = self._key("vehicules", immat, "travaux", numero_dossier, "factures", facture_id)
        _facture_store[fk] = facture.model_dump(mode="json")
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            dossier.factures.append(facture)
            await self.update_dossier_reparation(immat, numero_dossier, dossier)
        return facture

    async def get_facture(self, immat, numero_dossier, facture_id):
        from app.models.repair_models import Facture
        fk = self._key("vehicules", immat, "travaux", numero_dossier, "factures", facture_id)
        data = _facture_store.get(fk)
        if not data:
            return None
        return Facture(**data)


def _override_valkey():
    return _MockValkeyService()


@pytest.fixture(autouse=True)
def _mock_valkey_and_cleanup():
    """Override ValkeyService and clean up stores after each test."""
    app.dependency_overrides[get_valkey_service] = _override_valkey
    yield
    app.dependency_overrides.pop(get_valkey_service, None)
    _dossier_store.clear()
    _dossier_index.clear()
    _dossier_counters.clear()
    _historique_store.clear()
    _devis_store.clear()
    _devis_counters.clear()
    _facture_store.clear()
    _facture_counters.clear()


def get_authenticated_client(email: str = "thomas.manson@croix-rouge.fr") -> TestClient:
    """Helper to get an authenticated test client."""
    okta_mock = auth_routes.okta_mock
    if not okta_mock:
        raise RuntimeError("okta_mock is None")
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

DEVIS_PAYLOAD = {
    "date_devis": "2026-03-20",
    "fournisseur_id": "f-001",
    "fournisseur_nom": "Garage Dupont",
    "description_travaux": "Brake repair",
    "montant": 500.0,
}

FACTURE_PAYLOAD = {
    "date_facture": "2026-04-15",
    "fournisseur_id": "f-001",
    "fournisseur_nom": "Garage Dupont",
    "classification": "entretien_courant",
    "description_travaux": "Brake repair",
    "montant_total": 520.0,
    "montant_crf": 520.0,
}


def _create_dossier(client) -> str:
    """Helper: create a dossier and return its numero."""
    resp = client.post(BASE, json={"description": ["Test repair"]})
    assert resp.status_code == 201
    return resp.json()["numero"]


# ===================== Devis Tests =====================


class TestCreateDevis:
    def test_create_devis_success(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        resp = client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "1"
        assert data["montant"] == 500.0
        assert data["statut"] == "en_attente"
        assert data["fournisseur"]["nom"] == "Garage Dupont"

    def test_create_devis_dossier_not_found(self):
        client = get_authenticated_client()
        resp = client.post(f"{BASE}/REP-2026-999/devis", json=DEVIS_PAYLOAD)
        assert resp.status_code == 404


class TestGetDevis:
    def test_get_devis_success(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        resp = client.get(f"{BASE}/{numero}/devis/1")
        assert resp.status_code == 200
        assert resp.json()["montant"] == 500.0

    def test_get_devis_not_found(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        resp = client.get(f"{BASE}/{numero}/devis/999")
        assert resp.status_code == 404



# ===================== Facture Tests =====================


class TestCreateFacture:
    def test_create_facture_without_devis_warning(self):
        """Facture sans devis approuvé → warning_no_devis=True."""
        client = get_authenticated_client()
        numero = _create_dossier(client)
        resp = client.post(f"{BASE}/{numero}/factures", json=FACTURE_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["warning_no_devis"] is True
        assert data["facture"]["montant_total"] == 520.0

    def test_create_facture_with_approved_devis(self):
        """Facture with approved devis and small écart → no warnings."""
        client = get_authenticated_client()
        numero = _create_dossier(client)
        # Create and approve a devis
        client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        client.patch(f"{BASE}/{numero}/devis/1", json={"statut": "approuve"})
        # Create facture linked to devis, montant within 20%
        payload = {**FACTURE_PAYLOAD, "devis_id": "1", "montant_total": 550.0}
        resp = client.post(f"{BASE}/{numero}/factures", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["warning_no_devis"] is False
        assert data["warning_devis_not_approved"] is False
        assert data["warning_ecart"] is False

    def test_create_facture_with_unapproved_devis_warning(self):
        """Facture referencing unapproved devis → warning_devis_not_approved=True."""
        client = get_authenticated_client()
        numero = _create_dossier(client)
        client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        # Don't approve it
        payload = {**FACTURE_PAYLOAD, "devis_id": "1"}
        resp = client.post(f"{BASE}/{numero}/factures", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["warning_devis_not_approved"] is True

    def test_create_facture_ecart_over_20_percent(self):
        """Facture with approved devis but écart > 20% → warning_ecart=True."""
        client = get_authenticated_client()
        numero = _create_dossier(client)
        # Create devis montant=500, approve
        client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        client.patch(f"{BASE}/{numero}/devis/1", json={"statut": "approuve"})
        # Facture montant_total=700 → écart = 40%
        payload = {**FACTURE_PAYLOAD, "devis_id": "1", "montant_total": 700.0}
        resp = client.post(f"{BASE}/{numero}/factures", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["warning_ecart"] is True
        assert data["ecart_pourcentage"] == 40.0

    def test_create_facture_no_devis_but_approved_exists(self):
        """Facture without devis_id but an approved devis exists → no warning."""
        client = get_authenticated_client()
        numero = _create_dossier(client)
        client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        client.patch(f"{BASE}/{numero}/devis/1", json={"statut": "approuve"})
        resp = client.post(f"{BASE}/{numero}/factures", json=FACTURE_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["warning_no_devis"] is False

    def test_create_facture_dossier_not_found(self):
        client = get_authenticated_client()
        resp = client.post(f"{BASE}/REP-2026-999/factures", json=FACTURE_PAYLOAD)
        assert resp.status_code == 404


class TestGetFacture:
    def test_get_facture_success(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        client.post(f"{BASE}/{numero}/factures", json=FACTURE_PAYLOAD)
        resp = client.get(f"{BASE}/{numero}/factures/1")
        assert resp.status_code == 200
        assert resp.json()["montant_total"] == 520.0

    def test_get_facture_not_found(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        resp = client.get(f"{BASE}/{numero}/factures/999")
        assert resp.status_code == 404


# ===================== Closed/Cancelled Dossier Tests =====================


class TestClosedDossier:
    def test_cannot_add_devis_to_closed_dossier(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        # Close the dossier
        client.patch(f"{BASE}/{numero}", json={"statut": "cloture"})
        resp = client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        assert resp.status_code == 409

    def test_cannot_add_facture_to_closed_dossier(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        client.patch(f"{BASE}/{numero}", json={"statut": "cloture"})
        resp = client.post(f"{BASE}/{numero}/factures", json=FACTURE_PAYLOAD)
        assert resp.status_code == 409

    def test_cannot_add_devis_to_cancelled_dossier(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        client.patch(f"{BASE}/{numero}", json={"statut": "annule"})
        resp = client.post(f"{BASE}/{numero}/devis", json=DEVIS_PAYLOAD)
        assert resp.status_code == 409

    def test_cannot_add_facture_to_cancelled_dossier(self):
        client = get_authenticated_client()
        numero = _create_dossier(client)
        client.patch(f"{BASE}/{numero}", json={"statut": "annule"})
        resp = client.post(f"{BASE}/{numero}/factures", json=FACTURE_PAYLOAD)
        assert resp.status_code == 409
