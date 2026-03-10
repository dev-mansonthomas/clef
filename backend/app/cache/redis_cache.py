"""Redis cache implementation with async support."""
import json
import os
from typing import Any, Optional
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Async Redis cache with TTL support.
    
    Provides generic cache interface for:
    - Référentiels (bénévoles, responsables) with 1-year TTL
    - Calendar IDs (persistent, no TTL)
    """
    
    # TTL constants
    TTL_ONE_YEAR = 31536000  # 1 year in seconds
    TTL_PERSISTENT = None  # No expiration
    
    # Key prefixes
    PREFIX_BENEVOLES = "clef:benevoles"
    PREFIX_RESPONSABLES = "clef:responsables"
    PREFIX_CALENDAR_IDS = "clef:calendar_ids"
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL (default: from REDIS_URL env var)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client: Optional[Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish async connection to Redis."""
        if self._connected:
            return
        
        try:
            self.client = Redis.from_url(
                self.redis_url,
                decode_responses=True,
                encoding="utf-8"
            )
            # Test connection
            await self.client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            self._connected = False
            logger.info("Disconnected from Redis")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        if not self._connected:
            await self.connect()
        
        try:
            value = await self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache (will be serialized to JSON)
            ttl: Time-to-live in seconds (None = no expiration)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            await self.connect()
        
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            if ttl is not None:
                await self.client.setex(key, ttl, serialized)
            else:
                await self.client.set(key, serialized)
            return True
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False otherwise
        """
        if not self._connected:
            await self.connect()
        
        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        if not self._connected:
            await self.connect()
        
        try:
            result = await self.client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error checking key {key}: {e}")
            return False


# Global cache instance
_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """
    Get global cache instance.
    
    Returns:
        RedisCache instance
    """
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache

