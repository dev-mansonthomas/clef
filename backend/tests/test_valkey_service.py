"""Tests for ValkeyService multi-tenant operations."""
import pytest
import pytest_asyncio
from datetime import datetime
from typing import AsyncGenerator
import fakeredis.aioredis

from app.services.valkey_service import ValkeyService
from app.models.valkey_models import (
    VehicleData,
    BenevoleData,
    CarnetBordEntry,
    DTConfiguration
)


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


@pytest_asyncio.fixture
async def valkey_dt92(redis_client) -> ValkeyService:
    """Create ValkeyService for DT92."""
    return ValkeyService(redis_client=redis_client, dt="DT92")


class TestValkeyServiceConfiguration:
    """Test DT configuration operations."""
    
    @pytest.mark.asyncio
    async def test_set_and_get_configuration(self, valkey_dt75):
        """Test setting and getting DT configuration."""
        config = DTConfiguration(
            dt="DT75",
            nom="Délégation Territoriale de Paris",
            gestionnaire_email="thomas.manson@croix-rouge.fr",
            region="Île-de-France",
            departement="75"
        )
        
        success = await valkey_dt75.set_configuration(config)
        assert success is True
        
        retrieved = await valkey_dt75.get_configuration()
        assert retrieved is not None
        assert retrieved.dt == "DT75"
        assert retrieved.nom == "Délégation Territoriale de Paris"
        assert retrieved.gestionnaire_email == "thomas.manson@croix-rouge.fr"


class TestValkeyServiceVehicles:
    """Test vehicle operations."""
    
    @pytest.mark.asyncio
    async def test_set_and_get_vehicle(self, valkey_dt75):
        """Test setting and getting a vehicle."""
        vehicle = VehicleData(
            immat="AB-123-CD",
            dt="DT75",
            dt_ul="UL Paris 15",
            marque="Renault",
            modele="Master",
            indicatif="VPSU 81",
            nom_synthetique="vpsu-81",
            operationnel_mecanique="Dispo",
            type="VSAV",
            carte_grise="CG123456",
            nb_places="3",
            lieu_stationnement="Garage UL"
        )
        
        success = await valkey_dt75.set_vehicle(vehicle)
        assert success is True
        
        retrieved = await valkey_dt75.get_vehicle("AB-123-CD")
        assert retrieved is not None
        assert retrieved.immat == "AB-123-CD"
        assert retrieved.dt == "DT75"
        assert retrieved.marque == "Renault"
    
    @pytest.mark.asyncio
    async def test_list_vehicles(self, valkey_dt75):
        """Test listing vehicles."""
        vehicle1 = VehicleData(
            immat="AB-123-CD", dt="DT75", dt_ul="UL Paris 15", marque="Renault", modele="Kangoo",
            indicatif="VL-01", nom_synthetique="vl-01", operationnel_mecanique="Dispo",
            type="VL", carte_grise="CG123", nb_places="5", lieu_stationnement="Garage"
        )
        vehicle2 = VehicleData(
            immat="EF-456-GH", dt="DT75", dt_ul="UL Paris 16", marque="Peugeot", modele="Partner",
            indicatif="VL-02", nom_synthetique="vl-02", operationnel_mecanique="Dispo",
            type="VL", carte_grise="CG456", nb_places="5", lieu_stationnement="Garage"
        )

        await valkey_dt75.set_vehicle(vehicle1)
        await valkey_dt75.set_vehicle(vehicle2)

        vehicles = await valkey_dt75.list_vehicles()
        assert len(vehicles) == 2
        assert "AB-123-CD" in vehicles
        assert "EF-456-GH" in vehicles

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, valkey_dt75, valkey_dt92):
        """Test that DT75 and DT92 data are isolated."""
        vehicle_dt75 = VehicleData(
            immat="AB-123-CD", dt="DT75", dt_ul="UL Paris 15", marque="Renault", modele="Kangoo",
            indicatif="VL-01", nom_synthetique="vl-01", operationnel_mecanique="Dispo",
            type="VL", carte_grise="CG123", nb_places="5", lieu_stationnement="Garage"
        )
        vehicle_dt92 = VehicleData(
            immat="IJ-789-KL", dt="DT92", dt_ul="UL Nanterre", marque="Peugeot", modele="Partner",
            indicatif="VL-02", nom_synthetique="vl-02", operationnel_mecanique="Dispo",
            type="VL", carte_grise="CG789", nb_places="5", lieu_stationnement="Garage"
        )
        
        await valkey_dt75.set_vehicle(vehicle_dt75)
        await valkey_dt92.set_vehicle(vehicle_dt92)
        
        # DT75 should only see its vehicle
        dt75_vehicles = await valkey_dt75.list_vehicles()
        assert len(dt75_vehicles) == 1
        assert "AB-123-CD" in dt75_vehicles
        assert "IJ-789-KL" not in dt75_vehicles
        
        # DT92 should only see its vehicle
        dt92_vehicles = await valkey_dt92.list_vehicles()
        assert len(dt92_vehicles) == 1
        assert "IJ-789-KL" in dt92_vehicles
        assert "AB-123-CD" not in dt92_vehicles


class TestValkeyServiceBenevoles:
    """Test bénévole operations."""

    @pytest.mark.asyncio
    async def test_set_and_get_benevole(self, valkey_dt75):
        """Test setting and getting a bénévole."""
        benevole = BenevoleData(
            nivol="123456",
            dt="DT75",
            ul="81",
            nom="Dupont",
            prenom="Jean",
            email="jean.dupont@croix-rouge.fr"
        )

        success = await valkey_dt75.set_benevole(benevole)
        assert success is True

        retrieved = await valkey_dt75.get_benevole("123456")
        assert retrieved is not None
        assert retrieved.nivol == "123456"
        assert retrieved.nom == "Dupont"
        assert retrieved.ul == "81"

    @pytest.mark.asyncio
    async def test_list_benevoles_by_ul(self, valkey_dt75):
        """Test listing bénévoles filtered by UL."""
        benevole1 = BenevoleData(nivol="123456", dt="DT75", ul="81", nom="Dupont", prenom="Jean")
        benevole2 = BenevoleData(nivol="789012", dt="DT75", ul="81", nom="Martin", prenom="Marie")
        benevole3 = BenevoleData(nivol="345678", dt="DT75", ul="82", nom="Durand", prenom="Paul")

        await valkey_dt75.set_benevole(benevole1)
        await valkey_dt75.set_benevole(benevole2)
        await valkey_dt75.set_benevole(benevole3)

        # List all
        all_benevoles = await valkey_dt75.list_benevoles()
        assert len(all_benevoles) == 3

        # List UL 81 only
        ul81_benevoles = await valkey_dt75.list_benevoles(ul="81")
        assert len(ul81_benevoles) == 2
        assert "123456" in ul81_benevoles
        assert "789012" in ul81_benevoles
        assert "345678" not in ul81_benevoles


class TestValkeyServiceCarnet:
    """Test carnet de bord operations."""

    @pytest.mark.asyncio
    async def test_add_and_get_carnet_entries(self, valkey_dt75):
        """Test adding and retrieving carnet entries."""
        entry1 = CarnetBordEntry(
            immat="AB-123-CD",
            dt="DT75",
            timestamp=datetime(2024, 1, 15, 10, 30),
            type="Prise",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            kilometrage=12500
        )

        entry2 = CarnetBordEntry(
            immat="AB-123-CD",
            dt="DT75",
            timestamp=datetime(2024, 1, 15, 14, 30),
            type="Retour",
            benevole_nom="Dupont",
            benevole_prenom="Jean",
            kilometrage=12550
        )

        await valkey_dt75.add_carnet_entry(entry1)
        await valkey_dt75.add_carnet_entry(entry2)

        entries = await valkey_dt75.get_carnet_entries("AB-123-CD")
        assert len(entries) == 2
        # Should be sorted newest first
        assert entries[0].type == "Retour"
        assert entries[1].type == "Prise"

    @pytest.mark.asyncio
    async def test_get_latest_carnet_entry(self, valkey_dt75):
        """Test getting the latest carnet entry."""
        entry1 = CarnetBordEntry(
            immat="AB-123-CD",
            dt="DT75",
            timestamp=datetime(2024, 1, 15, 10, 30),
            type="Prise",
            benevole_nom="Dupont",
            benevole_prenom="Jean"
        )

        entry2 = CarnetBordEntry(
            immat="AB-123-CD",
            dt="DT75",
            timestamp=datetime(2024, 1, 15, 14, 30),
            type="Retour",
            benevole_nom="Dupont",
            benevole_prenom="Jean"
        )

        await valkey_dt75.add_carnet_entry(entry1)
        await valkey_dt75.add_carnet_entry(entry2)

        latest = await valkey_dt75.get_latest_carnet_entry("AB-123-CD")
        assert latest is not None
        assert latest.type == "Retour"

        latest_prise = await valkey_dt75.get_latest_carnet_entry("AB-123-CD", entry_type="Prise")
        assert latest_prise is not None
        assert latest_prise.type == "Prise"

