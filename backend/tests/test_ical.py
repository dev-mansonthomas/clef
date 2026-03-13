"""Tests for iCal feed generation."""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from app.main import app
from app.routers.ical import create_ical_from_events, extract_indicatif_from_summary, parse_event_datetime
from icalendar import Calendar


client = TestClient(app)


def test_extract_indicatif_from_summary():
    """Test extracting indicatif from event summary."""
    # Standard format
    assert extract_indicatif_from_summary("VL75-01 - Jean Dupont - Mission Secours") == "VL75-01"
    
    # With spaces
    assert extract_indicatif_from_summary("AB-123-CD - Marie Martin - Formation") == "AB-123-CD"
    
    # Edge cases
    assert extract_indicatif_from_summary("") == ""
    assert extract_indicatif_from_summary("NoSeparator") == "NoSeparator"


def test_parse_event_datetime():
    """Test parsing datetime from Google Calendar format."""
    # ISO format with Z
    event_dt = {'dateTime': '2024-01-15T10:30:00Z'}
    result = parse_event_datetime(event_dt)
    assert isinstance(result, datetime)
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    
    # ISO format with timezone
    event_dt = {'dateTime': '2024-01-15T10:30:00+01:00'}
    result = parse_event_datetime(event_dt)
    assert isinstance(result, datetime)


def test_create_ical_from_events():
    """Test creating iCal from Google Calendar events."""
    events = [
        {
            'id': 'event-123',
            'summary': 'VL75-01 - Jean Dupont - Mission Secours',
            'description': 'Mission de secours urgente',
            'start': {'dateTime': '2024-01-15T10:00:00Z'},
            'end': {'dateTime': '2024-01-15T12:00:00Z'},
            'status': 'confirmed'
        },
        {
            'id': 'event-456',
            'summary': 'AB-123-CD - Marie Martin - Formation PSC1',
            'description': 'Formation premiers secours',
            'start': {'dateTime': '2024-01-16T14:00:00Z'},
            'end': {'dateTime': '2024-01-16T18:00:00Z'},
            'status': 'confirmed'
        }
    ]
    
    ical_data = create_ical_from_events(events, "CLEF - Réservations DT75", "DT75")
    
    # Parse the iCal to verify structure
    cal = Calendar.from_ical(ical_data)
    
    # Check calendar properties
    assert cal.get('prodid') == '-//CLEF//Reservations//FR'
    assert cal.get('version') == '2.0'
    assert cal.get('x-wr-calname') == 'CLEF - Réservations DT75'
    assert cal.get('x-wr-timezone') == 'Europe/Paris'
    
    # Check events
    events_in_cal = [component for component in cal.walk() if component.name == 'VEVENT']
    assert len(events_in_cal) == 2
    
    # Check first event
    event1 = events_in_cal[0]
    assert 'DT75-res-event-123@clef.croix-rouge.fr' in str(event1.get('uid'))
    assert event1.get('summary') == 'VL75-01 - Jean Dupont - Mission Secours'
    assert event1.get('description') == 'Mission de secours urgente'
    assert event1.get('status') == 'CONFIRMED'


def test_get_reservations_ical_endpoint():
    """Test the /api/calendar/{dt}/reservations.ics endpoint."""
    # Mock calendar service
    mock_calendar_service = Mock()
    mock_calendar_service.get_events.return_value = [
        {
            'id': 'event-123',
            'summary': 'VL75-01 - Jean Dupont - Mission',
            'description': 'Test mission',
            'start': {'dateTime': '2024-01-15T10:00:00Z'},
            'end': {'dateTime': '2024-01-15T12:00:00Z'},
            'status': 'confirmed'
        }
    ]

    # Mock cache (no cache hit)
    mock_cache = Mock()
    mock_cache._connected = True
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    async def mock_dependency():
        return (mock_calendar_service, mock_cache)

    # Override the dependency
    from app.routers import ical
    app.dependency_overrides[ical.get_calendar_service_with_cache] = mock_dependency

    try:
        # Make request
        response = client.get("/api/calendar/DT75/reservations.ics")

        # Check response
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/calendar; charset=utf-8'
        assert 'DT75-reservations.ics' in response.headers['content-disposition']

        # Verify iCal content
        cal = Calendar.from_ical(response.content)
        assert cal.get('x-wr-calname') == 'CLEF - Réservations DT75'
    finally:
        # Clean up
        app.dependency_overrides.clear()


def test_get_vehicle_ical_endpoint():
    """Test the /api/calendar/{dt}/vehicle/{immat}.ics endpoint."""
    # Mock calendar service with multiple events
    mock_calendar_service = Mock()
    mock_calendar_service.get_events.return_value = [
        {
            'id': 'event-123',
            'summary': 'VL75-01 - Jean Dupont - Mission',
            'description': 'Test mission',
            'start': {'dateTime': '2024-01-15T10:00:00Z'},
            'end': {'dateTime': '2024-01-15T12:00:00Z'},
            'status': 'confirmed'
        },
        {
            'id': 'event-456',
            'summary': 'AB-123-CD - Marie Martin - Formation',
            'description': 'Formation',
            'start': {'dateTime': '2024-01-16T14:00:00Z'},
            'end': {'dateTime': '2024-01-16T18:00:00Z'},
            'status': 'confirmed'
        }
    ]

    # Mock cache (no cache hit)
    mock_cache = Mock()
    mock_cache._connected = True
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    async def mock_dependency():
        return (mock_calendar_service, mock_cache)

    # Override the dependency
    from app.routers import ical
    app.dependency_overrides[ical.get_calendar_service_with_cache] = mock_dependency

    try:
        # Make request for specific vehicle
        response = client.get("/api/calendar/DT75/vehicle/VL75-01.ics")

        # Check response
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/calendar; charset=utf-8'

        # Verify iCal content - should only have 1 event for VL75-01
        cal = Calendar.from_ical(response.content)
        events_in_cal = [component for component in cal.walk() if component.name == 'VEVENT']
        assert len(events_in_cal) == 1
        assert 'VL75-01' in str(events_in_cal[0].get('summary'))
    finally:
        # Clean up
        app.dependency_overrides.clear()

