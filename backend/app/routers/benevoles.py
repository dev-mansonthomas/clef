"""Bénévoles management API endpoints for DT administration."""
import logging
from typing import Annotated, List, Dict, Any, Literal, Optional
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
    """Response model for a bénévole.

    `role` a disparu, remplacé par l'organisation détenue par CLEF :
    `responsable_ul` et `fonctions_dt`. Voir
    `docs/specs/synchronisation-referentiel-benevoles.md`.

    Les modèles TypeScript du frontend n'ont ni `telephone` ni ces deux champs :
    TypeScript ignore les propriétés supplémentaires, donc les sélecteurs de chauffeur
    continuent de fonctionner sans modification.
    """
    email: str
    nom: str
    prenom: str
    ul: Optional[str] = None
    telephone: Optional[str] = None
    nivol: Optional[str] = None
    #: Le bénévole figure aussi au référentiel sous l'UL de la délégation.
    #
    # ⚠️ Aucun droit dans CLEF, et sans rapport avec `fonctions_dt` : c'est un fait
    # d'appartenance lu dans la feuille. Exposé ici pour distinguer ces personnes dans
    # un sélecteur — un bénévole rattaché à la DT est souvent celui qu'on cherche.
    rattachement_dt: bool = False
    responsable_ul: bool = False
    fonctions_dt: List[str] = Field(default_factory=list)


class BenevoleListResponse(BaseModel):
    """Response model for list of bénévoles."""
    count: int
    benevoles: List[BenevoleResponse]


class BenevoleOrganisationUpdate(BaseModel):
    """Mise à jour partielle de l'organisation d'un bénévole.

    Ne porte **que** des champs détenus par CLEF. L'identité (nom, prénom, UL, email,
    téléphone) vient de la feuille et n'est pas modifiable ici : les champs
    supplémentaires sont ignorés par Pydantic, donc une tentative reste sans effet
    plutôt que d'être acceptée puis écrasée à la synchronisation suivante.

    Un champ à `None` signifie « ne pas modifier ».
    """
    responsable_ul: Optional[bool] = Field(
        None, description="Responsable de son unité locale"
    )
    fonctions_dt: Optional[List[str]] = Field(
        None, description="Fonctions exercées au niveau de la DT"
    )
    statut: Optional[Literal["actif", "inactif"]] = Field(
        None, description="`inactif` révoque l'accès sans effacer l'historique"
    )


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
async def update_benevole_organisation(
    dt: str,
    email: str,
    update: "BenevoleOrganisationUpdate",
    current_user: Annotated[User, Depends(require_dt_manager)],
    redis_store: Annotated[RedisService, Depends(get_redis_service)],
) -> BenevoleResponse:
    """
    Met à jour l'**organisation** d'un bénévole : responsabilité d'UL, fonctions DT,
    statut.

    **Accès** : gestionnaire DT.

    Cette route ne peut pas toucher à l'identité — nom, prénom, UL, email, téléphone
    appartiennent à la feuille « CLEF Benevoles » et sont réécrits à chaque
    synchronisation. L'endpoint précédent écrivait l'UL en nommant un responsable : la
    valeur était de toute façon rétablie à la synchronisation suivante, en laissant
    entre-temps un état incohérent.

    Mise à jour **partielle** : un champ absent du corps n'est pas modifié.

    Voir `docs/specs/synchronisation-referentiel-benevoles.md`.
    """
    # Le `{dt}` de l'URL n'est pas la source du périmètre — `get_redis_service` le
    # prend sur `current_user.dt` — mais un écart signale une requête mal formée.
    if current_user.dt != dt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this DT"
        )

    # Recherche par l'index email : à coût constant, là où l'implémentation précédente
    # parcourait tous les bénévoles de la délégation et désérialisait chaque document.
    benevole = await redis_store.get_benevole_by_email(email)
    if not benevole:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bénévole not found"
        )

    updated = await redis_store.set_benevole_organisation(
        benevole.nivol,
        responsable_ul=update.responsable_ul,
        fonctions_dt=update.fonctions_dt,
        statut=update.statut,
    )

    logger.info(
        "Organisation du bénévole %s mise à jour par %s : responsable_ul=%s, "
        "fonctions_dt=%s, statut=%s",
        updated.nivol, current_user.email, updated.responsable_ul,
        updated.fonctions_dt, updated.statut,
    )

    return BenevoleResponse(
        email=updated.email or email,
        nom=updated.nom,
        prenom=updated.prenom,
        ul=updated.ul,
        telephone=updated.telephone,
        nivol=updated.nivol,
        responsable_ul=updated.responsable_ul,
        fonctions_dt=updated.fonctions_dt,
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
        # Les bénévoles désactivés sont exclus : les laisser proposés dans un sélecteur
        # de chauffeur conduirait à attribuer une réservation à quelqu'un qui a quitté
        # le département.
        if data and data.statut == "actif":
            benevoles.append(BenevoleResponse(
                email=data.email or "",
                nom=data.nom,
                prenom=data.prenom,
                ul=data.ul,
                telephone=data.telephone,
                nivol=data.nivol,
                rattachement_dt=data.rattachement_dt,
                responsable_ul=data.responsable_ul,
                fonctions_dt=data.fonctions_dt,
            ))

    benevoles.sort(key=lambda b: (b.nom.lower(), b.prenom.lower()))

    return BenevoleListResponse(count=len(benevoles), benevoles=benevoles)
