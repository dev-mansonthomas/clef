"""Mock implementation of Google Drive API service."""
from typing import Any, Dict, List, Optional
from datetime import datetime


class GoogleDriveMock:
    """Mock Google Drive service for file operations."""
    
    def __init__(self):
        """Initialize the mock service."""
        self._mock_files: Dict[str, Dict[str, Any]] = {
            "mock-folder-id-1": {
                "id": "mock-folder-id-1",
                "name": "VSAV-PARIS15-01",
                "mimeType": "application/vnd.google-apps.folder",
                "webViewLink": "https://drive.google.com/drive/folders/mock-folder-id-1"
            },
            "mock-folder-id-2": {
                "id": "mock-folder-id-2",
                "name": "VL-PARIS15-02",
                "mimeType": "application/vnd.google-apps.folder",
                "webViewLink": "https://drive.google.com/drive/folders/mock-folder-id-2"
            }
        }
    
    def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mock folder creation.
        
        Args:
            name: Name of the folder
            parent_id: Parent folder ID (optional)
            
        Returns:
            Mock folder metadata
        """
        folder_id = f"mock-folder-{datetime.now().timestamp()}"
        folder = {
            "id": folder_id,
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "webViewLink": f"https://drive.google.com/drive/folders/{folder_id}",
            "parents": [parent_id] if parent_id else []
        }
        self._mock_files[folder_id] = folder
        return folder
    
    def upload_file(
        self,
        file_name: str,
        file_content: bytes,
        mime_type: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mock file upload.
        
        Args:
            file_name: Name of the file
            file_content: File content as bytes
            mime_type: MIME type of the file
            parent_id: Parent folder ID (optional)
            
        Returns:
            Mock file metadata
        """
        file_id = f"mock-file-{datetime.now().timestamp()}"
        file_metadata = {
            "id": file_id,
            "name": file_name,
            "mimeType": mime_type,
            "size": len(file_content),
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "parents": [parent_id] if parent_id else []
        }
        self._mock_files[file_id] = file_metadata
        return file_metadata
    
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata by ID.
        
        Args:
            file_id: The file ID
            
        Returns:
            File metadata or None if not found
        """
        return self._mock_files.get(file_id)
    
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
        files = list(self._mock_files.values())
        
        if parent_id:
            files = [
                f for f in files 
                if parent_id in f.get("parents", [])
            ]
        
        if query:
            # Simple name-based filtering for mock
            files = [
                f for f in files
                if query.lower() in f.get("name", "").lower()
            ]
        
        return files
    
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file.

        Args:
            file_id: The file ID to delete

        Returns:
            True if deleted, False if not found
        """
        if file_id in self._mock_files:
            del self._mock_files[file_id]
            return True
        return False

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
        # Search for existing folder
        for file_data in self._mock_files.values():
            if (file_data.get("name") == folder_name and
                parent_id in file_data.get("parents", []) and
                file_data.get("mimeType") == "application/vnd.google-apps.folder"):
                return file_data

        # Create if not found
        return self.create_folder(folder_name, parent_id)

