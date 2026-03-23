"""Dossiers Réparation API endpoints."""
import logging
import os
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.models.repair_models import (
    DossierReparation,
    DossierReparationCreate,
    DossierReparationUpdate,
    DossierReparationListResponse,
    DevisCreate,
    DevisUpdate,
    FactureCreate,
    FactureUpdate,
    FactureResponse,
    Devis,
    Facture,
    FichierDrive,
    FournisseurSnapshot,
    StatutDossier,
    StatutDevis,
    ActionHistorique,
    HistoriqueEntry,
    SendApprovalRequest,
    SendApprovalResponse,
    BulkApprovalRequest,
    BulkApprovalResponse,
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService
from app.services.approval_service import ApprovalService
from app.services.email_service import email_service
from app.services.drive_service import drive_service

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
        est_sinistre=body.est_sinistre,
        franchise_applicable=body.franchise_applicable,
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

    if body.est_sinistre is not None:
        dossier.est_sinistre = body.est_sinistre
        updated = True
        if action is None:
            action = ActionHistorique.MODIFICATION
            details = "Sinistre modifié"

    if body.franchise_applicable is not None:
        dossier.franchise_applicable = body.franchise_applicable
        updated = True
        if action is None:
            action = ActionHistorique.MODIFICATION
            details = "Franchise modifiée"

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

    # If editing fields (not just statut), devis must be en_attente or refuse
    if has_field_edits and existing_devis.statut not in (StatutDevis.EN_ATTENTE, StatutDevis.REFUSE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit devis with status '{existing_devis.statut.value}'. Only 'en_attente' or 'refuse' devis can be edited.",
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

    # Create dossier-level approval token (with single devis)
    token_data = await approval_svc.create_dossier_approval_token(
        immat=immat,
        numero_dossier=numero,
        devis_ids=[devis_id],
        valideur_email=body.valideur_email,
    )

    # Build approval URL
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
    approval_url = f"{frontend_url}/approbation/{token_data['token']}"

    # Get franchise config
    config = await valkey.get_configuration()
    montant_franchise = config.montant_franchise if config else 350.0

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
        est_sinistre=dossier.est_sinistre,
        franchise_applicable=dossier.franchise_applicable,
        montant_franchise=montant_franchise,
        total_devis=devis.montant,
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


@router.post(
    "/{numero}/send-bulk-approval",
    response_model=BulkApprovalResponse,
    status_code=status.HTTP_200_OK,
)
async def send_bulk_approval(
    dt: str,
    immat: str,
    numero: str,
    body: BulkApprovalRequest,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> BulkApprovalResponse:
    """Send all pending devis for approval in one action."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    _check_dossier_open(dossier)

    # Find all devis with statut en_attente
    pending_devis = [d for d in dossier.devis if d.statut == StatutDevis.EN_ATTENTE]
    if not pending_devis:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun devis en attente d'approbation",
        )

    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
    approval_svc = ApprovalService(redis_client=valkey.redis, dt=dt)

    # Create ONE dossier-level approval token covering all pending devis
    devis_ids = [d.id for d in pending_devis]
    token_data = await approval_svc.create_dossier_approval_token(
        immat=immat,
        numero_dossier=numero,
        devis_ids=devis_ids,
        valideur_email=body.valideur_email,
    )
    dossier_token = token_data["token"]
    approval_url = f"{frontend_url}/approbation/{dossier_token}"

    devis_dicts = []
    for devis in pending_devis:
        devis_dicts.append(devis.model_dump(mode="json"))

        # Update devis status to "envoye" with the SAME token
        await valkey.update_devis(immat, numero, devis.id, {
            "statut": StatutDevis.ENVOYE,
            "valideur_email": body.valideur_email,
            "token_approbation": dossier_token,
            "date_envoi_approbation": token_data["created_at"],
        })

    # Get franchise config
    config = await valkey.get_configuration()
    montant_franchise = config.montant_franchise if config else 350.0
    total_devis = sum(d.get("montant", 0) for d in devis_dicts)

    # Send ONE summary email with ONE approval URL
    await email_service.send_bulk_approval_email(
        dt_id=dt,
        numero_dossier=numero,
        devis_list=devis_dicts,
        approval_url=approval_url,
        valideur_email=body.valideur_email,
        sender_email=current_user.email,
        dossier_description=dossier.description,
        dossier_commentaire=dossier.commentaire,
        est_sinistre=dossier.est_sinistre,
        franchise_applicable=dossier.franchise_applicable,
        montant_franchise=montant_franchise,
        total_devis=total_devis,
    )

    # Add historique entry
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=current_user.email,
            action=ActionHistorique.DOSSIER_ENVOYE_APPROBATION,
            details=f"{len(pending_devis)} devis envoyés pour approbation groupée à {body.valideur_email}",
            ref=key,
        ),
    )

    return BulkApprovalResponse(
        count=len(pending_devis),
        token=dossier_token,
        valideur_email=body.valideur_email,
        message=f"{len(pending_devis)} devis envoyés pour approbation",
    )


# ========== Devis File Upload ==========

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/{numero}/devis/{devis_id}/upload", response_model=Devis)
async def upload_devis_fichier(
    dt: str,
    immat: str,
    numero: str,
    devis_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Devis:
    """Upload or update the file attached to a devis (PDF/image, max 10 MB)."""
    # Validate dossier exists
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    # Validate devis exists
    devis = await valkey.get_devis(immat, numero, devis_id)
    if not devis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Devis '{devis_id}' not found in dossier '{numero}'",
        )

    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file.content_type}' not allowed. Accepted: PDF, JPEG, PNG.",
        )

    # Read and validate file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({len(file_content)} bytes). Maximum: 10 MB.",
        )

    # Get vehicle for nom_synthetique
    vehicle = await valkey.get_vehicle(immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{immat}' not found",
        )

    # Get or create the "Dossiers Réparation" folder for this vehicle
    drive_folders = getattr(vehicle, "drive_folders", {}) or {}
    factures_folder = drive_folders.get("factures")
    if factures_folder and isinstance(factures_folder, dict) and factures_folder.get("folder_id"):
        repair_parent_id = factures_folder["folder_id"]
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle Drive folder tree not configured. Please sync Drive folders first.",
        )

    # Build repair subfolder name: YYYY-MM-DD - nom_synth - Réparation - TITRE
    date_str = dossier.cree_le.strftime("%Y-%m-%d")
    parts = [date_str, vehicle.nom_synthetique, "Réparation"]
    if dossier.titre:
        parts.append(dossier.titre)
    subfolder_name = " - ".join(parts)

    # Get or create the repair subfolder
    repair_subfolder = await drive_service.get_or_create_folder(
        dt_id=dt,
        name=subfolder_name,
        parent_folder_id=repair_parent_id,
    )

    # Create a sub-folder "Devis XX" inside the repair subfolder
    devis_folder_name = f"Devis {devis_id.zfill(2)}"
    devis_folder = await drive_service.get_or_create_folder(
        dt_id=dt, name=devis_folder_name, parent_folder_id=repair_subfolder["id"],
    )

    # Build filename: {date_devis} - {nom_synthetique} - {dossier.numero} - Devis XX.ext
    ext_map = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
    ext = ext_map.get(file.content_type, ".pdf")
    date_devis = devis.date_devis.strftime("%Y-%m-%d")
    upload_filename = f"{date_devis} - {vehicle.nom_synthetique} - {dossier.numero} - Devis {devis_id.zfill(2)}{ext}"

    if devis.fichier and devis.fichier.file_id:
        # Update existing file (versioning)
        await drive_service.ensure_first_revision_kept(dt_id=dt, file_id=devis.fichier.file_id)
        uploaded = await drive_service.update_file_version(
            dt_id=dt,
            file_id=devis.fichier.file_id,
            file_content=file_content,
            mime_type=file.content_type,
            keep_forever=True,
        )
    else:
        # New upload — into the Devis XX subfolder
        uploaded = await drive_service.upload_file(
            dt_id=dt,
            file_content=file_content,
            filename=upload_filename,
            mime_type=file.content_type,
            parent_folder_id=devis_folder["id"],
            description=f"Devis #{devis_id} - {dossier.numero}",
        )

    # Update devis with fichier info
    fichier = FichierDrive(
        file_id=uploaded["id"],
        name=uploaded.get("name", upload_filename),
        web_view_link=uploaded.get("webViewLink", ""),
    )
    updated_devis = await valkey.update_devis(immat, numero, devis_id, {"fichier": fichier})
    if not updated_devis:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update devis with file info",
        )

    # Add historique entry
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}:devis:{devis_id}"
    action_detail = "mis à jour" if devis.fichier else "ajouté"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=current_user.email,
            action=ActionHistorique.DEVIS_FICHIER_UPLOAD,
            details=f"Fichier devis #{devis_id} {action_detail} ({upload_filename})",
            ref=key,
        ),
    )

    return updated_devis


@router.post("/{numero}/devis/{devis_id}/annuler", response_model=Devis)
async def annuler_devis(
    dt: str,
    immat: str,
    numero: str,
    devis_id: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Devis:
    """Cancel a devis at any stage (as long as dossier is open)."""
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

    if devis.statut == StatutDevis.ANNULE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce devis est déjà annulé",
        )

    # Invalidate approval token if one exists
    if devis.token_approbation:
        approval_svc = ApprovalService(redis_client=valkey.redis, dt=dt)
        await approval_svc.invalidate_token(devis.token_approbation)

    # Update devis status to annule
    updated_devis = await valkey.update_devis(immat, numero, devis_id, {
        "statut": StatutDevis.ANNULE,
    })

    # Add historique entry
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}:devis:{devis_id}"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=current_user.email,
            action=ActionHistorique.DEVIS_ANNULE,
            details=f"Devis #{devis_id} annulé",
            ref=key,
        ),
    )

    return updated_devis


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


# ========== Facture File Upload ==========


@router.post("/{numero}/factures/{facture_id}/upload", response_model=Facture)
async def upload_facture_fichier(
    dt: str,
    immat: str,
    numero: str,
    facture_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Facture:
    """Upload or update the file attached to a facture (PDF/image, max 10 MB)."""
    # Validate dossier exists
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found for vehicle '{immat}'",
        )

    # Validate facture exists
    facture = await valkey.get_facture(immat, numero, facture_id)
    if not facture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facture '{facture_id}' not found in dossier '{numero}'",
        )

    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file.content_type}' not allowed. Accepted: PDF, JPEG, PNG.",
        )

    # Read and validate file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({len(file_content)} bytes). Maximum: 10 MB.",
        )

    # Get vehicle for nom_synthetique
    vehicle = await valkey.get_vehicle(immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{immat}' not found",
        )

    # Get or create the "Dossiers Réparation" folder for this vehicle
    drive_folders = getattr(vehicle, "drive_folders", {}) or {}
    factures_folder = drive_folders.get("factures")
    if factures_folder and isinstance(factures_folder, dict) and factures_folder.get("folder_id"):
        repair_parent_id = factures_folder["folder_id"]
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle Drive folder tree not configured. Please sync Drive folders first.",
        )

    # Build repair subfolder name: YYYY-MM-DD - nom_synth - Réparation - TITRE
    date_str = dossier.cree_le.strftime("%Y-%m-%d")
    parts = [date_str, vehicle.nom_synthetique, "Réparation"]
    if dossier.titre:
        parts.append(dossier.titre)
    subfolder_name = " - ".join(parts)

    # Get or create the repair subfolder
    repair_subfolder = await drive_service.get_or_create_folder(
        dt_id=dt,
        name=subfolder_name,
        parent_folder_id=repair_parent_id,
    )

    # Determine target folder based on devis_id
    if facture.devis_id:
        # Facture linked to a devis: upload into the same "Devis XX" subfolder
        devis_folder_name = f"Devis {facture.devis_id.zfill(2)}"
        devis_folder = await drive_service.get_or_create_folder(
            dt_id=dt, name=devis_folder_name, parent_folder_id=repair_subfolder["id"],
        )
        target_folder_id = devis_folder["id"]
    else:
        # Facture without devis: store in "Factures Seules" subfolder
        factures_seules = await drive_service.get_or_create_folder(
            dt_id=dt,
            name="Factures Seules",
            parent_folder_id=repair_subfolder["id"],
        )
        target_folder_id = factures_seules["id"]

    # Build filename: Facture {facture_id.zfill(2)} - {fournisseur_nom}{ext}
    ext_map = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
    ext = ext_map.get(file.content_type, ".pdf")
    upload_filename = f"Facture {facture_id.zfill(2)} - {facture.fournisseur.nom}{ext}"

    if facture.fichier and facture.fichier.file_id:
        # Update existing file (versioning)
        await drive_service.ensure_first_revision_kept(dt_id=dt, file_id=facture.fichier.file_id)
        uploaded = await drive_service.update_file_version(
            dt_id=dt,
            file_id=facture.fichier.file_id,
            file_content=file_content,
            mime_type=file.content_type,
            keep_forever=True,
        )
    else:
        # New upload
        uploaded = await drive_service.upload_file(
            dt_id=dt,
            file_content=file_content,
            filename=upload_filename,
            mime_type=file.content_type,
            parent_folder_id=target_folder_id,
            description=f"Facture #{facture_id} - {dossier.numero}",
        )

    # Update facture with fichier info
    fichier = FichierDrive(
        file_id=uploaded["id"],
        name=uploaded.get("name", upload_filename),
        web_view_link=uploaded.get("webViewLink", ""),
    )
    updated_facture = await valkey.update_facture(immat, numero, facture_id, {"fichier": fichier})
    if not updated_facture:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update facture with file info",
        )

    # Add historique entry
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}:factures:{facture_id}"
    action_detail = "mis à jour" if facture.fichier else "ajouté"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=current_user.email,
            action=ActionHistorique.FACTURE_FICHIER_UPLOAD,
            details=f"Fichier facture #{facture_id} {action_detail} ({upload_filename})",
            ref=key,
        ),
    )

    return updated_facture


# ========== Facture Update ==========


@router.patch("/{numero}/factures/{facture_id}", response_model=Facture)
async def update_facture(
    dt: str,
    immat: str,
    numero: str,
    facture_id: str,
    body: FactureUpdate,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Facture:
    """Update a facture."""
    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{numero}' not found",
        )
    _check_dossier_open(dossier)

    facture = await valkey.get_facture(immat, numero, facture_id)
    if not facture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facture '{facture_id}' not found",
        )

    update_data = body.model_dump(exclude_none=True)
    # Handle fournisseur update
    if 'fournisseur_id' in update_data and 'fournisseur_nom' in update_data:
        update_data['fournisseur'] = FournisseurSnapshot(
            id=update_data.pop('fournisseur_id'),
            nom=update_data.pop('fournisseur_nom'),
        )
    elif 'fournisseur_id' in update_data or 'fournisseur_nom' in update_data:
        update_data.pop('fournisseur_id', None)
        update_data.pop('fournisseur_nom', None)

    # Map description_travaux to description field
    if 'description_travaux' in update_data:
        update_data['description'] = update_data.pop('description_travaux')

    updated = await valkey.update_facture(immat, numero, facture_id, update_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update facture",
        )

    # Add historique entry
    key = f"{valkey.dt}:vehicules:{immat}:travaux:{numero}:factures:{facture_id}"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=current_user.email,
            action=ActionHistorique.FACTURE_MODIFIEE,
            details=f"Facture #{facture_id} modifiée",
            ref=key,
        ),
    )

    return updated