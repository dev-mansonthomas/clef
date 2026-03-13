"""Tests for sync API endpoints."""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from typing import AsyncGenerator
import fakeredis.aioredis
import os

from app.main import app
from app.cache import get_cache
from app.services.valkey_service import ValkeyService
from app.models.valkey_models import VehicleData, ResponsableData, BenevoleData


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
async def valkey_dt75(redis_client) -> ValkeyService:
    """Create ValkeyService for DT75."""
    return ValkeyService(redis_client=redis_client, dt="DT75")


@pytest.fixture
def api_key():
    """Set and return API key for testing."""
    test_key = "test-api-key-12345"
    os.environ["SYNC_API_KEY"] = test_key
    yield test_key
    # Cleanup
    if "SYNC_API_KEY" in os.environ:
        del os.environ["SYNC_API_KEY"]


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
    
    def test_valid_api_key(self, client, auth_headers, valkey_dt75):
        """Test request with valid API key."""
        # This will fail if Redis is not mocked properly, but auth should pass
        response = client.get("/api/sync/DT75/vehicules", headers=auth_headers)
        # Should not be 401 (auth error)
        assert response.status_code != 401


class TestSyncVehicules:
    """Test vehicle sync endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_empty_vehicules(self, client, auth_headers, valkey_dt75, redis_client):
        """Test getting vehicles when none exist."""
        # Mock the cache
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True
        
        response = client.get("/api/sync/DT75/vehicules", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_get_vehicules_with_data(self, client, auth_headers, valkey_dt75, redis_client):
        """Test getting vehicles with data."""
        # Setup test data
        vehicle1 = VehicleData(immat="AB-123-CD", dt="DT75", marque="Renault", modele="Master")
        vehicle2 = VehicleData(immat="EF-456-GH", dt="DT75", marque="Peugeot", modele="Partner")
        
        await valkey_dt75.set_vehicle(vehicle1)
        await valkey_dt75.set_vehicle(vehicle2)
        
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
    async def test_get_empty_responsables(self, client, auth_headers, valkey_dt75, redis_client):
        """Test getting responsables when none exist."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True
        
        response = client.get("/api/sync/DT75/responsables", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_get_responsables_with_data(self, client, auth_headers, valkey_dt75, redis_client):
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
        
        await valkey_dt75.set_responsable(resp1)
        await valkey_dt75.set_responsable(resp2)
        
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
    """Test benevoles sync endpoint."""

    @pytest.mark.asyncio
    async def test_sync_benevoles_empty_list(self, client, auth_headers, redis_client):
        """Test syncing empty list of benevoles."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        response = client.post("/api/sync/DT75/benevoles", headers=auth_headers, json=[])
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_sync_benevoles_with_data(self, client, auth_headers, valkey_dt75, redis_client):
        """Test syncing benevoles with data."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        benevoles_data = [
            {
                "nivol": "123456",
                "nom": "Dupont",
                "prenom": "Jean",
                "email": "jean.dupont@croix-rouge.fr",
                "ul": "UL Paris 15",
                "role": "Bénévole"
            },
            {
                "nivol": "789012",
                "nom": "Martin",
                "prenom": "Marie",
                "email": "marie.martin@croix-rouge.fr",
                "ul": "UL Paris 16",
                "role": "Bénévole"
            }
        ]

        response = client.post("/api/sync/DT75/benevoles", headers=auth_headers, json=benevoles_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2
        assert "Successfully synced 2 bénévoles" in data["message"]

        # Verify data was stored
        benevole1 = await valkey_dt75.get_benevole("123456")
        assert benevole1 is not None
        assert benevole1.nom == "Dupont"
        assert benevole1.prenom == "Jean"
        assert benevole1.email == "jean.dupont@croix-rouge.fr"

        benevole2 = await valkey_dt75.get_benevole("789012")
        assert benevole2 is not None
        assert benevole2.nom == "Martin"

    @pytest.mark.asyncio
    async def test_sync_benevoles_upsert(self, client, auth_headers, valkey_dt75, redis_client):
        """Test that sync updates existing benevoles."""
        cache = get_cache()
        cache.client = redis_client
        cache._connected = True

        # Create initial benevole
        initial = BenevoleData(
            nivol="123456",
            dt="DT75",
            nom="Dupont",
            prenom="Jean",
            email="old.email@croix-rouge.fr",
            ul="UL Paris 15",
            role="Bénévole"
        )
        await valkey_dt75.set_benevole(initial)

        # Sync with updated data
        updated_data = [
            {
                "nivol": "123456",
                "nom": "Dupont",
                "prenom": "Jean",
                "email": "new.email@croix-rouge.fr",
                "ul": "UL Paris 16",
                "role": "Responsable UL"
            }
        ]

        response = client.post("/api/sync/DT75/benevoles", headers=auth_headers, json=updated_data)
        assert response.status_code == 200

        # Verify data was updated
        benevole = await valkey_dt75.get_benevole("123456")
        assert benevole is not None
        assert benevole.email == "new.email@croix-rouge.fr"
        assert benevole.ul == "UL Paris 16"
        assert benevole.role == "Responsable UL"

