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
    DevisCreate,
    DevisUpdate,
    FactureCreate,
    FactureResponse,
    Devis,
    Facture,
    StatutDossier,
    StatutDevis,
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



# ========== Devis Endpoints ==========


def _check_dossier_open(dossier: DossierReparation) -> None:
    """Raise 409 if dossier is closed or cancelled."""
    if dossier.statut in (StatutDossier.CLOTURE, StatutDossier.ANNULE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot modify dossier with status '{dossier.statut.value}'",
        )


@router.post("/{numero}/devis", response_model=Devis, status_code=status.HTTP_201_CREATED)
async def create_devis(
    dt: str,
    immat: str,
    numero: str,
    body: DevisCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Devis:
    """Add a devis to a dossier de réparation."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    _check_dossier_open(dossier)

    devis_data = body.model_dump()
    devis_data["cree_par"] = current_user.email

    devis = await valkey.add_devis(immat, numero, devis_data)
    return devis


@router.get("/{numero}/devis/{devis_id}", response_model=Devis)
async def get_devis(
    dt: str,
    immat: str,
    numero: str,
    devis_id: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Devis:
    """Get a specific devis."""
    devis = await valkey.get_devis(immat, numero, devis_id)
    if not devis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Devis '{devis_id}' not found in dossier '{numero}'",
        )
    return devis


@router.patch("/{numero}/devis/{devis_id}", response_model=Devis)
async def update_devis(
    dt: str,
    immat: str,
    numero: str,
    devis_id: str,
    body: DevisUpdate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Devis:
    """Update a devis (e.g. status change for approval workflow)."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    devis = await valkey.update_devis(immat, numero, devis_id, {"statut": body.statut})
    if not devis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Devis '{devis_id}' not found in dossier '{numero}'",
        )

    # Add history entry
    action_map = {
        StatutDevis.APPROUVE: ActionHistorique.DEVIS_APPROUVE,
        StatutDevis.REFUSE: ActionHistorique.DEVIS_REFUSE,
        StatutDevis.ANNULE: ActionHistorique.DEVIS_ANNULE,
    }
    action = action_map.get(body.statut, ActionHistorique.DEVIS_MODIFIE)
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}:devis:{devis_id}"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=current_user.email,
            action=action,
            details=f"Devis #{devis_id} — statut → {body.statut.value}",
            ref=key,
        ),
    )

    return devis


# ========== Facture Endpoints ==========


@router.post("/{numero}/factures", response_model=FactureResponse, status_code=status.HTTP_201_CREATED)
async def create_facture(
    dt: str,
    immat: str,
    numero: str,
    body: FactureCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> FactureResponse:
    """Add a facture to a dossier de réparation with business-logic warnings."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    _check_dossier_open(dossier)

    # --- Business logic warnings ---
    warning_no_devis = False
    warning_devis_not_approved = False
    warning_ecart = False
    ecart_pourcentage: float | None = None

    if body.devis_id:
        devis = await valkey.get_devis(immat, numero, body.devis_id)
        if not devis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Devis '{body.devis_id}' not found in dossier '{numero}'",
            )
        if devis.statut != StatutDevis.APPROUVE:
            warning_devis_not_approved = True
        else:
            # Check écart > 20%
            if devis.montant > 0:
                ecart = abs(body.montant_total - devis.montant) / devis.montant * 100
                if ecart > 20:
                    warning_ecart = True
                    ecart_pourcentage = round(ecart, 2)
    else:
        # No devis_id provided — check if any approved devis exists in dossier
        has_approved = any(d.statut == StatutDevis.APPROUVE for d in dossier.devis)
        if not has_approved:
            warning_no_devis = True

    # --- Create the facture ---
    facture_data = body.model_dump()
    facture_data["cree_par"] = current_user.email

    facture = await valkey.add_facture(immat, numero, facture_data)

    return FactureResponse(
        facture=facture,
        warning_no_devis=warning_no_devis,
        warning_devis_not_approved=warning_devis_not_approved,
        warning_ecart=warning_ecart,
        ecart_pourcentage=ecart_pourcentage,
    )


@router.get("/{numero}/factures/{facture_id}", response_model=Facture)
async def get_facture(
    dt: str,
    immat: str,
    numero: str,
    facture_id: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Facture:
    """Get a specific facture."""
    facture = await valkey.get_facture(immat, numero, facture_id)
    if not facture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facture '{facture_id}' not found in dossier '{numero}'",
        )
    return facture