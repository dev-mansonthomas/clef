"""Valideurs (approvers) API endpoints."""
import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.repair_models import (
    Valideur,
    ValideurCreate,
    ValideurUpdate,
    ValideurListResponse,
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_service import ValkeyService
from app.services.valkey_dependencies import get_valkey_service

router = APIRouter(
    prefix="/api/{dt}/valideurs",
    tags=["valideurs"],
)


@router.get("", response_model=ValideurListResponse)
async def list_valideurs(
    dt: str,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> ValideurListResponse:
    """List all valideurs for this DT."""
    valideurs = await valkey_service.list_valideurs()
    return ValideurListResponse(count=len(valideurs), valideurs=valideurs)


@router.post("", response_model=Valideur, status_code=status.HTTP_201_CREATED)
async def create_valideur(
    dt: str,
    body: ValideurCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> Valideur:
    """Add a new valideur. Only Gestionnaire DT can create valideurs."""
    if current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Gestionnaire DT can manage valideurs",
        )

    valideur = Valideur(
        id=str(uuid.uuid4()),
        nom=body.nom,
        email=body.email,
        role=body.role,
        actif=body.actif,
        cree_par=current_user.email,
        cree_le=datetime.utcnow(),
    )

    success = await valkey_service.set_valideur(valideur)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create valideur",
        )
    return valideur


@router.patch("/{valideur_id}", response_model=Valideur)
async def update_valideur(
    dt: str,
    valideur_id: str,
    body: ValideurUpdate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> Valideur:
    """Update a valideur. Only Gestionnaire DT can update valideurs."""
    if current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Gestionnaire DT can manage valideurs",
        )

    valideur = await valkey_service.get_valideur(valideur_id)
    if not valideur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Valideur '{valideur_id}' not found",
        )

    # Apply partial updates
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(valideur, field, value)

    success = await valkey_service.set_valideur(valideur)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update valideur",
        )
    return valideur

