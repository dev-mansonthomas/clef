"""Vehicle API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from app.models.vehicle import Vehicle, VehicleUpdate, VehicleListResponse
from app.models.qr_code import QrEncodeRequest, QrEncodeResponse, QrDecodeRequest, QrDecodeResponse
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.vehicle_service import VehicleService
from app.services.qr_code_service import QrCodeService
from app.services.calendar_service import CalendarService
from app.mocks.service_factory import get_sheets_service
from app.cache import get_cache


router = APIRouter(
    prefix="/api/vehicles",
    tags=["vehicles"]
)


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    current_user: User = Depends(require_authenticated_user)
) -> VehicleListResponse:
    """
    Get list of vehicles filtered by user's UL.
    
    - **Gestionnaire DT**: sees all vehicles
    - **Responsable UL**: sees only vehicles from their UL
    - **Bénévole**: sees only vehicles from their UL
    
    Returns:
        List of vehicles with computed status fields
    """
    # Get all vehicles from sheets
    sheets_service = get_sheets_service()
    all_vehicles = sheets_service.get_vehicules()
    
    # Filter by user access
    filtered_vehicles = VehicleService.filter_by_user_access(
        all_vehicles,
        current_user
    )
    
    # Enrich with status calculations
    enriched_vehicles = [
        VehicleService.enrich_vehicle(v)
        for v in filtered_vehicles
    ]
    
    return VehicleListResponse(
        count=len(enriched_vehicles),
        vehicles=enriched_vehicles
    )


@router.get("/{nom_synthetique}", response_model=Vehicle)
async def get_vehicle(
    nom_synthetique: str,
    current_user: User = Depends(require_authenticated_user)
) -> Vehicle:
    """
    Get a specific vehicle by its synthetic name.
    
    Args:
        nom_synthetique: Unique synthetic name of the vehicle
        
    Returns:
        Vehicle details with computed status fields
        
    Raises:
        404: Vehicle not found or user doesn't have access
    """
    # Get vehicle from sheets
    sheets_service = get_sheets_service()
    vehicle_data = sheets_service.get_vehicule_by_nom_synthetique(nom_synthetique)
    
    if not vehicle_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{nom_synthetique}' not found"
        )
    
    # Check user access
    filtered = VehicleService.filter_by_user_access([vehicle_data], current_user)
    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this vehicle"
        )
    
    # Enrich with status calculations
    return VehicleService.enrich_vehicle(vehicle_data)


@router.patch("/{nom_synthetique}", response_model=Vehicle)
async def update_vehicle(
    nom_synthetique: str,
    update_data: VehicleUpdate,
    current_user: User = Depends(require_authenticated_user)
) -> Vehicle:
    """
    Update vehicle metadata (calendar color, comments, etc.).
    
    Note: This endpoint currently only supports updating metadata fields.
    The main vehicle data (19 columns) is managed in Google Sheets.
    
    Args:
        nom_synthetique: Unique synthetic name of the vehicle
        update_data: Fields to update
        
    Returns:
        Updated vehicle details
        
    Raises:
        404: Vehicle not found or user doesn't have access
        501: Not fully implemented (metadata storage pending)
    """
    # Get vehicle from sheets
    sheets_service = get_sheets_service()
    vehicle_data = sheets_service.get_vehicule_by_nom_synthetique(nom_synthetique)
    
    if not vehicle_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{nom_synthetique}' not found"
        )
    
    # Check user access
    filtered = VehicleService.filter_by_user_access([vehicle_data], current_user)
    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this vehicle"
        )
    
    # TODO: Store metadata updates in "Metadata CLEF" sheet tab
    # For now, we just update the in-memory data and return it
    # This will be implemented when the real Sheets service is available
    
    if update_data.commentaires is not None:
        vehicle_data["commentaires"] = update_data.commentaires
    
    # Note: couleur_calendrier would be stored in the "Metadata CLEF" tab
    # which is not yet implemented in the mock service

    # Return enriched vehicle
    return VehicleService.enrich_vehicle(vehicle_data)


@router.get("/available", response_model=VehicleListResponse)
async def get_available_vehicles(
    start: datetime = Query(..., description="Start datetime for availability check"),
    end: datetime = Query(..., description="End datetime for availability check"),
    current_user: User = Depends(require_authenticated_user)
) -> VehicleListResponse:
    """
    Get list of available vehicles for a given time period.

    A vehicle is available if:
    - It is mechanically operational (operationnel_mecanique = "Dispo")
    - It has no reservations overlapping with the requested time period
    - User has access to it based on their UL

    Args:
        start: Start datetime for the reservation
        end: End datetime for the reservation
        current_user: Authenticated user

    Returns:
        List of available vehicles with computed status fields

    Raises:
        400: Invalid date range
    """
    # Validate date range
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date"
        )

    # Get all vehicles
    sheets_service = get_sheets_service()
    all_vehicles = sheets_service.get_vehicules()

    # Filter by user access
    filtered_vehicles = VehicleService.filter_by_user_access(
        all_vehicles,
        current_user
    )

    # Filter by mechanical availability
    mechanically_available = [
        v for v in filtered_vehicles
        if v.get("operationnel_mecanique") == "Dispo"
    ]

    # Get calendar service to check reservations
    cache = get_cache()
    redis_client = cache.client if cache._connected else None
    calendar_service = CalendarService(redis_client=redis_client)

    try:
        # Get all events in the requested time period
        events = calendar_service.get_events(
            time_min=start,
            time_max=end
        )

        # Extract indicatifs from reserved events
        # Event summary format: "{indicatif} - {chauffeur} - {mission}"
        reserved_indicatifs = set()
        for event in events:
            summary = event.get('summary', '')
            if ' - ' in summary:
                indicatif = summary.split(' - ')[0]
                reserved_indicatifs.add(indicatif)

        # Filter out reserved vehicles
        available_vehicles = [
            v for v in mechanically_available
            if v.get("indicatif") not in reserved_indicatifs
        ]

    except ValueError:
        # Calendar not configured yet - return all mechanically available vehicles
        available_vehicles = mechanically_available
    except Exception as e:
        # Log error but don't fail - return mechanically available vehicles
        import logging
        logging.error(f"Error checking calendar availability: {e}")
        available_vehicles = mechanically_available

    # Enrich with status calculations
    enriched_vehicles = [
        VehicleService.enrich_vehicle(v)
        for v in available_vehicles
    ]

    return VehicleListResponse(
        count=len(enriched_vehicles),
        vehicles=enriched_vehicles
    )


@router.post("/encode", response_model=QrEncodeResponse)
async def encode_vehicle_qr(
    request: QrEncodeRequest,
    current_user: User = Depends(require_authenticated_user)
) -> QrEncodeResponse:
    """
    Encode a vehicle nom_synthetique for QR code generation.

    Uses HMAC-SHA256 with SALT to create a secure, tamper-proof encoded ID.
    The encoded ID can be decoded back to the nom_synthetique.

    Args:
        request: Contains nom_synthetique to encode
        current_user: Authenticated user (required)

    Returns:
        Encoded ID and full QR code URL

    Raises:
        500: If QR_CODE_SALT is not configured
    """
    try:
        qr_service = QrCodeService()
        encoded_id = qr_service.encode(request.nom_synthetique)
        qr_url = qr_service.get_qr_url(encoded_id)

        return QrEncodeResponse(
            encoded_id=encoded_id,
            qr_url=qr_url
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/decode", response_model=QrDecodeResponse)
async def decode_vehicle_qr(
    request: QrDecodeRequest
) -> QrDecodeResponse:
    """
    Decode a QR code encoded ID back to nom_synthetique.

    Validates the HMAC signature to ensure the ID hasn't been tampered with.
    This endpoint does NOT require authentication as it's used by the public
    form application when scanning QR codes.

    Args:
        request: Contains encoded_id to decode

    Returns:
        Decoded nom_synthetique

    Raises:
        400: If encoded_id is invalid or signature verification fails
        500: If QR_CODE_SALT is not configured
    """
    try:
        qr_service = QrCodeService()
        nom_synthetique = qr_service.decode(request.encoded_id)

        if nom_synthetique is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or tampered QR code"
            )

        return QrDecodeResponse(nom_synthetique=nom_synthetique)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
