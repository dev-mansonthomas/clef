"""Tests for DT Token Service."""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

# Set mock mode
os.environ["USE_MOCKS"] = "true"


@pytest.fixture
def mock_cache():
    """Create a mock cache with mocked Redis operations."""
    import app.services.dt_token_service

    with patch("app.services.dt_token_service.get_cache") as mock_get_cache:
        cache = MagicMock()
        cache._connected = True

        # Mock the Redis client with plain set/get (service uses json.dumps/loads)
        redis_client = MagicMock()

        # Storage for string data (like real Redis)
        string_storage = {}

        async def redis_set(key, value):
            string_storage[key] = value
            return True

        async def redis_get(key):
            return string_storage.get(key)

        async def redis_delete(key):
            if key in string_storage:
                del string_storage[key]
                return 1
            return 0

        redis_client.set = AsyncMock(side_effect=redis_set)
        redis_client.get = AsyncMock(side_effect=redis_get)
        redis_client.delete = AsyncMock(side_effect=redis_delete)

        # Also mock json() interface for backward compatibility
        json_interface = MagicMock()
        json_interface.set = AsyncMock()
        json_interface.get = AsyncMock()
        redis_client.json = MagicMock(return_value=json_interface)

        cache.client = redis_client
        mock_get_cache.return_value = cache

        yield cache


@pytest.fixture
def mock_kms():
    """Mock KMS service."""
    with patch("app.services.dt_token_service.kms_service") as mock:
        mock.encrypt = MagicMock(side_effect=lambda x: f"encrypted:{x}")
        mock.decrypt = MagicMock(side_effect=lambda x: x.replace("encrypted:", ""))
        yield mock


class TestDTTokenService:
    @pytest.mark.asyncio
    async def test_store_tokens(self, mock_cache, mock_kms):
        from app.services.dt_token_service import DTTokenService
        import json as _json
        service = DTTokenService()

        result = await service.store_tokens(
            dt_id="DT75",
            email="test@croix-rouge.fr",
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
        )

        assert result is True

        # Verify KMS encryption was called for both tokens
        assert mock_kms.encrypt.call_count == 2

        # Verify Valkey storage (service uses plain set with json.dumps)
        stored_raw = await mock_cache.client.get("DT75:oauth:dt_manager_tokens")
        assert stored_raw is not None
        stored_data = _json.loads(stored_raw)
        assert stored_data["email"] == "test@croix-rouge.fr"
        assert stored_data["access_token"] == "encrypted:access123"
        assert stored_data["refresh_token"] == "encrypted:refresh456"
        assert "authorized_at" in stored_data
    
    @pytest.mark.asyncio
    async def test_get_access_token_decrypts(self, mock_cache, mock_kms):
        from app.services.dt_token_service import DTTokenService
        service = DTTokenService()

        # Store tokens first
        await service.store_tokens(
            dt_id="DT75",
            email="test@croix-rouge.fr",
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
        )

        # Get access token (should decrypt)
        token = await service.get_access_token("DT75")

        assert token == "access123"
        # Verify decrypt was called for the encrypted access token
        mock_kms.decrypt.assert_called_with("encrypted:access123")
    
    @pytest.mark.asyncio
    async def test_get_access_token_valid(self, mock_cache, mock_kms):
        from app.services.dt_token_service import DTTokenService
        service = DTTokenService()
        
        # Store tokens with future expiry
        await service.store_tokens(
            dt_id="DT75",
            email="test@croix-rouge.fr",
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,  # 1 hour from now
        )
        
        # Get access token
        token = await service.get_access_token("DT75")
        
        assert token == "access123"
    
    @pytest.mark.asyncio
    async def test_get_authorization_status_authorized(self, mock_cache, mock_kms):
        from app.services.dt_token_service import DTTokenService
        service = DTTokenService()
        
        # Store tokens
        await service.store_tokens(
            dt_id="DT75",
            email="test@croix-rouge.fr",
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
        )
        
        status = await service.get_authorization_status("DT75")
        
        assert status["authorized"] == True
        assert status["email"] == "test@croix-rouge.fr"
        assert "authorized_at" in status
    
    @pytest.mark.asyncio
    async def test_get_authorization_status_not_authorized(self, mock_cache, mock_kms):
        from app.services.dt_token_service import DTTokenService
        service = DTTokenService()
        
        status = await service.get_authorization_status("DT99")
        
        assert status["authorized"] == False
    
    @pytest.mark.asyncio
    async def test_revoke_tokens(self, mock_cache, mock_kms):
        from app.services.dt_token_service import DTTokenService
        service = DTTokenService()

        # Store tokens first
        await service.store_tokens(
            dt_id="DT75",
            email="test@croix-rouge.fr",
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
        )

        # Verify tokens exist
        status = await service.get_authorization_status("DT75")
        assert status["authorized"] is True

        # Revoke tokens
        result = await service.revoke_tokens("DT75")
        assert result is True

        # Verify tokens are gone
        status = await service.get_authorization_status("DT75")
        assert status["authorized"] is False

    @pytest.mark.asyncio
    async def test_token_refresh_on_expiry(self, mock_cache, mock_kms):
        from app.services.dt_token_service import DTTokenService
        service = DTTokenService()

        # Store tokens with very short expiry (already expired)
        await service.store_tokens(
            dt_id="DT75",
            email="test@croix-rouge.fr",
            access_token="old_access",
            refresh_token="refresh456",
            expires_in=-100,  # Already expired
        )

        # Mock the GoogleOAuthService refresh
        with patch("app.auth.google_oauth.GoogleOAuthService") as mock_oauth:
            mock_instance = MagicMock()
            mock_instance.refresh_access_token = AsyncMock(return_value={
                "access_token": "new_access",
                "expires_in": 3600,
            })
            mock_oauth.return_value = mock_instance

            # Get access token should trigger refresh
            token = await service.get_access_token("DT75")

            # Should have called refresh with decrypted refresh token
            mock_instance.refresh_access_token.assert_called_once_with("refresh456")

            # Should return new token
            assert token == "new_access"


