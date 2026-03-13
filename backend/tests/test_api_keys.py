"""Tests for API Keys management."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.services.valkey_service import ValkeyService


@pytest.fixture
async def redis_client():
    """Mock Redis client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.smembers = AsyncMock(return_value=set())
    client.sadd = AsyncMock(return_value=1)
    client.srem = AsyncMock(return_value=1)
    client.delete = AsyncMock(return_value=1)
    return client


@pytest.fixture
async def valkey_service(redis_client):
    """ValkeyService instance with mocked Redis."""
    return ValkeyService(redis_client=redis_client, dt="DT75")


class TestApiKeysDT:
    """Test DT-level API key operations."""
    
    @pytest.mark.asyncio
    async def test_generate_api_key_dt(self, valkey_service, redis_client):
        """Test generating a DT-level API key."""
        # Mock empty config
        redis_client.get.return_value = json.dumps({})
        
        api_key = await valkey_service.generate_api_key_dt(
            name="Test Key",
            created_by="test@example.com"
        )
        
        assert api_key["name"] == "Test Key"
        assert api_key["created_by"] == "test@example.com"
        assert api_key["key"].startswith("clef_sk_")
        assert len(api_key["key"]) == 40  # clef_sk_ + 32 hex chars
        assert "id" in api_key
        assert "created_at" in api_key
        assert api_key["last_used"] is None
        
        # Verify Redis was called to save
        redis_client.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_api_keys_dt_masked(self, valkey_service, redis_client):
        """Test listing DT-level API keys with masking."""
        # Mock config with API keys
        config = {
            "api_keys": [
                {
                    "id": "key-1",
                    "name": "Key 1",
                    "key": "clef_sk_abc123",
                    "created_at": "2024-01-01T00:00:00",
                    "created_by": "user@example.com",
                    "last_used": None
                }
            ]
        }
        redis_client.get.return_value = json.dumps(config)
        
        keys = await valkey_service.list_api_keys_dt(mask_keys=True)
        
        assert len(keys) == 1
        assert keys[0]["name"] == "Key 1"
        assert keys[0]["key"] == "clef_sk_●●●●●●●●●●●●●●●●"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_dt_valid(self, valkey_service, redis_client):
        """Test validating a valid DT-level API key."""
        # Mock config with API key
        config = {
            "api_keys": [
                {
                    "id": "key-1",
                    "name": "Key 1",
                    "key": "clef_sk_validkey123",
                    "created_at": "2024-01-01T00:00:00",
                    "created_by": "user@example.com",
                    "last_used": None
                }
            ]
        }
        redis_client.get.return_value = json.dumps(config)
        
        is_valid = await valkey_service.validate_api_key("clef_sk_validkey123")
        
        assert is_valid is True
        # Verify last_used was updated
        redis_client.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_api_key_dt_invalid(self, valkey_service, redis_client):
        """Test validating an invalid DT-level API key."""
        # Mock config with API key
        config = {
            "api_keys": [
                {
                    "id": "key-1",
                    "name": "Key 1",
                    "key": "clef_sk_validkey123",
                    "created_at": "2024-01-01T00:00:00",
                    "created_by": "user@example.com",
                    "last_used": None
                }
            ]
        }
        redis_client.get.return_value = json.dumps(config)
        
        is_valid = await valkey_service.validate_api_key("clef_sk_invalidkey")
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_delete_api_key_dt(self, valkey_service, redis_client):
        """Test deleting a DT-level API key."""
        # Mock config with API keys
        config = {
            "api_keys": [
                {
                    "id": "key-1",
                    "name": "Key 1",
                    "key": "clef_sk_key1",
                    "created_at": "2024-01-01T00:00:00",
                    "created_by": "user@example.com",
                    "last_used": None
                },
                {
                    "id": "key-2",
                    "name": "Key 2",
                    "key": "clef_sk_key2",
                    "created_at": "2024-01-01T00:00:00",
                    "created_by": "user@example.com",
                    "last_used": None
                }
            ]
        }
        redis_client.get.return_value = json.dumps(config)
        
        success = await valkey_service.delete_api_key_dt("key-1")
        
        assert success is True
        # Verify Redis was called to save updated config
        redis_client.set.assert_called_once()

