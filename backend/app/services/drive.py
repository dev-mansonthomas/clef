"""Google Drive service module with abstract interface and implementations."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import os


class DriveService(ABC):
    """Abstract base class for Google Drive service."""
    
    @abstractmethod
    def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a folder in Google Drive.
        
        Args:
            name: Name of the folder
            parent_id: Parent folder ID (optional)
            
        Returns:
            Folder metadata with id, name, webViewLink
        """
        pass
    
    @abstractmethod
    def upload_file(
        self,
        file_name: str,
        file_content: bytes,
        mime_type: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_name: Name of the file
            file_content: File content as bytes
            mime_type: MIME type of the file
            parent_id: Parent folder ID (optional)
            
        Returns:
            File metadata with id, name, webViewLink, webContentLink
        """
        pass
    
    @abstractmethod
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata by ID.
        
        Args:
            file_id: The file ID
            
        Returns:
            File metadata or None if not found
        """
        pass
    
    @abstractmethod
    def list_files(
        self,
        parent_id: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List files in a folder.
        
        Args:
            parent_id: Parent folder ID to filter by
            query: Search query (optional)
            
        Returns:
            List of file metadata
        """
        pass
    
    @abstractmethod
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file.
        
        Args:
            file_id: The file ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    def find_or_create_folder(
        self,
        folder_name: str,
        parent_id: str
    ) -> Dict[str, Any]:
        """
        Find a folder by name in parent, or create it if it doesn't exist.
        
        Args:
            folder_name: Name of the folder to find or create
            parent_id: Parent folder ID
            
        Returns:
            Folder metadata
        """
        pass


def get_drive_service() -> DriveService:
    """
    Factory function to get the appropriate Drive service implementation.
    
    Returns:
        DriveService implementation (mock or real based on USE_MOCKS env var)
    """
    use_mocks = os.getenv("USE_MOCKS", "false").lower() == "true"
    
    if use_mocks:
        from app.mocks.google_drive_mock import GoogleDriveMock
        return GoogleDriveMock()
    else:
        from app.services.drive_real import GoogleDriveService
        return GoogleDriveService()

