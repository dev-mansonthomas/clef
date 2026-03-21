"""Dossiers Réparation API endpoints."""
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.repair_models import (
    DossierReparation,
    DossierReparationCreate,
    DossierReparationUpdate,
    DossierReparationListResponse,
    StatutDossier,
    ActionHistorique,
    HistoriqueEntry,
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}/vehicles/{immat}/dossiers-reparation",
    tags=["dossiers-reparation"],
)


@router.post("", response_model=DossierReparation, status_code=status.HTTP_201_CREATED)
async def create_dossier(
    dt: str,
    immat: str,
    body: DossierReparationCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> DossierReparation:
    """Create a new dossier de réparation for a vehicle."""
    # Verify vehicle exists
    vehicle = await valkey.get_vehicle(immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{immat}' not found",
        )

    dossier = await valkey.create_dossier_reparation(
        immat=immat,
        description=body.description,
        cree_par=current_user.email,
    )
    return dossier


@router.get("", response_model=DossierReparationListResponse)
async def list_dossiers(
    dt: str,
    immat: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> DossierReparationListResponse:
    """List all dossiers de réparation for a vehicle."""
    vehicle = await valkey.get_vehicle(immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{immat}' not found",
        )

    dossiers = await valkey.list_dossiers_reparation(immat)
    return DossierReparationListResponse(count=len(dossiers), dossiers=dossiers)


@router.get("/{numero}", response_model=DossierReparation)
async def get_dossier(
    dt: str,
    immat: str,
    numero: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> DossierReparation:
    """Get details of a specific dossier de réparation."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )
    return dossier


@router.patch("/{numero}", response_model=DossierReparation)
async def update_dossier(
    dt: str,
    immat: str,
    numero: str,
    body: DossierReparationUpdate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> DossierReparation:
    """Update a dossier de réparation (description, close/reopen, cancel)."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    updated = False
    action: ActionHistorique | None = None
    details = ""

    if body.description is not None:
        dossier.description = body.description
        updated = True
        action = ActionHistorique.MODIFICATION
        details = "Description modifiée"

    if body.statut is not None and body.statut != dossier.statut:
        old_statut = dossier.statut
        dossier.statut = body.statut

        if body.statut == StatutDossier.CLOTURE:
            dossier.cloture_le = datetime.utcnow()
            action = ActionHistorique.CLOTURE
            details = "Dossier clôturé"
        elif body.statut == StatutDossier.OUVERT and old_statut == StatutDossier.CLOTURE:
            dossier.cloture_le = None
            action = ActionHistorique.REOUVERTURE
            details = "Dossier réouvert"
        elif body.statut == StatutDossier.ANNULE:
            action = ActionHistorique.ANNULATION
            details = "Dossier annulé"

        updated = True

    if not updated:
        return dossier

    success = await valkey.update_dossier_reparation(immat, numero, dossier)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dossier",
        )

    if action:
        key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}"
        await valkey.add_historique_entry(
            immat=immat,
            numero=numero,
            entry=HistoriqueEntry(
                auteur=current_user.email,
                action=action,
                details=details,
                ref=key,
            ),
        )

    return dossier

