"""Tests for Google Calendar service."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import redis

from app.services.calendar_service import CalendarService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock_client = Mock(spec=redis.Redis)
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    return mock_client


@pytest.fixture
def mock_google_service():
    """Create a mock Google Calendar API service."""
    mock_service = MagicMock()
    return mock_service


@pytest.fixture
def calendar_service(mock_redis):
    """Create a CalendarService instance with mock Redis."""
    return CalendarService(redis_client=mock_redis)


class TestCalendarService:
    """Test the CalendarService class."""
    
    def test_init(self, mock_redis):
        """Test service initialization."""
        service = CalendarService(redis_client=mock_redis)
        assert service.redis_client == mock_redis
        assert service._service is None
        assert service._calendar_id_cache is None
    
    def test_get_calendar_name_dev(self, calendar_service):
        """Test calendar name generation for dev environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            name = calendar_service._get_calendar_name()
            assert "DEV" in name
            assert "CLEF" in name
            assert "Réservation Véhicule" in name
    
    def test_get_calendar_name_prod(self, calendar_service):
        """Test calendar name generation for prod environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            name = calendar_service._get_calendar_name()
            assert "PROD" in name or "CLEF" in name
            assert "Réservation Véhicule" in name
    
    def test_get_stored_calendar_id_from_redis(self, calendar_service, mock_redis):
        """Test retrieving calendar ID from Redis."""
        mock_redis.get.return_value = "test-calendar-id"
        
        calendar_id = calendar_service._get_stored_calendar_id()
        
        assert calendar_id == "test-calendar-id"
        mock_redis.get.assert_called_once_with(CalendarService.REDIS_CALENDAR_KEY)
    
    def test_get_stored_calendar_id_cache(self, calendar_service, mock_redis):
        """Test calendar ID caching."""
        mock_redis.get.return_value = "test-calendar-id"
        
        # First call should hit Redis
        calendar_id1 = calendar_service._get_stored_calendar_id()
        # Second call should use cache
        calendar_id2 = calendar_service._get_stored_calendar_id()
        
        assert calendar_id1 == calendar_id2
        # Redis should only be called once
        assert mock_redis.get.call_count == 1
    
    def test_store_calendar_id(self, calendar_service, mock_redis):
        """Test storing calendar ID in Redis."""
        calendar_service._store_calendar_id("new-calendar-id")
        
        assert calendar_service._calendar_id_cache == "new-calendar-id"
        mock_redis.set.assert_called_once_with(
            CalendarService.REDIS_CALENDAR_KEY,
            "new-calendar-id"
        )
    
    @patch('app.services.calendar_service.build')
    @patch('app.services.calendar_service.service_account.Credentials.from_service_account_file')
    def test_create_calendar(
        self,
        mock_credentials,
        mock_build,
        calendar_service,
        mock_google_service,
        mock_redis
    ):
        """Test creating a calendar."""
        # Setup mocks
        mock_build.return_value = mock_google_service
        mock_calendar = {
            'id': 'created-calendar-id',
            'summary': 'Test Calendar',
            'description': 'Test Description',
            'timeZone': 'Europe/Paris'
        }
        mock_google_service.calendars().insert().execute.return_value = mock_calendar
        
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}):
            result = calendar_service.create_calendar(
                summary="Test Calendar",
                description="Test Description"
            )
        
        assert result == mock_calendar
        assert calendar_service._calendar_id_cache == 'created-calendar-id'
        mock_redis.set.assert_called_once_with(
            CalendarService.REDIS_CALENDAR_KEY,
            'created-calendar-id'
        )
    
    @patch('app.services.calendar_service.build')
    @patch('app.services.calendar_service.service_account.Credentials.from_service_account_file')
    def test_get_events(
        self,
        mock_credentials,
        mock_build,
        calendar_service,
        mock_google_service,
        mock_redis
    ):
        """Test getting events from calendar."""
        # Setup mocks
        mock_build.return_value = mock_google_service
        mock_redis.get.return_value = "test-calendar-id"
        
        mock_events = {
            'items': [
                {
                    'id': 'event-1',
                    'summary': 'Test Event 1',
                    'start': {'dateTime': '2024-01-01T10:00:00Z'},
                    'end': {'dateTime': '2024-01-01T11:00:00Z'}
                },
                {
                    'id': 'event-2',
                    'summary': 'Test Event 2',
                    'start': {'dateTime': '2024-01-02T10:00:00Z'},
                    'end': {'dateTime': '2024-01-02T11:00:00Z'}
                }
            ]
        }
        mock_google_service.events().list().execute.return_value = mock_events
        
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}):
            result = calendar_service.get_events()
        
        assert len(result) == 2
        assert result[0]['id'] == 'event-1'
        assert result[1]['id'] == 'event-2'

    @patch('app.services.calendar_service.build')
    @patch('app.services.calendar_service.service_account.Credentials.from_service_account_file')
    def test_create_reservation(
        self,
        mock_credentials,
        mock_build,
        calendar_service,
        mock_google_service,
        mock_redis
    ):
        """Test creating a reservation event."""
        # Setup mocks
        mock_build.return_value = mock_google_service
        mock_redis.get.return_value = "test-calendar-id"

        start = datetime(2024, 1, 15, 10, 0)
        end = datetime(2024, 1, 15, 12, 0)

        mock_event = {
            'id': 'event-123',
            'summary': 'VL75-01 - Jean Dupont - Mission Secours',
            'start': {'dateTime': start.isoformat(), 'timeZone': 'Europe/Paris'},
            'end': {'dateTime': end.isoformat(), 'timeZone': 'Europe/Paris'},
            'colorId': '5'
        }
        mock_google_service.events().insert().execute.return_value = mock_event

        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}):
            result = calendar_service.create_reservation(
                indicatif="VL75-01",
                chauffeur="Jean Dupont",
                mission="Mission Secours",
                start=start,
                end=end,
                description="Informations techniques",
                color_id="5"
            )

        assert result['id'] == 'event-123'
        assert result['summary'] == 'VL75-01 - Jean Dupont - Mission Secours'
        assert result['colorId'] == '5'

    @patch('app.services.calendar_service.build')
    @patch('app.services.calendar_service.service_account.Credentials.from_service_account_file')
    def test_delete_reservation(
        self,
        mock_credentials,
        mock_build,
        calendar_service,
        mock_google_service,
        mock_redis
    ):
        """Test deleting a reservation event."""
        # Setup mocks
        mock_build.return_value = mock_google_service
        mock_redis.get.return_value = "test-calendar-id"
        mock_google_service.events().delete().execute.return_value = None

        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}):
            result = calendar_service.delete_reservation("event-123")

        assert result is True
        # Verify delete was called with correct parameters
        call_args = mock_google_service.events().delete.call_args
        assert call_args[1]['calendarId'] == 'test-calendar-id'
        assert call_args[1]['eventId'] == 'event-123'

    @patch('app.services.calendar_service.build')
    @patch('app.services.calendar_service.service_account.Credentials.from_service_account_file')
    def test_get_events_no_calendar_id(
        self,
        mock_credentials,
        mock_build,
        calendar_service,
        mock_redis
    ):
        """Test get_events raises error when no calendar ID is available."""
        mock_redis.get.return_value = None

        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}):
            with pytest.raises(ValueError, match="No calendar ID available"):
                calendar_service.get_events()

    @patch('app.services.calendar_service.build')
    @patch('app.services.calendar_service.service_account.Credentials.from_service_account_file')
    def test_create_reservation_no_calendar_id(
        self,
        mock_credentials,
        mock_build,
        calendar_service,
        mock_redis
    ):
        """Test create_reservation raises error when no calendar ID is available."""
        mock_redis.get.return_value = None

        start = datetime(2024, 1, 15, 10, 0)
        end = datetime(2024, 1, 15, 12, 0)

        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}):
            with pytest.raises(ValueError, match="No calendar ID available"):
                calendar_service.create_reservation(
                    indicatif="VL75-01",
                    chauffeur="Jean Dupont",
                    mission="Mission Secours",
                    start=start,
                    end=end
                )

    @patch('app.services.calendar_service.build')
    @patch('app.services.calendar_service.service_account.Credentials.from_service_account_file')
    def test_delete_reservation_no_calendar_id(
        self,
        mock_credentials,
        mock_build,
        calendar_service,
        mock_redis
    ):
        """Test delete_reservation raises error when no calendar ID is available."""
        mock_redis.get.return_value = None

        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"}):
            with pytest.raises(ValueError, match="No calendar ID available"):
                calendar_service.delete_reservation("event-123")

    def test_get_calendar_id(self, calendar_service, mock_redis):
        """Test getting calendar ID."""
        mock_redis.get.return_value = "stored-calendar-id"

        calendar_id = calendar_service.get_calendar_id()

        assert calendar_id == "stored-calendar-id"

