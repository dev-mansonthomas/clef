"""Tests for Carnet de Bord API endpoints with Valkey."""
import os
import pytest
import pytest_asyncio
from datetime import datetime
from fastapi.testclient import TestClient
from typing import AsyncGenerator
import fakeredis.aioredis

# Set USE_MOCKS before importing app
os.environ["USE_MOCKS"] = "true"
os.environ["GOOGLE_DOMAIN"] = "test.okta.com"
os.environ["GOOGLE_CLIENT_ID"] = "test_client_id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test_client_secret"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_testing_only_min_32_chars"

from app.main import app
from app.auth.dependencies import require_authenticated_user
from app.auth.models import User
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService
from app.models.valkey_models import VehicleData


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    """Create a fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def valkey_dt75(redis_client) -> ValkeyService:
    """Create ValkeyService for DT75 with test vehicle."""
    service = ValkeyService(redis_client=redis_client, dt="DT75")

    # Add test vehicle with all required fields
    vehicle = VehicleData(
        immat="AB-123-CD",
        dt="DT75",
        dt_ul="UL Paris 15",
        marque="Renault",
        modele="Master",
        indicatif="VSAV-PARIS15-01",
        nom_synthetique="VSAV-PARIS15-01",
        operationnel_mecanique="Dispo",
        type="VSAV",
        carte_grise="CG123456",
        nb_places="3",
        lieu_stationnement="Garage UL Paris 15"
    )
    await service.set_vehicle(vehicle)

    return service


# Mock authenticated user
def mock_current_user():
    return User(
        email="jean.dupont@croix-rouge.fr",
        nom="Dupont",
        prenom="Jean",
        ul="UL Paris 15",
        dt="DT75",
        role="Bénévole"
    )


@pytest.fixture
def client():
    """Test client with mocked authentication and proper cleanup."""
    app.dependency_overrides[require_authenticated_user] = mock_current_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.pop(require_authenticated_user, None)
    app.dependency_overrides.pop(get_valkey_service, None)


class TestCarnetDeBordAPI:
    """Test suite for Carnet de Bord API endpoints with Valkey."""

    @pytest.mark.asyncio
    async def test_enregistrer_prise_success(self, client, valkey_dt75):
        """Test successful prise registration."""
        # Override Valkey dependency
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        prise_data = {
            "vehicule_id": "VSAV-PARIS15-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12500,
            "niveau_carburant": "3/4",
            "etat_general": "Bon état",
            "observations": "RAS"
        }

        response = client.post("/api/carnet-de-bord/prise", json=prise_data)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "Prise enregistrée avec succès" in data["message"]
        assert data["perimetre"] == "DT75"

        # Verify data was stored in Valkey
        derniere_prise = await valkey_dt75.get_derniere_prise("AB-123-CD")
        assert derniere_prise is not None
        assert derniere_prise["benevole_nom"] == "Dupont"
        assert derniere_prise["kilometrage"] == 12500

    @pytest.mark.asyncio
    async def test_enregistrer_prise_vehicule_not_found(self, client, valkey_dt75):
        """Test prise registration with non-existent vehicle."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        prise_data = {
            "vehicule_id": "NONEXISTENT-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12500,
            "niveau_carburant": "3/4",
            "etat_general": "Bon état"
        }

        response = client.post("/api/carnet-de-bord/prise", json=prise_data)

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_enregistrer_prise_vehicule_deja_pris(self, client, valkey_dt75):
        """Test prise registration when vehicle is already taken."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        # First prise
        await valkey_dt75.enregistrer_prise(
            immat="AB-123-CD",
            benevole_nom="Martin",
            benevole_prenom="Pierre",
            benevole_email="pierre.martin@croix-rouge.fr",
            kilometrage=12000,
            niveau_carburant="Full",
            etat_general="Bon"
        )

        # Try to take again
        prise_data = {
            "vehicule_id": "VSAV-PARIS15-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12500,
            "niveau_carburant": "3/4",
            "etat_general": "Bon état"
        }

        response = client.post("/api/carnet-de-bord/prise", json=prise_data)

        assert response.status_code == 400
        assert "déjà pris" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_enregistrer_retour_success(self, client, valkey_dt75):
        """Test successful retour registration."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        # First register a prise
        await valkey_dt75.enregistrer_prise(
            immat="AB-123-CD",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            benevole_email="jean.dupont@croix-rouge.fr",
            kilometrage=12500,
            niveau_carburant="3/4",
            etat_general="Bon état"
        )

        retour_data = {
            "vehicule_id": "VSAV-PARIS15-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12580,
            "niveau_carburant": "1/2",
            "etat_general": "Bon état",
            "problemes_signales": "Voyant moteur allumé",
            "observations": "80 km parcourus"
        }

        response = client.post("/api/carnet-de-bord/retour", json=retour_data)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "80 km parcourus" in data["message"]
        assert data["perimetre"] == "DT75"

        # Verify derniere_prise was cleared
        derniere_prise = await valkey_dt75.get_derniere_prise("AB-123-CD")
        assert derniere_prise is None

    @pytest.mark.asyncio
    async def test_enregistrer_retour_vehicule_not_found(self, client, valkey_dt75):
        """Test retour registration with non-existent vehicle."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        retour_data = {
            "vehicule_id": "NONEXISTENT-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12580,
            "niveau_carburant": "1/2",
            "etat_general": "Bon état"
        }

        response = client.post("/api/carnet-de-bord/retour", json=retour_data)

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_enregistrer_retour_vehicule_non_pris(self, client, valkey_dt75):
        """Test retour registration when vehicle is not taken."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        retour_data = {
            "vehicule_id": "VSAV-PARIS15-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12580,
            "niveau_carburant": "1/2",
            "etat_general": "Bon état"
        }

        response = client.post("/api/carnet-de-bord/retour", json=retour_data)

        assert response.status_code == 400
        assert "non pris" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_derniere_prise_vehicule_not_found(self, client, valkey_dt75):
        """Test getting last prise for non-existent vehicle."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        response = client.get("/api/carnet-de-bord/NONEXISTENT-01/derniere-prise")

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_derniere_prise_no_data(self, client, valkey_dt75):
        """Test getting last prise when no data exists."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        response = client.get("/api/carnet-de-bord/VSAV-PARIS15-01/derniere-prise")

        # Should return 200 with null/None since no data exists yet
        assert response.status_code == 200
        # Response should be null or empty
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_derniere_prise_with_data(self, client, valkey_dt75):
        """Test getting last prise when data exists."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        # Register a prise
        await valkey_dt75.enregistrer_prise(
            immat="AB-123-CD",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            benevole_email="jean.dupont@croix-rouge.fr",
            kilometrage=12500,
            niveau_carburant="3/4",
            etat_general="Bon état",
            observations="RAS"
        )

        response = client.get("/api/carnet-de-bord/VSAV-PARIS15-01/derniere-prise")

        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["benevole_nom"] == "Dupont"
        assert data["kilometrage"] == 12500

    @pytest.mark.asyncio
    async def test_prise_validation_negative_kilometrage(self, client, valkey_dt75):
        """Test prise validation with negative kilometrage."""
        app.dependency_overrides[get_valkey_service] = lambda: valkey_dt75

        prise_data = {
            "vehicule_id": "VSAV-PARIS15-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": -100,  # Invalid
            "niveau_carburant": "3/4",
            "etat_general": "Bon état"
        }

        response = client.post("/api/carnet-de-bord/prise", json=prise_data)

        assert response.status_code == 422  # Validation error



class TestValkeyCarnetMethods:
    """Test suite for ValkeyService carnet methods."""

    @pytest.mark.asyncio
    async def test_enregistrer_prise_and_get_derniere_prise(self, valkey_dt75):
        """Test registering a prise and retrieving it."""
        timestamp = await valkey_dt75.enregistrer_prise(
            immat="AB-123-CD",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            benevole_email="jean.dupont@croix-rouge.fr",
            kilometrage=12500,
            niveau_carburant="3/4",
            etat_general="Bon état",
            observations="RAS"
        )

        assert timestamp is not None

        # Get derniere prise
        derniere_prise = await valkey_dt75.get_derniere_prise("AB-123-CD")
        assert derniere_prise is not None
        assert derniere_prise["benevole_nom"] == "Dupont"
        assert derniere_prise["kilometrage"] == 12500

    @pytest.mark.asyncio
    async def test_enregistrer_retour_clears_derniere_prise(self, valkey_dt75):
        """Test that retour clears derniere_prise."""
        # Register prise
        await valkey_dt75.enregistrer_prise(
            immat="AB-123-CD",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            benevole_email="jean.dupont@croix-rouge.fr",
            kilometrage=12500,
            niveau_carburant="3/4",
            etat_general="Bon état"
        )

        # Register retour
        await valkey_dt75.enregistrer_retour(
            immat="AB-123-CD",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            benevole_email="jean.dupont@croix-rouge.fr",
            kilometrage=12580,
            niveau_carburant="1/2",
            etat_general="Bon état",
            problemes_signales="RAS"
        )

        # Derniere prise should be None
        derniere_prise = await valkey_dt75.get_derniere_prise("AB-123-CD")
        assert derniere_prise is None

    @pytest.mark.asyncio
    async def test_get_historique_carnet(self, valkey_dt75):
        """Test getting carnet history."""
        # Register prise
        await valkey_dt75.enregistrer_prise(
            immat="AB-123-CD",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            benevole_email="jean.dupont@croix-rouge.fr",
            kilometrage=12500,
            niveau_carburant="3/4",
            etat_general="Bon état"
        )

        # Register retour
        await valkey_dt75.enregistrer_retour(
            immat="AB-123-CD",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            benevole_email="jean.dupont@croix-rouge.fr",
            kilometrage=12580,
            niveau_carburant="1/2",
            etat_general="Bon état"
        )

        # Get history
        historique = await valkey_dt75.get_historique_carnet("AB-123-CD")
        assert len(historique) == 2
        # Most recent first
        assert historique[0]["type"] == "Retour"
        assert historique[1]["type"] == "Prise"

    @pytest.mark.asyncio
    async def test_get_vehicle_by_nom_synthetique(self, valkey_dt75):
        """Test getting vehicle by synthetic name."""
        vehicle = await valkey_dt75.get_vehicle_by_nom_synthetique("VSAV-PARIS15-01")
        assert vehicle is not None
        assert vehicle.immat == "AB-123-CD"
        assert vehicle.nom_synthetique == "VSAV-PARIS15-01"

        # Test non-existent
        vehicle = await valkey_dt75.get_vehicle_by_nom_synthetique("NONEXISTENT")
        assert vehicle is None
