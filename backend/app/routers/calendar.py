"""Calendar API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from app.models.calendar import CalendarStatusResponse, CalendarCreateResponse
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.mocks.service_factory import get_calendar_service
from app.cache import RedisCache, get_cache


router = APIRouter(
    prefix="/api/calendar",
    tags=["calendar"]
)


@router.get("/status", response_model=CalendarStatusResponse)
async def get_calendar_status(
    current_user: User = Depends(require_authenticated_user),
    cache: Annotated[RedisCache, Depends(get_cache)] = None
) -> CalendarStatusResponse:
    """
    Check if the calendar exists.
    
    Returns:
        Calendar status with ID if it exists
    """
    # Get calendar service with Redis client
    redis_client = cache.client if cache and cache._connected else None
    calendar_service = get_calendar_service(redis_client=redis_client)
    
    # Check if calendar ID is stored in Redis
    calendar_id = calendar_service.get_calendar_id()
    
    if calendar_id:
        # Calendar exists
        return CalendarStatusResponse(
            exists=True,
            calendar_id=calendar_id,
            calendar_name=calendar_service._get_calendar_name()
        )
    else:
        # Calendar doesn't exist
        return CalendarStatusResponse(
            exists=False,
            calendar_id=None,
            calendar_name=None
        )


@router.post("/create", response_model=CalendarCreateResponse)
async def create_calendar(
    current_user: User = Depends(require_authenticated_user),
    cache: Annotated[RedisCache, Depends(get_cache)] = None
) -> CalendarCreateResponse:
    """
    Create a new calendar for vehicle reservations.
    
    Only accessible to authenticated users (responsables).
    The calendar name is automatically determined based on the environment (DEV/TEST/PROD).
    The calendar ID is stored in Redis with persistence.
    
    Returns:
        Created calendar metadata
        
    Raises:
        400: Calendar already exists
        500: Failed to create calendar
    """
    # Get calendar service with Redis client
    redis_client = cache.client if cache and cache._connected else None
    calendar_service = get_calendar_service(redis_client=redis_client)
    
    # Check if calendar already exists
    existing_calendar_id = calendar_service.get_calendar_id()
    if existing_calendar_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Calendar already exists with ID: {existing_calendar_id}"
        )
    
    try:
        # Create the calendar (name is auto-determined by environment)
        calendar = calendar_service.create_calendar()
        
        return CalendarCreateResponse(
            id=calendar['id'],
            summary=calendar['summary'],
            description=calendar['description'],
            timeZone=calendar['timeZone']
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create calendar: {str(e)}"
        )

