"""
Configuration API endpoints.
DT manager only access.
"""
import asyncio
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, Dict, Any, List, Optional
from pydantic import BaseModel

from app.models.config import ConfigUpdate, ConfigResponse
from app.models.valkey_models import DTConfiguration
from app.services.config_service import ConfigService
from app.services.valkey_service import ValkeyService
from app.services.valkey_dependencies import get_valkey_service
from app.services.calendar_service import calendar_service
from app.services.vehicle_document_service import vehicle_document_service
from app.auth.models import User
from app.auth.dependencies import is_dt_manager

logger = logging.getLogger(__name__)

# Mandatory folder names that cannot be removed or set to mandatory=false
MANDATORY_FOLDER_NAMES = {
    "Assurance",
    "Carte Grise",
    "Carte Total",
    "Controle Technique",
    "Factures",
    "Plan d'Entretien",
    "Sinistres",
}


class DriveFolderConfig(BaseModel):
    """Drive folder configuration."""
    folder_id: str
    folder_url: Optional[str] = None


class DocumentFolderItem(BaseModel):
    """A single document folder definition."""
    name: str
    mandatory: bool


class DocumentFoldersUpdate(BaseModel):
    """Request body for updating document folders."""
    folders: List[DocumentFolderItem]


def _extract_folder_id_from_url(url: str) -> Optional[str]:
    """Extract Google Drive folder ID from a URL.

    Supports formats:
    - https://drive.google.com/drive/folders/FOLDER_ID
    - https://drive.google.com/drive/folders/FOLDER_ID?...
    - https://drive.google.com/drive/u/0/folders/FOLDER_ID
    """
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None


router = APIRouter(
    prefix="/api/config",
    tags=["configuration"]
)


def get_config_service(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)]
) -> ConfigService:
    """Dependency to get ConfigService instance."""
    return ConfigService(valkey_service)


@router.get("", response_model=ConfigResponse)
async def get_config(
    config_service: Annotated[ConfigService, Depends(get_config_service)],
    current_user: User = Depends(is_dt_manager)
):
    """
    Get current configuration.

    **Access**: DT manager only

    Returns:
        Current configuration including URLs and email settings
    """
    config = await config_service.get_config()
    response = ConfigResponse(**config)

    # Enrich sync message with subfolder progress if sync is in_progress
    if response.drive_sync_status == 'in_progress' and response.drive_sync_message:
        valkey_service = config_service.valkey_service
        response = await _enrich_sync_message_with_subfolder_count(valkey_service, response)

    return response


@router.patch("", response_model=ConfigResponse)
async def update_config(
    updates: ConfigUpdate,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
    current_user: User = Depends(is_dt_manager)
):
    """
    Update configuration.

    **Access**: DT manager only

    When drive_folder_url is provided, extracts the folder ID from the URL,
    saves it to config, and launches Drive tree creation for all vehicles
    as a background task.

    Args:
        updates: Configuration updates (only non-null fields will be updated)

    Returns:
        Updated configuration

    Raises:
        HTTPException: If validation fails or user is not DT manager
    """
    # Convert Pydantic model to dict, excluding None values
    updates_dict = updates.model_dump(exclude_none=True)

    # If drive_folder_url is provided, extract folder_id
    drive_folder_url = updates_dict.get("drive_folder_url")
    folder_id = None
    if drive_folder_url:
        folder_id = _extract_folder_id_from_url(drive_folder_url)
        if not folder_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract folder ID from the provided Google Drive URL"
            )
        updates_dict["drive_folder_id"] = folder_id

    try:
        # Read current config BEFORE update to compare drive_folder_id
        valkey_service = config_service.valkey_service
        previous_config = await valkey_service.get_configuration()
        previous_folder_id = previous_config.drive_folder_id if previous_config else None

        updated_config = await config_service.update_config(updates_dict)

        # Only launch sync if folder_id actually changed (new URL or was previously empty)
        if folder_id and folder_id != previous_folder_id:
            # Set sync status BEFORE returning response so frontend starts polling
            dt_config = await valkey_service.get_configuration()
            if dt_config:
                dt_config.drive_sync_status = "in_progress"
                dt_config.drive_sync_processed = 0
                dt_config.drive_sync_total = 0
                dt_config.drive_sync_error = None
                dt_config.drive_sync_current_vehicle = None
                dt_config.drive_sync_cancel_requested = False
                dt_config.drive_sync_message = "Démarrage de la synchronisation..."
                await valkey_service.set_configuration(dt_config)

            asyncio.create_task(
                _run_drive_sync(valkey_service, folder_id)
            )

            # Re-read config to include the in_progress status in the response
            updated_config = await config_service.get_config()

        return ConfigResponse(**updated_config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update configuration: {str(e)}"
        )


@router.post("/drive-sync/cancel")
async def cancel_drive_sync(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """Request cancellation of the ongoing Drive sync."""
    dt_config = await valkey_service.get_configuration()
    if not dt_config or dt_config.drive_sync_status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune synchronisation en cours"
        )
    dt_config.drive_sync_cancel_requested = True
    dt_config.drive_sync_message = "Annulation en cours..."
    await valkey_service.set_configuration(dt_config)
    return {"message": "Annulation demandée"}


@router.post("/drive-sync/restart")
async def restart_drive_sync(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """Restart the Drive folder creation for all vehicles."""
    dt_config = await valkey_service.get_configuration()
    if not dt_config or not dt_config.drive_folder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun dossier Google Drive configuré"
        )
    # Reset sync state and relaunch (works even if previous sync is stuck)
    dt_config.drive_sync_status = "in_progress"
    dt_config.drive_sync_processed = 0
    dt_config.drive_sync_total = 0
    dt_config.drive_sync_error = None
    dt_config.drive_sync_current_vehicle = None
    dt_config.drive_sync_cancel_requested = False
    dt_config.drive_sync_message = "Relancement de la création des dossiers..."
    await valkey_service.set_configuration(dt_config)

    asyncio.create_task(
        _run_drive_sync(valkey_service, dt_config.drive_folder_id)
    )

    return {"message": "Synchronisation relancée", "status": "in_progress"}



async def _enrich_sync_message_with_subfolder_count(
    valkey_service: ValkeyService, response: ConfigResponse
) -> ConfigResponse:
    """Add (X/Y) subfolder count to sync message if not already present."""
    msg = response.drive_sync_message or ""
    # Skip if already has subfolder count
    if "(" in msg and "/" in msg.split("(")[-1]:
        return response

    # Try to find the current vehicle and count its folders
    current_vehicle_label = response.drive_sync_current_vehicle
    if not current_vehicle_label:
        return response

    # Extract immat from label (format: "UL XX - INDICATIF - IMMAT" or "UL XX - IMMAT")
    parts = current_vehicle_label.split(" - ")
    if len(parts) >= 2:
        immat = parts[-1].strip()
        vehicle = await valkey_service.get_vehicle(immat)
        if vehicle:
            drive_folders = vehicle.drive_folders or {}
            subfolder_count = sum(
                1 for key, val in drive_folders.items()
                if isinstance(val, dict) and val.get('folder_url')
            )
            dt_config = await valkey_service.get_configuration()
            total_folders = len(dt_config.document_folders) if dt_config and dt_config.document_folders else 11

            # Append (X/Y) to message and current_vehicle
            suffix = f" ({subfolder_count}/{total_folders})"
            response = response.model_copy(update={
                "drive_sync_message": msg + suffix,
                "drive_sync_current_vehicle": current_vehicle_label + suffix,
            })

    return response


async def _run_drive_sync(valkey_service: ValkeyService, folder_id: str) -> None:
    """Background task: create Drive tree for all vehicles with progress updates."""
    try:
        dt_config = await valkey_service.get_configuration()
        if not dt_config:
            return
        # Status was already set to in_progress by the caller
        # Just ensure cancel flag is reset
        dt_config.drive_sync_cancel_requested = False
        await valkey_service.set_configuration(dt_config)

        cancelled = False

        async def progress_callback(index: int, total: int, vehicle, subfolder_created: int = 0, subfolder_total: int = 0) -> None:
            nonlocal cancelled
            # Check for cancellation before processing each vehicle
            cfg = await valkey_service.get_configuration()
            if cfg and cfg.drive_sync_cancel_requested:
                cancelled = True
                raise asyncio.CancelledError("Sync cancelled by user")

            if cfg:
                cfg.drive_sync_status = "in_progress"
                cfg.drive_sync_processed = index
                cfg.drive_sync_total = total
                vehicle_label = f"{vehicle.dt_ul} - {vehicle.indicatif} - {vehicle.immat}" if vehicle.indicatif else f"{vehicle.dt_ul} - {vehicle.immat}"
                if subfolder_total > 0:
                    vehicle_label += f" ({subfolder_created}/{subfolder_total})"
                cfg.drive_sync_current_vehicle = vehicle_label
                cfg.drive_sync_message = f"Traitement {index}/{total}: {vehicle_label}"
                await valkey_service.set_configuration(cfg)

        try:
            count = await vehicle_document_service.ensure_vehicle_trees_for_all_vehicles(
                valkey_service=valkey_service,
                root_folder_id=folder_id,
                progress_callback=progress_callback,
            )
        except asyncio.CancelledError:
            # Cancelled by user — clean up all Drive folder data
            cfg = await valkey_service.get_configuration()
            if cfg:
                cfg.drive_folder_id = None
                cfg.drive_folder_url = None
                cfg.drive_vehicles_folder_id = None
                cfg.drive_vehicles_folder_url = None
                cfg.drive_dt_folder_id = None
                cfg.drive_dt_folder_url = None
                cfg.drive_sync_status = "idle"
                cfg.drive_sync_processed = 0
                cfg.drive_sync_total = 0
                cfg.drive_sync_cancel_requested = False
                cfg.drive_sync_current_vehicle = None
                cfg.drive_sync_message = "Synchronisation stoppée"
                cfg.drive_sync_error = None
                await valkey_service.set_configuration(cfg)

            # Clear drive_folders and documents from all vehicles
            vehicle_ids = await valkey_service.list_vehicles()
            for immat in vehicle_ids:
                vehicle = await valkey_service.get_vehicle(immat)
                if vehicle and (vehicle.drive_folders or vehicle.documents):
                    vehicle.drive_folders = {}
                    vehicle.documents = {}
                    await valkey_service.set_vehicle(vehicle)
            return

        # Mark sync as complete
        cfg = await valkey_service.get_configuration()
        if cfg:
            cfg.drive_sync_status = "complete"
            cfg.drive_sync_processed = count
            cfg.drive_sync_total = count
            cfg.drive_sync_current_vehicle = None
            cfg.drive_sync_cancel_requested = False
            cfg.drive_sync_message = f"Synchronisation terminée: {count} véhicules traités"
            await valkey_service.set_configuration(cfg)

    except Exception as e:
        logger.error(f"Drive sync failed: {e}")
        cfg = await valkey_service.get_configuration()
        if cfg:
            cfg.drive_sync_status = "error"
            cfg.drive_sync_error = str(e)
            cfg.drive_sync_message = f"Erreur: {str(e)}"
            cfg.drive_sync_current_vehicle = None
            cfg.drive_sync_cancel_requested = False
            await valkey_service.set_configuration(cfg)


@router.get("/document-folders")
async def get_document_folders(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager),
) -> List[Dict[str, Any]]:
    """
    Get the configured document folder types.

    **Access**: DT manager only

    Returns the document_folders list from DTConfiguration.
    If empty or not set, returns the defaults.
    """
    dt_config = await valkey_service.get_configuration()
    if dt_config and dt_config.document_folders:
        return dt_config.document_folders
    # Return defaults from the model
    return DTConfiguration(
        dt=current_user.dt or "DT00",
        nom="",
        gestionnaire_email="",
    ).document_folders


def _validate_mandatory_folders(folders: List[DocumentFolderItem]) -> None:
    """Validate that all mandatory folders are present and marked mandatory."""
    provided_names = {f.name for f in folders}
    missing = MANDATORY_FOLDER_NAMES - provided_names
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Les dossiers obligatoires suivants sont manquants: {', '.join(sorted(missing))}",
        )
    for f in folders:
        if f.name in MANDATORY_FOLDER_NAMES and not f.mandatory:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le dossier '{f.name}' est obligatoire et ne peut pas être défini comme non-obligatoire",
            )


@router.put("/document-folders")
async def update_document_folders(
    body: DocumentFoldersUpdate,
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager),
) -> Dict[str, Any]:
    """
    Update the document folder types configuration.

    **Access**: DT manager only

    Validates that all 7 mandatory folders are present and marked mandatory.
    """
    _validate_mandatory_folders(body.folders)

    dt_config = await valkey_service.get_configuration()
    if not dt_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration DT introuvable",
        )

    dt_config.document_folders = [f.model_dump() for f in body.folders]
    await valkey_service.set_configuration(dt_config)

    return {"message": "Configuration des dossiers mise à jour", "folders": dt_config.document_folders}


@router.post("/document-folders/sync")
async def sync_document_folders(
    body: DocumentFoldersUpdate,
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager),
) -> Dict[str, Any]:
    """
    Update document folder types and launch async sync to Google Drive.

    **Access**: DT manager only

    Saves the folder definitions, then for each vehicle:
    - Creates folders that are in config but don't exist in Drive
    - Deletes empty folders that exist in Drive but not in config
    - Skips non-empty folders (logs warning)
    """
    _validate_mandatory_folders(body.folders)

    dt_config = await valkey_service.get_configuration()
    if not dt_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration DT introuvable",
        )

    if not dt_config.drive_folder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun dossier Google Drive configuré. Configurez d'abord le dossier Drive.",
        )

    # Save folder definitions
    dt_config.document_folders = [f.model_dump() for f in body.folders]

    # Set sync status before returning
    dt_config.drive_sync_status = "in_progress"
    dt_config.drive_sync_processed = 0
    dt_config.drive_sync_total = 0
    dt_config.drive_sync_error = None
    dt_config.drive_sync_current_vehicle = None
    dt_config.drive_sync_cancel_requested = False
    dt_config.drive_sync_message = "Démarrage de la synchronisation des dossiers..."
    await valkey_service.set_configuration(dt_config)

    folder_names = [f.name for f in body.folders]
    asyncio.create_task(
        _run_folder_sync(valkey_service, dt_config.drive_folder_id, folder_names)
    )

    return {
        "message": "Synchronisation des dossiers lancée",
        "folders": dt_config.document_folders,
        "sync_status": "in_progress",
    }


async def _run_folder_sync(
    valkey_service: ValkeyService, root_folder_id: str, folder_names: list[str]
) -> None:
    """Background task: sync document folders for all vehicles."""
    try:
        dt_config = await valkey_service.get_configuration()
        if not dt_config:
            return

        vehicle_ids = await valkey_service.list_vehicles()
        vehicles = []
        for immat in vehicle_ids:
            vehicle = await valkey_service.get_vehicle(immat)
            if vehicle and vehicle.drive_folders:
                vehicles.append(vehicle)

        total = len(vehicles)
        for index, vehicle in enumerate(vehicles, start=1):
            # Check for cancellation
            cfg = await valkey_service.get_configuration()
            if cfg and cfg.drive_sync_cancel_requested:
                cfg.drive_sync_status = "idle"
                cfg.drive_sync_message = "Synchronisation annulée"
                cfg.drive_sync_cancel_requested = False
                await valkey_service.set_configuration(cfg)
                return

            vehicle_label = (
                f"{vehicle.dt_ul} - {vehicle.indicatif} - {vehicle.immat}"
                if vehicle.indicatif
                else f"{vehicle.dt_ul} - {vehicle.immat}"
            )

            if cfg:
                cfg.drive_sync_processed = index
                cfg.drive_sync_total = total
                cfg.drive_sync_current_vehicle = vehicle_label
                cfg.drive_sync_message = f"Synchronisation dossiers {index}/{total}: {vehicle_label}"
                await valkey_service.set_configuration(cfg)

            await vehicle_document_service.sync_vehicle_folders(
                valkey_service=valkey_service,
                vehicle=vehicle,
                root_folder_id=root_folder_id,
                configured_folder_names=folder_names,
            )

        # Mark complete
        cfg = await valkey_service.get_configuration()
        if cfg:
            cfg.drive_sync_status = "complete"
            cfg.drive_sync_processed = total
            cfg.drive_sync_total = total
            cfg.drive_sync_current_vehicle = None
            cfg.drive_sync_cancel_requested = False
            cfg.drive_sync_message = f"Synchronisation des dossiers terminée: {total} véhicules traités"
            await valkey_service.set_configuration(cfg)

    except Exception as e:
        logger.error(f"Folder sync failed: {e}")
        cfg = await valkey_service.get_configuration()
        if cfg:
            cfg.drive_sync_status = "error"
            cfg.drive_sync_error = str(e)
            cfg.drive_sync_message = f"Erreur: {str(e)}"
            cfg.drive_sync_current_vehicle = None
            cfg.drive_sync_cancel_requested = False
            await valkey_service.set_configuration(cfg)


@router.post("/calendar")
async def create_calendar(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """
    Create a Google Calendar for vehicle reservations.

    **Access**: DT manager only

    Returns:
        Calendar ID and URL

    Raises:
        HTTPException: If calendar already exists or creation fails
    """
    dt_id = current_user.dt or "DT75"

    # Check if calendar already exists
    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key)

    if config and config.get("calendar_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un calendrier existe déjà. Supprimez-le d'abord."
        )

    try:
        # Create the calendar
        calendar = await calendar_service.create_calendar(
            dt_id=dt_id,
            name=f"Réservations Véhicules {dt_id}",
            description="Calendrier des réservations de véhicules géré par CLEF",
        )

        # Store calendar ID in config
        if not config:
            config = {}
        config["calendar_id"] = calendar["id"]
        config["calendar_url"] = f"https://calendar.google.com/calendar/embed?src={calendar['id']}"

        await valkey_service.redis.json().set(config_key, "$", config)

        return {
            "calendar_id": calendar["id"],
            "calendar_url": config["calendar_url"],
            "message": "Calendrier créé avec succès",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create calendar: {str(e)}"
        )


@router.get("/calendar")
async def get_calendar_config(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """
    Get calendar configuration.

    **Access**: DT manager only

    Returns:
        Calendar configuration status
    """
    dt_id = current_user.dt or "DT75"

    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key)

    if not config or not config.get("calendar_id"):
        return {"configured": False}

    return {
        "configured": True,
        "calendar_id": config["calendar_id"],
        "calendar_url": config.get("calendar_url"),
    }


@router.delete("/calendar")
async def delete_calendar_config(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, str]:
    """
    Remove calendar configuration (doesn't delete the Google Calendar).

    **Access**: DT manager only

    Returns:
        Success message
    """
    dt_id = current_user.dt or "DT75"

    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key)

    if config:
        config.pop("calendar_id", None)
        config.pop("calendar_url", None)
        await valkey_service.redis.json().set(config_key, "$", config)

    return {"message": "Configuration du calendrier supprimée"}


@router.delete("/drive-sync")
async def reset_drive_sync(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """
    Reset Drive sync: remove drive folder config and sync state.
    Does NOT delete files from Google Drive (user must clean up manually).
    """
    # Clear drive-related fields from DT configuration
    dt_config = await valkey_service.get_configuration()
    if dt_config:
        dt_config.drive_folder_id = None
        dt_config.drive_folder_url = None
        dt_config.drive_vehicles_folder_id = None
        dt_config.drive_vehicles_folder_url = None
        dt_config.drive_dt_folder_id = None
        dt_config.drive_dt_folder_url = None
        dt_config.drive_sync_status = "idle"
        dt_config.drive_sync_processed = 0
        dt_config.drive_sync_total = 0
        dt_config.drive_sync_current_vehicle = None
        dt_config.drive_sync_message = None
        dt_config.drive_sync_error = None
        await valkey_service.set_configuration(dt_config)

    # Clear drive_folders and documents from all vehicles
    vehicle_ids = await valkey_service.list_vehicles()
    for immat in vehicle_ids:
        vehicle = await valkey_service.get_vehicle(immat)
        if vehicle and (vehicle.drive_folders or vehicle.documents):
            vehicle.drive_folders = {}
            vehicle.documents = {}
            await valkey_service.set_vehicle(vehicle)

    return {"message": "Synchronisation Drive supprimée. Veuillez nettoyer le contenu du dossier Google Drive manuellement."}


@router.post("/drive-folder")
async def set_drive_folder(
    config_data: DriveFolderConfig,
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """
    Configure the Google Drive folder for vehicle photos.

    **Access**: DT manager only

    Args:
        config_data: Drive folder configuration

    Returns:
        Success message with folder configuration
    """
    dt_id = current_user.dt or "DT75"

    # Get existing config
    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key) or {}

    # Update with Drive folder
    config["drive_folder_id"] = config_data.folder_id
    config["drive_folder_url"] = config_data.folder_url or f"https://drive.google.com/drive/folders/{config_data.folder_id}"

    await valkey_service.redis.json().set(config_key, "$", config)

    return {
        "message": "Drive folder configured",
        "folder_id": config_data.folder_id,
        "folder_url": config["drive_folder_url"]
    }


@router.get("/drive-folder")
async def get_drive_folder(
    valkey_service: Annotated[ValkeyService, Depends(get_valkey_service)],
    current_user: User = Depends(is_dt_manager)
) -> Dict[str, Any]:
    """
    Get configured Drive folder.

    **Access**: DT manager only

    Returns:
        Drive folder configuration status
    """
    dt_id = current_user.dt or "DT75"

    config_key = f"{dt_id}:configuration"
    config = await valkey_service.redis.json().get(config_key)

    if not config or not config.get("drive_folder_id"):
        return {"configured": False}

    return {
        "configured": True,
        "folder_id": config["drive_folder_id"],
        "folder_url": config.get("drive_folder_url"),
    }
