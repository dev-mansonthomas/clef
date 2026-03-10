"""Mock implementation of Google Sheets API service."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.sheets import SheetsService


class GoogleSheetsMock(SheetsService):
    """Mock Google Sheets service that returns data from JSON files."""
    
    def __init__(self):
        """Initialize the mock service with data from JSON files."""
        self.data_dir = Path(__file__).parent / "data"
        self._vehicules_data = self._load_json("vehicules.json")
        self._benevoles_data = self._load_json("benevoles.json")
        self._responsables_data = self._load_json("responsables.json")
    
    def _load_json(self, filename: str) -> List[Dict[str, Any]]:
        """Load JSON data from file."""
        file_path = self.data_dir / filename
        if not file_path.exists():
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def get_vehicles(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all vehicles from the mock data.

        Args:
            spreadsheet_id: Ignored in mock, kept for interface compatibility

        Returns:
            List of vehicle dictionaries with 19 columns
        """
        return self._vehicules_data.copy()

    # Alias for backward compatibility
    def get_vehicules(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Alias for get_vehicles for backward compatibility."""
        return self.get_vehicles(spreadsheet_id)

    def get_benevoles(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all volunteers from the mock data.

        Args:
            spreadsheet_id: Ignored in mock, kept for interface compatibility

        Returns:
            List of volunteer dictionaries
        """
        return self._benevoles_data.copy()

    def get_responsables(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all managers from the mock data.

        Args:
            spreadsheet_id: Ignored in mock, kept for interface compatibility

        Returns:
            List of manager dictionaries
        """
        return self._responsables_data.copy()
    
    def get_vehicule_by_nom_synthetique(
        self,
        nom_synthetique: str,
        spreadsheet_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific vehicle by its synthetic name.

        Args:
            nom_synthetique: The unique synthetic name of the vehicle
            spreadsheet_id: Ignored in mock, kept for interface compatibility

        Returns:
            Vehicle dictionary or None if not found
        """
        for vehicule in self._vehicules_data:
            if vehicule.get("nom_synthetique") == nom_synthetique:
                return vehicule.copy()
        return None

    def get_vehicule_by_indicatif(
        self,
        indicatif: str,
        spreadsheet_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific vehicle by its radio code (indicatif).

        Args:
            indicatif: The radio code of the vehicle
            spreadsheet_id: Ignored in mock, kept for interface compatibility

        Returns:
            Vehicle dictionary or None if not found
        """
        for vehicule in self._vehicules_data:
            if vehicule.get("indicatif") == indicatif:
                return vehicule.copy()
        return None
    
    def get_benevole_by_email(
        self,
        email: str,
        spreadsheet_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific volunteer by email.
        
        Args:
            email: The email address of the volunteer
            spreadsheet_id: Ignored in mock, kept for interface compatibility
            
        Returns:
            Volunteer dictionary or None if not found
        """
        for benevole in self._benevoles_data:
            if benevole.get("email") == email:
                return benevole.copy()
        return None
    
    def append_carnet_bord(
        self,
        spreadsheet_id: str,
        values: List[List[Any]],
        range_name: str = "Sheet1!A1"
    ) -> Dict[str, Any]:
        """
        Mock append operation for carnet de bord - returns success without actually writing.

        Args:
            spreadsheet_id: The spreadsheet ID
            values: The values to append
            range_name: The range to append to

        Returns:
            Mock response indicating success
        """
        return {
            "spreadsheetId": spreadsheet_id,
            "updates": {
                "updatedRange": range_name,
                "updatedRows": len(values),
                "updatedColumns": len(values[0]) if values else 0,
                "updatedCells": len(values) * (len(values[0]) if values else 0)
            }
        }

    # Alias for backward compatibility
    def append_row(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]]
    ) -> Dict[str, Any]:
        """Alias for append_carnet_bord for backward compatibility."""
        return self.append_carnet_bord(spreadsheet_id, values, range_name)

