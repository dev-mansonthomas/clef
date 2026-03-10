"""Real Google Drive service implementation using google-api-python-client."""
import os
import time
from typing import Any, Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

from app.services.drive import DriveService


class GoogleDriveService(DriveService):
    """Real Google Drive service using Google API client."""
    
    def __init__(self):
        """Initialize the Google Drive service with credentials."""
        self.credentials = self._get_credentials()
        self.service = build('drive', 'v3', credentials=self.credentials)
    
    def _get_credentials(self):
        """Get service account credentials from environment."""
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        
        scopes = [
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
        ]
        
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes
        )
    
    def _retry_with_backoff(self, func, max_retries=3):
        """Execute a function with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                return func()
            except HttpError as e:
                if e.resp.status in [429, 500, 503] and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 1
                    time.sleep(wait_time)
                else:
                    raise
    
    def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a folder in Google Drive."""
        def _execute_create():
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink, parents'
            ).execute()
            return folder
        
        return self._retry_with_backoff(_execute_create)
    
    def upload_file(
        self,
        file_name: str,
        file_content: bytes,
        mime_type: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a file to Google Drive."""
        def _execute_upload():
            file_metadata = {'name': file_name}
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            media = MediaInMemoryUpload(
                file_content,
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, webContentLink, size, mimeType, parents'
            ).execute()
            return file
        
        return self._retry_with_backoff(_execute_upload)
    
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID."""
        try:
            def _execute_get():
                return self.service.files().get(
                    fileId=file_id,
                    fields='id, name, webViewLink, webContentLink, size, mimeType, parents'
                ).execute()
            
            return self._retry_with_backoff(_execute_get)
        except HttpError as e:
            if e.resp.status == 404:
                return None
            raise
    
    def list_files(
        self,
        parent_id: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List files in a folder."""
        def _execute_list():
            q_parts = []
            if parent_id:
                q_parts.append(f"'{parent_id}' in parents")
            if query:
                q_parts.append(query)
            
            q = " and ".join(q_parts) if q_parts else None
            
            results = self.service.files().list(
                q=q,
                fields='files(id, name, webViewLink, mimeType, parents)',
                pageSize=100
            ).execute()
            
            return results.get('files', [])
        
        return self._retry_with_backoff(_execute_list)
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file."""
        try:
            def _execute_delete():
                self.service.files().delete(fileId=file_id).execute()
                return True

            return self._retry_with_backoff(_execute_delete)
        except HttpError as e:
            if e.resp.status == 404:
                return False
            raise

    def find_or_create_folder(
        self,
        folder_name: str,
        parent_id: str
    ) -> Dict[str, Any]:
        """Find a folder by name in parent, or create it if it doesn't exist."""
        # Search for existing folder
        query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        existing_folders = self.list_files(query=query)

        if existing_folders:
            return existing_folders[0]

        # Create if not found
        return self.create_folder(folder_name, parent_id)

