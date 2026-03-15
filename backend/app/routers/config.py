"""
Configuration API endpoints.
DT manager only access.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from app.models.config import ConfigUpdate, ConfigResponse
from app.services.config_service import ConfigService
from app.services.valkey_service import ValkeyService
from app.services.valkey_dependencies import get_valkey_service
from app.auth.models import User
from app.auth.dependencies import is_dt_manager


router = APIRouter(
    prefix="/api/config",
    tags=["configuration"]
)


def get_config_service(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)]
) -> ConfigService:
    """Dependency to get ConfigService instance."""
    return ConfigService(valkey_service)


@router.get("", response_model=ConfigResponse)
async def get_config(
    config_service: Annotated[ConfigService, Depends(get_config_service)],
    current_user: User = Depends(is_dt_manager)
):
    """
    Get current configuration.

    **Access**: DT manager only

    Returns:
        Current configuration including URLs and email settings
    """
    config = await config_service.get_config()
    return ConfigResponse(**config)


@router.patch("", response_model=ConfigResponse)
async def update_config(
    updates: ConfigUpdate,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
    current_user: User = Depends(is_dt_manager)
):
    """
    Update configuration.

    **Access**: DT manager only

    Args:
        updates: Configuration updates (only non-null fields will be updated)

    Returns:
        Updated configuration

    Raises:
        HTTPException: If validation fails or user is not DT manager
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

