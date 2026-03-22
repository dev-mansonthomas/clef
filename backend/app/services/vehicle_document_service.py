"""Google Drive document management for vehicle admin."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

from fastapi import HTTPException, status

from app.models.valkey_models import VehicleData
from app.models.vehicle import (
    VehicleDocumentType,
    VehicleDriveDocument,
    VehicleDriveDocumentsResponse,
    VehicleDriveFile,
    VehicleDriveFileListResponse,
)
from app.services.drive_service import drive_service
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)


DOCUMENT_CONFIG: dict[VehicleDocumentType, dict[str, Any]] = {
    VehicleDocumentType.CARTE_GRISE: {
        "label": "Carte grise",
        "folder_name": "Carte Grise",
        "managed": True,
    },
    VehicleDocumentType.CARTE_TOTAL: {
        "label": "Carte Total",
        "folder_name": "Carte Total",
        "managed": True,
    },
    VehicleDocumentType.PLAN_ENTRETIEN: {
        "label": "Plan d'entretien",
        "folder_name": "Plan d'Entretien",
        "managed": True,
    },
    VehicleDocumentType.FACTURES: {
        "label": "Dossier Réparation",
        "folder_name": "Dossier Réparation",
        "managed": False,
    },
    VehicleDocumentType.ASSURANCE: {
        "label": "Assurance",
        "folder_name": "Assurance",
        "managed": True,
    },
    VehicleDocumentType.CONTROLE_TECHNIQUE: {
        "label": "Controle Technique",
        "folder_name": "Controle Technique",
        "managed": False,
    },
    VehicleDocumentType.CARNET_SUIVI: {
        "label": "Carnet de suivi",
        "folder_name": "Carnet de Bord - Documentation CRF",
        "managed": False,
    },
    VehicleDocumentType.COMMANDE: {
        "label": "Commande",
        "folder_name": "Commande",
        "managed": False,
    },
    VehicleDocumentType.DOCUMENTATION_TECHNIQUE: {
        "label": "Documentation Technique",
        "folder_name": "Documentation Technique",
        "managed": False,
    },
    VehicleDocumentType.PHOTOS: {
        "label": "Photos",
        "folder_name": "Photos",
        "managed": False,
    },
    VehicleDocumentType.SINISTRES: {
        "label": "Sinistres",
        "folder_name": "Sinistres",
        "managed": False,
    },
}

MANAGED_DOCUMENT_TYPES = (
    VehicleDocumentType.CARTE_GRISE,
    VehicleDocumentType.CARTE_TOTAL,
    VehicleDocumentType.PLAN_ENTRETIEN,
    VehicleDocumentType.ASSURANCE,
)
MANAGED_DOCUMENT_TYPE_SET = set(MANAGED_DOCUMENT_TYPES)


class VehicleDocumentService:
    """Manage Drive-backed vehicle documents and their current associations."""

    async def ensure_vehicle_trees_for_all_vehicles(
        self,
        valkey_service: ValkeyService,
        root_folder_id: str,
        progress_callback: Callable[..., Awaitable[None]] | None = None,
    ) -> tuple[int, list[str]]:
        """Ensure the Google Drive folder tree exists for every vehicle in the DT.

        Returns:
            A tuple of (ensured_count, errors) where errors is a list of
            error descriptions for vehicles that failed.
        """
        if not root_folder_id:
            return 0, []

        vehicle_ids = await valkey_service.list_vehicles()
        vehicles: list[VehicleData] = []
        for immat in vehicle_ids:
            vehicle = await valkey_service.get_vehicle(immat)
            if vehicle:
                vehicles.append(vehicle)

        vehicles.sort(
            key=lambda vehicle: (
                (vehicle.dt_ul or "").casefold(),
                (vehicle.indicatif or "").casefold(),
                (vehicle.nom_synthetique or "").casefold(),
                (vehicle.immat or "").casefold(),
            )
        )

        total_vehicles = len(vehicles)
        ensured_count = 0
        errors: list[str] = []
        # Get total configured folders for subfolder progress reporting
        dt_config = await valkey_service.get_configuration()
        total_folders = len(dt_config.document_folders) if dt_config and dt_config.document_folders else len(DOCUMENT_CONFIG)

        for index, vehicle in enumerate(vehicles, start=1):
            if progress_callback:
                await progress_callback(index, total_vehicles, vehicle)

            try:
                await self._ensure_vehicle_tree(valkey_service, vehicle, root_folder_id)
            except Exception as e:
                logger.error(f"Failed to ensure tree for vehicle {vehicle.immat}: {e}")
                errors.append(f"{vehicle.immat}: {str(e)}")
                continue

            # Report updated subfolder progress AFTER processing
            if progress_callback:
                drive_folders = vehicle.drive_folders or {}
                subfolder_count = sum(
                    1 for key, val in drive_folders.items()
                    if isinstance(val, dict) and val.get('folder_url')
                )
                await progress_callback(index, total_vehicles, vehicle, subfolder_count, total_folders)

            ensured_count += 1

        return ensured_count, errors

    async def get_documents_overview(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
    ) -> VehicleDriveDocumentsResponse:
        """Return the Drive overview for a vehicle using cached folder data from Valkey."""
        root_config = await self._get_drive_root(valkey_service)
        documents = self._build_empty_documents()

        if not root_config["folder_id"]:
            return VehicleDriveDocumentsResponse(
                configured=False,
                root_folder_id=None,
                root_folder_url=None,
                vehicle_folder_name=vehicle.nom_synthetique,
                vehicle_folder_id=None,
                vehicle_folder_url=None,
                documents=documents,
            )

        # Use cached folder data from Valkey — NO Drive API calls needed
        drive_folders = getattr(vehicle, "drive_folders", {}) or {}

        if not drive_folders.get("vehicle_folder_id"):
            # No cached data — need to build tree (first time only)
            try:
                await self._ensure_vehicle_tree(valkey_service, vehicle, root_config["folder_id"])
            except Exception as e:
                logger.error(f"Failed to ensure Drive tree for vehicle {vehicle.immat}: {e}")
                return VehicleDriveDocumentsResponse(
                    configured=True,
                    root_folder_id=root_config["folder_id"],
                    root_folder_url=root_config.get("folder_url"),
                    vehicle_folder_name=vehicle.nom_synthetique,
                    vehicle_folder_id=None,
                    vehicle_folder_url=None,
                    documents=documents,
                    error=f"Erreur d'accès aux dossiers Google Drive: {e}",
                )
            # After _ensure_vehicle_tree, drive_folders is now populated
            drive_folders = vehicle.drive_folders or {}

        # Populate folder info from cache
        for document_type in DOCUMENT_CONFIG:
            cached = drive_folders.get(document_type.value)
            if cached and isinstance(cached, dict):
                documents[document_type].folder_id = cached.get("folder_id")
                documents[document_type].folder_url = cached.get("folder_url")

        # Populate current file from stored documents (also in Valkey — no Drive API)
        stored_documents = getattr(vehicle, "documents", {}) or {}
        for document_type in MANAGED_DOCUMENT_TYPES:
            stored_file = stored_documents.get(document_type.value)
            if stored_file:
                documents[document_type].current_file = self._serialize_file(
                    stored_file,
                    stored_file=stored_file,
                )
                # file_count = 1 if we have a current file (we don't need exact count from Drive)
                documents[document_type].file_count = 1

        return VehicleDriveDocumentsResponse(
            configured=True,
            root_folder_id=root_config["folder_id"],
            root_folder_url=root_config["folder_url"],
            vehicle_folder_name=vehicle.nom_synthetique,
            vehicle_folder_id=drive_folders.get("vehicle_folder_id"),
            vehicle_folder_url=drive_folders.get("vehicle_folder_url"),
            documents=documents,
        )

    async def list_document_files(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
        document_type: VehicleDocumentType,
    ) -> VehicleDriveFileListResponse:
        """List files in a managed vehicle document folder."""
        self._ensure_managed_document(document_type)
        folder = await self._get_document_folder(valkey_service, vehicle, document_type)
        files = await self._list_folder_files(valkey_service, folder_id=folder["id"])
        return VehicleDriveFileListResponse(
            files=[self._serialize_file(file, folder=folder) for file in files]
        )

    async def associate_existing_file(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
        document_type: VehicleDocumentType,
        file_id: str,
    ) -> VehicleDriveDocument:
        """Select an existing file in the folder as the current document."""
        self._ensure_managed_document(document_type)
        folder = await self._get_document_folder(valkey_service, vehicle, document_type)
        files = await self._list_folder_files(valkey_service, folder_id=folder["id"])
        selected_file = next((file for file in files if file["id"] == file_id), None)

        if not selected_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in the selected Drive folder",
            )

        # Rename the file in Drive to match the standard naming convention
        original_name = selected_file.get("name", "")
        extension = Path(original_name).suffix if original_name else ""
        label = DOCUMENT_CONFIG[document_type]["label"]
        new_name = f"{vehicle.nom_synthetique} - {label}{extension}"
        await drive_service.rename_file(
            dt_id=valkey_service.dt,
            file_id=file_id,
            new_name=new_name,
        )
        selected_file["name"] = new_name

        stored_file = self._build_stored_file(selected_file, folder)
        await self._persist_document_selection(valkey_service, vehicle, document_type, stored_file)

        return VehicleDriveDocument(
            key=document_type,
            label=DOCUMENT_CONFIG[document_type]["label"],
            folder_name=DOCUMENT_CONFIG[document_type]["folder_name"],
            managed=True,
            folder_id=folder.get("id"),
            folder_url=folder.get("webViewLink"),
            file_count=len(files),
            current_file=self._serialize_file(selected_file, stored_file=stored_file, folder=folder),
        )

    async def upload_document(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
        document_type: VehicleDocumentType,
        file_content: bytes,
        filename: str,
        mime_type: str,
    ) -> VehicleDriveDocument:
        """Upload a new document version and make it the current association."""
        self._ensure_managed_document(document_type)
        folder = await self._get_document_folder(valkey_service, vehicle, document_type)

        # Check if there's already a file for this document type
        existing_documents = getattr(vehicle, "documents", {}) or {}
        existing_file = existing_documents.get(document_type.value)
        existing_file_id = existing_file.get("file_id") if existing_file else None

        if existing_file_id:
            # Ensure the first revision is kept forever (it may have been uploaded outside CLEF)
            await drive_service.ensure_first_revision_kept(
                dt_id=valkey_service.dt,
                file_id=existing_file_id,
            )
            # Update existing file with new version (Google Drive versioning)
            uploaded_file = await drive_service.update_file_version(
                dt_id=valkey_service.dt,
                file_id=existing_file_id,
                file_content=file_content,
                mime_type=mime_type,
                keep_forever=True,
            )
        else:
            # First upload — create new file
            upload_name = self._build_upload_filename(document_type, filename, vehicle.nom_synthetique)
            uploaded_file = await drive_service.upload_file(
                dt_id=valkey_service.dt,
                file_content=file_content,
                filename=upload_name,
                mime_type=mime_type,
                parent_folder_id=folder["id"],
                description=f"{DOCUMENT_CONFIG[document_type]['label']} - {vehicle.nom_synthetique}",
            )

        stored_file = self._build_stored_file(uploaded_file, folder)
        await self._persist_document_selection(valkey_service, vehicle, document_type, stored_file)

        files = await self._list_folder_files(valkey_service, folder_id=folder["id"])
        return VehicleDriveDocument(
            key=document_type,
            label=DOCUMENT_CONFIG[document_type]["label"],
            folder_name=DOCUMENT_CONFIG[document_type]["folder_name"],
            managed=True,
            folder_id=folder.get("id"),
            folder_url=folder.get("webViewLink"),
            file_count=max(len(files), 1),
            current_file=self._serialize_file(uploaded_file, stored_file=stored_file, folder=folder),
        )

    async def _get_drive_root(self, valkey_service: ValkeyService) -> dict[str, str | None]:
        config_key = f"{valkey_service.dt}:configuration"
        config = await valkey_service.redis.json().get(config_key) or {}
        return {
            "folder_id": config.get("drive_folder_id"),
            "folder_url": config.get("drive_folder_url"),
        }

    async def _rename_legacy_factures_folder(
        self,
        valkey_service: ValkeyService,
        vehicle_folder: dict[str, Any],
    ) -> None:
        """Rename legacy 'Factures' folder to 'Dossier Réparation' if it exists."""
        old_folder = await drive_service.find_folder(
            dt_id=valkey_service.dt,
            name="Factures",
            parent_folder_id=vehicle_folder["id"],
        )
        if not old_folder:
            return
        new_folder = await drive_service.find_folder(
            dt_id=valkey_service.dt,
            name="Dossier Réparation",
            parent_folder_id=vehicle_folder["id"],
        )
        if new_folder:
            return  # already renamed / both exist — skip
        await drive_service.rename_file(
            dt_id=valkey_service.dt,
            file_id=old_folder["id"],
            new_name="Dossier Réparation",
        )
        logger.info(
            f"Renamed 'Factures' → 'Dossier Réparation' in {vehicle_folder.get('name', vehicle_folder['id'])}"
        )

    async def _ensure_vehicle_tree(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
        root_folder_id: str,
        folder_names: list[str] | None = None,
    ) -> dict[str, Any]:
        vehicles_root = await drive_service.get_or_create_folder(
            dt_id=valkey_service.dt,
            name="Véhicules",
            parent_folder_id=root_folder_id,
        )
        perimeter_folder = await drive_service.get_or_create_folder(
            dt_id=valkey_service.dt,
            name=vehicle.dt_ul,
            parent_folder_id=vehicles_root["id"],
        )
        vehicle_folder = await drive_service.get_or_create_folder(
            dt_id=valkey_service.dt,
            name=vehicle.nom_synthetique,
            parent_folder_id=perimeter_folder["id"],
        )

        # Migrate: rename "Factures" → "Dossier Réparation" if needed
        await self._rename_legacy_factures_folder(valkey_service, vehicle_folder)

        document_folders: dict[VehicleDocumentType, dict[str, Any]] = {}

        if folder_names is not None:
            # Use dynamic folder names from config
            for name in folder_names:
                await drive_service.get_or_create_folder(
                    dt_id=valkey_service.dt,
                    name=name,
                    parent_folder_id=vehicle_folder["id"],
                )
            # Still create DOCUMENT_CONFIG folders for managed types tracking
            for document_type, config in DOCUMENT_CONFIG.items():
                document_folders[document_type] = await drive_service.get_or_create_folder(
                    dt_id=valkey_service.dt,
                    name=config["folder_name"],
                    parent_folder_id=vehicle_folder["id"],
                )
        else:
            for document_type, config in DOCUMENT_CONFIG.items():
                document_folders[document_type] = await drive_service.get_or_create_folder(
                    dt_id=valkey_service.dt,
                    name=config["folder_name"],
                    parent_folder_id=vehicle_folder["id"],
                )

        # Store folder URLs in vehicle.drive_folders and persist
        drive_folders: dict[str, Any] = {
            "vehicle_folder_id": vehicle_folder.get("id"),
            "vehicle_folder_url": vehicle_folder.get("webViewLink"),
        }
        for document_type, folder in document_folders.items():
            drive_folders[document_type.value] = {
                "folder_id": folder.get("id"),
                "folder_url": folder.get("webViewLink"),
            }
        vehicle.drive_folders = drive_folders
        await valkey_service.set_vehicle(vehicle)

        return {
            "vehicles_root": vehicles_root,
            "perimeter_folder": perimeter_folder,
            "vehicle_folder": vehicle_folder,
            "document_folders": document_folders,
        }

    async def sync_vehicle_folders(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
        root_folder_id: str,
        configured_folder_names: list[str],
        progress_callback: Callable[[int, int, VehicleData], Awaitable[None]] | None = None,
    ) -> dict:
        """Sync folders for a vehicle: create missing, delete empty removed ones."""
        # Get or create vehicle folder hierarchy
        vehicles_root = await drive_service.get_or_create_folder(
            dt_id=valkey_service.dt,
            name="Véhicules",
            parent_folder_id=root_folder_id,
        )
        perimeter_folder = await drive_service.get_or_create_folder(
            dt_id=valkey_service.dt,
            name=vehicle.dt_ul,
            parent_folder_id=vehicles_root["id"],
        )
        vehicle_folder = await drive_service.get_or_create_folder(
            dt_id=valkey_service.dt,
            name=vehicle.nom_synthetique,
            parent_folder_id=perimeter_folder["id"],
        )

        # Migrate: rename "Factures" → "Dossier Réparation" if needed
        await self._rename_legacy_factures_folder(valkey_service, vehicle_folder)

        # List existing subfolders
        existing_subfolders = await drive_service.list_subfolders(
            dt_id=valkey_service.dt,
            parent_folder_id=vehicle_folder["id"],
        )
        existing_by_name = {f["name"]: f for f in existing_subfolders}

        created = 0
        deleted = 0
        skipped = 0

        # Create missing folders
        for folder_name in configured_folder_names:
            if folder_name not in existing_by_name:
                await drive_service.create_folder(
                    dt_id=valkey_service.dt,
                    name=folder_name,
                    parent_folder_id=vehicle_folder["id"],
                )
                created += 1

        # Delete empty folders not in config
        configured_set = set(configured_folder_names)
        for folder_name, folder_data in existing_by_name.items():
            if folder_name not in configured_set:
                # Check if folder is empty
                contents = await drive_service.list_files(
                    dt_id=valkey_service.dt,
                    folder_id=folder_data["id"],
                )
                if len(contents) == 0:
                    await drive_service.delete_file(
                        dt_id=valkey_service.dt,
                        file_id=folder_data["id"],
                    )
                    deleted += 1
                else:
                    logger.warning(
                        f"Skipping non-empty folder '{folder_name}' in vehicle {vehicle.immat} "
                        f"(contains {len(contents)} items)"
                    )
                    skipped += 1

        return {"created": created, "deleted": deleted, "skipped": skipped}

    async def _get_document_folder(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
        document_type: VehicleDocumentType,
    ) -> dict[str, Any]:
        # Try cached folder data first
        drive_folders = getattr(vehicle, "drive_folders", {}) or {}
        cached = drive_folders.get(document_type.value)
        if cached and isinstance(cached, dict) and cached.get("folder_id"):
            return {
                "id": cached["folder_id"],
                "webViewLink": cached.get("folder_url"),
                "name": DOCUMENT_CONFIG[document_type]["folder_name"],
            }

        # Fallback: build tree if no cache (should be rare)
        root_config = await self._get_drive_root(valkey_service)
        if not root_config["folder_id"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Google Drive folder is not configured for this DT",
            )

        tree = await self._ensure_vehicle_tree(valkey_service, vehicle, root_config["folder_id"])
        return tree["document_folders"][document_type]

    async def _list_folder_files(self, valkey_service: ValkeyService, folder_id: str) -> list[dict[str, Any]]:
        files = await drive_service.list_files(dt_id=valkey_service.dt, folder_id=folder_id)
        return sorted(
            files,
            key=lambda file: file.get("modifiedTime") or file.get("createdTime") or "",
            reverse=True,
        )

    async def _persist_document_selection(
        self,
        valkey_service: ValkeyService,
        vehicle: VehicleData,
        document_type: VehicleDocumentType,
        stored_file: dict[str, Any],
    ) -> None:
        documents = dict(getattr(vehicle, "documents", {}) or {})
        documents[document_type.value] = stored_file
        vehicle.documents = documents

        saved = await valkey_service.set_vehicle(vehicle)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to persist vehicle document association",
            )

    def _build_empty_documents(self) -> dict[VehicleDocumentType, VehicleDriveDocument]:
        return {
            document_type: VehicleDriveDocument(
                key=document_type,
                label=config["label"],
                folder_name=config["folder_name"],
                managed=config["managed"],
                file_count=0,
                current_file=None,
            )
            for document_type, config in DOCUMENT_CONFIG.items()
        }

    def _build_stored_file(self, file_data: dict[str, Any], folder: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_id": file_data.get("id") or file_data.get("file_id"),
            "name": file_data.get("name"),
            "web_view_link": file_data.get("webViewLink") or file_data.get("web_view_link"),
            "mime_type": file_data.get("mimeType") or file_data.get("mime_type"),
            "created_time": file_data.get("createdTime") or file_data.get("created_time"),
            "modified_time": file_data.get("modifiedTime") or file_data.get("modified_time"),
            "selected_at": datetime.now(timezone.utc).isoformat(),
            "folder_id": folder.get("id"),
            "folder_name": folder.get("name"),
        }

    def _serialize_file(
        self,
        file_data: dict[str, Any],
        *,
        stored_file: dict[str, Any] | None = None,
        folder: dict[str, Any] | None = None,
    ) -> VehicleDriveFile:
        stored_file = stored_file or {}
        return VehicleDriveFile(
            file_id=file_data.get("id") or file_data.get("file_id"),
            name=file_data.get("name") or stored_file.get("name") or "Document",
            web_view_link=file_data.get("webViewLink") or file_data.get("web_view_link") or stored_file.get("web_view_link"),
            mime_type=file_data.get("mimeType") or file_data.get("mime_type") or stored_file.get("mime_type"),
            created_time=file_data.get("createdTime") or file_data.get("created_time") or stored_file.get("created_time"),
            modified_time=file_data.get("modifiedTime") or file_data.get("modified_time") or stored_file.get("modified_time"),
            selected_at=stored_file.get("selected_at"),
            folder_id=(folder or {}).get("id") or stored_file.get("folder_id"),
            folder_name=(folder or {}).get("name") or stored_file.get("folder_name"),
        )

    def _build_upload_filename(self, document_type: VehicleDocumentType, filename: str, nom_synthetique: str) -> str:
        extension = Path(filename).suffix
        label = DOCUMENT_CONFIG[document_type]["label"]
        return f"{nom_synthetique} - {label}{extension}"

    def _ensure_managed_document(self, document_type: VehicleDocumentType) -> None:
        if document_type not in MANAGED_DOCUMENT_TYPE_SET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This document type is not yet managed from the admin UI",
            )


vehicle_document_service = VehicleDocumentService()