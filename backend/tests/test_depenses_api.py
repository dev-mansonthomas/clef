"""Tests for dépenses (expenses) API endpoints."""
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
_facture_counters: dict = {}
_historique_store: dict = {}


class _MockValkeyService:
    """Mock ValkeyService for depenses tests."""
    dt = "DT75"

    async def get_vehicle(self, immat: str):
        return _MOCK_VEHICLE_DATA.get(immat)

    async def get_configuration(self):
        return None

    def _key(self, *parts: str) -> str:
        return f"{self.dt}:{':'.join(parts)}"

    async def create_dossier_reparation(self, immat: str, description, cree_par: str, commentaire=None, titre=None, est_sinistre=False, franchise_applicable=False):
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
            est_sinistre=est_sinistre, franchise_applicable=franchise_applicable,
            cree_par=cree_par, cree_le=datetime.utcnow(),
        )
        key = self._key("vehicules", immat, "travaux", numero)
        _dossier_store[key] = dossier.model_dump(mode="json")
        _dossier_index.setdefault(immat, set()).add(numero)
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
        return True

    async def add_facture(self, immat: str, numero_dossier: str, facture_data: dict):
        from datetime import datetime
        from app.models.repair_models import Facture, FournisseurSnapshot, ClassificationComptable
        ckey = f"{immat}:{numero_dossier}"
        _facture_counters[ckey] = _facture_counters.get(ckey, 0) + 1
        facture_id = str(_facture_counters[ckey])
        fournisseur_snapshot = FournisseurSnapshot(
            id=facture_data["fournisseur_id"], nom=facture_data["fournisseur_nom"],
        )
        facture = Facture(
            id=facture_id,
            date_facture=facture_data["date_facture"],
            fournisseur=fournisseur_snapshot,
            classification=facture_data["classification"],
            description=facture_data.get("description_travaux"),
            montant_total=facture_data["montant_total"],
            montant_crf=facture_data["montant_crf"],
            devis_id=facture_data.get("devis_id"),
            cree_par=facture_data["cree_par"],
            cree_le=datetime.utcnow(),
        )
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            dossier.factures.append(facture)
            await self.update_dossier_reparation(immat, numero_dossier, dossier)
        return facture

    async def get_devis(self, immat, numero, devis_id):
        return None

    async def get_vehicle_depenses(self, immat: str) -> dict:
        """Reuse the real logic via list_dossiers_reparation."""
        from collections import defaultdict
        dossiers = await self.list_dossiers_reparation(immat)
        year_data = defaultdict(lambda: {"factures": [], "dossier_numeros": set(), "total_cout": 0.0, "total_crf": 0.0})
        total_cout = 0.0
        total_crf = 0.0
        for dossier in dossiers:
            for facture in dossier.factures:
                year = facture.date_facture.year
                entry = year_data[year]
                entry["factures"].append({
                    "date": facture.date_facture.isoformat(),
                    "numero_dossier": dossier.numero,
                    "description": facture.description,
                    "fournisseur_nom": facture.fournisseur.nom,
                    "classification": facture.classification.value if hasattr(facture.classification, 'value') else facture.classification,
                    "montant_total": facture.montant_total,
                    "montant_crf": facture.montant_crf,
                })
                entry["dossier_numeros"].add(dossier.numero)
                entry["total_cout"] += facture.montant_total
                entry["total_crf"] += facture.montant_crf
                total_cout += facture.montant_total
                total_crf += facture.montant_crf
        years = []
        for year in sorted(year_data.keys(), reverse=True):
            d = year_data[year]
            sorted_factures = sorted(d["factures"], key=lambda f: f["date"])
            years.append({"year": year, "nb_dossiers": len(d["dossier_numeros"]),
                          "total_cout": round(d["total_cout"], 2), "total_crf": round(d["total_crf"], 2),
                          "factures": sorted_factures})
        return {"years": years, "total_all_years_cout": round(total_cout, 2), "total_all_years_crf": round(total_crf, 2)}


def _override_valkey():
    return _MockValkeyService()


@pytest.fixture(autouse=True)
def _mock_valkey_and_cleanup():
    app.dependency_overrides[get_valkey_service] = _override_valkey
    yield
    app.dependency_overrides.pop(get_valkey_service, None)
    _dossier_store.clear()
    _dossier_index.clear()
    _dossier_counters.clear()
    _facture_counters.clear()
    _historique_store.clear()


def get_authenticated_client(email: str = "thomas.manson@croix-rouge.fr") -> TestClient:
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
DEPENSES_URL = f"/api/{DT}/vehicles/{IMMAT}/depenses"
DOSSIERS_URL = f"/api/{DT}/vehicles/{IMMAT}/dossiers-reparation"


def _create_dossier_with_facture(client, date_facture="2026-03-15", montant_total=850.0, montant_crf=850.0, classification="entretien_courant"):
    """Helper: create a dossier then add a facture to it."""
    resp = client.post(DOSSIERS_URL, json={"description": ["Test repair"]})
    assert resp.status_code == 201
    numero = resp.json()["numero"]
    facture_resp = client.post(f"{DOSSIERS_URL}/{numero}/factures", json={
        "date_facture": date_facture,
        "fournisseur_id": "f-001",
        "fournisseur_nom": "Garage Martin",
        "classification": classification,
        "description_travaux": "Réparation freins",
        "montant_total": montant_total,
        "montant_crf": montant_crf,
    })
    assert facture_resp.status_code == 201
    return numero


class TestGetDepenses:
    """Test GET /api/{dt}/vehicles/{immat}/depenses."""

    def test_empty_depenses(self):
        client = get_authenticated_client()
        resp = client.get(DEPENSES_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["years"] == []
        assert data["total_all_years_cout"] == 0.0
        assert data["total_all_years_crf"] == 0.0

    def test_depenses_with_factures(self):
        client = get_authenticated_client()
        _create_dossier_with_facture(client, "2026-03-15", 850.0, 850.0)
        _create_dossier_with_facture(client, "2026-06-20", 400.0, 300.0)
        resp = client.get(DEPENSES_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["years"]) == 1
        year = data["years"][0]
        assert year["year"] == 2026
        assert year["nb_dossiers"] == 2
        assert year["total_cout"] == 1250.0
        assert year["total_crf"] == 1150.0
        assert len(year["factures"]) == 2
        assert data["total_all_years_cout"] == 1250.0
        assert data["total_all_years_crf"] == 1150.0

    def test_depenses_multiple_years(self):
        client = get_authenticated_client()
        _create_dossier_with_facture(client, "2025-06-01", 500.0, 500.0)
        _create_dossier_with_facture(client, "2026-01-15", 300.0, 200.0)
        resp = client.get(DEPENSES_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["years"]) == 2
        # Sorted by year descending
        assert data["years"][0]["year"] == 2026
        assert data["years"][1]["year"] == 2025
        assert data["total_all_years_cout"] == 800.0

    def test_depenses_grouping_by_year(self):
        client = get_authenticated_client()
        _create_dossier_with_facture(client, "2025-03-01", 100.0, 100.0)
        _create_dossier_with_facture(client, "2025-09-01", 200.0, 150.0)
        _create_dossier_with_facture(client, "2026-02-01", 300.0, 300.0)
        resp = client.get(DEPENSES_URL)
        data = resp.json()
        assert len(data["years"]) == 2
        year_2025 = next(y for y in data["years"] if y["year"] == 2025)
        year_2026 = next(y for y in data["years"] if y["year"] == 2026)
        assert year_2025["total_cout"] == 300.0
        assert year_2025["total_crf"] == 250.0
        assert len(year_2025["factures"]) == 2
        assert year_2026["total_cout"] == 300.0
        assert len(year_2026["factures"]) == 1

    def test_depenses_vehicle_not_found(self):
        client = get_authenticated_client()
        resp = client.get(f"/api/{DT}/vehicles/NONEXISTENT/depenses")
        assert resp.status_code == 404


class TestExportDepenses:
    """Test GET /api/{dt}/vehicles/{immat}/depenses/export."""

    def test_csv_export_empty(self):
        client = get_authenticated_client()
        resp = client.get(f"{DEPENSES_URL}/export?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1  # header only

    def test_csv_export_with_data(self):
        client = get_authenticated_client()
        _create_dossier_with_facture(client, "2026-03-15", 850.0, 850.0)
        resp = client.get(f"{DEPENSES_URL}/export?format=csv")
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert "Garage Martin" in lines[1]
        assert "850.0" in lines[1]

    def test_pdf_export(self):
        client = get_authenticated_client()
        _create_dossier_with_facture(client, "2026-03-15", 850.0, 850.0)
        resp = client.get(f"{DEPENSES_URL}/export?format=pdf")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Garage Martin" in resp.text

