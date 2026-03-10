"""
Configuration API endpoints.
DT manager only access.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from app.models.config import ConfigUpdate, ConfigResponse
from app.services.config_service import ConfigService
from app.cache import RedisCache, get_cache


router = APIRouter(
    prefix="/api/config",
    tags=["configuration"]
)


def get_config_service(
    cache: Annotated[RedisCache, Depends(get_cache)]
) -> ConfigService:
    """Dependency to get ConfigService instance."""
    return ConfigService(cache)


# TODO: Add is_dt_manager dependency when auth module (2.1) is implemented
# For now, endpoints are unprotected (development only)


@router.get("", response_model=ConfigResponse)
async def get_config(
    config_service: Annotated[ConfigService, Depends(get_config_service)]
):
    """
    Get current configuration.

    **Access**: DT manager only (TODO: add auth guard)

    Returns:
        Current configuration including URLs and email settings
    """
    config = await config_service.get_config()
    return ConfigResponse(**config)


@router.patch("", response_model=ConfigResponse)
async def update_config(
    updates: ConfigUpdate,
    config_service: Annotated[ConfigService, Depends(get_config_service)]
):
    """
    Update configuration.

    **Access**: DT manager only (TODO: add auth guard)

    Args:
        updates: Configuration updates (only non-null fields will be updated)

    Returns:
        Updated configuration

    Raises:
        HTTPException: If validation fails
    """
    # Convert Pydantic model to dict, excluding None values
    updates_dict = updates.model_dump(exclude_none=True)

    try:
        updated_config = await config_service.update_config(updates_dict)
        return ConfigResponse(**updated_config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update configuration: {str(e)}"
        )

