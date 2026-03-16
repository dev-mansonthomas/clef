"""Cache service for calendar ID persistence.

DEPRECATED: Bénévoles and responsables are now stored in Valkey with DT prefixes.
Use ValkeyService for benevoles/responsables operations.
This service only maintains calendar ID persistence for backward compatibility.
"""
import logging
from typing import Optional

from .redis_cache import RedisCache

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for managing calendar ID persistence.

    DEPRECATED: Bénévoles and responsables methods have been removed.
    Use ValkeyService for benevoles/responsables operations.

    Handles:
    - Calendar ID persistence (still needed for Google Calendar integration)
    """

    def __init__(self, cache: RedisCache):
        """
        Initialize cache service.

        Args:
            cache: RedisCache instance
        """
        self.cache = cache
    
    async def set_calendar_id(self, vehicle_name: str, calendar_id: str) -> bool:
        """
        Store calendar ID for a vehicle (persistent, no TTL).
        
        Args:
            vehicle_name: Vehicle synthetic name
            calendar_id: Google Calendar ID
            
        Returns:
            True if successful, False otherwise
        """
        key = f"{RedisCache.PREFIX_CALENDAR_IDS}:{vehicle_name}"
        return await self.cache.set(key, calendar_id, ttl=RedisCache.TTL_PERSISTENT)
    
    async def get_calendar_id(self, vehicle_name: str) -> Optional[str]:
        """
        Get calendar ID for a vehicle.
        
        Args:
            vehicle_name: Vehicle synthetic name
            
        Returns:
            Calendar ID or None if not found
        """
        key = f"{RedisCache.PREFIX_CALENDAR_IDS}:{vehicle_name}"
        return await self.cache.get(key)

