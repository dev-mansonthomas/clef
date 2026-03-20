"""Tests for API Keys management."""
import pytest
import pytest_asyncio
import fakeredis.aioredis
from app.services.valkey_service import ValkeyService


@pytest_asyncio.fixture
async def redis_client():
    """Fake Redis client with JSON support."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def valkey_service(redis_client):
    """ValkeyService instance with fake Redis."""
    return ValkeyService(redis_client=redis_client, dt="DT75")


class TestApiKeysDT:
    """Test DT-level API key operations."""

    @pytest.mark.asyncio
    async def test_generate_api_key_dt(self, valkey_service):
        """Test generating a DT-level API key."""
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

        # Verify key was actually stored
        keys = await valkey_service.list_api_keys_dt(mask_keys=False)
        assert len(keys) == 1
        assert keys[0]["name"] == "Test Key"

    @pytest.mark.asyncio
    async def test_list_api_keys_dt_masked(self, valkey_service):
        """Test listing DT-level API keys with masking."""
        # Generate a key first
        await valkey_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )

        keys = await valkey_service.list_api_keys_dt(mask_keys=True)

        assert len(keys) == 1
        assert keys[0]["name"] == "Key 1"
        assert keys[0]["key"] == "clef_sk_●●●●●●●●●●●●●●●●"

    @pytest.mark.asyncio
    async def test_validate_api_key_dt_valid(self, valkey_service):
        """Test validating a valid DT-level API key."""
        # Generate a key first
        api_key = await valkey_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )

        is_valid = await valkey_service.validate_api_key(api_key["key"])

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_api_key_dt_invalid(self, valkey_service):
        """Test validating an invalid DT-level API key."""
        # Generate a key first so config exists
        await valkey_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )

        is_valid = await valkey_service.validate_api_key("clef_sk_invalidkey")

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_delete_api_key_dt(self, valkey_service):
        """Test deleting a DT-level API key."""
        # Generate two keys
        key1 = await valkey_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )
        await valkey_service.generate_api_key_dt(
            name="Key 2",
            created_by="user@example.com"
        )

        success = await valkey_service.delete_api_key_dt(key1["id"])

        assert success is True
        # Verify only one key remains
        keys = await valkey_service.list_api_keys_dt(mask_keys=False)
        assert len(keys) == 1
        assert keys[0]["name"] == "Key 2"

