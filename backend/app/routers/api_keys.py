"""API Keys management endpoints for DT and UL levels."""
import logging
import os
from typing import Annotated, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.valkey_service import ValkeyService
from app.auth.models import User
from app.auth.dependencies import require_dt_manager
from app.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}",
    tags=["api-keys"]
)


class ApiKeyCreate(BaseModel):
    """Model for creating a new API key."""
    key_type: str = Field(..., description="Type de clé: referentiel, benevoles, responsables")


class ApiKeyResponse(BaseModel):
    """Model for API key response."""
    id: str
    name: str
    key: str
    created_at: str
    created_by: str
    last_used: str | None


async def get_valkey_for_dt(dt: str) -> ValkeyService:
    """Get ValkeyService instance for a specific DT."""
    cache = get_cache()
    
    if not cache._connected:
        await cache.connect()
    
    if not cache.client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available"
        )
    
    return ValkeyService(redis_client=cache.client, dt=dt)


# ========== DT-level API Keys ==========

@router.get("/config/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys_dt(
    dt: str,
    current_user: User = Depends(require_dt_manager)
) -> List[ApiKeyResponse]:
    """
    List all API keys for DT level (masked).
    
    **Access**: DT manager only
    
    Args:
        dt: DT identifier
        
    Returns:
        List of API keys with masked key values
    """
    valkey = await get_valkey_for_dt(dt)
    api_keys = await valkey.list_api_keys_dt(mask_keys=True)
    return [ApiKeyResponse(**key) for key in api_keys]


@router.post("/config/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_dt(
    dt: str,
    api_key_data: ApiKeyCreate,
    current_user: User = Depends(require_dt_manager)
) -> ApiKeyResponse:
    """
    Generate a new API key for DT level.

    **Access**: DT manager only

    Args:
        dt: DT identifier
        api_key_data: API key creation data (key_type: referentiel, benevoles, responsables)

    Returns:
        Created API key with full key value (only shown once)
    """
    valkey = await get_valkey_for_dt(dt)

    try:
        # Auto-generate name based on key type and environment
        env = os.getenv("ENVIRONMENT", "DEV")
        key_name = f"{api_key_data.key_type}-{env}"

        api_key = await valkey.generate_api_key_dt(
            name=key_name,
            created_by=current_user.email
        )
        logger.info(f"Created DT-level API key '{key_name}' for {dt} by {current_user.email}")
        return ApiKeyResponse(**api_key)
    except Exception as e:
        logger.error(f"Error creating DT-level API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.delete("/config/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key_dt(
    dt: str,
    key_id: str,
    current_user: User = Depends(require_dt_manager)
):
    """
    Delete an API key at DT level.
    
    **Access**: DT manager only
    
    Args:
        dt: DT identifier
        key_id: ID of the API key to delete
    """
    valkey = await get_valkey_for_dt(dt)
    
    success = await valkey.delete_api_key_dt(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found"
        )
    
    logger.info(f"Deleted DT-level API key {key_id} for {dt} by {current_user.email}")


# ========== UL-level API Keys ==========

@router.get("/unites-locales/{ul_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys_ul(
    dt: str,
    ul_id: str,
    current_user: User = Depends(require_dt_manager)
) -> List[ApiKeyResponse]:
    """
    List all API keys for UL level (masked).

    **Access**: DT manager only

    Args:
        dt: DT identifier
        ul_id: UL identifier

    Returns:
        List of API keys with masked key values
    """
    valkey = await get_valkey_for_dt(dt)
    api_keys = await valkey.list_api_keys_ul(ul_id, mask_keys=True)
    return [ApiKeyResponse(**key) for key in api_keys]


@router.post("/unites-locales/{ul_id}/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_ul(
    dt: str,
    ul_id: str,
    api_key_data: ApiKeyCreate,
    current_user: User = Depends(require_dt_manager)
) -> ApiKeyResponse:
    """
    Generate a new API key for UL level.

    **Access**: DT manager only

    Args:
        dt: DT identifier
        ul_id: UL identifier
        api_key_data: API key creation data (key_type: referentiel, benevoles, responsables)

    Returns:
        Created API key with full key value (only shown once)
    """
    valkey = await get_valkey_for_dt(dt)

    try:
        # Auto-generate name based on key type and environment
        env = os.getenv("ENVIRONMENT", "DEV")
        key_name = f"{api_key_data.key_type}-{env}"

        api_key = await valkey.generate_api_key_ul(
            ul_id=ul_id,
            name=key_name,
            created_by=current_user.email
        )
        logger.info(f"Created UL-level API key '{key_name}' for {dt} UL {ul_id} by {current_user.email}")
        return ApiKeyResponse(**api_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating UL-level API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.delete("/unites-locales/{ul_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key_ul(
    dt: str,
    ul_id: str,
    key_id: str,
    current_user: User = Depends(require_dt_manager)
):
    """
    Delete an API key at UL level.

    **Access**: DT manager only

    Args:
        dt: DT identifier
        ul_id: UL identifier
        key_id: ID of the API key to delete
    """
    valkey = await get_valkey_for_dt(dt)

    success = await valkey.delete_api_key_ul(ul_id, key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found for UL {ul_id}"
        )

    logger.info(f"Deleted UL-level API key {key_id} for {dt} UL {ul_id} by {current_user.email}")


