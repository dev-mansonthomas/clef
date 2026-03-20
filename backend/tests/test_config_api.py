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
from app.services.valkey_service import ValkeyService
from app.models.valkey_models import DTConfiguration
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


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Ensure dependency overrides are cleared between tests."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_valkey_service():
    """Create a mock ValkeyService with stateful configuration."""
    valkey_mock = AsyncMock(spec=ValkeyService)
    valkey_mock.dt = "DT75"

    # Store configuration state
    stored_config = None

    async def get_config():
        return stored_config

    async def set_config(config):
        nonlocal stored_config
        stored_config = config
        return True

    valkey_mock.get_configuration.side_effect = get_config
    valkey_mock.set_configuration.side_effect = set_config

    return valkey_mock


@pytest.fixture
async def client(mock_valkey_service):
    """Create an async test client with mocked ValkeyService and auth."""
    # Override the dependencies
    from app.routers.config import get_config_service
    from app.services.config_service import ConfigService
    from app.auth.dependencies import is_dt_manager
    from app.auth.models import User

    def override_get_config_service():
        return ConfigService(mock_valkey_service)

    def override_is_dt_manager():
        """Mock DT manager user for tests."""
        return User(
            email="thomas.manson@croix-rouge.fr",
            nom="Manson",
            prenom="Thomas",
            role="Gestionnaire DT",
            ul="DT Paris",
            perimetre="DT Paris",
            type_perimetre="DT",
            dt="DT75"
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
    async def test_get_config_from_env(self, client, env_vars, mock_valkey_service):
        """Test getting configuration from environment variables."""
        response = await client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        assert data["email_destinataire_alertes"] == "alerts@croix-rouge.fr"
        assert data["email_gestionnaire_dt"] == "thomas.manson@croix-rouge.fr"
        assert data["drive_sync_status"] == "idle"
        assert data["drive_sync_processed"] == 0
        assert data["drive_sync_total"] == 0

    @pytest.mark.asyncio
    async def test_get_config_from_valkey(self, client, env_vars, mock_valkey_service):
        """Test getting configuration from Valkey storage."""
        stored_config = DTConfiguration(
            dt="DT75",
            nom="DT Paris",
            gestionnaire_email="thomas.manson@croix-rouge.fr",
            email_destinataire_alertes="valkey-alerts@croix-rouge.fr",
            drive_folder_id="folder-abc123",
            drive_folder_url="https://drive.google.com/drive/folders/folder-abc123",
            drive_sync_status="complete",
            drive_sync_processed=5,
            drive_sync_total=5,
        )

        # Use side_effect to set the stored config
        await mock_valkey_service.set_configuration(stored_config)

        response = await client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        # Should use Valkey values
        assert data["email_destinataire_alertes"] == "valkey-alerts@croix-rouge.fr"
        assert data["drive_folder_id"] == "folder-abc123"
        assert data["drive_folder_url"] == "https://drive.google.com/drive/folders/folder-abc123"
        assert data["drive_sync_status"] == "complete"
        assert data["drive_sync_processed"] == 5
        # email_gestionnaire_dt always comes from env
        assert data["email_gestionnaire_dt"] == "thomas.manson@croix-rouge.fr"


class TestUpdateConfig:
    """Tests for PATCH /api/config endpoint."""

    @pytest.mark.asyncio
    async def test_update_single_field(self, client, env_vars, mock_valkey_service):
        """Test updating a single configuration field."""
        update_data = {
            "email_destinataire_alertes": "new-alerts@croix-rouge.fr"
        }

        response = await client.patch("/api/config", json=update_data)

        assert response.status_code == 200
        data = response.json()

        assert data["email_destinataire_alertes"] == "new-alerts@croix-rouge.fr"

        # Verify Valkey was called to store the update
        mock_valkey_service.set_configuration.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_invalid_email(self, client, env_vars, mock_valkey_service):
        """Test that invalid emails are rejected."""
        update_data = {
            "email_destinataire_alertes": "not-an-email"
        }

        response = await client.patch("/api/config", json=update_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_cannot_update_gestionnaire_dt_email(self, client, env_vars, mock_valkey_service):
        """Test that email_gestionnaire_dt cannot be updated (read-only)."""
        update_data = {
            "email_gestionnaire_dt": "hacker@example.com"
        }

        response = await client.patch("/api/config", json=update_data)

        # Should succeed but ignore the field (not in ConfigUpdate model)
        assert response.status_code == 200
        data = response.json()

        # Should still be the original value from env
        assert data["email_gestionnaire_dt"] == "thomas.manson@croix-rouge.fr"

    @pytest.mark.asyncio
    async def test_update_drive_folder_url_invalid(self, client, env_vars, mock_valkey_service):
        """Test that invalid Drive URLs are rejected."""
        update_data = {
            "drive_folder_url": "https://example.com/not-drive"
        }

        response = await client.patch("/api/config", json=update_data)
        assert response.status_code == 422  # Validation error


class TestConfigValidation:
    """Tests for configuration validation."""

    @pytest.mark.asyncio
    async def test_valid_drive_folder_url(self, client, env_vars, mock_valkey_service):
        """Test that valid Google Drive folder URLs are accepted."""
        update_data = {
            "drive_folder_url": "https://drive.google.com/drive/folders/abc123xyz"
        }

        response = await client.patch("/api/config", json=update_data)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_email_format(self, client, env_vars, mock_valkey_service):
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

    @pytest.mark.skip(reason="Requires real Redis/Valkey connection - integration test")
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

