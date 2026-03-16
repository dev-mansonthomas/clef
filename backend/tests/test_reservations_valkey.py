"""Tests for Valkey-based reservation operations."""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator
import fakeredis.aioredis

from app.services.valkey_service import ValkeyService
from app.models.reservation import ValkeyReservationCreate
from app.models.valkey_models import VehicleData, BenevoleData


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    """Create a fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def valkey_dt75(redis_client) -> ValkeyService:
    """Create ValkeyService for DT75 with test data."""
    service = ValkeyService(redis_client=redis_client, dt="DT75")

    # Add test vehicle
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
    await service.set_vehicle(vehicle)
    
    # Add test benevole
    benevole = BenevoleData(
        nivol="123456",
        dt="DT75",
        ul="81",
        nom="DUPONT",
        prenom="Jean",
        email="jean.dupont@croix-rouge.fr"
    )
    await service.set_benevole(benevole)
    
    return service


class TestReservationCRUD:
    """Test basic CRUD operations for reservations."""
    
    @pytest.mark.asyncio
    async def test_create_reservation(self, valkey_dt75):
        """Test creating a reservation."""
        reservation_data = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Formation PSC1",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0),
            lieu_depart="45 rue de la Paix",
            commentaire="Test reservation"
        )
        
        created = await valkey_dt75.create_reservation(
            reservation_data=reservation_data,
            created_by="test@croix-rouge.fr"
        )
        
        assert created.id is not None
        assert created.vehicule_immat == "AB-123-CD"
        assert created.chauffeur_nivol == "123456"
        assert created.mission == "Formation PSC1"
        assert created.created_by == "test@croix-rouge.fr"
        assert created.created_at is not None
    
    @pytest.mark.asyncio
    async def test_get_reservation(self, valkey_dt75):
        """Test retrieving a reservation by ID."""
        # Create a reservation
        reservation_data = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Formation PSC1",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )
        
        created = await valkey_dt75.create_reservation(
            reservation_data=reservation_data,
            created_by="test@croix-rouge.fr"
        )
        
        # Retrieve it
        retrieved = await valkey_dt75.get_reservation(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.vehicule_immat == "AB-123-CD"
        assert retrieved.mission == "Formation PSC1"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_reservation(self, valkey_dt75):
        """Test retrieving a non-existent reservation."""
        retrieved = await valkey_dt75.get_reservation("nonexistent-id")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_list_reservations(self, valkey_dt75):
        """Test listing all reservations."""
        # Create multiple reservations
        for i in range(3):
            reservation_data = ValkeyReservationCreate(
                vehicule_immat="AB-123-CD",
                chauffeur_nivol="123456",
                chauffeur_nom="Jean DUPONT",
                mission=f"Mission {i}",
                debut=datetime(2026, 3, 15 + i, 8, 0, 0),
                fin=datetime(2026, 3, 15 + i, 18, 0, 0)
            )
            await valkey_dt75.create_reservation(
                reservation_data=reservation_data,
                created_by="test@croix-rouge.fr"
            )
        
        # List all
        reservations = await valkey_dt75.list_reservations()
        
        assert len(reservations) == 3
        assert reservations[0].mission == "Mission 0"  # Sorted by start date
        assert reservations[1].mission == "Mission 1"
        assert reservations[2].mission == "Mission 2"

    @pytest.mark.asyncio
    async def test_list_reservations_by_date_range(self, valkey_dt75):
        """Test listing reservations with date filters."""
        # Create reservations on different dates
        dates = [
            datetime(2026, 3, 15, 8, 0, 0),
            datetime(2026, 3, 20, 8, 0, 0),
            datetime(2026, 3, 25, 8, 0, 0)
        ]

        for i, start_date in enumerate(dates):
            reservation_data = ValkeyReservationCreate(
                vehicule_immat="AB-123-CD",
                chauffeur_nivol="123456",
                chauffeur_nom="Jean DUPONT",
                mission=f"Mission {i}",
                debut=start_date,
                fin=start_date + timedelta(hours=10)
            )
            await valkey_dt75.create_reservation(
                reservation_data=reservation_data,
                created_by="test@croix-rouge.fr"
            )

        # Filter by date range
        from datetime import date
        reservations = await valkey_dt75.list_reservations(
            from_date=date(2026, 3, 18),
            to_date=date(2026, 3, 22)
        )

        assert len(reservations) == 1
        assert reservations[0].mission == "Mission 1"

    @pytest.mark.asyncio
    async def test_list_reservations_by_vehicle(self, valkey_dt75):
        """Test listing reservations filtered by vehicle."""
        # Add another vehicle
        vehicle2 = VehicleData(
            immat="EF-456-GH",
            dt="DT75",
            dt_ul="UL Paris 16",
            marque="Peugeot",
            modele="Boxer",
            indicatif="VPSU 82",
            nom_synthetique="vpsu-82",
            operationnel_mecanique="Dispo",
            type="VPSP",
            carte_grise="CG456789",
            nb_places="3",
            lieu_stationnement="Garage UL"
        )
        await valkey_dt75.set_vehicle(vehicle2)

        # Create reservations for different vehicles
        for immat in ["AB-123-CD", "EF-456-GH"]:
            reservation_data = ValkeyReservationCreate(
                vehicule_immat=immat,
                chauffeur_nivol="123456",
                chauffeur_nom="Jean DUPONT",
                mission=f"Mission for {immat}",
                debut=datetime(2026, 3, 15, 8, 0, 0),
                fin=datetime(2026, 3, 15, 18, 0, 0)
            )
            await valkey_dt75.create_reservation(
                reservation_data=reservation_data,
                created_by="test@croix-rouge.fr"
            )

        # Filter by vehicle
        reservations = await valkey_dt75.list_reservations(vehicule_immat="AB-123-CD")

        assert len(reservations) == 1
        assert reservations[0].vehicule_immat == "AB-123-CD"

    @pytest.mark.asyncio
    async def test_update_reservation(self, valkey_dt75):
        """Test updating a reservation."""
        # Create a reservation
        reservation_data = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Original Mission",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        created = await valkey_dt75.create_reservation(
            reservation_data=reservation_data,
            created_by="test@croix-rouge.fr"
        )

        # Update it
        updated_data = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Updated Mission",
            debut=datetime(2026, 3, 16, 9, 0, 0),
            fin=datetime(2026, 3, 16, 19, 0, 0)
        )

        updated = await valkey_dt75.update_reservation(
            reservation_id=created.id,
            reservation_data=updated_data
        )

        assert updated is not None
        assert updated.id == created.id
        assert updated.mission == "Updated Mission"
        assert updated.debut == datetime(2026, 3, 16, 9, 0, 0)
        assert updated.created_by == "test@croix-rouge.fr"  # Preserved

    @pytest.mark.asyncio
    async def test_delete_reservation(self, valkey_dt75):
        """Test deleting a reservation."""
        # Create a reservation
        reservation_data = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="To be deleted",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        created = await valkey_dt75.create_reservation(
            reservation_data=reservation_data,
            created_by="test@croix-rouge.fr"
        )

        # Delete it
        deleted = await valkey_dt75.delete_reservation(created.id)
        assert deleted is True

        # Verify it's gone
        retrieved = await valkey_dt75.get_reservation(created.id)
        assert retrieved is None

        # Verify it's removed from indexes
        reservations = await valkey_dt75.list_reservations()
        assert len(reservations) == 0


class TestReservationOverlapValidation:
    """Test overlap validation for reservations."""

    @pytest.mark.asyncio
    async def test_no_overlap_different_times(self, valkey_dt75):
        """Test that non-overlapping reservations are allowed."""
        # Create first reservation
        reservation1 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Morning Mission",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 12, 0, 0)
        )

        await valkey_dt75.create_reservation(
            reservation_data=reservation1,
            created_by="test@croix-rouge.fr"
        )

        # Create second reservation (afternoon, no overlap)
        reservation2 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Afternoon Mission",
            debut=datetime(2026, 3, 15, 14, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        # Should succeed
        created2 = await valkey_dt75.create_reservation(
            reservation_data=reservation2,
            created_by="test@croix-rouge.fr"
        )

        assert created2 is not None
        assert created2.mission == "Afternoon Mission"

    @pytest.mark.asyncio
    async def test_overlap_same_time(self, valkey_dt75):
        """Test that overlapping reservations are rejected."""
        # Create first reservation
        reservation1 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="First Mission",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        await valkey_dt75.create_reservation(
            reservation_data=reservation1,
            created_by="test@croix-rouge.fr"
        )

        # Try to create overlapping reservation
        reservation2 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Overlapping Mission",
            debut=datetime(2026, 3, 15, 10, 0, 0),
            fin=datetime(2026, 3, 15, 16, 0, 0)
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="overlaps"):
            await valkey_dt75.create_reservation(
                reservation_data=reservation2,
                created_by="test@croix-rouge.fr"
            )

    @pytest.mark.asyncio
    async def test_overlap_partial_start(self, valkey_dt75):
        """Test overlap detection when new reservation starts during existing one."""
        # Create first reservation
        reservation1 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="First Mission",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 12, 0, 0)
        )

        await valkey_dt75.create_reservation(
            reservation_data=reservation1,
            created_by="test@croix-rouge.fr"
        )

        # Try to create reservation that starts during first one
        reservation2 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Overlapping Mission",
            debut=datetime(2026, 3, 15, 10, 0, 0),
            fin=datetime(2026, 3, 15, 14, 0, 0)
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="overlaps"):
            await valkey_dt75.create_reservation(
                reservation_data=reservation2,
                created_by="test@croix-rouge.fr"
            )

    @pytest.mark.asyncio
    async def test_overlap_partial_end(self, valkey_dt75):
        """Test overlap detection when new reservation ends during existing one."""
        # Create first reservation
        reservation1 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="First Mission",
            debut=datetime(2026, 3, 15, 12, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        await valkey_dt75.create_reservation(
            reservation_data=reservation1,
            created_by="test@croix-rouge.fr"
        )

        # Try to create reservation that ends during first one
        reservation2 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Overlapping Mission",
            debut=datetime(2026, 3, 15, 10, 0, 0),
            fin=datetime(2026, 3, 15, 14, 0, 0)
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="overlaps"):
            await valkey_dt75.create_reservation(
                reservation_data=reservation2,
                created_by="test@croix-rouge.fr"
            )

    @pytest.mark.asyncio
    async def test_update_no_overlap_with_self(self, valkey_dt75):
        """Test that updating a reservation doesn't check overlap with itself."""
        # Create a reservation
        reservation_data = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Original Mission",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        created = await valkey_dt75.create_reservation(
            reservation_data=reservation_data,
            created_by="test@croix-rouge.fr"
        )

        # Update with overlapping time (but same reservation)
        updated_data = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Updated Mission",
            debut=datetime(2026, 3, 15, 9, 0, 0),  # Slightly different time
            fin=datetime(2026, 3, 15, 17, 0, 0)
        )

        # Should succeed (not checking overlap with itself)
        updated = await valkey_dt75.update_reservation(
            reservation_id=created.id,
            reservation_data=updated_data
        )

        assert updated is not None
        assert updated.mission == "Updated Mission"

    @pytest.mark.asyncio
    async def test_overlap_different_vehicles(self, valkey_dt75):
        """Test that reservations for different vehicles don't conflict."""
        # Add another vehicle
        vehicle2 = VehicleData(
            immat="EF-456-GH",
            dt="DT75",
            dt_ul="UL Paris 16",
            marque="Peugeot",
            modele="Boxer",
            indicatif="VPSU 82",
            nom_synthetique="vpsu-82",
            operationnel_mecanique="Dispo",
            type="VPSP",
            carte_grise="CG456789",
            nb_places="3",
            lieu_stationnement="Garage UL"
        )
        await valkey_dt75.set_vehicle(vehicle2)

        # Create reservation for first vehicle
        reservation1 = ValkeyReservationCreate(
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Vehicle 1 Mission",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        await valkey_dt75.create_reservation(
            reservation_data=reservation1,
            created_by="test@croix-rouge.fr"
        )

        # Create reservation for second vehicle at same time
        reservation2 = ValkeyReservationCreate(
            vehicule_immat="EF-456-GH",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Vehicle 2 Mission",
            debut=datetime(2026, 3, 15, 8, 0, 0),
            fin=datetime(2026, 3, 15, 18, 0, 0)
        )

        # Should succeed (different vehicles)
        created2 = await valkey_dt75.create_reservation(
            reservation_data=reservation2,
            created_by="test@croix-rouge.fr"
        )

        assert created2 is not None
        assert created2.vehicule_immat == "EF-456-GH"

