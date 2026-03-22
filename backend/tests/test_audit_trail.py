"""Tests for audit trail (historique) endpoint and logging."""
import os
import json
import pytest

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


class _MockValkeyService:
    dt = "DT75"

    async def get_vehicle(self, immat):
        return _MOCK_VEHICLE_DATA.get(immat)

    async def get_configuration(self):
        return None

    def _key(self, *parts):
        return f"{self.dt}:{':'.join(parts)}"

    async def create_dossier_reparation(self, immat, description, cree_par, commentaire=None, titre=None):
        from datetime import datetime
        from app.models.repair_models import DossierReparation, HistoriqueEntry, ActionHistorique
        _dossier_counters[immat] = _dossier_counters.get(immat, 0) + 1
        counter = _dossier_counters[immat]
        numero = f"REP-{datetime.utcnow().year}-{counter:03d}"
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
        return DossierReparation(**data) if data else None

    async def update_dossier_reparation(self, immat, numero, dossier):
        key = self._key("vehicules", immat, "travaux", numero)
        _dossier_store[key] = dossier.model_dump(mode="json")
        return True

    async def add_historique_entry(self, immat, numero, entry):
        key = self._key("vehicules", immat, "travaux", numero, "historique")
        _historique_store.setdefault(key, []).append(entry.model_dump(mode="json"))
        return True

    async def get_historique(self, immat, numero):
        from app.models.repair_models import HistoriqueEntry
        key = self._key("vehicules", immat, "travaux", numero, "historique")
        data = _historique_store.get(key, [])
        return [HistoriqueEntry(**e) for e in data]

    async def add_devis(self, immat, numero_dossier, devis_data):
        from datetime import datetime
        from app.models.repair_models import Devis, FournisseurSnapshot, HistoriqueEntry, ActionHistorique
        _devis_counters[numero_dossier] = _devis_counters.get(numero_dossier, 0) + 1
        devis_id = str(_devis_counters[numero_dossier])
        fs = FournisseurSnapshot(id=devis_data["fournisseur_id"], nom=devis_data["fournisseur_nom"])
        devis = Devis(
            id=devis_id, date_devis=devis_data["date_devis"], fournisseur=fs,
            description=devis_data.get("description_travaux"), montant=devis_data["montant"],
            cree_par=devis_data["cree_par"], cree_le=datetime.utcnow(),
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
            details=f"Devis #{devis_id} - {devis_data['fournisseur_nom']} - {devis_data['montant']}€",
            ref=dk,
        ))
        return devis


def _override():
    return _MockValkeyService()


@pytest.fixture(autouse=True)
def _mock_and_cleanup():
    app.dependency_overrides[get_valkey_service] = _override
    yield
    app.dependency_overrides.pop(get_valkey_service, None)
    _dossier_store.clear(); _dossier_index.clear()
    _dossier_counters.clear(); _historique_store.clear()
    _devis_store.clear(); _devis_counters.clear()


def _client(email="thomas.manson@croix-rouge.fr"):
    okta_mock = auth_routes.okta_mock
    tc = TestClient(app)
    code = okta_mock.create_mock_authorization_code(email)
    resp = tc.get(f"/auth/callback?code={code}&state=s", follow_redirects=False)
    cookie = resp.cookies.get(auth_settings.session_cookie_name)
    if cookie:
        tc.cookies.set(auth_settings.session_cookie_name, cookie)
    return tc


IMMAT = "AB-123-CD"
DT = "DT75"
BASE = f"/api/{DT}/vehicles/{IMMAT}/dossiers-reparation"


class TestAuditTrail:
    """Test GET historique endpoint and audit trail entries."""

    def test_create_dossier_has_creation_entry(self):
        c = _client()
        resp = c.post(BASE, json={"description": ["Brake repair"]})
        assert resp.status_code == 201
        numero = resp.json()["numero"]

        hist = c.get(f"{BASE}/{numero}/historique")
        assert hist.status_code == 200
        entries = hist.json()
        assert len(entries) >= 1
        actions = [e["action"] for e in entries]
        assert "creation" in actions
        # Verify all fields present
        for e in entries:
            assert "date" in e
            assert "auteur" in e
            assert "action" in e
            assert "details" in e
            assert "ref" in e

    def test_add_devis_has_devis_ajoute_entry(self):
        c = _client()
        resp = c.post(BASE, json={"description": ["Engine work"]})
        numero = resp.json()["numero"]

        c.post(f"{BASE}/{numero}/devis", json={
            "date_devis": "2026-03-15",
            "fournisseur_id": "f1",
            "fournisseur_nom": "Garage Martin",
            "montant": 850,
        })

        hist = c.get(f"{BASE}/{numero}/historique")
        entries = hist.json()
        actions = [e["action"] for e in entries]
        assert "devis_ajoute" in actions

    def test_close_dossier_has_cloture_entry(self):
        c = _client()
        resp = c.post(BASE, json={"description": ["Tire change"]})
        numero = resp.json()["numero"]

        c.patch(f"{BASE}/{numero}", json={"statut": "cloture"})

        hist = c.get(f"{BASE}/{numero}/historique")
        entries = hist.json()
        actions = [e["action"] for e in entries]
        assert "cloture" in actions

    def test_all_entries_have_required_fields(self):
        c = _client()
        resp = c.post(BASE, json={"description": ["Full test"]})
        numero = resp.json()["numero"]

        c.post(f"{BASE}/{numero}/devis", json={
            "date_devis": "2026-03-15",
            "fournisseur_id": "f1",
            "fournisseur_nom": "Garage Test",
            "montant": 500,
        })
        c.patch(f"{BASE}/{numero}", json={"statut": "cloture"})

        hist = c.get(f"{BASE}/{numero}/historique")
        entries = hist.json()
        assert len(entries) >= 3  # creation + devis + cloture
        for e in entries:
            assert isinstance(e["date"], str) and len(e["date"]) > 0
            assert "@" in e["auteur"]  # email format
            assert len(e["action"]) > 0
            assert len(e["details"]) > 0
            assert len(e["ref"]) > 0

    def test_historique_sorted_descending(self):
        c = _client()
        resp = c.post(BASE, json={"description": ["Sort test"]})
        numero = resp.json()["numero"]

        c.post(f"{BASE}/{numero}/devis", json={
            "date_devis": "2026-03-15",
            "fournisseur_id": "f1",
            "fournisseur_nom": "Garage A",
            "montant": 100,
        })

        hist = c.get(f"{BASE}/{numero}/historique")
        entries = hist.json()
        dates = [e["date"] for e in entries]
        assert dates == sorted(dates, reverse=True)

    def test_historique_dossier_not_found(self):
        c = _client()
        resp = c.get(f"{BASE}/REP-9999-999/historique")
        assert resp.status_code == 404

