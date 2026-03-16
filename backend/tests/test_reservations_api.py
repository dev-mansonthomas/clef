"""Tests for reservation API endpoints."""
import os
import pytest
from datetime import datetime, timedelta

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"

# Import and configure auth settings BEFORE importing app
from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.auth import routes as auth_routes

client = TestClient(app)


def get_authenticated_client(email: str) -> TestClient:
    """Helper to get an authenticated test client via OAuth flow."""
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


def get_authenticated_cookies(email: str) -> dict:
    """Helper to get authenticated cookies for a user."""
    test_client = get_authenticated_client(email)
    return test_client.cookies


class TestCreateReservation:
    """Test POST /api/reservations endpoint."""

    def test_create_reservation_success(self):
        """Test creating a reservation successfully."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=4)

        reservation_data = {
            "indicatif": "VL75-01",
            "chauffeur": "Jean Dupont",
            "mission": "Mission Secours",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "description": "Test reservation"
        }

        response = auth_client.post("/api/reservations", json=reservation_data)

        assert response.status_code == 201
        data = response.json()
        assert data["indicatif"] == "VL75-01"
        assert data["chauffeur"] == "Jean Dupont"
        assert data["mission"] == "Mission Secours"
        assert "id" in data

    def test_create_reservation_invalid_dates(self):
        """Test that end date must be after start date."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        start = datetime.now() + timedelta(days=1)
        end = start - timedelta(hours=1)  # End before start

        reservation_data = {
            "indicatif": "VL75-01",
            "chauffeur": "Jean Dupont",
            "mission": "Mission Secours",
            "start": start.isoformat(),
            "end": end.isoformat()
        }

        response = auth_client.post("/api/reservations", json=reservation_data)

        assert response.status_code == 400
        assert "End date must be after start date" in response.json()["detail"]

    def test_create_reservation_vehicle_not_found(self):
        """Test creating reservation with non-existent vehicle."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=4)

        reservation_data = {
            "indicatif": "INVALID-99",
            "chauffeur": "Jean Dupont",
            "mission": "Mission Secours",
            "start": start.isoformat(),
            "end": end.isoformat()
        }

        response = auth_client.post("/api/reservations", json=reservation_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_reservation_unauthorized(self):
        """Test that authentication is required."""
        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        
        reservation_data = {
            "indicatif": "VL75-01",
            "chauffeur": "Jean Dupont",
            "mission": "Mission Secours",
            "start": start.isoformat(),
            "end": end.isoformat()
        }
        
        response = client.post("/api/reservations", json=reservation_data)
        
        assert response.status_code == 401


class TestGetAvailableVehicles:
    """Test GET /api/vehicles/available endpoint."""

    def test_get_available_vehicles_success(self):
        """Test getting available vehicles for a time period."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=4)

        response = auth_client.get(
            "/api/vehicles/available",
            params={
                "start": start.isoformat(),
                "end": end.isoformat()
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "vehicles" in data
        assert isinstance(data["vehicles"], list)

        # All returned vehicles should be mechanically available
        for vehicle in data["vehicles"]:
            assert vehicle["operationnel_mecanique"] == "Dispo"

    def test_get_available_vehicles_invalid_dates(self):
        """Test that end date must be after start date."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        start = datetime.now() + timedelta(days=1)
        end = start - timedelta(hours=1)

        response = auth_client.get(
            "/api/vehicles/available",
            params={
                "start": start.isoformat(),
                "end": end.isoformat()
            }
        )

        assert response.status_code == 400
        assert "End date must be after start date" in response.json()["detail"]

    def test_get_available_vehicles_unauthorized(self):
        """Test that authentication is required."""
        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        
        response = client.get(
            "/api/vehicles/available",
            params={
                "start": start.isoformat(),
                "end": end.isoformat()
            }
        )
        
        assert response.status_code == 401

