"""Tests for Redis cache module."""
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
import fakeredis.aioredis

# Set test environment
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.cache import RedisCache, CacheService


@pytest_asyncio.fixture
async def redis_cache() -> AsyncGenerator[RedisCache, None]:
    """Create a Redis cache instance for testing with fakeredis."""
    cache = RedisCache()
    # Use fakeredis for testing
    cache.client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache._connected = True

    # Clean up test keys before test
    await cache.client.flushdb()

    yield cache

    # Clean up after test
    await cache.client.flushdb()
    await cache.client.aclose()


@pytest_asyncio.fixture
async def cache_service(redis_cache: RedisCache) -> CacheService:
    """Create a CacheService instance for testing."""
    return CacheService(redis_cache)


class TestRedisCache:
    """Test RedisCache basic operations."""
    
    @pytest.mark.asyncio
    async def test_connection(self, redis_cache: RedisCache):
        """Test Redis connection."""
        assert redis_cache._connected is True
        assert redis_cache.client is not None
    
    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_cache: RedisCache):
        """Test setting and getting a value."""
        key = "test:key"
        value = {"name": "test", "count": 42}
        
        # Set value
        success = await redis_cache.set(key, value)
        assert success is True
        
        # Get value
        result = await redis_cache.get(key)
        assert result == value
    
    @pytest.mark.asyncio
    async def test_get_nonexistent(self, redis_cache: RedisCache):
        """Test getting a non-existent key."""
        result = await redis_cache.get("nonexistent:key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete(self, redis_cache: RedisCache):
        """Test deleting a key."""
        key = "test:delete"
        value = "test value"
        
        # Set and verify
        await redis_cache.set(key, value)
        assert await redis_cache.exists(key) is True
        
        # Delete and verify
        success = await redis_cache.delete(key)
        assert success is True
        assert await redis_cache.exists(key) is False
    
    @pytest.mark.asyncio
    async def test_exists(self, redis_cache: RedisCache):
        """Test checking key existence."""
        key = "test:exists"
        
        # Key should not exist initially
        assert await redis_cache.exists(key) is False
        
        # Set key
        await redis_cache.set(key, "value")
        
        # Key should exist now
        assert await redis_cache.exists(key) is True
    
    @pytest.mark.asyncio
    async def test_ttl(self, redis_cache: RedisCache):
        """Test setting value with TTL."""
        key = "test:ttl"
        value = "expires soon"
        ttl = 10  # 10 seconds
        
        # Set with TTL
        success = await redis_cache.set(key, value, ttl=ttl)
        assert success is True
        
        # Verify value exists
        result = await redis_cache.get(key)
        assert result == value
        
        # Check TTL is set (should be <= 10 seconds)
        actual_ttl = await redis_cache.client.ttl(key)
        assert 0 < actual_ttl <= ttl
    
    @pytest.mark.asyncio
    async def test_persistent_no_ttl(self, redis_cache: RedisCache):
        """Test setting value without TTL (persistent)."""
        key = "test:persistent"
        value = "never expires"
        
        # Set without TTL
        success = await redis_cache.set(key, value, ttl=None)
        assert success is True
        
        # Check TTL is -1 (no expiration)
        actual_ttl = await redis_cache.client.ttl(key)
        assert actual_ttl == -1


class TestCacheService:
    """Test CacheService for calendar ID persistence."""

    @pytest.mark.asyncio
    async def test_calendar_id_persistence(self, cache_service: CacheService):
        """Test storing and retrieving calendar IDs (persistent)."""
        vehicle_name = "VSAV-PARIS15-01"
        calendar_id = "calendar123@group.calendar.google.com"

        # Store calendar ID
        success = await cache_service.set_calendar_id(vehicle_name, calendar_id)
        assert success is True

        # Retrieve calendar ID
        cached_id = await cache_service.get_calendar_id(vehicle_name)
        assert cached_id == calendar_id

        # Verify no TTL is set (persistent)
        key = f"{RedisCache.PREFIX_CALENDAR_IDS}:{vehicle_name}"
        ttl = await cache_service.cache.client.ttl(key)
        assert ttl == -1  # No expiration

    @pytest.mark.asyncio
    async def test_get_nonexistent_calendar_id(self, cache_service: CacheService):
        """Test getting a non-existent calendar ID."""
        result = await cache_service.get_calendar_id("NONEXISTENT-VEHICLE")
        assert result is None

