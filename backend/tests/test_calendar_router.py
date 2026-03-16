"""Tests for calendar API endpoints."""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"

# Import and configure auth settings BEFORE importing app
from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.auth.models import User
from app.auth import routes as auth_routes

client = TestClient(app)


def get_authenticated_client(email: str) -> TestClient:
    """Helper to get an authenticated test client via OAuth flow."""
    # Use the same okta_mock instance that auth routes uses
    okta_mock = auth_routes.okta_mock
    if not okta_mock:
        raise RuntimeError("okta_mock is None - ensure USE_MOCKS=true is set")

    # Create a new client for this test
    test_client = TestClient(app)

    # Go through OAuth flow
    code = okta_mock.create_mock_authorization_code(email)
    response = test_client.get(
        f"/auth/callback?code={code}&state=test-state",
        follow_redirects=False
    )

    # The callback should set a cookie and redirect
    assert response.status_code == 307, f"Callback failed: {response.status_code}"

    # Extract and set the session cookie on the client
    session_cookie = response.cookies.get(auth_settings.session_cookie_name)
    if session_cookie:
        test_client.cookies.set(auth_settings.session_cookie_name, session_cookie)

    return test_client


def test_get_calendar_status_not_exists():
    """Test getting calendar status when calendar doesn't exist."""
    # Get authenticated client (use a valid email from mock data)
    auth_client = get_authenticated_client("claire.rousseau@croix-rouge.fr")

    # Mock the calendar service to return no calendar
    mock_service = Mock()
    mock_service.get_calendar_id = Mock(return_value=None)
    mock_service._get_calendar_name = Mock(return_value="DEV - CLEF - Réservation Véhicule")

    with patch('app.routers.calendar.get_calendar_service', return_value=mock_service):
        response = auth_client.get("/api/calendar/status")

        assert response.status_code == 200
        data = response.json()
        assert data['exists'] is False
        assert data['calendar_id'] is None
        assert data['calendar_name'] is None


def test_get_calendar_status_exists():
    """Test getting calendar status when calendar exists."""
    # Get authenticated client (use a valid email from mock data)
    auth_client = get_authenticated_client("claire.rousseau@croix-rouge.fr")

    # Mock the calendar service to return an existing calendar
    mock_service = Mock()
    mock_service.get_calendar_id = Mock(return_value="existing-calendar-id")
    mock_service._get_calendar_name = Mock(return_value="DEV - CLEF - Réservation Véhicule")

    with patch('app.routers.calendar.get_calendar_service', return_value=mock_service):
        response = auth_client.get("/api/calendar/status")

        assert response.status_code == 200
        data = response.json()
        assert data['exists'] is True
        assert data['calendar_id'] == "existing-calendar-id"
        assert data['calendar_name'] == "DEV - CLEF - Réservation Véhicule"


def test_create_calendar_success():
    """Test creating a calendar successfully."""
    # Get authenticated client (use a valid email from mock data)
    auth_client = get_authenticated_client("claire.rousseau@croix-rouge.fr")

    # Mock the calendar service
    mock_service = Mock()
    mock_service.get_calendar_id = Mock(return_value=None)
    mock_service.create_calendar = Mock(return_value={
        'id': 'test-calendar-id',
        'summary': 'DEV - CLEF - Réservation Véhicule',
        'description': 'Calendrier de réservation des véhicules (DEV)',
        'timeZone': 'Europe/Paris'
    })

    with patch('app.routers.calendar.get_calendar_service', return_value=mock_service):
        response = auth_client.post("/api/calendar/create")

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 'test-calendar-id'
        assert data['summary'] == 'DEV - CLEF - Réservation Véhicule'
        assert data['description'] == 'Calendrier de réservation des véhicules (DEV)'
        assert data['timeZone'] == 'Europe/Paris'

        # Verify create_calendar was called
        mock_service.create_calendar.assert_called_once()


def test_create_calendar_already_exists():
    """Test creating a calendar when it already exists."""
    # Get authenticated client (use a valid email from mock data)
    auth_client = get_authenticated_client("claire.rousseau@croix-rouge.fr")

    # Mock the calendar service to return an existing calendar
    mock_service = Mock()
    mock_service.get_calendar_id = Mock(return_value="existing-calendar-id")

    with patch('app.routers.calendar.get_calendar_service', return_value=mock_service):
        response = auth_client.post("/api/calendar/create")

        assert response.status_code == 400
        data = response.json()
        assert "already exists" in data['detail']


def test_create_calendar_failure():
    """Test calendar creation failure."""
    # Get authenticated client (use a valid email from mock data)
    auth_client = get_authenticated_client("claire.rousseau@croix-rouge.fr")

    # Mock the calendar service to raise an exception
    mock_service = Mock()
    mock_service.get_calendar_id = Mock(return_value=None)
    mock_service.create_calendar = Mock(side_effect=Exception("Google API error"))

    with patch('app.routers.calendar.get_calendar_service', return_value=mock_service):
        response = auth_client.post("/api/calendar/create")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to create calendar" in data['detail']

