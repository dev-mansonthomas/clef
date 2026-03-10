"""Cache service for preloading and managing référentiels."""
import logging
from typing import Any, Dict, List, Optional

from .redis_cache import RedisCache

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for managing cached référentiels.
    
    Handles:
    - Preloading bénévoles and responsables at startup
    - Caching with appropriate TTLs
    - Calendar ID persistence
    """
    
    def __init__(self, cache: RedisCache):
        """
        Initialize cache service.
        
        Args:
            cache: RedisCache instance
        """
        self.cache = cache
    
    async def preload_benevoles(self, benevoles: List[Dict[str, Any]]) -> bool:
        """
        Preload bénévoles into cache with 1-year TTL.
        
        Args:
            benevoles: List of bénévole dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Cache full list
            key = f"{RedisCache.PREFIX_BENEVOLES}:all"
            success = await self.cache.set(key, benevoles, ttl=RedisCache.TTL_ONE_YEAR)
            
            if not success:
                logger.error("Failed to cache bénévoles list")
                return False
            
            # Cache count for quick access
            count_key = f"{RedisCache.PREFIX_BENEVOLES}:count"
            await self.cache.set(count_key, len(benevoles), ttl=RedisCache.TTL_ONE_YEAR)
            
            # Cache individual bénévoles by email
            for benevole in benevoles:
                email = benevole.get("email")
                if email:
                    benevole_key = f"{RedisCache.PREFIX_BENEVOLES}:email:{email}"
                    await self.cache.set(benevole_key, benevole, ttl=RedisCache.TTL_ONE_YEAR)
            
            logger.info(f"Preloaded {len(benevoles)} bénévoles into cache")
            return True
        except Exception as e:
            logger.error(f"Error preloading bénévoles: {e}")
            return False
    
    async def preload_responsables(self, responsables: List[Dict[str, Any]]) -> bool:
        """
        Preload responsables into cache with 1-year TTL.
        
        Args:
            responsables: List of responsable dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Cache full list
            key = f"{RedisCache.PREFIX_RESPONSABLES}:all"
            success = await self.cache.set(key, responsables, ttl=RedisCache.TTL_ONE_YEAR)
            
            if not success:
                logger.error("Failed to cache responsables list")
                return False
            
            # Cache count for quick access
            count_key = f"{RedisCache.PREFIX_RESPONSABLES}:count"
            await self.cache.set(count_key, len(responsables), ttl=RedisCache.TTL_ONE_YEAR)
            
            # Cache individual responsables by email
            for responsable in responsables:
                email = responsable.get("email")
                if email:
                    responsable_key = f"{RedisCache.PREFIX_RESPONSABLES}:email:{email}"
                    await self.cache.set(responsable_key, responsable, ttl=RedisCache.TTL_ONE_YEAR)
            
            logger.info(f"Preloaded {len(responsables)} responsables into cache")
            return True
        except Exception as e:
            logger.error(f"Error preloading responsables: {e}")
            return False
    
    async def get_benevoles(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all bénévoles from cache.
        
        Returns:
            List of bénévole dictionaries or None if not cached
        """
        key = f"{RedisCache.PREFIX_BENEVOLES}:all"
        return await self.cache.get(key)
    
    async def get_benevole_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific bénévole by email from cache.
        
        Args:
            email: Bénévole email address
            
        Returns:
            Bénévole dictionary or None if not found
        """
        key = f"{RedisCache.PREFIX_BENEVOLES}:email:{email}"
        return await self.cache.get(key)
    
    async def get_responsables(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all responsables from cache.
        
        Returns:
            List of responsable dictionaries or None if not cached
        """
        key = f"{RedisCache.PREFIX_RESPONSABLES}:all"
        return await self.cache.get(key)
    
    async def get_responsable_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific responsable by email from cache.
        
        Args:
            email: Responsable email address
            
        Returns:
            Responsable dictionary or None if not found
        """
        key = f"{RedisCache.PREFIX_RESPONSABLES}:email:{email}"
        return await self.cache.get(key)
    
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

