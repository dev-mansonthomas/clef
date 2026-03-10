"""
Tests for configuration API endpoints.
"""
import pytest
import os
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# Set USE_MOCKS before importing app to avoid Google credentials error
os.environ["USE_MOCKS"] = "true"

from app.main import app
from app.services.config_service import ConfigService
from app.cache import RedisCache
from app.auth.config import auth_settings

# Ensure we're using mocks for auth tests
auth_settings.use_mocks = True

# Create a synchronous test client for auth tests
sync_client = TestClient(app)

# Import okta_mock from routes to use the same instance
from app.auth import routes
okta_mock = routes.okta_mock

# Create a synchronous test client for auth tests
sync_client = TestClient(app)


@pytest.fixture
def mock_cache():
    """Create a mock RedisCache."""
    cache_mock = AsyncMock(spec=RedisCache)
    cache_mock.get.return_value = None  # No stored config by default
    cache_mock.set.return_value = True
    cache_mock._connected = True
    return cache_mock


@pytest.fixture
async def client(mock_cache):
    """Create an async test client with mocked cache and auth."""
    # Override the dependencies
    from app.routers.config import get_config_service
    from app.services.config_service import ConfigService
    from app.auth.dependencies import is_dt_manager
    from app.auth.models import User

    def override_get_config_service():
        return ConfigService(mock_cache)

    def override_is_dt_manager():
        """Mock DT manager user for tests."""
        return User(
            email="thomas.manson@croix-rouge.fr",
            nom="Manson",
            prenom="Thomas",
            role="Gestionnaire DT",
            ul="DT Paris",
            perimetre="DT Paris",
            type_perimetre="DT"
        )

    app.dependency_overrides[get_config_service] = override_get_config_service
    app.dependency_overrides[is_dt_manager] = override_is_dt_manager

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def env_vars():
    """Set up environment variables for testing."""
    original_env = os.environ.copy()

    os.environ.update({
        "USE_MOCKS": "true",
        "REDIS_URL": "redis://localhost:6379/0",
        "SHEETS_URL_VEHICULES": "https://docs.google.com/spreadsheets/d/test-vehicules",
        "SHEETS_URL_BENEVOLES": "https://docs.google.com/spreadsheets/d/test-benevoles",
        "SHEETS_URL_RESPONSABLES": "https://docs.google.com/spreadsheets/d/test-responsables",
        "TEMPLATE_DOCUMENT_VEHICULE_URL": "https://docs.google.com/document/d/test-template",
        "EMAIL_DESTINATAIRE_ALERTES": "alerts@croix-rouge.fr",
        "EMAIL_GESTIONNAIRE_DT": "thomas.manson@croix-rouge.fr",
    })

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


class TestGetConfig:
    """Tests for GET /api/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_from_env(self, client, env_vars, mock_cache):
        """Test getting configuration from environment variables."""
        response = await client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        assert data["sheets_url_vehicules"] == "https://docs.google.com/spreadsheets/d/test-vehicules"
        assert data["sheets_url_benevoles"] == "https://docs.google.com/spreadsheets/d/test-benevoles"
        assert data["sheets_url_responsables"] == "https://docs.google.com/spreadsheets/d/test-responsables"
        assert data["template_doc_url"] == "https://docs.google.com/document/d/test-template"
        assert data["email_destinataire_alertes"] == "alerts@croix-rouge.fr"
        assert data["email_gestionnaire_dt"] == "thomas.manson@croix-rouge.fr"

    @pytest.mark.asyncio
    async def test_get_config_from_cache(self, client, env_vars, mock_cache):
        """Test getting configuration from cache storage."""
        stored_config = {
            "sheets_url_vehicules": "https://docs.google.com/spreadsheets/d/cache-vehicules",
            "sheets_url_benevoles": "https://docs.google.com/spreadsheets/d/cache-benevoles",
            "sheets_url_responsables": "https://docs.google.com/spreadsheets/d/cache-responsables",
            "template_doc_url": "https://docs.google.com/document/d/cache-template",
            "email_destinataire_alertes": "cache-alerts@croix-rouge.fr",
        }

        mock_cache.get.return_value = stored_config

        response = await client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        # Should use cache values
        assert data["sheets_url_vehicules"] == "https://docs.google.com/spreadsheets/d/cache-vehicules"
        assert data["email_destinataire_alertes"] == "cache-alerts@croix-rouge.fr"
        # email_gestionnaire_dt always comes from env
        assert data["email_gestionnaire_dt"] == "thomas.manson@croix-rouge.fr"


class TestUpdateConfig:
    """Tests for PATCH /api/config endpoint."""

    @pytest.mark.asyncio
    async def test_update_single_field(self, client, env_vars, mock_cache):
        """Test updating a single configuration field."""
        update_data = {
            "email_destinataire_alertes": "new-alerts@croix-rouge.fr"
        }

        response = await client.patch("/api/config", json=update_data)

        assert response.status_code == 200
        data = response.json()

        assert data["email_destinataire_alertes"] == "new-alerts@croix-rouge.fr"
        # Other fields should remain from env
        assert data["sheets_url_vehicules"] == "https://docs.google.com/spreadsheets/d/test-vehicules"

        # Verify cache was called to store the update
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, client, env_vars, mock_cache):
        """Test updating multiple configuration fields."""
        update_data = {
            "sheets_url_vehicules": "https://docs.google.com/spreadsheets/d/updated-vehicules",
            "email_destinataire_alertes": "updated@croix-rouge.fr"
        }

        response = await client.patch("/api/config", json=update_data)

        assert response.status_code == 200
        data = response.json()

        assert data["sheets_url_vehicules"] == "https://docs.google.com/spreadsheets/d/updated-vehicules"
        assert data["email_destinataire_alertes"] == "updated@croix-rouge.fr"

    @pytest.mark.asyncio
    async def test_update_with_invalid_url(self, client, env_vars, mock_cache):
        """Test that invalid URLs are rejected."""
        update_data = {
            "sheets_url_vehicules": "https://example.com/not-google-docs"
        }

        response = await client.patch("/api/config", json=update_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_update_with_invalid_email(self, client, env_vars, mock_cache):
        """Test that invalid emails are rejected."""
        update_data = {
            "email_destinataire_alertes": "not-an-email"
        }

        response = await client.patch("/api/config", json=update_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_cannot_update_gestionnaire_dt_email(self, client, env_vars, mock_cache):
        """Test that email_gestionnaire_dt cannot be updated (read-only)."""
        update_data = {
            "email_gestionnaire_dt": "hacker@example.com"
        }

        response = await client.patch("/api/config", json=update_data)

        # Should succeed but ignore the field
        assert response.status_code == 200
        data = response.json()

        # Should still be the original value from env
        assert data["email_gestionnaire_dt"] == "thomas.manson@croix-rouge.fr"


class TestConfigValidation:
    """Tests for configuration validation."""

    @pytest.mark.asyncio
    async def test_valid_google_sheets_url(self, client, env_vars, mock_cache):
        """Test that valid Google Sheets URLs are accepted."""
        update_data = {
            "sheets_url_vehicules": "https://docs.google.com/spreadsheets/d/abc123/edit"
        }

        response = await client.patch("/api/config", json=update_data)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_google_docs_url(self, client, env_vars, mock_cache):
        """Test that valid Google Docs URLs are accepted."""
        update_data = {
            "template_doc_url": "https://docs.google.com/document/d/xyz789/edit"
        }

        response = await client.patch("/api/config", json=update_data)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_url_scheme(self, client, env_vars, mock_cache):
        """Test that non-HTTPS URLs are rejected."""
        update_data = {
            "sheets_url_vehicules": "http://docs.google.com/spreadsheets/d/abc123"
        }

        response = await client.patch("/api/config", json=update_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_email_format(self, client, env_vars, mock_cache):
        """Test that valid email formats are accepted."""
        update_data = {
            "email_destinataire_alertes": "test.user@croix-rouge.fr"
        }

        response = await client.patch("/api/config", json=update_data)
        assert response.status_code == 200


class TestConfigAuthGuard:
    """Tests for DT manager authentication guard on config endpoints."""

    def _get_authenticated_client(self, email: str) -> TestClient:
        """Helper to get an authenticated test client via OAuth flow."""
        # Create a new client for this test with base_url
        test_client = TestClient(app, base_url="http://testserver")

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

    def test_patch_config_without_auth(self, env_vars):
        """Test that PATCH /api/config requires authentication."""
        test_client = TestClient(app, base_url="http://testserver")
        update_data = {
            "email_destinataire_alertes": "new-alerts@croix-rouge.fr"
        }

        response = test_client.patch("/api/config", json=update_data)
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_patch_config_as_non_dt_manager(self, env_vars):
        """Test that PATCH /api/config rejects non-DT manager users."""
        # Authenticate as UL responsible (not DT manager)
        test_client = self._get_authenticated_client("claire.rousseau@croix-rouge.fr")

        update_data = {
            "email_destinataire_alertes": "new-alerts@croix-rouge.fr"
        }

        response = test_client.patch("/api/config", json=update_data)
        assert response.status_code == 403
        assert response.json()["detail"] == "DT manager access required"

    def test_patch_config_as_dt_manager(self, env_vars):
        """Test that PATCH /api/config allows DT manager users."""
        # Authenticate as DT manager
        test_client = self._get_authenticated_client("thomas.manson@croix-rouge.fr")

        update_data = {
            "email_destinataire_alertes": "new-alerts@croix-rouge.fr"
        }

        response = test_client.patch("/api/config", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["email_destinataire_alertes"] == "new-alerts@croix-rouge.fr"

