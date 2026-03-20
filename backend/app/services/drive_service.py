"""
Service for Google Drive operations using DT manager's OAuth tokens.
"""
import asyncio
import io
import logging
from typing import Optional, Dict, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

from app.services.dt_token_service import dt_token_service
from app.auth.config import auth_settings

logger = logging.getLogger(__name__)


class DriveService:
    """Service for Google Drive operations using DT manager tokens."""
    
    def __init__(self):
        self.use_mocks = auth_settings.use_mocks

    @staticmethod
    def _shared_drive_kwargs(*, include_items: bool = False) -> dict[str, bool]:
        """Return Google Drive API flags required for shared drives."""
        kwargs = {"supportsAllDrives": True}
        if include_items:
            kwargs["includeItemsFromAllDrives"] = True
        return kwargs
    
    async def _get_service(self, dt_id: str):
        """Get authenticated Drive service using DT manager tokens."""
        if self.use_mocks:
            return None
        
        access_token = await dt_token_service.get_access_token(dt_id)
        if not access_token:
            raise ValueError(f"No valid tokens for DT {dt_id}")
        
        credentials = Credentials(token=access_token)
        return build("drive", "v3", credentials=credentials)
    
    async def upload_file(
        self,
        dt_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        parent_folder_id: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive.
        
        Args:
            dt_id: DT identifier
            file_content: File content as bytes
            filename: Name of the file
            mime_type: MIME type (e.g., "image/jpeg")
            parent_folder_id: ID of the parent folder
            description: Optional file description
            
        Returns:
            File resource with id, webViewLink, etc.
        """
        if self.use_mocks:
            return {
                "id": f"mock-file-{filename}",
                "name": filename,
                "webViewLink": f"https://drive.google.com/file/d/mock-{filename}/view",
                "webContentLink": f"https://drive.google.com/uc?id=mock-{filename}",
                "mimeType": mime_type,
            }
        
        service = await self._get_service(dt_id)
        
        file_metadata = {
            "name": filename,
            "description": description,
            "parents": [parent_folder_id],
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=mime_type,
            resumable=True,
        )
        
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,name,webViewLink,webContentLink,mimeType",
            **self._shared_drive_kwargs(),
        )
        file = await asyncio.to_thread(request.execute)
        
        logger.info(f"Uploaded file {file['id']} to folder {parent_folder_id}")
        return file
    
    async def create_folder(
        self,
        dt_id: str,
        name: str,
        parent_folder_id: str,
    ) -> Dict[str, Any]:
        """
        Create a folder in Google Drive.
        
        Returns:
            Folder resource with id, webViewLink, etc.
        """
        if self.use_mocks:
            return {
                "id": f"mock-folder-{name}",
                "name": name,
                "webViewLink": f"https://drive.google.com/drive/folders/mock-{name}",
                "mimeType": "application/vnd.google-apps.folder",
            }
        
        service = await self._get_service(dt_id)
        
        folder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }
        
        request = service.files().create(
            body=folder_metadata,
            fields="id,name,webViewLink,mimeType",
            **self._shared_drive_kwargs(),
        )
        folder = await asyncio.to_thread(request.execute)
        
        logger.info(f"Created folder {folder['id']} in {parent_folder_id}")
        return folder
    
    async def find_folder(
        self,
        dt_id: str,
        name: str,
        parent_folder_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a folder by name in a parent folder.
        
        Returns:
            Folder resource if found, None otherwise.
        """
        if self.use_mocks:
            return None
        
        service = await self._get_service(dt_id)

        query = (
            f"'{parent_folder_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"trashed=false"
        )

        request = service.files().list(
            q=query,
            fields="files(id,name,webViewLink)",
            **self._shared_drive_kwargs(include_items=True),
        )
        results = await asyncio.to_thread(request.execute)

        files = [file for file in results.get("files", []) if file.get("name") == name]
        return files[0] if files else None

    async def get_or_create_folder(
        self,
        dt_id: str,
        name: str,
        parent_folder_id: str,
    ) -> Dict[str, Any]:
        """
        Get existing folder or create if it doesn't exist.
        """
        existing = await self.find_folder(dt_id, name, parent_folder_id)
        if existing:
            return existing
        return await self.create_folder(dt_id, name, parent_folder_id)

    async def delete_file(
        self,
        dt_id: str,
        file_id: str,
    ) -> bool:
        """Delete a file from Google Drive."""
        if self.use_mocks:
            return True

        service = await self._get_service(dt_id)
        request = service.files().delete(
            fileId=file_id,
            **self._shared_drive_kwargs(),
        )
        await asyncio.to_thread(request.execute)
        logger.info(f"Deleted file {file_id}")
        return True

    async def rename_file(
        self,
        dt_id: str,
        file_id: str,
        new_name: str,
    ) -> Dict[str, Any]:
        """Rename a file in Google Drive."""
        if self.use_mocks:
            return {
                "id": file_id,
                "name": new_name,
            }

        service = await self._get_service(dt_id)
        request = service.files().update(
            fileId=file_id,
            body={"name": new_name},
            fields="id,name,webViewLink,mimeType",
            **self._shared_drive_kwargs(),
        )
        file = await asyncio.to_thread(request.execute)
        logger.info(f"Renamed file {file_id} to {new_name}")
        return file

    async def list_subfolders(self, dt_id: str, parent_folder_id: str) -> list:
        """List only subfolders (not files) in a folder."""
        if self.use_mocks:
            return []
        service = await self._get_service(dt_id)
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        request = service.files().list(
            q=query, pageSize=100,
            fields="files(id,name,webViewLink,mimeType)",
            **self._shared_drive_kwargs(include_items=True),
        )
        results = await asyncio.to_thread(request.execute)
        return results.get("files", [])

    async def list_files(
        self,
        dt_id: str,
        folder_id: str,
        max_results: int = 100,
    ) -> list:
        """List files in a folder."""
        if self.use_mocks:
            return [
                {"id": "mock-file-1", "name": "document-exemple-1.pdf", "webViewLink": "https://drive.google.com/file/d/mock-1/view", "mimeType": "application/pdf", "createdTime": "2026-01-15T10:00:00Z"},
                {"id": "mock-file-2", "name": "document-exemple-2.pdf", "webViewLink": "https://drive.google.com/file/d/mock-2/view", "mimeType": "application/pdf", "createdTime": "2026-02-20T14:30:00Z"},
            ]

        service = await self._get_service(dt_id)

        query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"

        request = service.files().list(
            q=query,
            pageSize=max_results,
            fields="files(id,name,webViewLink,mimeType,createdTime)",
            **self._shared_drive_kwargs(include_items=True),
        )
        results = await asyncio.to_thread(request.execute)

        return results.get("files", [])


# Global instance
drive_service = DriveService()

