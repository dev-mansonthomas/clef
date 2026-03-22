"""Contacts CC (carbon copy contacts) API endpoints."""
import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.repair_models import (
    ContactCC,
    ContactCCCreate,
    ContactCCUpdate,
    ContactCCListResponse,
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_service import ValkeyService
from app.services.valkey_dependencies import get_valkey_service

router = APIRouter(
    prefix="/api/{dt}/contacts-cc",
    tags=["contacts-cc"],
)


@router.get("", response_model=ContactCCListResponse)
async def list_contacts_cc(
    dt: str,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> ContactCCListResponse:
    """List all contacts CC for this DT."""
    contacts = await valkey_service.list_contacts_cc()
    return ContactCCListResponse(count=len(contacts), contacts_cc=contacts)


@router.post("", response_model=ContactCC, status_code=status.HTTP_201_CREATED)
async def create_contact_cc(
    dt: str,
    body: ContactCCCreate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> ContactCC:
    """Add a new contact CC. Only Gestionnaire DT can create contacts CC."""
    if current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Gestionnaire DT can manage contacts CC",
        )

    contact = ContactCC(
        id=str(uuid.uuid4()),
        prenom=body.prenom,
        nom=body.nom,
        email=body.email,
        role=body.role,
        actif=body.actif,
        cc_par_defaut=body.cc_par_defaut,
        cree_par=current_user.email,
        cree_le=datetime.utcnow(),
    )

    success = await valkey_service.set_contact_cc(contact)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create contact CC",
        )
    return contact


@router.patch("/{contact_id}", response_model=ContactCC)
async def update_contact_cc(
    dt: str,
    contact_id: str,
    body: ContactCCUpdate,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service),
) -> ContactCC:
    """Update a contact CC. Only Gestionnaire DT can update contacts CC."""
    if current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Gestionnaire DT can manage contacts CC",
        )

    contact = await valkey_service.get_contact_cc(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact CC '{contact_id}' not found",
        )

    # Apply partial updates
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    success = await valkey_service.set_contact_cc(contact)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update contact CC",
        )
    return contact

