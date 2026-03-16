"""Service for managing Carnet de Bord (vehicle logbook) operations."""
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.sheets import SheetsService
from app.cache.redis_cache import RedisCache


class CarnetBordService:
    """Service for managing vehicle logbook operations."""
    
    REDIS_PREFIX = "clef:carnet_bord:sheet_id"
    VERSION = 1  # Current version of the carnet de bord structure
    
    def __init__(self, sheets_service: SheetsService, cache: Optional[RedisCache] = None):
        """
        Initialize the carnet de bord service.
        
        Args:
            sheets_service: Google Sheets service instance
            cache: Optional Redis cache for storing sheet IDs
        """
        self.sheets_service = sheets_service
        self.cache = cache
        self._drive_service = None
        self._sheets_api_service = None
    
    def _get_credentials(self):
        """Get Google service account credentials."""
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file'
        ]
        
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes
        )
    
    def _get_drive_service(self):
        """Get or create Google Drive API service."""
        if self._drive_service is None:
            credentials = self._get_credentials()
            self._drive_service = build('drive', 'v3', credentials=credentials)
        return self._drive_service
    
    def _get_sheets_api_service(self):
        """Get or create Google Sheets API service."""
        if self._sheets_api_service is None:
            credentials = self._get_credentials()
            self._sheets_api_service = build('sheets', 'v4', credentials=credentials)
        return self._sheets_api_service
    
    def determine_perimetre(self, vehicule_data: Dict[str, Any]) -> str:
        """
        Determine the perimeter (UL, activité, DT) for a vehicle.
        
        Args:
            vehicule_data: Vehicle data dictionary
            
        Returns:
            Perimeter string (e.g., "UL Paris 15", "DT Paris", "Secours d'Urgence")
        """
        dt_ul = vehicule_data.get("dt_ul", "")
        
        # If it starts with "DT", it's a DT vehicle
        if dt_ul.startswith("DT"):
            return dt_ul
        
        # If it starts with "UL", it's a UL vehicle
        if dt_ul.startswith("UL"):
            return dt_ul
        
        # Otherwise, it's likely an activity (activité spécialisée)
        return dt_ul
    
    async def get_or_create_sheet_id(self, perimetre: str) -> str:
        """
        Get or create the Google Sheet ID for a given perimeter.
        
        Args:
            perimetre: The perimeter (UL, activité, DT)
            
        Returns:
            Google Sheet ID
        """
        # Try to get from cache first
        cache_key = f"{self.REDIS_PREFIX}:{perimetre}:v{self.VERSION}"
        
        if self.cache:
            cached_id = await self.cache.get(cache_key)
            if cached_id:
                return cached_id
        
        # Search for existing sheet
        sheet_id = self._find_existing_sheet(perimetre)
        
        if not sheet_id:
            # Create new sheet
            sheet_id = self._create_new_sheet(perimetre)
        
        # Cache the sheet ID (persistent, no TTL)
        if self.cache:
            await self.cache.set(cache_key, sheet_id, ttl=None)
        
        return sheet_id
    
    def _find_existing_sheet(self, perimetre: str) -> Optional[str]:
        """
        Search for an existing carnet de bord sheet for the perimeter.
        
        Args:
            perimetre: The perimeter to search for
            
        Returns:
            Sheet ID if found, None otherwise
        """
        try:
            drive_service = self._get_drive_service()
            sheet_name = f"CLEF - Carnet de Bord - {perimetre} - v{self.VERSION}"
            
            # Search for the file by name
            query = f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            if files:
                return files[0]['id']
            
            return None
        except HttpError:
            return None
    
    def _create_new_sheet(self, perimetre: str) -> str:
        """
        Create a new carnet de bord Google Sheet for the perimeter.

        Args:
            perimetre: The perimeter

        Returns:
            New sheet ID
        """
        sheets_service = self._get_sheets_api_service()
        sheet_name = f"CLEF - Carnet de Bord - {perimetre} - v{self.VERSION}"

        # Create spreadsheet with headers
        spreadsheet_body = {
            'properties': {
                'title': sheet_name
            },
            'sheets': [{
                'properties': {
                    'title': 'Carnet de Bord',
                    'gridProperties': {
                        'frozenRowCount': 1
                    }
                },
                'data': [{
                    'startRow': 0,
                    'startColumn': 0,
                    'rowData': [{
                        'values': [
                            {'userEnteredValue': {'stringValue': 'Type'}},
                            {'userEnteredValue': {'stringValue': 'Date/Heure'}},
                            {'userEnteredValue': {'stringValue': 'Véhicule'}},
                            {'userEnteredValue': {'stringValue': 'Bénévole Nom'}},
                            {'userEnteredValue': {'stringValue': 'Bénévole Prénom'}},
                            {'userEnteredValue': {'stringValue': 'Email'}},
                            {'userEnteredValue': {'stringValue': 'Kilométrage'}},
                            {'userEnteredValue': {'stringValue': 'Niveau Carburant'}},
                            {'userEnteredValue': {'stringValue': 'État Général'}},
                            {'userEnteredValue': {'stringValue': 'Observations'}},
                            {'userEnteredValue': {'stringValue': 'Problèmes Signalés'}}
                        ]
                    }]
                }]
            }]
        }

        try:
            spreadsheet = sheets_service.spreadsheets().create(
                body=spreadsheet_body
            ).execute()

            return spreadsheet['spreadsheetId']
        except HttpError as error:
            raise Exception(f"Failed to create carnet de bord sheet: {error}")

    async def append_prise(
        self,
        vehicule_data: Dict[str, Any],
        prise_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Append a prise (pickup) record to the appropriate sheet.

        Args:
            vehicule_data: Vehicle data dictionary
            prise_data: Prise form data

        Returns:
            Response with success status and sheet info
        """
        perimetre = self.determine_perimetre(vehicule_data)
        sheet_id = await self.get_or_create_sheet_id(perimetre)

        # Format the row data
        timestamp = prise_data.get('timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp_str = str(timestamp)

        row = [
            'Prise',
            timestamp_str,
            prise_data.get('vehicule_id', ''),
            prise_data.get('benevole_nom', ''),
            prise_data.get('benevole_prenom', ''),
            prise_data.get('benevole_email', ''),
            str(prise_data.get('kilometrage', '')),
            prise_data.get('niveau_carburant', ''),
            prise_data.get('etat_general', ''),
            prise_data.get('observations', ''),
            ''  # Problèmes signalés (empty for prise)
        ]

        # Append to sheet
        result = self.sheets_service.append_carnet_bord(
            spreadsheet_id=sheet_id,
            values=[row],
            range_name="Carnet de Bord!A1"
        )

        return {
            'success': True,
            'spreadsheet_id': sheet_id,
            'perimetre': perimetre,
            'updates': result.get('updates', {})
        }

    async def append_retour(
        self,
        vehicule_data: Dict[str, Any],
        retour_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Append a retour (return) record to the appropriate sheet.

        Args:
            vehicule_data: Vehicle data dictionary
            retour_data: Retour form data

        Returns:
            Response with success status and sheet info
        """
        perimetre = self.determine_perimetre(vehicule_data)
        sheet_id = await self.get_or_create_sheet_id(perimetre)

        # Format the row data
        timestamp = retour_data.get('timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp_str = str(timestamp)

        row = [
            'Retour',
            timestamp_str,
            retour_data.get('vehicule_id', ''),
            retour_data.get('benevole_nom', ''),
            retour_data.get('benevole_prenom', ''),
            retour_data.get('benevole_email', ''),
            str(retour_data.get('kilometrage', '')),
            retour_data.get('niveau_carburant', ''),
            retour_data.get('etat_general', ''),
            retour_data.get('observations', ''),
            retour_data.get('problemes_signales', '')
        ]

        # Append to sheet
        result = self.sheets_service.append_carnet_bord(
            spreadsheet_id=sheet_id,
            values=[row],
            range_name="Carnet de Bord!A1"
        )

        return {
            'success': True,
            'spreadsheet_id': sheet_id,
            'perimetre': perimetre,
            'updates': result.get('updates', {})
        }

    async def get_derniere_prise(self, vehicule_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the last prise (pickup) record for a vehicle.

        Args:
            vehicule_id: Vehicle synthetic name

        Returns:
            Last prise record or None if not found
        """
        # This is a simplified implementation
        # In a real scenario, we would need to search across all sheets
        # For now, return None (to be implemented when needed)
        return None


