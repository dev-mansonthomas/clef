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
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService


router = APIRouter(
    prefix="/api/carnet-de-bord",
    tags=["carnet-de-bord"]
)


@router.post("/prise", response_model=CarnetBordResponse, status_code=status.HTTP_201_CREATED)
async def enregistrer_prise(
    prise: PriseVehicule,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service)
) -> CarnetBordResponse:
    """
    Enregistrer une prise de véhicule.

    Args:
        prise: Données du formulaire de prise
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Returns:
        Confirmation de l'enregistrement

    Raises:
        404: Véhicule non trouvé
        400: Véhicule déjà pris
        500: Erreur lors de l'enregistrement
    """
    # Get vehicle data from Valkey
    vehicule = await valkey.get_vehicle_by_nom_synthetique(prise.vehicule_id)

    if not vehicule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule '{prise.vehicule_id}' non trouvé"
        )

    # Check if vehicle is already taken
    derniere_prise = await valkey.get_derniere_prise(vehicule.immat)
    if derniere_prise:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Véhicule déjà pris par {derniere_prise.get('benevole_prenom')} {derniere_prise.get('benevole_nom')}"
        )

    try:
        # Register prise in Valkey
        timestamp = await valkey.enregistrer_prise(
            immat=vehicule.immat,
            benevole_nom=prise.benevole_nom,
            benevole_prenom=prise.benevole_prenom,
            benevole_email=prise.benevole_email,
            kilometrage=prise.kilometrage,
            niveau_carburant=prise.niveau_carburant,
            etat_general=prise.etat_general,
            observations=prise.observations or ""
        )

        return CarnetBordResponse(
            success=True,
            message="Prise enregistrée avec succès",
            spreadsheet_id=None,  # No longer using Google Sheets
            perimetre=current_user.dt
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
    valkey: ValkeyService = Depends(get_valkey_service)
) -> CarnetBordResponse:
    """
    Enregistrer un retour de véhicule.

    Args:
        retour: Données du formulaire de retour
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Returns:
        Confirmation de l'enregistrement

    Raises:
        404: Véhicule non trouvé
        400: Véhicule non pris
        500: Erreur lors de l'enregistrement
    """
    # Get vehicle data from Valkey
    vehicule = await valkey.get_vehicle_by_nom_synthetique(retour.vehicule_id)

    if not vehicule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule '{retour.vehicule_id}' non trouvé"
        )

    # Check if vehicle is currently taken
    derniere_prise = await valkey.get_derniere_prise(vehicule.immat)
    if not derniere_prise:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Véhicule non pris, impossible d'enregistrer un retour"
        )

    try:
        # Register retour in Valkey
        timestamp = await valkey.enregistrer_retour(
            immat=vehicule.immat,
            benevole_nom=retour.benevole_nom,
            benevole_prenom=retour.benevole_prenom,
            benevole_email=retour.benevole_email,
            kilometrage=retour.kilometrage,
            niveau_carburant=retour.niveau_carburant,
            etat_general=retour.etat_general,
            problemes_signales=retour.problemes_signales or "",
            observations=retour.observations or ""
        )

        # Calculate km parcourus
        km_depart = derniere_prise.get('kilometrage', 0)
        km_parcourus = retour.kilometrage - km_depart

        return CarnetBordResponse(
            success=True,
            message=f"Retour enregistré avec succès. {km_parcourus} km parcourus.",
            spreadsheet_id=None,  # No longer using Google Sheets
            perimetre=current_user.dt
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
    valkey: ValkeyService = Depends(get_valkey_service)
) -> Optional[DernierePrise]:
    """
    Récupérer la dernière prise d'un véhicule pour comparaison.

    Args:
        vehicule_id: Nom synthétique du véhicule
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Returns:
        Dernière prise ou None si aucune prise trouvée

    Raises:
        404: Véhicule non trouvé
    """
    # Get vehicle from Valkey
    vehicule = await valkey.get_vehicle_by_nom_synthetique(vehicule_id)

    if not vehicule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule '{vehicule_id}' non trouvé"
        )

    # Get last prise from Valkey
    derniere_prise = await valkey.get_derniere_prise(vehicule.immat)

    if derniere_prise:
        return DernierePrise(
            vehicule_id=vehicule_id,
            benevole_nom=derniere_prise.get('benevole_nom', ''),
            benevole_prenom=derniere_prise.get('benevole_prenom', ''),
            kilometrage=derniere_prise.get('kilometrage', 0),
            niveau_carburant=derniere_prise.get('niveau_carburant', ''),
            etat_general=derniere_prise.get('etat_general', ''),
            observations=derniere_prise.get('observations', ''),
            timestamp=derniere_prise.get('timestamp', '')
        )

    return None

