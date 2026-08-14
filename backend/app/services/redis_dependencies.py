"""FastAPI dependencies for RedisService."""
from typing import Optional
from fastapi import Depends
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.cache import get_cache
from app.services.redis_service import RedisService


async def get_redis_service(
    current_user: User = Depends(require_authenticated_user)
) -> RedisService:
    """
    Get RedisService instance for the current user's DT.
    
    Args:
        current_user: Authenticated user with DT information
        
    Returns:
        RedisService instance configured for user's DT
        
    Raises:
        RuntimeError: If Redis connection is not available
    """
    cache = get_cache()
    
    # Ensure cache is connected
    if not cache._connected:
        await cache.connect()
    
    if not cache.client:
        raise RuntimeError("Redis client not available")
    
    return RedisService(redis_client=cache.client, dt=current_user.dt)


async def get_redis_service_optional(
    current_user: Optional[User] = None
) -> Optional[RedisService]:
    """
    Get RedisService instance if user is authenticated.
    
    Args:
        current_user: Optional authenticated user
        
    Returns:
        RedisService instance or None if user not authenticated
    """
    if not current_user:
        return None
    
    cache = get_cache()
    
    # Ensure cache is connected
    if not cache._connected:
        await cache.connect()
    
    if not cache.client:
        return None
    
    return RedisService(redis_client=cache.client, dt=current_user.dt)

