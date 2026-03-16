"""
Tests for Unités Locales API endpoints.
"""
import pytest
import os
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

# Set USE_MOCKS before importing app
os.environ["USE_MOCKS"] = "true"

from app.main import app
from app.cache import RedisCache
from app.auth.models import User
from app.auth.config import auth_settings

# Ensure we're using mocks
auth_settings.use_mocks = True


@pytest.fixture
def mock_cache():
    """Create a mock RedisCache with UL data."""
    cache_mock = AsyncMock(spec=RedisCache)
    cache_mock._connected = True

    # Mock client for set operations
    cache_mock.client = AsyncMock()
    cache_mock.client.smembers = AsyncMock()
    cache_mock.client.sadd = AsyncMock()

    # Mock JSON operations
    cache_mock.client.json = MagicMock()
    cache_mock.client.json.return_value = AsyncMock()
    cache_mock.client.json().get = AsyncMock(return_value=None)
    cache_mock.client.json().set = AsyncMock(return_value=True)

    # Default: no UL data
    cache_mock.get.return_value = None
    cache_mock.set.return_value = True
    cache_mock.exists.return_value = False
    cache_mock.client.smembers.return_value = set()

    return cache_mock


@pytest.fixture
async def client(mock_cache):
    """Create an async test client with mocked cache and auth."""
    from app.cache import get_cache
    from app.auth.dependencies import require_authenticated_user, require_dt_manager
    
    def override_get_cache():
        return mock_cache
    
    def override_require_authenticated_user():
        """Mock authenticated user."""
        return User(
            email="user@croix-rouge.fr",
            nom="User",
            prenom="Test",
            role="Responsable UL",
            ul="UL 01-02",
            perimetre="UL 01-02",
            type_perimetre="UL"
        )
    
    def override_require_dt_manager():
        """Mock DT manager user."""
        return User(
            email="thomas.manson@croix-rouge.fr",
            nom="Manson",
            prenom="Thomas",
            role="Gestionnaire DT",
            ul="DT75",
            perimetre="DT75",
            type_perimetre="DT"
        )
    
    app.dependency_overrides[get_cache] = override_get_cache
    app.dependency_overrides[require_authenticated_user] = override_require_authenticated_user
    app.dependency_overrides[require_dt_manager] = override_require_dt_manager
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    # Clean up
    app.dependency_overrides.clear()


class TestListUnitesLocales:
    """Tests for GET /api/{dt}/unites-locales endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_empty(self, client, mock_cache):
        """Test listing UL when none exist."""
        mock_cache.client.smembers.return_value = set()
        
        response = await client.get("/api/DT75/unites-locales")
        
        assert response.status_code == 200
        data = response.json()
        assert data["unites_locales"] == []
        assert data["total"] == 0
    
    @pytest.mark.asyncio
    async def test_list_with_data(self, client, mock_cache):
        """Test listing UL with data."""
        # Mock index with 2 UL IDs
        mock_cache.client.smembers.return_value = {"81", "82"}

        # Mock UL data using JSON native storage
        async def mock_json_get(key):
            if key == "DT75:unite_locale:81":
                return {
                    "id": "81",
                    "nom": "UL 01-02",
                    "dt": "DT75",
                    "created_at": "2026-03-13T00:00:00Z"
                }
            elif key == "DT75:unite_locale:82":
                return {
                    "id": "82",
                    "nom": "UL 03-10",
                    "dt": "DT75",
                    "created_at": "2026-03-13T00:00:00Z"
                }
            return None

        mock_cache.client.json().get.side_effect = mock_json_get

        response = await client.get("/api/DT75/unites-locales")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["unites_locales"]) == 2


class TestGetUniteLocale:
    """Tests for GET /api/{dt}/unites-locales/{ul_id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_existing_ul(self, client, mock_cache):
        """Test getting an existing UL."""
        mock_cache.client.json().get.return_value = {
            "id": "81",
            "nom": "UL 01-02",
            "dt": "DT75",
            "created_at": "2026-03-13T00:00:00Z"
        }

        response = await client.get("/api/DT75/unites-locales/81")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "81"
        assert data["nom"] == "UL 01-02"
        assert data["dt"] == "DT75"

    @pytest.mark.asyncio
    async def test_get_nonexistent_ul(self, client, mock_cache):
        """Test getting a non-existent UL."""
        mock_cache.client.json().get.return_value = None

        response = await client.get("/api/DT75/unites-locales/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestCreateUniteLocale:
    """Tests for POST /api/{dt}/unites-locales endpoint."""

    @pytest.mark.asyncio
    async def test_create_ul(self, client, mock_cache):
        """Test creating a new UL."""
        mock_cache.exists.return_value = False

        ul_data = {
            "id": "99",
            "nom": "UL Test",
            "dt": "DT75"
        }

        response = await client.post("/api/DT75/unites-locales", json=ul_data)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "99"
        assert data["nom"] == "UL Test"
        assert data["dt"] == "DT75"
        assert "created_at" in data

        # Verify cache was called with JSON native storage
        mock_cache.client.json().set.assert_called_once()
        mock_cache.client.sadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_duplicate_ul(self, client, mock_cache):
        """Test creating a UL that already exists."""
        mock_cache.exists.return_value = True

        ul_data = {
            "id": "81",
            "nom": "UL Duplicate",
            "dt": "DT75"
        }

        response = await client.post("/api/DT75/unites-locales", json=ul_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestUpdateUniteLocale:
    """Tests for PUT /api/{dt}/unites-locales/{ul_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_ul(self, client, mock_cache):
        """Test updating an existing UL."""
        mock_cache.client.json().get.return_value = {
            "id": "81",
            "nom": "UL 01-02",
            "dt": "DT75",
            "created_at": "2026-03-13T00:00:00Z"
        }

        update_data = {
            "nom": "UL 01-02 Updated"
        }

        response = await client.put("/api/DT75/unites-locales/81", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["nom"] == "UL 01-02 Updated"
        assert data["id"] == "81"

        # Verify cache was updated with JSON native storage
        mock_cache.client.json().set.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonexistent_ul(self, client, mock_cache):
        """Test updating a non-existent UL."""
        mock_cache.client.json().get.return_value = None

        update_data = {
            "nom": "UL Updated"
        }

        response = await client.put("/api/DT75/unites-locales/999", json=update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestDeleteUniteLocale:
    """Tests for DELETE /api/{dt}/unites-locales/{ul_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_ul(self, client, mock_cache):
        """Test deleting an existing UL."""
        mock_cache.exists.return_value = True
        mock_cache.client.delete = AsyncMock(return_value=1)
        mock_cache.client.srem = AsyncMock(return_value=1)

        response = await client.delete("/api/DT75/unites-locales/81")

        assert response.status_code == 204

        # Verify cache operations
        mock_cache.exists.assert_called_once_with("DT75:unite_locale:81")
        mock_cache.client.delete.assert_called_once_with("DT75:unite_locale:81")
        mock_cache.client.srem.assert_called_once_with("DT75:unite_locales:index", "81")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_ul(self, client, mock_cache):
        """Test deleting a non-existent UL."""
        mock_cache.exists.return_value = False

        response = await client.delete("/api/DT75/unites-locales/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

        # Verify delete was not called
        mock_cache.client.delete.assert_not_called()

