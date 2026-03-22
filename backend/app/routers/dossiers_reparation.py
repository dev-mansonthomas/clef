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
    FournisseurSnapshot,
    StatutDossier,
    StatutDevis,
    ActionHistorique,
    HistoriqueEntry,
    SendApprovalRequest,
    SendApprovalResponse,
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService
from app.services.approval_service import ApprovalService
from app.services.email_service import email_service

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
        commentaire=body.commentaire,
        titre=body.titre,
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

    if body.titre is not None:
        dossier.titre = body.titre
        updated = True
        action = ActionHistorique.MODIFICATION
        details = "Titre modifié"

    if body.description is not None:
        dossier.description = body.description
        updated = True
        action = ActionHistorique.MODIFICATION
        details = "Description modifiée"

    if body.commentaire is not None:
        dossier.commentaire = body.commentaire
        updated = True
        if action is None:
            action = ActionHistorique.MODIFICATION
            details = "Commentaire modifié"

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
    """Update a devis (field edits when en_attente, or status change for approval workflow)."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    existing_devis = await valkey.get_devis(immat, numero, devis_id)
    if not existing_devis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Devis '{devis_id}' not found in dossier '{numero}'",
        )

    # Determine which fields are being edited (non-statut fields)
    edit_fields = body.model_dump(exclude_unset=True)
    has_field_edits = any(k != "statut" for k in edit_fields)

    # If editing fields (not just statut), devis must be en_attente
    if has_field_edits and existing_devis.statut != StatutDevis.EN_ATTENTE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit devis with status '{existing_devis.statut.value}'. Only 'en_attente' devis can be edited.",
        )

    # Build update dict
    update_data: dict = {}

    if body.date_devis is not None:
        update_data["date_devis"] = body.date_devis
    if body.description_travaux is not None:
        update_data["description"] = body.description_travaux
    if body.montant is not None:
        update_data["montant"] = body.montant
    if body.fournisseur_id is not None:
        update_data["fournisseur"] = FournisseurSnapshot(
            id=body.fournisseur_id,
            nom=body.fournisseur_nom or existing_devis.fournisseur.nom,
        )
    if body.statut is not None:
        update_data["statut"] = body.statut

    if not update_data:
        return existing_devis

    devis = await valkey.update_devis(immat, numero, devis_id, update_data)
    if not devis:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update devis",
        )

    # Add history entry
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}:devis:{devis_id}"
    if body.statut is not None and not has_field_edits:
        # Pure status change — use specific action
        action_map = {
            StatutDevis.APPROUVE: ActionHistorique.DEVIS_APPROUVE,
            StatutDevis.REFUSE: ActionHistorique.DEVIS_REFUSE,
            StatutDevis.ANNULE: ActionHistorique.DEVIS_ANNULE,
        }
        action = action_map.get(body.statut, ActionHistorique.DEVIS_MODIFIE)
        details = f"Devis #{devis_id} — statut → {body.statut.value}"
    else:
        # Field edit
        action = ActionHistorique.DEVIS_MODIFIE
        changed = [k for k in edit_fields if k != "statut"]
        details = f"Devis #{devis_id} modifié ({', '.join(changed)})"

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

    return devis


@router.post(
    "/{numero}/devis/{devis_id}/send-approval",
    response_model=SendApprovalResponse,
    status_code=status.HTTP_200_OK,
)
async def send_devis_for_approval(
    dt: str,
    immat: str,
    numero: str,
    devis_id: str,
    body: SendApprovalRequest,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> SendApprovalResponse:
    """Send a devis for approval: create token, send email, update status."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    _check_dossier_open(dossier)

    devis = await valkey.get_devis(immat, numero, devis_id)
    if not devis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Devis '{devis_id}' not found in dossier '{numero}'",
        )

    if devis.statut not in (StatutDevis.EN_ATTENTE, StatutDevis.ENVOYE, StatutDevis.REFUSE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot send devis with status '{devis.statut.value}' for approval",
        )

    # Track whether this is a re-send (for history)
    is_resend = devis.statut in (StatutDevis.ENVOYE, StatutDevis.REFUSE)

    # Invalidate old approval token if re-sending
    approval_svc = ApprovalService(redis_client=valkey.redis, dt=dt)
    if is_resend and devis.token_approbation:
        await approval_svc.invalidate_token(devis.token_approbation)

    # Create approval token
    token_data = await approval_svc.create_approval_token(
        immat=immat,
        numero_dossier=numero,
        devis_id=devis_id,
        valideur_email=body.valideur_email,
    )

    # Build approval URL
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
    approval_url = f"{frontend_url}/approbation/{token_data['token']}"

    # Send approval email
    devis_dict = devis.model_dump(mode="json")
    await email_service.send_approval_email(
        dt_id=dt,
        devis_data=devis_dict,
        valideur_email=body.valideur_email,
        approval_url=approval_url,
        sender_email=current_user.email,
        dossier_description=dossier.description,
        dossier_commentaire=dossier.commentaire,
    )

    # Update devis status to "envoye"
    await valkey.update_devis(immat, numero, devis_id, {
        "statut": StatutDevis.ENVOYE,
        "valideur_email": body.valideur_email,
        "token_approbation": token_data["token"],
        "date_envoi_approbation": token_data["created_at"],
    })

    # Add history entry
    history_action = ActionHistorique.DEVIS_RENVOYE_APPROBATION if is_resend else ActionHistorique.DEVIS_ENVOYE_APPROBATION
    history_verb = "renvoyé" if is_resend else "envoyé"
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}:devis:{devis_id}"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=current_user.email,
            action=history_action,
            details=f"Devis #{devis_id} {history_verb} pour approbation à {body.valideur_email}",
            ref=key,
        ),
    )

    return SendApprovalResponse(
        token=token_data["token"],
        valideur_email=body.valideur_email,
        expires_at=token_data["expires_at"],
    )


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


@router.get("/{numero}/historique", response_model=List[HistoriqueEntry])
async def get_historique(
    dt: str,
    immat: str,
    numero: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> List[HistoriqueEntry]:
    """Get audit trail for a repair dossier, sorted by date descending."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )
    entries = await valkey.get_historique(immat, numero)
    # Sort by date descending
    entries.sort(key=lambda e: e.date, reverse=True)
    return entries


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