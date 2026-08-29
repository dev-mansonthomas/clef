"""Sync API endpoints for Google Apps Script integration."""
import os
import logging
import re
from typing import List, Dict, Any, Tuple
from fastapi import APIRouter, Header, HTTPException, status, Depends
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.services.redis_service import BenevoleIdentite, RedisService
from app.models.redis_models import VehicleData, ResponsableData, BenevoleData, ResponsableVehiculeData
from app.cache import get_cache

logger = logging.getLogger(__name__)

#: Proportion maximale de bénévoles actifs qu'une seule synchronisation peut
#: désactiver. Au-delà, la réconciliation est abandonnée : un onglet tronqué ou
#: filtré produirait sinon une révocation massive d'accès légitimes.
SYNC_MAX_DEACTIVATION_RATIO = float(os.getenv("SYNC_MAX_DEACTIVATION_RATIO", "0.2"))

router = APIRouter(
    prefix="/api/sync",
    tags=["sync"]
)


#: Colonnes de l'onglet « Bénévoles » sans lesquelles une ligne est inexploitable.
#: Déclarées explicitement — et non déduites du modèle — pour que le contrôle
#: « colonne absente de toutes les lignes » puisse **nommer** la colonne manquante,
#: plutôt que produire N erreurs de ligne identiques et illisibles.
MANDATORY_COLUMNS: Tuple[str, ...] = ("Nivol", "Nom", "Prénom", "UL", "id_structure")

#: Reconnaît une UL qui désigne la DÉLÉGATION et non une unité locale.
#
# Un bénévole porteur d'une fonction à la délégation figure DEUX FOIS au référentiel :
# une ligne pour son unité locale, une pour la DT. Observé le 2026-08-28 sur 120 des
# 4546 lignes du référentiel DT75, avec les libellés « DT DE PARIS » et
# « UNITE LOCALE DE PARIS XII ».
#
# ⚠️ La règle porte sur le LIBELLÉ, faute de colonne qui le dise. Une délégation qui
# nommerait autrement sa ligne — « DÉLÉGATION TERRITORIALE DE … » — est couverte par la
# seconde alternative ; tout autre libellé retomberait sur le traitement de doublon
# ordinaire, donc signalé, jamais silencieux.
UL_DE_DELEGATION = re.compile(r"^\s*(DT|D[ÉE]L[ÉE]GATION\s+TERRITORIALE)\b", re.I)


def est_ul_de_delegation(ul: str) -> bool:
    """`True` si ce libellé d'UL désigne la délégation elle-même."""
    return bool(UL_DE_DELEGATION.match(ul or ""))


#: Raisons d'erreur de ligne — des CONSTANTES, jamais des phrases interpolées.
#
# ⚠️ Elles ne portent AUCUNE donnée. Tout ce qui varie — nivol, nom, prénom, libellés
# d'UL, nom de champ — passe par `values`, que l'Apps Script écrit dans des colonnes
# séparées de l'onglet « ERREURS SYNCHRO ».
#
# Ce n'est pas de l'esthétique : une raison interpolée n'est ni triable ni
# dénombrable. Trier par UL pour traiter une unité locale à la fois était impossible,
# et regrouper par nature exigeait d'effacer les valeurs à coups d'expressions
# régulières — donc de deviner ce qui variait.
RAISON_COLONNE_ABSENTE = "Colonne absente"
RAISON_CHAMP_INVALIDE = "Champ invalide"
RAISON_UL_DIVERGENTES = "Doublon : unités locales différentes"
RAISON_UL_DIVERGENTES_MULTIPLES = "Doublon : plus de deux unités locales"
RAISON_IDENTITE_DIVERGENTE = "Doublon : identité divergente"


class BenevoleReferentielRow(BaseModel):
    """Une ligne de l'onglet « Bénévoles » du classeur « CLEF Benevoles ».

    Les alias sont les **libellés de colonnes de la feuille** : l'Apps Script envoie
    des objets dont les clés sont les en-têtes. C'était jusqu'ici un contrat implicite
    — le modèle attendait des noms anglais en minuscules, si bien qu'un `Nom`
    majuscule faisait échouer la synchronisation entière.

    La colonne `Prénom Nom` est une concaténation de commodité : Pydantic l'ignore,
    comme tout champ supplémentaire.

    Cette ligne ne porte que de l'**identité**. Le statut, la responsabilité d'UL et
    les fonctions DT appartiennent à CLEF : ils ne peuvent structurellement pas être
    écrasés par une synchronisation.
    """
    nivol: str = Field(..., alias="Nivol")
    nom: str = Field(..., alias="Nom")
    prenom: str = Field(..., alias="Prénom")
    ul: str = Field(..., alias="UL")
    telephone: str | None = Field(None, alias="Téléphone")
    email: str | None = Field(None, alias="Email")

    #: Identifiant interne Croix-Rouge de l'UNITÉ LOCALE du bénévole. OBLIGATOIRE.
    #
    # ⚠️ Pourquoi il est obligatoire : l'UL d'un bénévole est sinon un LIBELLÉ LIBRE
    # (« UNITE LOCALE DE PARIS XII »), et c'est sur lui que se ferait la jointure avec le
    # référentiel national des structures. Une variante d'orthographe, un accent
    # décomposé, et le bénévole se retrouve sans UL connue donc sans périmètre — le mode
    # de panne déjà rencontré sur les en-têtes de colonnes. Cet identifiant rend la
    # jointure STRICTE, ce qui n'a de valeur que s'il est toujours là.
    #
    # ⚠️ Conservé en `str`, pas en `int` : c'est un identifiant, jamais un nombre sur
    # lequel on calcule. La validation vérifie qu'il EST un entier positif — une
    # cellule numérique de Sheets arrive en `int`, une cellule texte avec des espaces
    # arrive avec ses espaces — et la valeur retenue est sa forme canonique.
    ul_id_structure: str = Field(..., alias="id_structure")

    model_config = {"populate_by_name": True}

    @field_validator("nivol", "nom", "prenom", "ul", mode="before")
    @classmethod
    def _required_not_blank(cls, v):
        """Une cellule vide n'est pas une valeur : la feuille en contient.

        Sans cela, `""` passerait la validation `str` et produirait un bénévole sans
        clé primaire ou sans UL.
        """
        if v is None:
            raise ValueError("valeur absente")
        v = str(v).strip()
        if not v:
            raise ValueError("valeur vide")
        return v

    @field_validator("ul_id_structure", mode="before")
    @classmethod
    def _entier_positif(cls, v):
        """Un identifiant de structure est un entier positif, et rien d'autre.

        Accepter « 0 », « -1 » ou « UL PARIS12 » produirait une jointure qui échoue plus
        tard, loin d'ici, sur un bénévole précis — alors que le défaut est dans la
        colonne. Refuser à la ligne le nomme tout de suite.
        """
        if v is None:
            raise ValueError("valeur absente")
        # Une cellule numérique de Sheets arrive en int ou float (889 ou 889.0).
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        texte = str(v).strip()
        if not texte:
            raise ValueError("valeur vide")
        if not texte.isdigit() or int(texte) <= 0:
            raise ValueError("doit être un entier positif")
        return str(int(texte))

    @field_validator("telephone", "email", mode="before")
    @classmethod
    def _optional_blank_is_none(cls, v):
        if v is None:
            return None
        v = str(v).strip()
        return v or None


def parse_referentiel_rows(
    rows: List[Dict[str, Any]]
) -> Tuple[List[BenevoleIdentite], List[Dict[str, Any]]]:
    """Valide les lignes **une par une** et renvoie (identités, erreurs).

    C'est ce qui remplace le tout-ou-rien : le corps était typé
    `List[BenevoleSync]`, donc validé par Pydantic *avant* d'entrer dans le handler —
    une seule ligne malformée rejetait le lot entier en 422.

    Les numéros de ligne rapportés sont ceux de la **feuille** : en-tête en ligne 1,
    données à partir de la ligne 2, pour qu'une erreur soit retrouvable à l'œil.

    En cas de NIVOL en doublon, la **dernière** occurrence gagne, et le doublon est
    signalé : deux lignes pour une même personne est une anomalie de la feuille.

    Returns:
        `(identites, errors)` — `errors` porte `line`, une `reason` **constante** (voir
        les `RAISON_*`) et un dictionnaire `values` structuré : `Nivol`, `Nom`,
        `Prénom`, `UL 1`, `UL 2`, `Détail`, selon la nature.

    ⚠️ `values` portait auparavant le seul nivol, « pour ne pas déverser de données
    personnelles dans des journaux à audience plus large que la base ». La précaution
    reste, mais son périmètre était mal posé : ces valeurs sont écrites par l'Apps
    Script dans un onglet du classeur **qui contient déjà** ces personnes — le public
    est exactement le même. Ce qui compte est ailleurs, et tient toujours : le SERVEUR
    ne journalise que des compteurs et des nivols, jamais ces `values`.
    """
    errors: List[Dict[str, Any]] = []

    # Passe 1 — valider chaque ligne indépendamment, en gardant son numéro de feuille.
    parsees: Dict[str, List[Tuple[int, BenevoleReferentielRow]]] = {}

    for index, row in enumerate(rows, start=2):
        missing = [c for c in MANDATORY_COLUMNS if c not in row]
        if missing:
            errors.append({
                "line": index,
                "reason": RAISON_COLONNE_ABSENTE,
                "values": {
                    "Nivol": str(row.get("Nivol", "")),
                    "Détail": ", ".join(missing),
                },
            })
            continue

        try:
            parsed = BenevoleReferentielRow(**row)
        except ValidationError as exc:
            champs = ", ".join(
                str(e["loc"][0]) if e["loc"] else "?" for e in exc.errors()
            )
            errors.append({
                "line": index,
                "reason": RAISON_CHAMP_INVALIDE,
                "values": {
                    "Nivol": str(row.get("Nivol", "")),
                    "Nom": str(row.get("Nom", "")),
                    "Prénom": str(row.get("Prénom", "")),
                    "Détail": champs,
                },
            })
            continue

        parsees.setdefault(parsed.nivol, []).append((index, parsed))

    # Passe 2 — fusionner les occurrences d'un même NIVOL.
    #
    # ⚠️ « La dernière occurrence gagne » était faux, et pas seulement imprécis.
    #
    # Un bénévole porteur d'une fonction à la délégation figure DEUX FOIS au
    # référentiel : une ligne sous son unité locale, une sous la DT. Conserver la
    # dernière faisait dépendre son UL de l'ORDRE DES LIGNES de la feuille — et
    # perdait, une fois sur deux, la seule information utile des deux : l'unité locale
    # réelle. Observé le 2026-08-28 : 120 « doublons » sur 4546 lignes, tous de cette
    # nature.
    #
    # La fusion conserve l'unité locale réelle et note le rattachement à la DT. Ce
    # n'est pas une erreur, donc ce n'est pas signalé comme telle. Un doublon qui ne
    # s'explique PAS par ce partage — deux unités locales différentes, ou une identité
    # qui diverge — reste signalé : c'est une anomalie de la feuille.
    identites: List[BenevoleIdentite] = []

    for nivol, occurrences in parsees.items():
        lignes_dt = [(i, p) for i, p in occurrences if est_ul_de_delegation(p.ul)]
        lignes_ul = [(i, p) for i, p in occurrences if not est_ul_de_delegation(p.ul)]

        # L'unité locale réelle prime sur le libellé de la délégation.
        reference = (lignes_ul or lignes_dt)[-1][1]

        uls_distinctes = {p.ul for _, p in lignes_ul}
        if len(uls_distinctes) > 1:
            # ⚠️ Le NIVOL n'est PAS répété dans la raison : il est dans `values`, que
            # l'Apps Script écrit dans sa propre colonne. Le répéter allongeait chaque
            # message d'une information déjà à l'écran, et rendait le regroupement par
            # nature dépendant d'un effacement de motif.
            triees = sorted(uls_distinctes)
            errors.append({
                "line": lignes_ul[-1][0],
                "reason": (
                    RAISON_UL_DIVERGENTES if len(triees) == 2
                    else RAISON_UL_DIVERGENTES_MULTIPLES
                ),
                "values": {
                    "Nivol": nivol,
                    "Nom": reference.nom,
                    "Prénom": reference.prenom,
                    "UL 1": triees[0],
                    "UL 2": triees[1],
                    # Au-delà de deux, les colonnes ne suffisent plus : le reste va au
                    # détail, et la raison le dit — plutôt que de laisser croire que
                    # deux colonnes décrivent tout.
                    "Détail": ", ".join(triees[2:]),
                },
            })

        # Une divergence d'identité entre deux lignes du même NIVOL est une anomalie :
        # deux personnes sous un même matricule, ou une saisie corrigée d'un seul côté.
        for champ in ("nom", "prenom", "email", "telephone"):
            valeurs = {getattr(p, champ) for _, p in occurrences if getattr(p, champ)}
            if len(valeurs) > 1:
                errors.append({
                    "line": occurrences[-1][0],
                    "reason": RAISON_IDENTITE_DIVERGENTE,
                    "values": {
                        "Nivol": nivol,
                        "Nom": reference.nom,
                        "Prénom": reference.prenom,
                        "Détail": f"{champ} : {len(valeurs)} valeurs",
                    },
                })

        identites.append(BenevoleIdentite(
            nivol=reference.nivol,
            nom=reference.nom,
            prenom=reference.prenom,
            ul=reference.ul,
            ul_id_structure=reference.ul_id_structure,
            email=reference.email,
            telephone=reference.telephone,
            rattachement_dt=bool(lignes_dt),
        ))

    return identites, errors


class ResponsableVehiculeSync(BaseModel):
    """Responsable véhicule data for sync from Apps Script."""
    nivol: str = Field(..., description="NIVOL identifier")
    nom: str = Field(..., description="Last name")
    prenom: str = Field(..., description="First name")
    ul: str = Field(..., description="Unité Locale")
    telephone: str = Field(..., description="Phone number")
    email: str = Field(..., description="Email address")


class SyncResponse(BaseModel):
    """Response for sync operations."""
    success: bool
    count: int
    message: str


async def verify_api_key(dt: str, x_api_key: str = Header(...)) -> None:
    """
    Vérifie que la clé API appartient à **la délégation de l'URL**.

    Correctif du constat **C3**. La garde précédente comparait la clé à un
    `SYNC_API_KEY` global, sans aucun lien avec le `{dt}` demandé : son porteur
    pouvait lire et **écraser** bénévoles, responsables et véhicules de *toutes* les
    délégations. Une clé de synchronisation est un credential ; elle doit être cadrée.

    `dt` est injecté depuis le paramètre de chemin par FastAPI, et
    `RedisService.validate_api_key` ne cherche la clé que dans la configuration de
    cette délégation — le cadrage est donc structurel, pas déclaratif.

    Les clés sont créées par l'écran de configuration
    (`RedisService.generate_api_key_dt`).

    Args:
        dt: identifiant de délégation, issu du chemin
        x_api_key: clé fournie dans l'en-tête `X-API-Key`

    Raises:
        HTTPException: 401 si la clé est absente, inconnue, ou propre à une autre
            délégation.
    """
    redis_store = await get_redis_for_dt(dt)

    if not await redis_store.validate_api_key(x_api_key):
        # Ne pas distinguer « clé inconnue » de « clé d'une autre délégation » :
        # ce serait renseigner un appelant illégitime.
        logger.warning("Clé API refusée pour %s", dt)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )


async def get_redis_for_dt(dt: str) -> RedisService:
    """
    Get RedisService instance for a specific DT.
    
    Args:
        dt: DT identifier (e.g., "DT75")
        
    Returns:
        RedisService instance
        
    Raises:
        HTTPException: If Redis is not available
    """
    cache = get_cache()
    
    if not cache._connected:
        await cache.connect()
    
    if not cache.client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available"
        )
    
    return RedisService(redis_client=cache.client, dt=dt)


@router.get("/{dt}/vehicules")
async def get_vehicules_for_sync(
    dt: str,
    _: None = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """
    Get all vehicles for a DT (for Apps Script sync).

    Args:
        dt: DT identifier (e.g., "DT75")

    Returns:
        List of vehicle dictionaries
    """
    redis_store = await get_redis_for_dt(dt)

    # Get all vehicle IDs
    vehicle_ids = await redis_store.list_vehicles()

    # Fetch all vehicles
    vehicles = []
    for immat in vehicle_ids:
        vehicle = await redis_store.get_vehicle(immat)
        if vehicle:
            vehicles.append(vehicle.model_dump())

    logger.info(f"Sync API: Retrieved {len(vehicles)} vehicles for {dt}")
    return vehicles


@router.get("/{dt}/vehicules/{ul_id}")
async def get_vehicules_for_ul(
    dt: str,
    ul_id: str,
    x_api_key: str = Header(...)
) -> List[Dict[str, Any]]:
    """
    Get vehicles for a specific UL (for Apps Script sync at UL level).

    Args:
        dt: DT identifier (e.g., "DT75")
        ul_id: UL identifier (e.g., "81")
        x_api_key: API key from X-API-Key header

    Returns:
        List of vehicle dictionaries filtered by UL
    """
    redis_store = await get_redis_for_dt(dt)

    # Validate API key for this UL
    if not await redis_store.validate_api_key(x_api_key, ul_id=ul_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key for this UL"
        )

    # Get UL name to match against vehicle dt_ul field
    ul_data = await redis_store.redis.json().get(redis_store._key("unite_locale", ul_id))
    if not ul_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UL {ul_id} not found"
        )

    ul_name = ul_data.get("nom")

    # Get all vehicle IDs
    vehicle_ids = await redis_store.list_vehicles()

    # Fetch and filter vehicles by UL name
    vehicles = []
    for immat in vehicle_ids:
        vehicle = await redis_store.get_vehicle(immat)
        # Match by UL name (dt_ul field contains the full UL name)
        if vehicle and vehicle.dt_ul == ul_name:
            vehicles.append(vehicle.model_dump())

    logger.info(f"Sync API: Retrieved {len(vehicles)} vehicles for {dt} UL {ul_id} ({ul_name})")
    return vehicles


@router.get("/{dt}/responsables")
async def get_responsables_for_sync(
    dt: str,
    _: None = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """
    Get all responsables for a DT (for Apps Script sync).
    
    Args:
        dt: DT identifier (e.g., "DT75")
        
    Returns:
        List of responsable dictionaries
    """
    redis_store = await get_redis_for_dt(dt)
    
    # Get all responsable emails
    responsable_emails = await redis_store.list_responsables()
    
    # Fetch all responsables
    responsables = []
    for email in responsable_emails:
        responsable = await redis_store.get_responsable(email)
        if responsable:
            responsables.append(responsable.model_dump())
    
    logger.info(f"Sync API: Retrieved {len(responsables)} responsables for {dt}")
    return responsables


class BenevoleSyncResult(BaseModel):
    """Résultat détaillé d'une synchronisation du référentiel bénévoles.

    Renvoyé en 200 même en présence d'erreurs de ligne : un lot partiellement valide
    est importé partiellement, et l'Apps Script journalise le détail dans l'onglet
    TECHLOG — sans quoi une synchronisation à moitié réussie passerait pour un succès.
    """
    success: bool
    created: int
    updated: int
    reactivated: int
    deactivated: int
    #: Bénévoles figurant aussi sous l'UL de la délégation — fusionnés, pas en erreur.
    rattachements_dt: int = 0
    errors: List[Dict[str, Any]]
    reconciliation_skipped: bool
    reconciliation_skipped_reason: str | None = None


@router.post("/{dt}/benevoles", response_model=BenevoleSyncResult)
async def sync_benevoles(
    dt: str,
    rows: List[Dict[str, Any]],
    _: None = Depends(verify_api_key)
) -> BenevoleSyncResult:
    """
    Synchronise le référentiel bénévoles depuis « CLEF Benevoles » vers Redis.

    Le lot est un **instantané complet** de la délégation : c'est ce qui autorise la
    réconciliation. Deux propriétés, opposées mais également nécessaires :

    - **Fusion** — la feuille écrase l'identité (nivol, nom, prénom, UL, téléphone,
      email) et ne touche **jamais** à l'organisation détenue par CLEF (statut,
      responsabilité d'UL, fonctions DT).
    - **Réconciliation** — un bénévole absent du lot est passé à `inactif`, ce qui
      révoque son accès sans effacer l'historique qui le référence.

    Chaque ligne est validée **indépendamment** : une ligne fautive n'emporte pas le
    lot. Voir `docs/specs/synchronisation-referentiel-benevoles.md`.

    Args:
        dt: identifiant de délégation, qui cadre aussi la clé API acceptée
        rows: lignes brutes de l'onglet, clés = libellés de colonnes

    Returns:
        Compteurs par opération et erreurs situées à la ligne
    """
    redis_store = await get_redis_for_dt(dt)

    identites, errors = parse_referentiel_rows(rows)

    counts = {"created": 0, "updated": 0, "reactivated": 0}
    for identite in identites:
        try:
            outcome = await redis_store.upsert_benevole_identite(identite)
            counts[outcome] += 1
        except Exception as e:
            logger.error("Échec d'écriture du bénévole %s : %s", identite.nivol, e)
            errors.append({
                "line": None,
                "reason": f"Écriture impossible : {e}",
                "values": {"Nivol": identite.nivol},
            })

    reconciliation = await redis_store.deactivate_benevoles_absent_from(
        {i.nivol for i in identites},
        max_ratio=SYNC_MAX_DEACTIVATION_RATIO,
    )

    logger.info(
        "Sync bénévoles %s : %d créés, %d mis à jour, %d réactivés, %d désactivés, "
        "%d erreurs de ligne",
        dt, counts["created"], counts["updated"], counts["reactivated"],
        reconciliation["deactivated"], len(errors)
    )

    return BenevoleSyncResult(
        success=True,
        created=counts["created"],
        updated=counts["updated"],
        reactivated=counts["reactivated"],
        deactivated=reconciliation["deactivated"],
        rattachements_dt=sum(1 for i in identites if i.rattachement_dt),
        errors=errors,
        reconciliation_skipped=reconciliation["skipped"],
        reconciliation_skipped_reason=reconciliation["reason"],
    )


@router.post("/{dt}/responsables", response_model=SyncResponse)
async def sync_responsables_vehicules(
    dt: str,
    responsables: List[ResponsableVehiculeSync],
    _: None = Depends(verify_api_key)
) -> SyncResponse:
    """
    Sync responsables véhicules from Apps Script to Redis.

    Args:
        dt: DT identifier (e.g., "DT75")
        responsables: List of responsable véhicule data from spreadsheet

    Returns:
        Sync response with count of processed records
    """
    redis_store = await get_redis_for_dt(dt)

    processed = 0
    for resp_data in responsables:
        try:
            # Create ResponsableVehiculeData instance
            responsable = ResponsableVehiculeData(
                email=resp_data.email,
                nivol=resp_data.nivol,
                nom=resp_data.nom,
                prenom=resp_data.prenom,
                ul=resp_data.ul,
                telephone=resp_data.telephone
            )

            # Store in Redis
            success = await redis_store.set_responsable_vehicule(responsable)
            if success:
                processed += 1
        except Exception as e:
            logger.error(f"Error syncing responsable véhicule {resp_data.email}: {e}")
            continue

    logger.info(f"Sync API: Processed {processed}/{len(responsables)} responsables véhicules for {dt}")

    return SyncResponse(
        success=True,
        count=processed,
        message=f"Successfully synced {processed} responsables véhicules"
    )


@router.get("/{dt}/responsables/vehicules")
async def get_responsables_vehicules_for_sync(
    dt: str,
    _: None = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """
    Get all responsables véhicules for a DT (for Apps Script sync).

    Args:
        dt: DT identifier (e.g., "DT75")

    Returns:
        List of responsable véhicule dictionaries
    """
    redis_store = await get_redis_for_dt(dt)

    # Get all responsables véhicules
    responsables = await redis_store.get_all_responsables_vehicules()

    logger.info(f"Sync API: Retrieved {len(responsables)} responsables véhicules for {dt}")
    return [r.model_dump() for r in responsables]

