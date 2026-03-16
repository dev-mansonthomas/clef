"""Reservation API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from app.models.reservation import ReservationCreate, ReservationResponse
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.calendar_service import CalendarService
from app.mocks.service_factory import get_sheets_service
from app.services.vehicle_service import VehicleService
from app.cache import get_cache
import redis.asyncio as redis


router = APIRouter(
    prefix="/api/reservations",
    tags=["reservations"]
)


async def get_calendar_service() -> CalendarService:
    """Get CalendarService instance with Redis client."""
    cache = get_cache()
    redis_client = cache.client if cache._connected else None
    return CalendarService(redis_client=redis_client)


@router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    reservation: ReservationCreate,
    current_user: User = Depends(require_authenticated_user),
    calendar_service: CalendarService = Depends(get_calendar_service)
) -> ReservationResponse:
    """
    Create a new reservation event in the calendar.
    
    Args:
        reservation: Reservation details
        current_user: Authenticated user
        calendar_service: Calendar service instance
        
    Returns:
        Created reservation details
        
    Raises:
        400: Invalid date range or vehicle not available
        404: Vehicle not found
        500: Calendar service error
    """
    # Validate date range
    if reservation.end <= reservation.start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date"
        )
    
    # Get vehicle to verify it exists and get color
    sheets_service = get_sheets_service()
    vehicle_data = sheets_service.get_vehicule_by_indicatif(reservation.indicatif)
    
    if not vehicle_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with indicatif '{reservation.indicatif}' not found"
        )
    
    # Check user has access to this vehicle
    filtered = VehicleService.filter_by_user_access([vehicle_data], current_user)
    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this vehicle"
        )
    
    # Get vehicle color from metadata (if available)
    # TODO: Implement metadata retrieval from "Metadata CLEF" sheet tab
    color_id = None
    
    try:
        # Create reservation in calendar
        event = calendar_service.create_reservation(
            indicatif=reservation.indicatif,
            chauffeur=reservation.chauffeur,
            mission=reservation.mission,
            start=reservation.start,
            end=reservation.end,
            description=reservation.description,
            color_id=color_id
        )
        
        # Parse response
        return ReservationResponse(
            id=event['id'],
            indicatif=reservation.indicatif,
            chauffeur=reservation.chauffeur,
            mission=reservation.mission,
            start=reservation.start,
            end=reservation.end,
            description=reservation.description,
            color_id=color_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reservation: {str(e)}"
        )

