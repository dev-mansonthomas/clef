"""Tests for DT Token Service."""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

# Set mock mode
os.environ["USE_MOCKS"] = "true"


@pytest.fixture
def mock_cache():
    """Create a mock cache with mocked JSON operations."""
    # Import the module first to ensure it exists
    import app.services.dt_token_service

    with patch("app.services.dt_token_service.get_cache") as mock_get_cache:
        cache = MagicMock()
        cache._connected = True

        # Mock the Redis client with JSON support
        redis_client = MagicMock()
        json_interface = MagicMock()

        # Storage for JSON data
        json_storage = {}

        async def json_set(key, path, value):
            json_storage[key] = value
            return True

        async def json_get(key, *args):
            return json_storage.get(key)

        async def delete(key):
            if key in json_storage:
                del json_storage[key]
                return 1
            return 0

        json_interface.set = AsyncMock(side_effect=json_set)
        json_interface.get = AsyncMock(side_effect=json_get)
        redis_client.json = MagicMock(return_value=json_interface)
        redis_client.delete = AsyncMock(side_effect=delete)

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
        service = DTTokenService()
        
        result = await service.store_tokens(
            dt_id="DT75",
            email="test@croix-rouge.fr",
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
        )
        
        assert result is True

        # Verify KMS encryption was called only for refresh token
        mock_kms.encrypt.assert_called_once_with("refresh456")

        # Verify Valkey storage
        stored_data = await mock_cache.client.json().get("DT75:dt_tokens")
        assert stored_data is not None
        assert stored_data["email"] == "test@croix-rouge.fr"
        assert stored_data["access_token"] == "access123"  # Not encrypted
        assert stored_data["refresh_token_encrypted"] == "encrypted:refresh456"
        assert stored_data["authorized"] == True
        assert "authorized_at" in stored_data
    
    @pytest.mark.asyncio
    async def test_get_tokens_decrypts_refresh(self, mock_cache, mock_kms):
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

        # Get tokens (should decrypt refresh token)
        tokens = await service.get_tokens("DT75")

        assert tokens is not None
        assert tokens["access_token"] == "access123"
        assert tokens["refresh_token"] == "refresh456"
        # Verify decrypt was called for refresh token
        mock_kms.decrypt.assert_called_once_with("encrypted:refresh456")
    
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


