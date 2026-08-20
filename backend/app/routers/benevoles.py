"""Bénévoles management API endpoints for DT administration."""
import logging
from typing import Annotated, List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.auth.models import User
from app.auth.dependencies import require_authenticated_user, require_dt_manager
from app.services.redis_dependencies import get_redis_service
from app.services.redis_service import RedisService
from app.models.redis_models import BenevoleData, ResponsableData

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}",
    tags=["benevoles"]
)

#: Annuaire sans segment `{dt}` dans l'URL : la délégation vient de la session.
#:
#: Ce router existe pour remplacer les routes que `main.py` déclarait en ligne — donc
#: sans aucun guard, l'annuaire des bénévoles étant public (constat C1). Les chemins
#: sont conservés à l'identique pour ne pas casser les sélecteurs de chauffeur des
#: deux applications.
directory_router = APIRouter(
    prefix="/api",
    tags=["benevoles"]
)


class BenevoleResponse(BaseModel):
    """Response model for a bénévole."""
    email: str
    nom: str
    prenom: str
    ul: Optional[str] = None
    role: Optional[str] = None
    nivol: Optional[str] = None


class BenevoleListResponse(BaseModel):
    """Response model for list of bénévoles."""
    count: int
    benevoles: List[BenevoleResponse]


class BenevoleRoleUpdate(BaseModel):
    """Request model for updating a bénévole's role."""
    role: Optional[str] = Field(None, description="New role: 'responsable_dt', 'responsable_ul', or null for regular bénévole")
    ul: Optional[str] = Field(None, description="UL for responsable_ul role")


@router.get("/benevoles", response_model=BenevoleListResponse)
async def list_benevoles(
    dt: str,
    current_user: User = Depends(require_dt_manager),
    redis_store: RedisService = Depends(get_redis_service)
) -> BenevoleListResponse:
    """
    List all bénévoles for the DT.
    
    **Access**: DT manager only
    
    Args:
        dt: DT identifier
        current_user: Current authenticated user (must be DT manager)
        redis_store: Redis service
        
    Returns:
        List of all bénévoles in the DT
    """
    # Verify DT matches user's DT
    if current_user.dt != dt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this DT"
        )
    
    # Get all benevoles from Redis (now includes responsables with role field)
    benevole_nivols = await redis_store.list_benevoles()

    benevoles = []
    for nivol in benevole_nivols:
        benevole_data = await redis_store.get_benevole(nivol)
        if benevole_data:
            benevoles.append(BenevoleResponse(
                email=benevole_data.email or "",
                nom=benevole_data.nom,
                prenom=benevole_data.prenom,
                ul=benevole_data.ul,
                role=benevole_data.role,
                nivol=benevole_data.nivol
            ))

    # For backward compatibility: also get responsables if they still exist
    # (This can be removed after migration is complete)
    try:
        responsable_emails = await redis_store.list_responsables()
        for email in responsable_emails:
            responsable_data = await redis_store.get_responsable(email)
            if responsable_data:
                # Check if already in benevoles list
                if not any(b.email == responsable_data.email for b in benevoles):
                    # Map old role to new role format
                    mapped_role = None
                    if responsable_data.role:
                        role_lower = responsable_data.role.lower()
                        if "gestionnaire" in role_lower or "dt" in role_lower:
                            mapped_role = "responsable_dt"
                        elif "ul" in role_lower or "responsable" in role_lower:
                            mapped_role = "responsable_ul"

                    benevoles.append(BenevoleResponse(
                        email=responsable_data.email,
                        nom=responsable_data.nom,
                        prenom=responsable_data.prenom,
                        ul=responsable_data.ul,
                        role=mapped_role,
                        nivol=None  # Responsables may not have NIVOL
                    ))
    except Exception as e:
        logger.warning(f"Could not fetch responsables (may have been migrated): {e}")
    
    return BenevoleListResponse(
        count=len(benevoles),
        benevoles=benevoles
    )


@router.patch("/benevoles/{email}", response_model=BenevoleResponse)
async def update_benevole_role(
    dt: str,
    email: str,
    role_update: BenevoleRoleUpdate,
    current_user: User = Depends(require_dt_manager),
    redis_store: RedisService = Depends(get_redis_service)
) -> BenevoleResponse:
    """
    Update a bénévole's role.
    
    **Access**: DT manager only
    
    Args:
        dt: DT identifier
        email: Bénévole email
        role_update: New role information
        current_user: Current authenticated user (must be DT manager)
        redis_store: Redis service
        
    Returns:
        Updated bénévole information
    """
    # Verify DT matches user's DT
    if current_user.dt != dt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this DT"
        )
    
    # Validate role value
    valid_roles = ["responsable_dt", "responsable_ul", None]
    if role_update.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {valid_roles}"
        )

    # If setting responsable_ul, UL must be provided
    if role_update.role == "responsable_ul" and not role_update.ul:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="UL must be specified for Responsable UL role"
        )

    # Find the benevole by email
    benevole_data = None
    benevole_nivols = await redis_store.list_benevoles()
    for nivol in benevole_nivols:
        b = await redis_store.get_benevole(nivol)
        if b and b.email and b.email.lower() == email.lower():
            benevole_data = b
            break

    if not benevole_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bénévole not found"
        )

    # Validate business rule: benevole from UL X cannot be responsable_ul of UL Y
    if role_update.role == "responsable_ul" and role_update.ul:
        if benevole_data.ul and benevole_data.ul != role_update.ul:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bénévole from {benevole_data.ul} cannot be responsable_ul of {role_update.ul}"
            )

    # Update the role
    benevole_data.role = role_update.role

    # Update UL if provided for responsable_ul
    if role_update.role == "responsable_ul" and role_update.ul:
        benevole_data.ul = role_update.ul

    # Save updated benevole
    await redis_store.set_benevole(benevole_data)

    # For backward compatibility: also update responsables table if it still exists
    # (This can be removed after migration is complete)
    try:
        if role_update.role in ["responsable_dt", "responsable_ul"]:
            # Map new role to old role format for backward compatibility
            old_role = "Gestionnaire DT" if role_update.role == "responsable_dt" else "Responsable UL"
            responsable_data = ResponsableData(
                email=benevole_data.email or email,
                dt=dt,
                nom=benevole_data.nom,
                prenom=benevole_data.prenom,
                role=old_role,
                perimetre=role_update.ul if role_update.role == "responsable_ul" else f"DT {dt}",
                type_perimetre="UL" if role_update.role == "responsable_ul" else "DT",
                ul=role_update.ul if role_update.role == "responsable_ul" else None
            )
            await redis_store.set_responsable(responsable_data)
        else:
            # If demoting, remove from responsables if exists
            existing_resp = await redis_store.get_responsable(email)
            if existing_resp:
                await redis_store.delete_responsable(email)
    except Exception as e:
        logger.warning(f"Could not update responsables table (may have been removed): {e}")

    return BenevoleResponse(
        email=benevole_data.email or email,
        nom=benevole_data.nom,
        prenom=benevole_data.prenom,
        ul=benevole_data.ul,
        role=benevole_data.role,
        nivol=benevole_data.nivol
    )



@directory_router.get("/benevoles", response_model=BenevoleListResponse)
async def list_benevoles_directory(
    current_user: Annotated[User, Depends(require_authenticated_user)],
    redis_store: Annotated[RedisService, Depends(get_redis_service)],
) -> BenevoleListResponse:
    """
    Annuaire des bénévoles de la délégation de l'appelant.

    **Accès** : tout utilisateur authentifié. C'est délibéré et nécessaire : le
    formulaire de réservation de l'app terrain, utilisé par les bénévoles eux-mêmes,
    a besoin de ce sélecteur de chauffeur. Le restreindre aux gestionnaires casserait
    ce parcours.

    **Périmètre** : `current_user.dt`, jamais un paramètre d'URL. C'est ce qui met
    cette route hors d'atteinte de la classe de faille C3.

    Remplace la route homonyme que `main.py` déclarait sans guard (constat C1) et qui
    lisait Google Sheets en direct. La source est désormais Redis.

    Note sur l'ordre des dépendances : l'autorisation est déclarée **avant**
    l'acquisition du datastore, contrairement aux routes de `config.py` (constat M26).
    """
    nivols = await redis_store.list_benevoles()

    benevoles: List[BenevoleResponse] = []
    for nivol in nivols:
        data = await redis_store.get_benevole(nivol)
        if data:
            benevoles.append(BenevoleResponse(
                email=data.email or "",
                nom=data.nom,
                prenom=data.prenom,
                ul=data.ul,
                role=data.role,
                nivol=data.nivol,
            ))

    benevoles.sort(key=lambda b: (b.nom.lower(), b.prenom.lower()))

    return BenevoleListResponse(count=len(benevoles), benevoles=benevoles)
