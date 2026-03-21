"""Approbation API endpoints — public routes secured by token."""
import logging
from fastapi import APIRouter, HTTPException, status

from app.cache import get_cache
from app.services.approval_service import ApprovalService
from app.services.valkey_service import ValkeyService
from app.models.repair_models import (
    ApprobationDataResponse,
    SubmitDecisionRequest,
    SubmitDecisionResponse,
    StatutDevis,
    ActionHistorique,
    HistoriqueEntry,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/approbation",
    tags=["approbation"],
)


async def _get_approval_service_and_data(token: str):
    """Helper: get approval data or raise 404/410."""
    cache = get_cache()
    if not cache._connected:
        await cache.connect()
    if not cache.client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        )

    # We need to try all possible DT prefixes. For now, use a scan approach.
    # Since the token is globally unique, we store with the DT prefix from creation.
    # We'll try common DTs or do a key scan.
    # Simpler approach: store a reverse lookup at approbation:{token} (no DT prefix)
    # But the spec says {DT}:approbation:{token}. Let's try DT75 first then scan.
    # In practice, we'll use the DT stored in the token data itself.

    # Try to find the token by scanning known DTs
    # For simplicity, try DT75 first (the main DT), then try a SCAN pattern
    for dt_prefix in ["DT75"]:
        approval_svc = ApprovalService(redis_client=cache.client, dt=dt_prefix)
        data = await approval_svc.get_approval_data(token)
        if data:
            return approval_svc, data

    # Fallback: scan for the key
    pattern = f"*:approbation:{token}"
    cursor = 0
    while True:
        cursor, keys = await cache.client.scan(cursor, match=pattern, count=100)
        for key in keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            dt_prefix = key_str.split(":")[0]
            approval_svc = ApprovalService(redis_client=cache.client, dt=dt_prefix)
            data = await approval_svc.get_approval_data(token)
            if data:
                return approval_svc, data
        if cursor == 0:
            break

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Token not found or expired",
    )


@router.get("/{token}", response_model=ApprobationDataResponse)
async def get_approbation_data(token: str) -> ApprobationDataResponse:
    """Get devis data for the approval page (NO auth required)."""
    _, token_data = await _get_approval_service_and_data(token)

    dt = token_data["dt"]
    immat = token_data["immat"]
    numero = token_data["numero_dossier"]
    devis_id = token_data["devis_id"]

    cache = get_cache()
    valkey = ValkeyService(redis_client=cache.client, dt=dt)

    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")

    devis = await valkey.get_devis(immat, numero, devis_id)
    if not devis:
        raise HTTPException(status_code=404, detail="Devis not found")

    return ApprobationDataResponse(
        dt=dt,
        immat=immat,
        numero_dossier=numero,
        devis_id=devis_id,
        devis=devis,
        dossier_description=dossier.description,
        valideur_email=token_data["valideur_email"],
        status=token_data["status"],
        created_at=token_data["created_at"],
        expires_at=token_data["expires_at"],
    )


@router.post("/{token}", response_model=SubmitDecisionResponse)
async def submit_decision(token: str, body: SubmitDecisionRequest) -> SubmitDecisionResponse:
    """Submit an approval decision (NO auth required — token-secured)."""
    approval_svc, token_data = await _get_approval_service_and_data(token)

    dt = token_data["dt"]
    immat = token_data["immat"]
    numero = token_data["numero_dossier"]
    devis_id = token_data["devis_id"]

    # Check if already decided — allow change if no facture yet
    if token_data["status"] in ("approuve", "refuse"):
        cache = get_cache()
        valkey = ValkeyService(redis_client=cache.client, dt=dt)
        dossier = await valkey.get_dossier_reparation(immat, numero)
        if dossier:
            has_facture_for_devis = any(
                f.devis_id == devis_id for f in dossier.factures
            )
            if has_facture_for_devis:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot change decision — a facture is already linked to this devis",
                )
    else:
        cache = get_cache()
        valkey = ValkeyService(redis_client=cache.client, dt=dt)

    # Submit decision on token
    updated = await approval_svc.submit_decision(token, body.decision, body.commentaire)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update decision")

    # Update devis status
    new_statut = StatutDevis.APPROUVE if body.decision == "approuve" else StatutDevis.REFUSE
    update_data = {"statut": new_statut}
    if body.commentaire:
        update_data["valideur_commentaire"] = body.commentaire
    await valkey.update_devis(immat, numero, devis_id, update_data)

    # Add historique entry
    action = ActionHistorique.DEVIS_APPROUVE if body.decision == "approuve" else ActionHistorique.DEVIS_REFUSE
    ref_key = f"{dt}:vehicules:{immat}:travaux:{numero}:devis:{devis_id}"
    await valkey.add_historique_entry(
        immat=immat,
        numero=numero,
        entry=HistoriqueEntry(
            auteur=token_data["valideur_email"],
            action=action,
            details=f"Devis #{devis_id} {'approuvé' if body.decision == 'approuve' else 'refusé'}"
                    + (f" — {body.commentaire}" if body.commentaire else ""),
            ref=ref_key,
        ),
    )

    decision_label = "approuvé" if body.decision == "approuve" else "refusé"
    return SubmitDecisionResponse(
        decision=body.decision,
        message=f"Devis {decision_label} avec succès",
    )

