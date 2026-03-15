"""Mock implementation of Google Sheets API service."""
from typing import Any, Dict, List, Optional

from app.services.sheets import SheetsService


class GoogleSheetsMock(SheetsService):
    """Mock Google Sheets service that returns hardcoded test data."""

    def __init__(self):
        """Initialize the mock service with hardcoded test data."""
        self._vehicules_data = self._get_test_vehicules()
        self._benevoles_data = self._get_test_benevoles()
        self._responsables_data = self._get_test_responsables()

    def _get_test_vehicules(self) -> List[Dict[str, Any]]:
        """Return hardcoded test vehicle data."""
        return [
            {
                "dt_ul": "UL Paris 15",
                "immat": "AB-123-CD",
                "indicatif": "PARIS-15-01",
                "operationnel_mecanique": "Dispo",
                "raison_indispo": "",
                "prochain_controle_technique": "2026-08-15",
                "prochain_controle_pollution": "2026-08-15",
                "marque": "RENAULT",
                "modele": "Master",
                "type": "VSAV",
                "date_mec": "2020-06-24",
                "nom_synthetique": "VSAV-PARIS15-01",
                "carte_grise": "OK",
                "nb_places": "5",
                "commentaires": "VSAV principal UL Paris 15",
                "lieu_stationnement": "Siège UL Paris 15",
                "instructions_recuperation": "Clés au bureau",
                "assurance_2026": "OK",
                "numero_serie_baus": ""
            },
            {
                "dt_ul": "UL Paris 15",
                "immat": "EF-456-GH",
                "indicatif": "PARIS-15-02",
                "operationnel_mecanique": "Dispo",
                "raison_indispo": "",
                "prochain_controle_technique": "2026-03-20",
                "prochain_controle_pollution": "2026-03-20",
                "marque": "RENAULT",
                "modele": "Kangoo",
                "type": "VL",
                "date_mec": "2019-03-15",
                "nom_synthetique": "VL-PARIS15-02",
                "carte_grise": "OK",
                "nb_places": "5",
                "commentaires": "VL de liaison",
                "lieu_stationnement": "UL Paris 15",
                "instructions_recuperation": "Contacter le responsable",
                "assurance_2026": "OK",
                "numero_serie_baus": ""
            },
            {
                "dt_ul": "UL Paris 16",
                "immat": "IJ-789-KL",
                "indicatif": "PARIS-16-01",
                "operationnel_mecanique": "Indispo",
                "raison_indispo": "Révision en cours",
                "prochain_controle_technique": "2025-08-10",
                "prochain_controle_pollution": "2025-08-10",
                "marque": "PEUGEOT",
                "modele": "Partner",
                "type": "VPSP",
                "date_mec": "2018-11-05",
                "nom_synthetique": "VPSP-PARIS16-01",
                "carte_grise": "OK",
                "nb_places": "3",
                "commentaires": "VPSP - En maintenance",
                "lieu_stationnement": "Garage UL Paris 16",
                "instructions_recuperation": "",
                "assurance_2026": "OK",
                "numero_serie_baus": "BAUS-12345"
            },
            {
                "dt_ul": "DT Paris",
                "immat": "MN-012-OP",
                "indicatif": "DT-PARIS-01",
                "operationnel_mecanique": "Dispo",
                "raison_indispo": "",
                "prochain_controle_technique": "2027-01-15",
                "prochain_controle_pollution": "2027-01-15",
                "marque": "CITROEN",
                "modele": "Jumper",
                "type": "VL",
                "date_mec": "2021-02-10",
                "nom_synthetique": "VL-DT-PARIS-01",
                "carte_grise": "OK",
                "nb_places": "7",
                "commentaires": "Véhicule DT",
                "lieu_stationnement": "Siège DT Paris",
                "instructions_recuperation": "Clés au secrétariat DT",
                "assurance_2026": "OK",
                "numero_serie_baus": ""
            }
        ]

    def _get_test_benevoles(self) -> List[Dict[str, Any]]:
        """Return hardcoded test volunteer data."""
        return [
            {
                "email": "jean.dupont@croix-rouge.fr",
                "nom": "Dupont",
                "prenom": "Jean",
                "ul": "UL Paris 15",
                "dt": "DT75",
                "statut": "Actif",
                "role": None  # Regular benevole
            },
            {
                "email": "marie.martin@croix-rouge.fr",
                "nom": "Martin",
                "prenom": "Marie",
                "ul": "UL Paris 15",
                "dt": "DT75",
                "statut": "Actif",
                "role": None  # Regular benevole
            },
            {
                "email": "pierre.bernard@croix-rouge.fr",
                "nom": "Bernard",
                "prenom": "Pierre",
                "ul": "UL Paris 16",
                "dt": "DT75",
                "statut": "Actif",
                "role": None  # Regular benevole
            },
            {
                "email": "sophie.dubois@croix-rouge.fr",
                "nom": "Dubois",
                "prenom": "Sophie",
                "ul": "UL Paris 16",
                "dt": "DT75",
                "statut": "Actif",
                "role": None  # Regular benevole
            },
            {
                "email": "thomas.manson@croix-rouge.fr",
                "nom": "Manson",
                "prenom": "Thomas",
                "ul": "DT Paris",
                "dt": "DT75",
                "role": "responsable_dt",  # DT manager
                "statut": "Actif"
            },
            {
                "email": "claire.rousseau@croix-rouge.fr",
                "nom": "Rousseau",
                "prenom": "Claire",
                "ul": "UL Paris 15",
                "dt": "DT75",
                "role": "responsable_ul",  # UL responsible
                "statut": "Actif"
            }
        ]

    def _get_test_responsables(self) -> List[Dict[str, Any]]:
        """Return hardcoded test manager data."""
        return [
            {
                "email": "thomas.manson@croix-rouge.fr",
                "nom": "Manson",
                "prenom": "Thomas",
                "role": "Gestionnaire DT",
                "perimetre": "DT Paris",
                "type_perimetre": "DT",
                "ul": "DT Paris",
                "dt": "DT75"
            },
            {
                "email": "claire.rousseau@croix-rouge.fr",
                "nom": "Rousseau",
                "prenom": "Claire",
                "role": "Responsable UL",
                "perimetre": "UL Paris 15",
                "type_perimetre": "UL",
                "ul": "UL Paris 15",
                "dt": "DT75"
            },
            {
                "email": "marc.durand@croix-rouge.fr",
                "nom": "Durand",
                "prenom": "Marc",
                "role": "Responsable UL",
                "perimetre": "UL Paris 16",
                "type_perimetre": "UL",
                "ul": "UL Paris 16",
                "dt": "DT75"
            },
            {
                "email": "sophie.bernard@croix-rouge.fr",
                "nom": "Bernard",
                "prenom": "Sophie",
                "role": "Responsable Activité",
                "perimetre": "Secours",
                "type_perimetre": "ACTIVITE",
                "ul": "",
                "dt": "DT75"
            }
        ]
    
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

