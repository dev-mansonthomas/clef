"""Google Sheets service module with abstract interface and implementations."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import os


class SheetsService(ABC):
    """Abstract base class for Google Sheets service."""
    
    @abstractmethod
    def get_vehicles(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all vehicles from the referential.
        
        Args:
            spreadsheet_id: Optional spreadsheet ID (uses env var if not provided)
            
        Returns:
            List of vehicle dictionaries with 19 columns
        """
        pass
    
    @abstractmethod
    def get_benevoles(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all volunteers from the referential.
        
        Args:
            spreadsheet_id: Optional spreadsheet ID (uses env var if not provided)
            
        Returns:
            List of volunteer dictionaries
        """
        pass
    
    @abstractmethod
    def get_responsables(self, spreadsheet_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all managers from the referential.
        
        Args:
            spreadsheet_id: Optional spreadsheet ID (uses env var if not provided)
            
        Returns:
            List of manager dictionaries
        """
        pass
    
    @abstractmethod
    def get_vehicule_by_nom_synthetique(
        self,
        nom_synthetique: str,
        spreadsheet_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific vehicle by its synthetic name.

        Args:
            nom_synthetique: The unique synthetic name of the vehicle
            spreadsheet_id: Optional spreadsheet ID (uses env var if not provided)

        Returns:
            Vehicle dictionary or None if not found
        """
        pass

    @abstractmethod
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
        pass


def get_sheets_service() -> SheetsService:
    """
    Factory function to get the appropriate Sheets service implementation.
    
    Returns:
        SheetsService implementation (mock or real based on USE_MOCKS env var)
    """
    use_mocks = os.getenv("USE_MOCKS", "false").lower() == "true"
    
    if use_mocks:
        from app.mocks.google_sheets_mock import GoogleSheetsMock
        return GoogleSheetsMock()
    else:
        from app.services.sheets_real import GoogleSheetsService
        return GoogleSheetsService()

