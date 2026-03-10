"""Vehicle API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.vehicle import Vehicle, VehicleUpdate, VehicleListResponse
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.vehicle_service import VehicleService
from app.mocks.service_factory import get_sheets_service


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

