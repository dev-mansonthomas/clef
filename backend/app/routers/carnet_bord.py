"""Carnet de Bord (Vehicle Logbook) API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.carnet_bord import (
    PriseVehicule,
    RetourVehicule,
    CarnetBordResponse,
    DernierePrise
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.carnet_bord_service import CarnetBordService
from app.mocks.service_factory import get_sheets_service
from app.cache import get_cache


router = APIRouter(
    prefix="/api/carnet-de-bord",
    tags=["carnet-de-bord"]
)


async def get_carnet_bord_service() -> CarnetBordService:
    """Get CarnetBordService instance with dependencies."""
    sheets_service = get_sheets_service()
    cache = get_cache()
    redis_cache = cache if cache._connected else None
    return CarnetBordService(sheets_service=sheets_service, cache=redis_cache)


@router.post("/prise", response_model=CarnetBordResponse, status_code=status.HTTP_201_CREATED)
async def enregistrer_prise(
    prise: PriseVehicule,
    current_user: User = Depends(require_authenticated_user),
    carnet_service: CarnetBordService = Depends(get_carnet_bord_service)
) -> CarnetBordResponse:
    """
    Enregistrer une prise de véhicule.
    
    Args:
        prise: Données du formulaire de prise
        current_user: Utilisateur authentifié
        carnet_service: Service carnet de bord
        
    Returns:
        Confirmation de l'enregistrement
        
    Raises:
        404: Véhicule non trouvé
        500: Erreur lors de l'enregistrement
    """
    # Get vehicle data to determine perimeter
    sheets_service = get_sheets_service()
    vehicule_data = sheets_service.get_vehicule_by_nom_synthetique(prise.vehicule_id)
    
    if not vehicule_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule '{prise.vehicule_id}' non trouvé"
        )
    
    try:
        # Convert prise to dict
        prise_dict = prise.model_dump()
        
        # Append to appropriate sheet
        result = await carnet_service.append_prise(vehicule_data, prise_dict)
        
        return CarnetBordResponse(
            success=True,
            message="Prise enregistrée avec succès",
            spreadsheet_id=result['spreadsheet_id'],
            perimetre=result['perimetre']
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'enregistrement de la prise: {str(e)}"
        )


@router.post("/retour", response_model=CarnetBordResponse, status_code=status.HTTP_201_CREATED)
async def enregistrer_retour(
    retour: RetourVehicule,
    current_user: User = Depends(require_authenticated_user),
    carnet_service: CarnetBordService = Depends(get_carnet_bord_service)
) -> CarnetBordResponse:
    """
    Enregistrer un retour de véhicule.
    
    Args:
        retour: Données du formulaire de retour
        current_user: Utilisateur authentifié
        carnet_service: Service carnet de bord
        
    Returns:
        Confirmation de l'enregistrement
        
    Raises:
        404: Véhicule non trouvé
        500: Erreur lors de l'enregistrement
    """
    # Get vehicle data to determine perimeter
    sheets_service = get_sheets_service()
    vehicule_data = sheets_service.get_vehicule_by_nom_synthetique(retour.vehicule_id)
    
    if not vehicule_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule '{retour.vehicule_id}' non trouvé"
        )
    
    try:
        # Convert retour to dict
        retour_dict = retour.model_dump()
        
        # Append to appropriate sheet
        result = await carnet_service.append_retour(vehicule_data, retour_dict)
        
        return CarnetBordResponse(
            success=True,
            message="Retour enregistré avec succès",
            spreadsheet_id=result['spreadsheet_id'],
            perimetre=result['perimetre']
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'enregistrement du retour: {str(e)}"
        )


@router.get("/{vehicule_id}/derniere-prise", response_model=Optional[DernierePrise])
async def get_derniere_prise(
    vehicule_id: str,
    current_user: User = Depends(require_authenticated_user),
    carnet_service: CarnetBordService = Depends(get_carnet_bord_service)
) -> Optional[DernierePrise]:
    """
    Récupérer la dernière prise d'un véhicule pour comparaison.
    
    Args:
        vehicule_id: Nom synthétique du véhicule
        current_user: Utilisateur authentifié
        carnet_service: Service carnet de bord
        
    Returns:
        Dernière prise ou None si aucune prise trouvée
        
    Raises:
        404: Véhicule non trouvé
    """
    # Verify vehicle exists
    sheets_service = get_sheets_service()
    vehicule_data = sheets_service.get_vehicule_by_nom_synthetique(vehicule_id)
    
    if not vehicule_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule '{vehicule_id}' non trouvé"
        )
    
    # Get last prise
    derniere_prise = await carnet_service.get_derniere_prise(vehicule_id)
    
    if derniere_prise:
        return DernierePrise(**derniere_prise)
    
    return None

