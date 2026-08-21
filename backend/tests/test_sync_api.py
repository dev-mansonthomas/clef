"""Tests for sync API endpoints."""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from typing import AsyncGenerator
import fakeredis.aioredis
import os

from app.main import app
from app.cache import get_cache
from app.services.redis_service import RedisService
from app.models.redis_models import VehicleData, ResponsableData, BenevoleData


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    """Create a fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def redis_dt75(redis_client) -> RedisService:
    """Create RedisService for DT75."""
    return RedisService(redis_client=redis_client, dt="DT75")


@pytest_asyncio.fixture
async def api_key(redis_dt75, redis_client) -> str:
    """Génère une vraie clé API **de DT75**, stockée dans sa configuration.

    Remplace l'ancienne variable d'environnement `SYNC_API_KEY`, globale et sans lien
    avec une délégation : son porteur pouvait écrire le référentiel de n'importe
    laquelle (constat C3).
    """
    cache = get_cache()
    cache.client = redis_client
    cache._connected = True

    created = await redis_dt75.generate_api_key_dt(
        name="Apps Script (test)", created_by="test@croix-rouge.fr"
    )
    return created["key"]


@pytest_asyncio.fixture
async def other_dt_api_key(redis_client) -> str:
    """Clé valide, mais appartenant à DT92."""
    cache = get_cache()
    cache.client = redis_client
    cache._connected = True

    dt92 = RedisService(redis_client=redis_client, dt="DT92")
    created = await dt92.generate_api_key_dt(
        name="Apps Script DT92", created_by="test@croix-rouge.fr"
    )
    return created["key"]


@pytest.fixture
def auth_headers(api_key):
    """Return authentication headers."""
    return {"X-API-Key": api_key}


class TestSyncAPIAuthentication:
    """Test API key authentication."""
    
    def test_missing_api_key(self, client):
        """Test request without API key."""
        response = client.get("/api/sync/DT75/vehicules")
        assert response.status_code == 422  # Missing required header
    
    def test_invalid_api_key(self, client, api_key):
        """Test request with invalid API key."""
        headers = {"X-API-Key": "wrong-key"}
        response = client.get("/api/sync/DT75/vehicules", headers=headers)
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_key_of_another_dt_is_rejected(
        self, client, other_dt_api_key, redis_client
    ):
        """AC-10 — une clé valide de DT92 ne donne aucun droit sur DT75.

        C'est le cœur du constat C3 : la garde comparait à un `SYNC_API_KEY` global,
        sans lien avec le `{dt}` de l'URL. Son porteur pouvait lire et **écraser** le
        référentiel de toutes les délégations.
        """
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        response = client.post(
            "/api/sync/DT75/benevoles",
            headers={"X-API-Key": other_dt_api_key},
            json=[],
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_key_is_rejected(self, client, redis_client):
        """Une clé inexistante est refusée en 401, jamais en 500."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        response = client.post(
            "/api/sync/DT75/benevoles",
            headers={"X-API-Key": "clef_sk_0000000000000000000000000000000"},
            json=[],
        )

        assert response.status_code == 401

    def test_valid_api_key(self, client, auth_headers, redis_dt75):
        """Test request with valid API key."""
        # This will fail if Redis is not mocked properly, but auth should pass
        response = client.get("/api/sync/DT75/vehicules", headers=auth_headers)
        # Should not be 401 (auth error)
        assert response.status_code != 401


class TestSyncVehicules:
    """Test vehicle sync endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_empty_vehicules(self, client, auth_headers, redis_dt75, redis_client):
        """Test getting vehicles when none exist."""
        # Mock the cache
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True
        
        response = client.get("/api/sync/DT75/vehicules", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_get_vehicules_with_data(self, client, auth_headers, redis_dt75, redis_client):
        """Test getting vehicles with data."""
        # Setup test data
        vehicle1 = VehicleData(
            immat="AB-123-CD", dt="DT75", dt_ul="UL Paris 15",
            marque="Renault", modele="Master", indicatif="PARIS-15-01",
            operationnel_mecanique="Dispo", type="VSAV",
            nom_synthetique="VSAV-PARIS15-01", carte_grise="CG123456",
            nb_places="5", lieu_stationnement="Garage UL Paris 15"
        )
        vehicle2 = VehicleData(
            immat="EF-456-GH", dt="DT75", dt_ul="UL Paris 15",
            marque="Peugeot", modele="Partner", indicatif="PARIS-15-02",
            operationnel_mecanique="Dispo", type="VL",
            nom_synthetique="VL-PARIS15-02", carte_grise="CG789012",
            nb_places="5", lieu_stationnement="Garage UL Paris 15"
        )
        
        await redis_dt75.set_vehicle(vehicle1)
        await redis_dt75.set_vehicle(vehicle2)
        
        # Mock the cache
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True
        
        response = client.get("/api/sync/DT75/vehicules", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(v["immat"] == "AB-123-CD" for v in data)
        assert any(v["immat"] == "EF-456-GH" for v in data)


class TestSyncResponsables:
    """Test responsables sync endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_empty_responsables(self, client, auth_headers, redis_dt75, redis_client):
        """Test getting responsables when none exist."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True
        
        response = client.get("/api/sync/DT75/responsables", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_get_responsables_with_data(self, client, auth_headers, redis_dt75, redis_client):
        """Test getting responsables with data."""
        # Setup test data
        resp1 = ResponsableData(
            email="resp1@croix-rouge.fr",
            dt="DT75",
            nom="Durand",
            prenom="Pierre",
            role="Responsable UL",
            perimetre="UL Paris 15",
            type_perimetre="UL"
        )
        resp2 = ResponsableData(
            email="resp2@croix-rouge.fr",
            dt="DT75",
            nom="Martin",
            prenom="Sophie",
            role="Gestionnaire DT",
            perimetre="DT75",
            type_perimetre="DT"
        )
        
        await redis_dt75.set_responsable(resp1)
        await redis_dt75.set_responsable(resp2)
        
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True
        
        response = client.get("/api/sync/DT75/responsables", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(r["email"] == "resp1@croix-rouge.fr" for r in data)
        assert any(r["email"] == "resp2@croix-rouge.fr" for r in data)


class TestSyncBenevoles:
    """Test benevoles sync endpoint.

    Le contrat de charge utile a changé : les clés sont désormais les **libellés de
    colonnes** de l'onglet « Bénévoles » du classeur « CLEF Benevoles », et la réponse
    détaille les opérations au lieu d'un simple compteur. Voir
    `docs/specs/synchronisation-referentiel-benevoles.md`.
    """

    @staticmethod
    def _row(nivol: str, nom: str, prenom: str, ul: str, email: str, tel: str = ""):
        return {
            "Prénom Nom": f"{prenom} {nom}",
            "Nivol": nivol,
            "Nom": nom,
            "Prénom": prenom,
            "UL": ul,
            "Téléphone": tel,
            "Email": email,
        }

    @pytest.mark.asyncio
    async def test_sync_benevoles_empty_list(self, client, auth_headers, redis_client):
        """Un lot vide n'écrit rien et ne désactive personne.

        C'est le mode de panne le plus probable d'une lecture de feuille : il ne doit
        jamais être interprété comme « plus aucun bénévole dans le département ».
        """
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        response = client.post("/api/sync/DT75/benevoles", headers=auth_headers, json=[])

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] == 0
        assert data["deactivated"] == 0
        assert data["reconciliation_skipped"] is True

    @pytest.mark.asyncio
    async def test_sync_benevoles_with_data(self, client, auth_headers, redis_dt75, redis_client):
        """Les identités sont créées depuis les libellés français de la feuille."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        rows = [
            self._row("123456", "Dupont", "Jean", "UL Paris 15",
                      "jean.dupont@croix-rouge.fr", "+33 6 11 22 33 44"),
            self._row("789012", "Martin", "Marie", "UL Paris 16",
                      "marie.martin@croix-rouge.fr"),
        ]

        response = client.post(
            "/api/sync/DT75/benevoles", headers=auth_headers, json=rows
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] == 2
        assert data["errors"] == []

        benevole1 = await redis_dt75.get_benevole("123456")
        assert benevole1.nom == "Dupont"
        assert benevole1.prenom == "Jean"
        assert benevole1.email == "jean.dupont@croix-rouge.fr"
        assert benevole1.telephone == "+33 6 11 22 33 44"
        # Organisation : valeurs par défaut, jamais devinées depuis la feuille.
        assert benevole1.statut == "actif"
        assert benevole1.responsable_ul is False
        assert benevole1.fonctions_dt == []

        benevole2 = await redis_dt75.get_benevole("789012")
        assert benevole2.nom == "Martin"
        assert benevole2.telephone is None

    @pytest.mark.asyncio
    async def test_sync_benevoles_upsert_preserves_organisation(
        self, client, auth_headers, redis_dt75, redis_client
    ):
        """La synchronisation met à jour l'identité **sans** toucher l'organisation.

        C'est la propriété centrale du nouveau modèle : un Responsable UL nommé dans
        CLEF ne doit pas redevenir simple bénévole à la synchronisation suivante.
        """
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        await redis_dt75.set_benevole(BenevoleData(
            nivol="123456", dt="DT75", nom="Dupont", prenom="Jean",
            email="old.email@croix-rouge.fr", ul="UL Paris 15",
            responsable_ul=True, fonctions_dt=["Référent flotte"],
        ))

        rows = [self._row("123456", "Dupont", "Jean", "UL Paris 15",
                          "new.email@croix-rouge.fr")]
        response = client.post(
            "/api/sync/DT75/benevoles", headers=auth_headers, json=rows
        )

        assert response.status_code == 200
        assert response.json()["updated"] == 1

        benevole = await redis_dt75.get_benevole("123456")
        assert benevole.email == "new.email@croix-rouge.fr"      # identité mise à jour
        assert benevole.responsable_ul is True                    # organisation intacte
        assert benevole.fonctions_dt == ["Référent flotte"]

    @pytest.mark.asyncio
    async def test_sync_benevoles_reports_row_errors_without_aborting(
        self, client, auth_headers, redis_dt75, redis_client
    ):
        """Une ligne fautive n'emporte pas le lot (fin du tout-ou-rien)."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        rows = [
            self._row("111111", "Valide", "Ligne", "UL Paris 15", "ok@croix-rouge.fr"),
            self._row("", "SansNivol", "Ligne", "UL Paris 15", "ko@croix-rouge.fr"),
        ]

        response = client.post(
            "/api/sync/DT75/benevoles", headers=auth_headers, json=rows
        )

        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["line"] == 3
        assert await redis_dt75.get_benevole("111111") is not None
