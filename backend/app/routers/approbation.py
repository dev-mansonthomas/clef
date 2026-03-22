"""Approbation API endpoints — public routes secured by token."""
import json
import logging
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from app.cache import get_cache
from app.services.approval_service import ApprovalService
from app.services.valkey_service import ValkeyService
from app.models.repair_models import (
    ApprobationDataResponse,
    DossierApprobationDataResponse,
    SubmitDecisionRequest,
    SubmitDecisionResponse,
    SubmitDossierDecisionRequest,
    SubmitDossierDecisionResponse,
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


@router.get("/{token}", response_model=DossierApprobationDataResponse)
async def get_approbation_data(token: str) -> DossierApprobationDataResponse:
    """Get devis data for the approval page (NO auth required).

    Supports both old (single devis_id) and new (devis_ids list) token formats.
    """
    _, token_data = await _get_approval_service_and_data(token)

    dt = token_data["dt"]
    immat = token_data["immat"]
    numero = token_data["numero_dossier"]

    # Backward compat: old tokens have devis_id, new ones have devis_ids
    devis_ids = token_data.get("devis_ids") or [token_data["devis_id"]]

    cache = get_cache()
    valkey = ValkeyService(redis_client=cache.client, dt=dt)

    dossier = await valkey.get_dossier_reparation(immat, numero)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")

    # Fetch all devis referenced in the token
    devis_list = []
    for did in devis_ids:
        d = await valkey.get_devis(immat, numero, did)
        if d:
            devis_list.append(d)

    if not devis_list:
        raise HTTPException(status_code=404, detail="Devis not found")

    return DossierApprobationDataResponse(
        dt=dt,
        immat=immat,
        numero_dossier=numero,
        devis_ids=devis_ids,
        devis=devis_list,
        dossier_description=dossier.description,
        dossier_titre=dossier.titre,
        valideur_email=token_data["valideur_email"],
        status=token_data["status"],
        created_at=token_data["created_at"],
        expires_at=token_data["expires_at"],
    )


@router.post("/{token}")
async def submit_decision(token: str, request: Request):
    """Submit an approval decision (NO auth required — token-secured).

    Accepts BOTH old format (SubmitDecisionRequest with 'decision' field)
    and new format (SubmitDossierDecisionRequest with 'mode' field).
    """
    approval_svc, token_data = await _get_approval_service_and_data(token)

    dt = token_data["dt"]
    immat = token_data["immat"]
    numero = token_data["numero_dossier"]

    # Backward compat: old tokens have devis_id, new ones have devis_ids
    devis_ids = token_data.get("devis_ids") or [token_data.get("devis_id")]

    cache = get_cache()
    valkey = ValkeyService(redis_client=cache.client, dt=dt)

    raw_body = await request.json()

    # Detect format: 'mode' field = new format, 'decision' field = old format
    if "decision" in raw_body and "mode" not in raw_body:
        # ========== Old format (single devis) ==========
        try:
            body = SubmitDecisionRequest(**raw_body)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())
        devis_id = devis_ids[0]

        # Check if already decided — allow change if no facture yet
        if token_data["status"] in ("approuve", "refuse"):
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

    # ========== New format (dossier-level) ==========
    try:
        body = SubmitDossierDecisionRequest(**raw_body)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Build per-devis decisions based on mode
    if body.mode == "approuve_tout":
        decisions = {did: "approuve" for did in devis_ids}
    elif body.mode == "refuse_tout":
        if not body.commentaire:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Commentaire required for refuse_tout",
            )
        decisions = {did: "refuse" for did in devis_ids}
    elif body.mode == "partiel":
        if not body.decisions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="decisions list required for mode=partiel",
            )
        if not body.commentaire:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Commentaire required for mode=partiel",
            )
        decisions = {d.devis_id: d.decision for d in body.decisions}
    else:
        raise HTTPException(status_code=422, detail=f"Unknown mode: {body.mode}")

    # Submit global decision on token
    global_decision = body.mode.replace("_tout", "") if body.mode != "partiel" else "partiel"
    await approval_svc.submit_decision(token, global_decision, body.commentaire)

    results = []
    for did in devis_ids:
        decision = decisions.get(did)
        if not decision:
            continue

        new_statut = StatutDevis.APPROUVE if decision == "approuve" else StatutDevis.REFUSE
        update_data = {"statut": new_statut}
        if body.commentaire:
            update_data["valideur_commentaire"] = body.commentaire
        await valkey.update_devis(immat, numero, did, update_data)

        # Add historique entry
        action = ActionHistorique.DEVIS_APPROUVE if decision == "approuve" else ActionHistorique.DEVIS_REFUSE
        ref_key = f"{dt}:vehicules:{immat}:travaux:{numero}:devis:{did}"
        label = "approuvé" if decision == "approuve" else "refusé"
        await valkey.add_historique_entry(
            immat=immat,
            numero=numero,
            entry=HistoriqueEntry(
                auteur=token_data["valideur_email"],
                action=action,
                details=f"Devis #{did} {label}"
                        + (f" — {body.commentaire}" if body.commentaire else ""),
                ref=ref_key,
            ),
        )

        results.append({"devis_id": did, "decision": decision, "status": label})

    nb = len(results)
    return SubmitDossierDecisionResponse(
        results=results,
        message=f"{nb} devis traité(s)",
    )

