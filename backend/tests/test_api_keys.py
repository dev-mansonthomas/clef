"""Tests for API Keys management."""
import pytest
import pytest_asyncio
import fakeredis.aioredis
from app.services.redis_service import RedisService


@pytest_asyncio.fixture
async def redis_client():
    """Fake Redis client with JSON support."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def redis_service(redis_client):
    """RedisService instance with fake Redis."""
    return RedisService(redis_client=redis_client, dt="DT75")


class TestApiKeysDT:
    """Test DT-level API key operations."""

    @pytest.mark.asyncio
    async def test_generate_api_key_dt(self, redis_service):
        """Test generating a DT-level API key."""
        api_key = await redis_service.generate_api_key_dt(
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
        keys = await redis_service.list_api_keys_dt(mask_keys=False)
        assert len(keys) == 1
        assert keys[0]["name"] == "Test Key"

    @pytest.mark.asyncio
    async def test_list_api_keys_dt_masked(self, redis_service):
        """Test listing DT-level API keys with masking."""
        # Generate a key first
        await redis_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )

        keys = await redis_service.list_api_keys_dt(mask_keys=True)

        assert len(keys) == 1
        assert keys[0]["name"] == "Key 1"
        assert keys[0]["key"] == "clef_sk_●●●●●●●●●●●●●●●●"

    @pytest.mark.asyncio
    async def test_validate_api_key_dt_valid(self, redis_service):
        """Test validating a valid DT-level API key."""
        # Generate a key first
        api_key = await redis_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )

        is_valid = await redis_service.validate_api_key(api_key["key"])

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_api_key_dt_invalid(self, redis_service):
        """Test validating an invalid DT-level API key."""
        # Generate a key first so config exists
        await redis_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )

        is_valid = await redis_service.validate_api_key("clef_sk_invalidkey")

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_delete_api_key_dt(self, redis_service):
        """Test deleting a DT-level API key."""
        # Generate two keys
        key1 = await redis_service.generate_api_key_dt(
            name="Key 1",
            created_by="user@example.com"
        )
        await redis_service.generate_api_key_dt(
            name="Key 2",
            created_by="user@example.com"
        )

        success = await redis_service.delete_api_key_dt(key1["id"])

        assert success is True
        # Verify only one key remains
        keys = await redis_service.list_api_keys_dt(mask_keys=False)
        assert len(keys) == 1
        assert keys[0]["name"] == "Key 2"

