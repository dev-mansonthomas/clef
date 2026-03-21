"""Fournisseurs (suppliers) API endpoints."""
import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.repair_models import (
    Fournisseur,
    FournisseurCreate,
    FournisseurUpdate,
    FournisseurListResponse,
    NiveauFournisseur,
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_service import ValkeyService
from app.services.valkey_dependencies import get_valkey_service

router = APIRouter(
    prefix="/api/{dt}/fournisseurs",
    tags=["fournisseurs"],
)


def _check_can_manage(user: User, niveau: NiveauFournisseur, ul_id: str | None) -> None:
    """Check if user can manage suppliers at the given level.

    - DT-level suppliers: only Gestionnaire DT
    - UL-level suppliers: Gestionnaire DT or Responsable UL of that UL
    """
    if niveau == NiveauFournisseur.DT:
        if user.role != "Gestionnaire DT":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Gestionnaire DT can manage DT-level suppliers",
            )
    else:  # UL
        if user.role == "Gestionnaire DT":
            return
        if user.role in ("Responsable UL", "Responsable Véhicule UL"):
            if user.ul == ul_id:
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage this UL's suppliers",
        )


@router.get("", response_model=FournisseurListResponse)
async def list_fournisseurs(
    dt: str,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> FournisseurListResponse:
    """List suppliers visible to the current user (DT + user's UL combined)."""
    ul_id = current_user.ul if current_user.role != "Gestionnaire DT" else None
    fournisseurs = await valkey_service.list_fournisseurs(ul_id=ul_id)
    return FournisseurListResponse(count=len(fournisseurs), fournisseurs=fournisseurs)


@router.post("", response_model=Fournisseur, status_code=status.HTTP_201_CREATED)
async def create_fournisseur(
    dt: str,
    body: FournisseurCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> Fournisseur:
    """Add a new supplier."""
    # Validate UL-level requires ul_id
    if body.niveau == NiveauFournisseur.UL and not body.ul_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ul_id is required for UL-level suppliers",
        )

    _check_can_manage(current_user, body.niveau, body.ul_id)

    fournisseur = Fournisseur(
        id=str(uuid.uuid4()),
        nom=body.nom,
        adresse=body.adresse,
        telephone=body.telephone,
        siret=body.siret,
        email=body.email,
        contact_nom=body.contact_nom,
        specialites=body.specialites,
        niveau=body.niveau,
        ul_id=body.ul_id if body.niveau == NiveauFournisseur.UL else None,
        cree_par=current_user.email,
        cree_le=datetime.utcnow(),
    )

    success = await valkey_service.set_fournisseur(fournisseur)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supplier",
        )
    return fournisseur


@router.patch("/{fournisseur_id}", response_model=Fournisseur)
async def update_fournisseur(
    dt: str,
    fournisseur_id: str,
    body: FournisseurUpdate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> Fournisseur:
    """Update a supplier."""
    # Try DT-level first, then UL-level with user's UL
    fournisseur = await valkey_service.get_fournisseur(fournisseur_id)
    if not fournisseur and current_user.ul:
        fournisseur = await valkey_service.get_fournisseur(fournisseur_id, ul_id=current_user.ul)
    if not fournisseur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier '{fournisseur_id}' not found",
        )

    _check_can_manage(current_user, fournisseur.niveau, fournisseur.ul_id)

    # Apply partial updates
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(fournisseur, field, value)

    success = await valkey_service.set_fournisseur(fournisseur)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update supplier",
        )
    return fournisseur

