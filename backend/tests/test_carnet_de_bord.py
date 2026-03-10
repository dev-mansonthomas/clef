"""Tests for Carnet de Bord API endpoints."""
import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

# Set USE_MOCKS before importing app
os.environ["USE_MOCKS"] = "true"
os.environ["OKTA_DOMAIN"] = "test.okta.com"
os.environ["OKTA_CLIENT_ID"] = "test_client_id"
os.environ["OKTA_CLIENT_SECRET"] = "test_client_secret"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_testing_only_min_32_chars"

from app.main import app
from app.auth.dependencies import require_authenticated_user
from app.auth.models import User


# Mock authenticated user
def mock_current_user():
    return User(
        email="jean.dupont@croix-rouge.fr",
        nom="Dupont",
        prenom="Jean",
        ul="UL Paris 15",
        role="Bénévole"
    )


# Override authentication dependency
app.dependency_overrides[require_authenticated_user] = mock_current_user

client = TestClient(app)


class TestCarnetDeBordAPI:
    """Test suite for Carnet de Bord API endpoints."""

    def test_enregistrer_prise_success(self):
        """Test successful prise registration."""
        from app.services.carnet_bord_service import CarnetBordService

        prise_data = {
            "vehicule_id": "VSAV-PARIS15-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12500,
            "niveau_carburant": "3/4",
            "etat_general": "Bon état",
            "observations": "RAS",
            "timestamp": "2026-03-10T14:30:00"
        }

        # Mock the Google API calls in the service
        with patch.object(CarnetBordService, '_get_credentials'), \
             patch.object(CarnetBordService, '_find_existing_sheet', return_value=None), \
             patch.object(CarnetBordService, '_create_new_sheet', return_value='mock-sheet-id'):

            response = client.post("/api/carnet-de-bord/prise", json=prise_data)

            assert response.status_code == 201
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Prise enregistrée avec succès"
            assert "spreadsheet_id" in data
            assert "perimetre" in data
    
    def test_enregistrer_prise_vehicule_not_found(self):
        """Test prise registration with non-existent vehicle."""
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
    
    def test_enregistrer_retour_success(self):
        """Test successful retour registration."""
        from app.services.carnet_bord_service import CarnetBordService

        retour_data = {
            "vehicule_id": "VSAV-PARIS15-01",
            "benevole_email": "jean.dupont@croix-rouge.fr",
            "benevole_nom": "Dupont",
            "benevole_prenom": "Jean",
            "kilometrage": 12580,
            "niveau_carburant": "1/2",
            "etat_general": "Bon état",
            "problemes_signales": "Voyant moteur allumé",
            "observations": "80 km parcourus",
            "timestamp": "2026-03-10T18:30:00"
        }

        # Mock the Google API calls in the service
        with patch.object(CarnetBordService, '_get_credentials'), \
             patch.object(CarnetBordService, '_find_existing_sheet', return_value=None), \
             patch.object(CarnetBordService, '_create_new_sheet', return_value='mock-sheet-id'):

            response = client.post("/api/carnet-de-bord/retour", json=retour_data)

            assert response.status_code == 201
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Retour enregistré avec succès"
            assert "spreadsheet_id" in data
            assert "perimetre" in data
    
    def test_enregistrer_retour_vehicule_not_found(self):
        """Test retour registration with non-existent vehicle."""
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
    
    def test_get_derniere_prise_vehicule_not_found(self):
        """Test getting last prise for non-existent vehicle."""
        response = client.get("/api/carnet-de-bord/NONEXISTENT-01/derniere-prise")
        
        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]
    
    def test_get_derniere_prise_no_data(self):
        """Test getting last prise when no data exists."""
        response = client.get("/api/carnet-de-bord/VSAV-PARIS15-01/derniere-prise")
        
        # Should return 200 with null/None since no data exists yet
        assert response.status_code == 200
        # Response should be null or empty
        assert response.json() is None or response.json() == {}
    
    def test_prise_validation_negative_kilometrage(self):
        """Test prise validation with negative kilometrage."""
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


class TestCarnetBordService:
    """Test suite for CarnetBordService."""

    @pytest.mark.asyncio
    async def test_determine_perimetre_ul(self):
        """Test perimeter determination for UL vehicle."""
        from app.services.carnet_bord_service import CarnetBordService
        from app.mocks.service_factory import get_sheets_service

        sheets_service = get_sheets_service()
        service = CarnetBordService(sheets_service=sheets_service)

        vehicule_data = {"dt_ul": "UL Paris 15"}
        perimetre = service.determine_perimetre(vehicule_data)

        assert perimetre == "UL Paris 15"

    @pytest.mark.asyncio
    async def test_determine_perimetre_dt(self):
        """Test perimeter determination for DT vehicle."""
        from app.services.carnet_bord_service import CarnetBordService
        from app.mocks.service_factory import get_sheets_service

        sheets_service = get_sheets_service()
        service = CarnetBordService(sheets_service=sheets_service)

        vehicule_data = {"dt_ul": "DT Paris"}
        perimetre = service.determine_perimetre(vehicule_data)

        assert perimetre == "DT Paris"

    @pytest.mark.asyncio
    async def test_determine_perimetre_activite(self):
        """Test perimeter determination for activity vehicle."""
        from app.services.carnet_bord_service import CarnetBordService
        from app.mocks.service_factory import get_sheets_service

        sheets_service = get_sheets_service()
        service = CarnetBordService(sheets_service=sheets_service)

        vehicule_data = {"dt_ul": "Secours d'Urgence"}
        perimetre = service.determine_perimetre(vehicule_data)

        assert perimetre == "Secours d'Urgence"

    @pytest.mark.asyncio
    async def test_append_prise(self):
        """Test appending a prise record."""
        from app.services.carnet_bord_service import CarnetBordService
        from app.mocks.service_factory import get_sheets_service

        sheets_service = get_sheets_service()

        # Mock the service to avoid Google API calls
        with patch.object(CarnetBordService, '_get_credentials'), \
             patch.object(CarnetBordService, '_find_existing_sheet', return_value=None), \
             patch.object(CarnetBordService, '_create_new_sheet', return_value='mock-sheet-id'):

            service = CarnetBordService(sheets_service=sheets_service)

            vehicule_data = {"dt_ul": "UL Paris 15", "nom_synthetique": "VSAV-PARIS15-01"}
            prise_data = {
                "vehicule_id": "VSAV-PARIS15-01",
                "benevole_email": "jean.dupont@croix-rouge.fr",
                "benevole_nom": "Dupont",
                "benevole_prenom": "Jean",
                "kilometrage": 12500,
                "niveau_carburant": "3/4",
                "etat_general": "Bon état",
                "observations": "RAS",
                "timestamp": datetime(2026, 3, 10, 14, 30, 0)
            }

            result = await service.append_prise(vehicule_data, prise_data)

            assert result["success"] is True
            assert result["perimetre"] == "UL Paris 15"
            assert "spreadsheet_id" in result

    @pytest.mark.asyncio
    async def test_append_retour(self):
        """Test appending a retour record."""
        from app.services.carnet_bord_service import CarnetBordService
        from app.mocks.service_factory import get_sheets_service

        sheets_service = get_sheets_service()

        # Mock the service to avoid Google API calls
        with patch.object(CarnetBordService, '_get_credentials'), \
             patch.object(CarnetBordService, '_find_existing_sheet', return_value=None), \
             patch.object(CarnetBordService, '_create_new_sheet', return_value='mock-sheet-id'):

            service = CarnetBordService(sheets_service=sheets_service)

            vehicule_data = {"dt_ul": "UL Paris 15", "nom_synthetique": "VSAV-PARIS15-01"}
            retour_data = {
                "vehicule_id": "VSAV-PARIS15-01",
                "benevole_email": "jean.dupont@croix-rouge.fr",
                "benevole_nom": "Dupont",
                "benevole_prenom": "Jean",
                "kilometrage": 12580,
                "niveau_carburant": "1/2",
                "etat_general": "Bon état",
                "problemes_signales": "Voyant moteur",
                "observations": "80 km",
                "timestamp": datetime(2026, 3, 10, 18, 30, 0)
            }

            result = await service.append_retour(vehicule_data, retour_data)

            assert result["success"] is True
            assert result["perimetre"] == "UL Paris 15"
            assert "spreadsheet_id" in result


