"""Real Google Sheets service implementation using google-api-python-client."""
import os
import time
from typing import Any, Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.sheets import SheetsService


class GoogleSheetsService(SheetsService):
    """Real Google Sheets service using Google API client."""
    
    def __init__(self):
        """Initialize the Google Sheets service with credentials."""
        self.credentials = self._get_credentials()
        self.service = build('sheets', 'v4', credentials=self.credentials)
        
        # Get spreadsheet IDs from environment
        self.vehicules_spreadsheet_id = os.getenv("VEHICULES_SPREADSHEET_ID")
        self.benevoles_spreadsheet_id = os.getenv("BENEVOLES_SPREADSHEET_ID")
        self.responsables_spreadsheet_id = os.getenv("RESPONSABLES_SPREADSHEET_ID")
    
    def _get_credentials(self):
        """Get Google service account credentials."""
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes
        )
    
    def _retry_with_backoff(self, func, *args, max_retries=5, **kwargs):
        """
        Execute a function with exponential backoff on 429 errors.
        
        Args:
            func: Function to execute
            max_retries: Maximum number of retries
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Function result
            
        Raises:
            HttpError: If max retries exceeded or non-429 error
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit error
                    if attempt < max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                        continue
                raise
    
    def _read_sheet(
        self,
        spreadsheet_id: str,
        range_name: str = "Sheet1!A:Z"
    ) -> List[Dict[str, Any]]:
        """
        Read data from a Google Sheet and convert to list of dictionaries.
        
        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: The range to read
            
        Returns:
            List of dictionaries with column headers as keys
        """
        def _execute_read():
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            return result.get('values', [])
        
        rows = self._retry_with_backoff(_execute_read)
        
        if not rows or len(rows) < 2:
            return []
        
        # First row is headers
        headers = rows[0]
        data = []
        
        for row in rows[1:]:
            # Pad row with empty strings if shorter than headers
            padded_row = row + [''] * (len(headers) - len(row))
            row_dict = {headers[i]: padded_row[i] for i in range(len(headers))}
            data.append(row_dict)
        
        return data
    
    def get_vehicles(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all vehicles from the referential."""
        sheet_id = spreadsheet_id or self.vehicules_spreadsheet_id
        if not sheet_id:
            raise ValueError("No vehicles spreadsheet ID provided")
        
        return self._read_sheet(sheet_id, "Sheet1!A:S")  # 19 columns (A-S)
    
    def get_benevoles(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all volunteers from the referential."""
        sheet_id = spreadsheet_id or self.benevoles_spreadsheet_id
        if not sheet_id:
            raise ValueError("No volunteers spreadsheet ID provided")
        
        return self._read_sheet(sheet_id)
    
    def get_responsables(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all managers from the referential."""
        sheet_id = spreadsheet_id or self.responsables_spreadsheet_id
        if not sheet_id:
            raise ValueError("No managers spreadsheet ID provided")

        return self._read_sheet(sheet_id)

    def append_carnet_bord(
        self,
        spreadsheet_id: str,
        values: List[List[Any]],
        range_name: str = "Sheet1!A1"
    ) -> Dict[str, Any]:
        """
        Append rows to a logbook (carnet de bord) spreadsheet.

        Args:
            spreadsheet_id: The spreadsheet ID to append to
            values: List of rows to append (each row is a list of values)
            range_name: The range to append to (default: "Sheet1!A1")

        Returns:
            Response with update information
        """
        def _execute_append():
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            return result

        return self._retry_with_backoff(_execute_append)

