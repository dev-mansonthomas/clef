"""Valkey-based Reservation API endpoints."""
import logging
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.models.reservation import (
    ValkeyReservationCreate,
    ValkeyReservation,
    ValkeyReservationListResponse
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/calendar/{dt}/reservations",
    tags=["reservations-valkey"]
)


@router.get("", response_model=ValkeyReservationListResponse)
async def list_reservations(
    dt: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    vehicule_immat: Optional[str] = Query(None),
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service)
) -> ValkeyReservationListResponse:
    """
    Liste des réservations avec filtres optionnels.

    Args:
        dt: Code de la Délégation Territoriale
        from_date: Date de début (optionnel)
        to_date: Date de fin (optionnel)
        vehicule_immat: Immatriculation du véhicule (optionnel)
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Returns:
        Liste des réservations
    """
    try:
        reservations = await valkey.list_reservations(
            from_date=from_date,
            to_date=to_date,
            vehicule_immat=vehicule_immat
        )

        return ValkeyReservationListResponse(
            count=len(reservations),
            reservations=reservations
        )
    except Exception as e:
        logger.error(f"Error listing reservations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list reservations: {str(e)}"
        )


@router.post("", response_model=ValkeyReservation, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    dt: str,
    reservation: ValkeyReservationCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service)
) -> ValkeyReservation:
    """
    Créer une réservation.

    Args:
        dt: Code de la Délégation Territoriale
        reservation: Données de la réservation
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Returns:
        Réservation créée

    Raises:
        400: Dates invalides ou chevauchement avec une autre réservation
        404: Véhicule ou chauffeur non trouvé
    """
    # Validate date range
    if reservation.fin <= reservation.debut:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de fin doit être après la date de début"
        )

    # Verify vehicle exists
    vehicle = await valkey.get_vehicle(reservation.vehicule_immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule {reservation.vehicule_immat} non trouvé"
        )

    # Verify driver exists
    benevole = await valkey.get_benevole(reservation.chauffeur_nivol)
    if not benevole:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chauffeur avec NIVOL {reservation.chauffeur_nivol} non trouvé"
        )

    try:
        created = await valkey.create_reservation(
            reservation_data=reservation,
            created_by=current_user.email
        )
        return created
    except ValueError as e:
        # Overlap error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating reservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reservation: {str(e)}"
        )


@router.get("/{id}", response_model=ValkeyReservation)
async def get_reservation(
    dt: str,
    id: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service)
) -> ValkeyReservation:
    """
    Détail d'une réservation.

    Args:
        dt: Code de la Délégation Territoriale
        id: ID de la réservation
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Returns:
        Réservation

    Raises:
        404: Réservation non trouvée
    """
    reservation = await valkey.get_reservation(id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Réservation {id} non trouvée"
        )
    return reservation


@router.put("/{id}", response_model=ValkeyReservation)
async def update_reservation(
    dt: str,
    id: str,
    reservation: ValkeyReservationCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service)
) -> ValkeyReservation:
    """
    Modifier une réservation (admin ou créateur).

    Args:
        dt: Code de la Délégation Territoriale
        id: ID de la réservation
        reservation: Données mises à jour
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Returns:
        Réservation mise à jour

    Raises:
        400: Dates invalides ou chevauchement
        403: Pas autorisé à modifier cette réservation
        404: Réservation non trouvée
    """
    # Get existing reservation
    existing = await valkey.get_reservation(id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Réservation {id} non trouvée"
        )

    # Check authorization: only creator or DT manager can modify
    if existing.created_by != current_user.email and current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas autorisé à modifier cette réservation"
        )

    # Validate date range
    if reservation.fin <= reservation.debut:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de fin doit être après la date de début"
        )

    # Verify vehicle exists
    vehicle = await valkey.get_vehicle(reservation.vehicule_immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Véhicule {reservation.vehicule_immat} non trouvé"
        )

    # Verify driver exists
    benevole = await valkey.get_benevole(reservation.chauffeur_nivol)
    if not benevole:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chauffeur avec NIVOL {reservation.chauffeur_nivol} non trouvé"
        )

    try:
        updated = await valkey.update_reservation(
            reservation_id=id,
            reservation_data=reservation
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Réservation {id} non trouvée"
            )
        return updated
    except ValueError as e:
        # Overlap error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating reservation {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update reservation: {str(e)}"
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reservation(
    dt: str,
    id: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service)
) -> None:
    """
    Annuler une réservation (admin ou créateur).

    Args:
        dt: Code de la Délégation Territoriale
        id: ID de la réservation
        current_user: Utilisateur authentifié
        valkey: Service Valkey

    Raises:
        403: Pas autorisé à supprimer cette réservation
        404: Réservation non trouvée
    """
    # Get existing reservation
    existing = await valkey.get_reservation(id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Réservation {id} non trouvée"
        )

    # Check authorization: only creator or DT manager can delete
    if existing.created_by != current_user.email and current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas autorisé à supprimer cette réservation"
        )

    try:
        deleted = await valkey.delete_reservation(id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Réservation {id} non trouvée"
            )
    except Exception as e:
        logger.error(f"Error deleting reservation {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete reservation: {str(e)}"
        )

