"""Sync API endpoints for Google Apps Script integration."""
import os
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Header, HTTPException, status, Depends
from pydantic import BaseModel, Field

from app.services.valkey_service import ValkeyService
from app.models.valkey_models import VehicleData, ResponsableData, BenevoleData
from app.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/sync",
    tags=["sync"]
)


class BenevoleSync(BaseModel):
    """Bénévole data for sync from Apps Script."""
    nivol: str = Field(..., description="NIVOL identifier")
    nom: str = Field(..., description="Last name")
    prenom: str = Field(..., description="First name")
    email: str | None = Field(None, description="Email address")
    ul: str | None = Field(None, description="UL identifier")
    role: str | None = Field(None, description="Role")


class SyncResponse(BaseModel):
    """Response for sync operations."""
    success: bool
    count: int
    message: str


async def verify_api_key(x_api_key: str = Header(...)) -> None:
    """
    Verify API key from header.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Raises:
        HTTPException: If API key is invalid
    """
    expected = os.getenv("SYNC_API_KEY")
    if not expected:
        logger.error("SYNC_API_KEY not configured in environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key authentication not configured"
        )
    
    if x_api_key != expected:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )


async def get_valkey_for_dt(dt: str) -> ValkeyService:
    """
    Get ValkeyService instance for a specific DT.
    
    Args:
        dt: DT identifier (e.g., "DT75")
        
    Returns:
        ValkeyService instance
        
    Raises:
        HTTPException: If Redis is not available
    """
    cache = get_cache()
    
    if not cache._connected:
        await cache.connect()
    
    if not cache.client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available"
        )
    
    return ValkeyService(redis_client=cache.client, dt=dt)


@router.get("/{dt}/vehicules")
async def get_vehicules_for_sync(
    dt: str,
    _: None = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """
    Get all vehicles for a DT (for Apps Script sync).

    Args:
        dt: DT identifier (e.g., "DT75")

    Returns:
        List of vehicle dictionaries
    """
    valkey = await get_valkey_for_dt(dt)

    # Get all vehicle IDs
    vehicle_ids = await valkey.list_vehicles()

    # Fetch all vehicles
    vehicles = []
    for immat in vehicle_ids:
        vehicle = await valkey.get_vehicle(immat)
        if vehicle:
            vehicles.append(vehicle.model_dump())

    logger.info(f"Sync API: Retrieved {len(vehicles)} vehicles for {dt}")
    return vehicles


@router.get("/{dt}/vehicules/{ul_id}")
async def get_vehicules_for_ul(
    dt: str,
    ul_id: str,
    x_api_key: str = Header(...)
) -> List[Dict[str, Any]]:
    """
    Get vehicles for a specific UL (for Apps Script sync at UL level).

    Args:
        dt: DT identifier (e.g., "DT75")
        ul_id: UL identifier (e.g., "81")
        x_api_key: API key from X-API-Key header

    Returns:
        List of vehicle dictionaries filtered by UL
    """
    valkey = await get_valkey_for_dt(dt)

    # Validate API key for this UL
    if not await valkey.validate_api_key(x_api_key, ul_id=ul_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key for this UL"
        )

    # Get UL name to match against vehicle dt_ul field
    ul_data_raw = await valkey.redis.get(valkey._key("unite_locale", ul_id))
    if not ul_data_raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UL {ul_id} not found"
        )

    import json
    ul_data = json.loads(ul_data_raw)
    ul_name = ul_data.get("nom")

    # Get all vehicle IDs
    vehicle_ids = await valkey.list_vehicles()

    # Fetch and filter vehicles by UL name
    vehicles = []
    for immat in vehicle_ids:
        vehicle = await valkey.get_vehicle(immat)
        # Match by UL name (dt_ul field contains the full UL name)
        if vehicle and vehicle.dt_ul == ul_name:
            vehicles.append(vehicle.model_dump())

    logger.info(f"Sync API: Retrieved {len(vehicles)} vehicles for {dt} UL {ul_id} ({ul_name})")
    return vehicles


@router.get("/{dt}/responsables")
async def get_responsables_for_sync(
    dt: str,
    _: None = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """
    Get all responsables for a DT (for Apps Script sync).
    
    Args:
        dt: DT identifier (e.g., "DT75")
        
    Returns:
        List of responsable dictionaries
    """
    valkey = await get_valkey_for_dt(dt)
    
    # Get all responsable emails
    responsable_emails = await valkey.list_responsables()
    
    # Fetch all responsables
    responsables = []
    for email in responsable_emails:
        responsable = await valkey.get_responsable(email)
        if responsable:
            responsables.append(responsable.model_dump())
    
    logger.info(f"Sync API: Retrieved {len(responsables)} responsables for {dt}")
    return responsables


@router.post("/{dt}/benevoles", response_model=SyncResponse)
async def sync_benevoles(
    dt: str,
    benevoles: List[BenevoleSync],
    _: None = Depends(verify_api_key)
) -> SyncResponse:
    """
    Sync bénévoles from Apps Script to Valkey.
    
    Args:
        dt: DT identifier (e.g., "DT75")
        benevoles: List of bénévole data from spreadsheet
        
    Returns:
        Sync response with count of processed records
    """
    valkey = await get_valkey_for_dt(dt)
    
    processed = 0
    for benevole_data in benevoles:
        try:
            # Create BenevoleData instance
            benevole = BenevoleData(
                nivol=benevole_data.nivol,
                dt=dt,
                nom=benevole_data.nom,
                prenom=benevole_data.prenom,
                email=benevole_data.email,
                ul=benevole_data.ul,
                role=benevole_data.role
            )
            
            # Store in Valkey
            success = await valkey.set_benevole(benevole)
            if success:
                processed += 1
        except Exception as e:
            logger.error(f"Error syncing benevole {benevole_data.nivol}: {e}")
            continue
    
    logger.info(f"Sync API: Processed {processed}/{len(benevoles)} bénévoles for {dt}")
    
    return SyncResponse(
        success=True,
        count=processed,
        message=f"Successfully synced {processed} bénévoles"
    )

