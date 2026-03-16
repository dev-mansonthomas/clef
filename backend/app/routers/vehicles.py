"""Vehicle API endpoints."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
import urllib.parse
from app.models.vehicle import Vehicle, VehicleCreate, VehicleUpdate, VehicleListResponse
from app.models.qr_code import QrEncodeRequest, QrEncodeResponse, QrDecodeRequest, QrDecodeResponse
from app.models.valkey_models import VehicleData
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.vehicle_service import VehicleService
from app.services.qr_code_service import QrCodeService
from app.services.calendar_service import CalendarService
from app.services.valkey_service import ValkeyService
from app.services.valkey_dependencies import get_valkey_service
from app.cache import get_cache


router = APIRouter(
    prefix="/api/vehicles",
    tags=["vehicles"]
)


def vehicle_data_to_dict(vehicle_data: VehicleData) -> Dict[str, Any]:
    """
    Convert VehicleData to dict compatible with VehicleService.enrich_vehicle().

    Args:
        vehicle_data: VehicleData from Valkey

    Returns:
        Dictionary with all vehicle fields
    """
    return vehicle_data.model_dump()


async def get_vehicle_by_nom_synthetique(
    valkey_service: ValkeyService,
    nom_synthetique: str
) -> Optional[VehicleData]:
    """
    Find vehicle by nom_synthetique (since Valkey stores by immat).

    Args:
        valkey_service: ValkeyService instance
        nom_synthetique: Synthetic name to search for

    Returns:
        VehicleData if found, None otherwise
    """
    # Get all vehicle IDs
    vehicle_immats = await valkey_service.list_vehicles()

    # Search for matching nom_synthetique
    for immat in vehicle_immats:
        vehicle_data = await valkey_service.get_vehicle(immat)
        if vehicle_data and vehicle_data.nom_synthetique == nom_synthetique:
            return vehicle_data

    return None


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service)
) -> VehicleListResponse:
    """
    Get list of vehicles filtered by user's UL.

    - **Gestionnaire DT**: sees all vehicles
    - **Responsable UL**: sees only vehicles from their UL
    - **Bénévole**: sees only vehicles from their UL

    Returns:
        List of vehicles with computed status fields
    """
    # Get all vehicles from Valkey
    vehicle_immats = await valkey_service.list_vehicles()

    # Fetch all vehicle data
    all_vehicles = []
    for immat in vehicle_immats:
        vehicle_data = await valkey_service.get_vehicle(immat)
        if vehicle_data:
            all_vehicles.append(vehicle_data_to_dict(vehicle_data))

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


@router.post("", response_model=Vehicle, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    vehicle_create: VehicleCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service)
) -> Vehicle:
    """
    Create a new vehicle.

    Args:
        vehicle_create: Vehicle data to create
        current_user: Authenticated user (must be Gestionnaire DT)

    Returns:
        Created vehicle with computed status fields

    Raises:
        403: User doesn't have permission to create vehicles
        409: Vehicle with this immat or nom_synthetique already exists
    """
    # Only Gestionnaire DT can create vehicles
    if current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Gestionnaire DT can create vehicles"
        )

    # Check if vehicle with this immat already exists
    existing_vehicle = await valkey_service.get_vehicle(vehicle_create.immat)
    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle with immat '{vehicle_create.immat}' already exists"
        )

    # Check if vehicle with this nom_synthetique already exists
    existing_by_nom = await valkey_service.get_vehicle_by_nom_synthetique(vehicle_create.nom_synthetique)
    if existing_by_nom:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle with nom_synthetique '{vehicle_create.nom_synthetique}' already exists"
        )

    # Get DT from user
    dt = current_user.dt

    # Create VehicleData for Valkey
    vehicle_data = VehicleData(
        immat=vehicle_create.immat,
        dt=dt,
        dt_ul=vehicle_create.dt_ul,
        indicatif=vehicle_create.indicatif,
        nom_synthetique=vehicle_create.nom_synthetique,
        marque=vehicle_create.marque,
        modele=vehicle_create.modele,
        type=vehicle_create.type,
        date_mec=vehicle_create.date_mec,
        nb_places=vehicle_create.nb_places,
        carte_grise=vehicle_create.carte_grise,
        operationnel_mecanique=vehicle_create.operationnel_mecanique.value,
        raison_indispo=vehicle_create.raison_indispo,
        prochain_controle_technique=vehicle_create.prochain_controle_technique,
        prochain_controle_pollution=vehicle_create.prochain_controle_pollution,
        lieu_stationnement=vehicle_create.lieu_stationnement,
        instructions_recuperation=vehicle_create.instructions_recuperation,
        assurance_2026=vehicle_create.assurance_2026,
        numero_serie_baus=vehicle_create.numero_serie_baus,
        commentaires=vehicle_create.commentaires,
        suivi_mode=vehicle_create.suivi_mode.value if vehicle_create.suivi_mode else None
    )

    # Save to Valkey
    success = await valkey_service.set_vehicle(vehicle_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create vehicle"
        )

    # Return enriched vehicle
    vehicle_dict = vehicle_data_to_dict(vehicle_data)
    return VehicleService.enrich_vehicle(vehicle_dict)


@router.get("/{nom_synthetique:path}", response_model=Vehicle)
async def get_vehicle(
    nom_synthetique: str,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service)
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
    # Decode URL-encoded characters (e.g., %2F for /)
    nom_synthetique = urllib.parse.unquote(nom_synthetique)

    # Try by nom_synthetique first
    vehicle_data = await get_vehicle_by_nom_synthetique(valkey_service, nom_synthetique)

    # If not found, try as immat (fallback)
    if not vehicle_data:
        vehicle_data = await valkey_service.get_vehicle(nom_synthetique)

    if not vehicle_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{nom_synthetique}' not found"
        )

    # Convert to dict for filtering
    vehicle_dict = vehicle_data_to_dict(vehicle_data)

    # Check user access
    filtered = VehicleService.filter_by_user_access([vehicle_dict], current_user)
    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this vehicle"
        )

    # Enrich with status calculations
    return VehicleService.enrich_vehicle(vehicle_dict)


@router.patch("/{nom_synthetique:path}", response_model=Vehicle)
async def update_vehicle(
    nom_synthetique: str,
    update_data: VehicleUpdate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service)
) -> Vehicle:
    """
    Update vehicle metadata (calendar color, comments, etc.).

    Note: This endpoint currently only supports updating metadata fields.
    The main vehicle data (19 columns) is managed in Valkey.

    Args:
        nom_synthetique: Unique synthetic name of the vehicle
        update_data: Fields to update

    Returns:
        Updated vehicle details

    Raises:
        404: Vehicle not found or user doesn't have access
    """
    # Decode URL-encoded characters (e.g., %2F for /)
    nom_synthetique = urllib.parse.unquote(nom_synthetique)

    # Get vehicle from Valkey
    vehicle_data = await get_vehicle_by_nom_synthetique(valkey_service, nom_synthetique)

    if not vehicle_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{nom_synthetique}' not found"
        )

    # Convert to dict for filtering
    vehicle_dict = vehicle_data_to_dict(vehicle_data)

    # Check user access
    filtered = VehicleService.filter_by_user_access([vehicle_dict], current_user)
    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this vehicle"
        )

    # Update fields in Valkey
    updated = False
    if update_data.commentaires is not None:
        vehicle_data.commentaires = update_data.commentaires
        vehicle_dict["commentaires"] = update_data.commentaires
        updated = True

    if update_data.suivi_mode is not None:
        vehicle_data.suivi_mode = update_data.suivi_mode.value
        vehicle_dict["suivi_mode"] = update_data.suivi_mode.value
        updated = True

    # Save back to Valkey if any field was updated
    if updated:
        await valkey_service.set_vehicle(vehicle_data)

    # Note: couleur_calendrier would be stored in a separate metadata structure
    # This is not yet implemented

    # Return enriched vehicle
    return VehicleService.enrich_vehicle(vehicle_dict)


@router.get("/available", response_model=VehicleListResponse)
async def get_available_vehicles(
    start: datetime = Query(..., description="Start datetime for availability check"),
    end: datetime = Query(..., description="End datetime for availability check"),
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service)
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

    # Get all vehicles from Valkey
    vehicle_immats = await valkey_service.list_vehicles()

    # Fetch all vehicle data
    all_vehicles = []
    for immat in vehicle_immats:
        vehicle_data = await valkey_service.get_vehicle(immat)
        if vehicle_data:
            all_vehicles.append(vehicle_data_to_dict(vehicle_data))

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
                if indicatif:  # Only add non-empty indicatifs
                    reserved_indicatifs.add(indicatif)

        # Filter out reserved vehicles
        # Only check reservation status for vehicles with an indicatif
        available_vehicles = [
            v for v in mechanically_available
            if not v.get("indicatif") or v.get("indicatif") not in reserved_indicatifs
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
