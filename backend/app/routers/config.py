"""
Configuration API endpoints.
DT manager only access.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, Dict, Any

from app.models.config import ConfigUpdate, ConfigResponse
from app.services.config_service import ConfigService
from app.services.valkey_service import ValkeyService
from app.services.valkey_dependencies import get_valkey_service
from app.services.calendar_service import calendar_service
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


@router.post("/calendar")
async def create_calendar(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """
    Create a Google Calendar for vehicle reservations.

    **Access**: DT manager only

    Returns:
        Calendar ID and URL

    Raises:
        HTTPException: If calendar already exists or creation fails
    """
    dt_id = current_user.dt or "DT75"

    # Check if calendar already exists
    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key)

    if config and config.get("calendar_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un calendrier existe déjà. Supprimez-le d'abord."
        )

    try:
        # Create the calendar
        calendar = await calendar_service.create_calendar(
            dt_id=dt_id,
            name=f"Réservations Véhicules {dt_id}",
            description="Calendrier des réservations de véhicules géré par CLEF",
        )

        # Store calendar ID in config
        if not config:
            config = {}
        config["calendar_id"] = calendar["id"]
        config["calendar_url"] = f"https://calendar.google.com/calendar/embed?src={calendar['id']}"

        await valkey_service.redis.json().set(config_key, "$", config)

        return {
            "calendar_id": calendar["id"],
            "calendar_url": config["calendar_url"],
            "message": "Calendrier créé avec succès",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create calendar: {str(e)}"
        )


@router.get("/calendar")
async def get_calendar_config(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """
    Get calendar configuration.

    **Access**: DT manager only

    Returns:
        Calendar configuration status
    """
    dt_id = current_user.dt or "DT75"

    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key)

    if not config or not config.get("calendar_id"):
        return {"configured": False}

    return {
        "configured": True,
        "calendar_id": config["calendar_id"],
        "calendar_url": config.get("calendar_url"),
    }


@router.delete("/calendar")
async def delete_calendar_config(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, str]:
    """
    Remove calendar configuration (doesn't delete the Google Calendar).

    **Access**: DT manager only

    Returns:
        Success message
    """
    dt_id = current_user.dt or "DT75"

    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key)

    if config:
        config.pop("calendar_id", None)
        config.pop("calendar_url", None)
        await valkey_service.redis.json().set(config_key, "$", config)

    return {"message": "Configuration du calendrier supprimée"}
