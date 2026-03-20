"""Tests for reservation-calendar integration."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

os.environ["USE_MOCKS"] = "true"

from app.services.valkey_service import ValkeyService
from app.models.reservation import ValkeyReservationCreate
from app.models.valkey_models import VehicleData


@pytest.fixture
async def valkey_service():
    """Create a ValkeyService instance for testing."""
    from redis.asyncio import Redis
    from unittest.mock import AsyncMock

    redis_mock = AsyncMock(spec=Redis)
    redis_mock.json = MagicMock()
    redis_mock.json.return_value.get = AsyncMock()
    redis_mock.json.return_value.set = AsyncMock()
    redis_mock.sadd = AsyncMock()
    redis_mock.srem = AsyncMock()
    redis_mock.smembers = AsyncMock(return_value=set())
    redis_mock.delete = AsyncMock()

    service = ValkeyService(redis_client=redis_mock, dt="DT75")
    return service


class TestReservationCalendarIntegration:
    """Test reservation-calendar integration."""
    
    @pytest.mark.asyncio
    async def test_create_reservation_creates_calendar_event(self, valkey_service):
        """When calendar is configured, creating reservation creates event."""
        # Mock configuration with calendar_id
        valkey_service.redis.json().get.return_value = {
            "calendar_id": "cal-123@group.calendar.google.com"
        }
        
        # Mock vehicle data
        vehicle_mock = VehicleData(
            immat="AB-123-CD",
            dt="DT75",
            dt_ul="UL Paris",
            marque="Renault",
            modele="Master",
            indicatif="VL75-01",
            nom_synthetique="vl75-01",
            operationnel_mecanique="Dispo",
            type="VL",
            nb_places="3",
            carte_grise="CG123456",
            lieu_stationnement="Garage UL"
        )
        
        with patch.object(valkey_service, 'get_vehicle', new_callable=AsyncMock) as mock_get_vehicle:
            with patch('app.services.valkey_service._get_calendar_service') as mock_get_cal_service:
                mock_get_vehicle.return_value = vehicle_mock
                
                mock_calendar = AsyncMock()
                mock_calendar.create_event = AsyncMock(return_value={
                    "id": "event-123",
                    "htmlLink": "https://calendar.google.com/event/123"
                })
                mock_get_cal_service.return_value = mock_calendar
                
                # Mock overlap check
                with patch.object(valkey_service, 'check_reservation_overlap', new_callable=AsyncMock) as mock_overlap:
                    mock_overlap.return_value = []
                    
                    reservation_data = ValkeyReservationCreate(
                        vehicule_immat="AB-123-CD",
                        chauffeur_nivol="123456",
                        chauffeur_nom="Jean DUPONT",
                        mission="Formation PSC1",
                        debut=datetime.now(),
                        fin=datetime.now() + timedelta(hours=2),
                    )
                    
                    result = await valkey_service.create_reservation(
                        reservation_data=reservation_data,
                        created_by="test@croix-rouge.fr"
                    )
                    
                    assert result.google_event_id == "event-123"
                    assert result.google_event_link == "https://calendar.google.com/event/123"
                    mock_calendar.create_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_reservation_without_calendar(self, valkey_service):
        """When no calendar configured, reservation still created."""
        # Mock configuration without calendar_id
        valkey_service.redis.json().get.return_value = {}
        
        with patch.object(valkey_service, 'check_reservation_overlap', new_callable=AsyncMock) as mock_overlap:
            mock_overlap.return_value = []
            
            reservation_data = ValkeyReservationCreate(
                vehicule_immat="AB-123-CD",
                chauffeur_nivol="123456",
                chauffeur_nom="Jean DUPONT",
                mission="Formation PSC1",
                debut=datetime.now(),
                fin=datetime.now() + timedelta(hours=2),
            )
            
            result = await valkey_service.create_reservation(
                reservation_data=reservation_data,
                created_by="test@croix-rouge.fr"
            )
            
            assert result.google_event_id is None
            assert result.google_event_link is None
            assert result.id is not None

    @pytest.mark.asyncio
    async def test_update_reservation_updates_calendar_event(self, valkey_service):
        """When reservation has calendar event, updating reservation updates event."""
        from app.models.reservation import ValkeyReservation

        # Mock existing reservation with calendar event
        existing_reservation = ValkeyReservation(
            id="res-123",
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Formation PSC1",
            debut=datetime.now(),
            fin=datetime.now() + timedelta(hours=2),
            created_by="test@croix-rouge.fr",
            created_at=datetime.now(),
            google_event_id="event-123",
            google_event_link="https://calendar.google.com/event/123"
        )

        # Mock configuration with calendar_id
        valkey_service.redis.json().get.return_value = {
            "calendar_id": "cal-123@group.calendar.google.com"
        }

        with patch.object(valkey_service, 'get_reservation', new_callable=AsyncMock) as mock_get_res:
            with patch.object(valkey_service, 'check_reservation_overlap', new_callable=AsyncMock) as mock_overlap:
                with patch('app.services.valkey_service._get_calendar_service') as mock_get_cal_service:
                    mock_get_res.return_value = existing_reservation
                    mock_overlap.return_value = []

                    mock_calendar = AsyncMock()
                    mock_calendar.update_event = AsyncMock(return_value={"id": "event-123"})
                    mock_get_cal_service.return_value = mock_calendar

                    # Update with new mission
                    updated_data = ValkeyReservationCreate(
                        vehicule_immat="AB-123-CD",
                        chauffeur_nivol="123456",
                        chauffeur_nom="Jean DUPONT",
                        mission="Formation PSE1",  # Changed
                        debut=existing_reservation.debut,
                        fin=existing_reservation.fin,
                    )

                    result = await valkey_service.update_reservation(
                        reservation_id="res-123",
                        reservation_data=updated_data
                    )

                    assert result is not None
                    mock_calendar.update_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_reservation_deletes_calendar_event(self, valkey_service):
        """When reservation has calendar event, deleting reservation deletes event."""
        from app.models.reservation import ValkeyReservation

        # Mock existing reservation with calendar event
        existing_reservation = ValkeyReservation(
            id="res-123",
            vehicule_immat="AB-123-CD",
            chauffeur_nivol="123456",
            chauffeur_nom="Jean DUPONT",
            mission="Formation PSC1",
            debut=datetime.now(),
            fin=datetime.now() + timedelta(hours=2),
            created_by="test@croix-rouge.fr",
            created_at=datetime.now(),
            google_event_id="event-123",
            google_event_link="https://calendar.google.com/event/123"
        )

        # Mock configuration with calendar_id
        valkey_service.redis.json().get.return_value = {
            "calendar_id": "cal-123@group.calendar.google.com"
        }

        with patch.object(valkey_service, 'get_reservation', new_callable=AsyncMock) as mock_get_res:
            with patch('app.services.valkey_service._get_calendar_service') as mock_get_cal_service:
                mock_get_res.return_value = existing_reservation

                mock_calendar = AsyncMock()
                mock_calendar.delete_event = AsyncMock(return_value=True)
                mock_get_cal_service.return_value = mock_calendar

                result = await valkey_service.delete_reservation("res-123")

                assert result is True
                mock_calendar.delete_event.assert_called_once_with(
                    dt_id="DT75",
                    calendar_id="cal-123@group.calendar.google.com",
                    event_id="event-123"
                )

