"""Tests for the devis approval workflow API endpoints."""
import os
import json
import pytest
from unittest.mock import patch

os.environ["USE_MOCKS"] = "true"

from app.auth.config import auth_settings
auth_settings.use_mocks = True

import fakeredis.aioredis
from fastapi.testclient import TestClient
from app.main import app
from app.auth import routes as auth_routes
from app.services.valkey_dependencies import get_valkey_service

_mock_data_path = os.path.join(os.path.dirname(__file__), "..", "app", "mocks", "data", "vehicules.json")
with open(_mock_data_path) as _f:
    MOCK_VEHICLES = json.load(_f)
for _v in MOCK_VEHICLES:
    _v["dt"] = "DT75"

from app.models.valkey_models import VehicleData as _VehicleData
_MOCK_VEHICLE_DATA = {v["immat"]: _VehicleData(**v) for v in MOCK_VEHICLES}

_dossier_store: dict = {}
_dossier_index: dict = {}
_dossier_counters: dict = {}
_historique_store: dict = {}
_devis_store: dict = {}
_devis_counters: dict = {}
_fake_redis = None


class _MockValkeyService:
    dt = "DT75"

    @property
    def redis(self):
        return _fake_redis

    async def get_vehicle(self, immat):
        return _MOCK_VEHICLE_DATA.get(immat)

    async def get_configuration(self):
        return None

    def _key(self, *parts):
        return f"{self.dt}:{':'.join(parts)}"

    async def create_dossier_reparation(self, immat, description, cree_par, commentaire=None, titre=None, est_sinistre=False, franchise_applicable=False):
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
            est_sinistre=est_sinistre, franchise_applicable=franchise_applicable,
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
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            for i, d in enumerate(dossier.devis):
                if d.id == devis_id:
                    dossier.devis[i] = devis
                    break
            await self.update_dossier_reparation(immat, numero_dossier, dossier)
        return devis

    async def get_facture(self, immat, numero_dossier, facture_id):
        return None



def _override_valkey():
    return _MockValkeyService()


def _make_fake_cache():
    class _FakeCache:
        _connected = True
        client = _fake_redis
    return _FakeCache()


@pytest.fixture(autouse=True)
def _mock_valkey_and_cleanup():
    global _fake_redis
    _fake_redis = fakeredis.aioredis.FakeRedis()
    app.dependency_overrides[get_valkey_service] = _override_valkey
    fake_cache = _make_fake_cache()
    mock_valkey = _MockValkeyService()

    # Patch ValkeyService constructor in approbation router to return our mock
    def _mock_valkey_constructor(**kwargs):
        return mock_valkey

    with patch("app.routers.approbation.get_cache", return_value=fake_cache), \
         patch("app.routers.approbation.ValkeyService", side_effect=_mock_valkey_constructor):
        yield
    app.dependency_overrides.pop(get_valkey_service, None)
    _dossier_store.clear()
    _dossier_index.clear()
    _dossier_counters.clear()
    _historique_store.clear()
    _devis_store.clear()
    _devis_counters.clear()


def get_authenticated_client(email="thomas.manson@croix-rouge.fr"):
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


def _create_dossier_and_devis(client):
    resp = client.post(BASE, json={"description": ["Test repair"]})
    assert resp.status_code == 201
    numero = resp.json()["numero"]
    resp = client.post(f"{BASE}/{numero}/devis", json={
        "date_devis": "2026-03-20",
        "fournisseur_id": "f-1",
        "fournisseur_nom": "Garage Dupont",
        "description_travaux": "Brake pads",
        "montant": 450.0,
    })
    assert resp.status_code == 201
    devis_id = resp.json()["id"]
    return numero, devis_id


class TestSendApproval:
    def test_send_approval_success(self):
        client = get_authenticated_client()
        numero, devis_id = _create_dossier_and_devis(client)
        resp = client.post(
            f"{BASE}/{numero}/devis/{devis_id}/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["valideur_email"] == "chef@croix-rouge.fr"

    def test_send_approval_devis_not_found(self):
        client = get_authenticated_client()
        resp = client.post(BASE, json={"description": ["Test"]})
        numero = resp.json()["numero"]
        resp = client.post(
            f"{BASE}/{numero}/devis/nonexistent/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        assert resp.status_code == 404

    def test_send_approval_dossier_closed(self):
        client = get_authenticated_client()
        numero, devis_id = _create_dossier_and_devis(client)
        client.patch(f"{BASE}/{numero}", json={"statut": "cloture"})
        resp = client.post(
            f"{BASE}/{numero}/devis/{devis_id}/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        assert resp.status_code == 409

    def test_send_approval_unauthorized(self):
        client = TestClient(app)
        resp = client.post(
            f"{BASE}/REP-2026-001/devis/1/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        assert resp.status_code == 401


class TestGetApprobationData:
    def test_get_approbation_data_success(self):
        client = get_authenticated_client()
        numero, devis_id = _create_dossier_and_devis(client)
        send_resp = client.post(
            f"{BASE}/{numero}/devis/{devis_id}/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        token = send_resp.json()["token"]
        # Use same client (endpoint doesn't require auth, works with or without session)
        resp = client.get(f"/api/approbation/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["devis_ids"] == [str(devis_id)]
        assert isinstance(data["devis"], list)
        assert len(data["devis"]) == 1
        assert data["valideur_email"] == "chef@croix-rouge.fr"
        assert data["status"] == "pending"

    def test_get_approbation_data_invalid_token(self):
        client = get_authenticated_client()
        resp = client.get("/api/approbation/invalid-token-123")
        assert resp.status_code == 404


class TestSubmitDecision:
    def test_approve_devis(self):
        client = get_authenticated_client()
        numero, devis_id = _create_dossier_and_devis(client)
        send_resp = client.post(
            f"{BASE}/{numero}/devis/{devis_id}/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        token = send_resp.json()["token"]
        resp = client.post(f"/api/approbation/{token}", json={"decision": "approuve"})
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approuve"
        # Verify devis status updated
        devis_resp = client.get(f"{BASE}/{numero}/devis/{devis_id}")
        assert devis_resp.status_code == 200
        assert devis_resp.json()["statut"] == "approuve"

    def test_reject_devis(self):
        client = get_authenticated_client()
        numero, devis_id = _create_dossier_and_devis(client)
        send_resp = client.post(
            f"{BASE}/{numero}/devis/{devis_id}/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        token = send_resp.json()["token"]
        resp = client.post(f"/api/approbation/{token}", json={
            "decision": "refuse", "commentaire": "Too expensive",
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "refuse"

    def test_change_decision_allowed(self):
        client = get_authenticated_client()
        numero, devis_id = _create_dossier_and_devis(client)
        send_resp = client.post(
            f"{BASE}/{numero}/devis/{devis_id}/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        token = send_resp.json()["token"]
        client.post(f"/api/approbation/{token}", json={"decision": "approuve"})
        resp = client.post(f"/api/approbation/{token}", json={"decision": "refuse"})
        assert resp.status_code == 200
        assert resp.json()["decision"] == "refuse"

    def test_invalid_decision(self):
        client = get_authenticated_client()
        numero, devis_id = _create_dossier_and_devis(client)
        send_resp = client.post(
            f"{BASE}/{numero}/devis/{devis_id}/send-approval",
            json={"valideur_email": "chef@croix-rouge.fr"},
        )
        token = send_resp.json()["token"]
        resp = client.post(f"/api/approbation/{token}", json={"decision": "invalid"})
        assert resp.status_code == 422

    def test_expired_token(self):
        client = get_authenticated_client()
        resp = client.post(
            "/api/approbation/expired-token-abc",
            json={"decision": "approuve"},
        )
        assert resp.status_code == 404