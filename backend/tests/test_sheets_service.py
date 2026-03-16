"""Tests for Google Sheets service module."""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from googleapiclient.errors import HttpError

# Set USE_MOCKS before importing services
os.environ["USE_MOCKS"] = "true"

from app.services.sheets import get_sheets_service, SheetsService
from app.mocks.google_sheets_mock import GoogleSheetsMock


class TestSheetsServiceInterface:
    """Test the abstract SheetsService interface."""
    
    def test_get_sheets_service_returns_mock_when_use_mocks_true(self):
        """Test that factory returns mock when USE_MOCKS=true."""
        service = get_sheets_service()
        assert isinstance(service, GoogleSheetsMock)
        assert isinstance(service, SheetsService)
    
    def test_sheets_service_has_required_methods(self):
        """Test that service has all required methods."""
        service = get_sheets_service()
        assert hasattr(service, "get_vehicles")
        assert hasattr(service, "get_benevoles")
        assert hasattr(service, "get_responsables")
        assert hasattr(service, "append_carnet_bord")


class TestGoogleSheetsMock:
    """Test Google Sheets mock implementation."""
    
    def test_get_vehicles(self):
        """Test getting vehicles from mock data."""
        service = get_sheets_service()
        vehicles = service.get_vehicles()
        
        assert len(vehicles) == 4
        assert vehicles[0]["immat"] == "AB-123-CD"
        assert vehicles[0]["nom_synthetique"] == "VSAV-PARIS15-01"
        
        # Verify 19 columns are present
        expected_keys = [
            "dt_ul", "immat", "indicatif", "operationnel_mecanique",
            "raison_indispo", "prochain_controle_technique",
            "prochain_controle_pollution", "marque", "modele", "type",
            "date_mec", "nom_synthetique", "carte_grise", "nb_places",
            "commentaires", "lieu_stationnement", "instructions_recuperation",
            "assurance_2026", "numero_serie_baus"
        ]
        for key in expected_keys:
            assert key in vehicles[0]
    
    def test_get_vehicles_backward_compatibility(self):
        """Test that get_vehicules alias still works."""
        service = get_sheets_service()
        vehicles = service.get_vehicules()
        assert len(vehicles) == 4
    
    def test_get_benevoles(self):
        """Test getting volunteers from mock data."""
        service = get_sheets_service()
        benevoles = service.get_benevoles()
        
        assert len(benevoles) == 5
        assert benevoles[0]["email"] == "jean.dupont@croix-rouge.fr"
        assert benevoles[0]["ul"] == "UL Paris 15"
    
    def test_get_responsables(self):
        """Test getting managers from mock data."""
        service = get_sheets_service()
        responsables = service.get_responsables()
        
        assert len(responsables) == 4
        assert responsables[0]["email"] == "thomas.manson@croix-rouge.fr"
        assert responsables[0]["role"] == "Gestionnaire DT"
    
    def test_append_carnet_bord(self):
        """Test appending to carnet de bord."""
        service = get_sheets_service()
        result = service.append_carnet_bord(
            spreadsheet_id="mock-id",
            values=[
                ["2026-03-10", "VSAV-PARIS15-01", "Jean Dupont", "Prise", "100", "3/4"]
            ]
        )
        
        assert result["spreadsheetId"] == "mock-id"
        assert result["updates"]["updatedRows"] == 1
        assert result["updates"]["updatedColumns"] == 6
    
    def test_append_carnet_bord_multiple_rows(self):
        """Test appending multiple rows to carnet de bord."""
        service = get_sheets_service()
        result = service.append_carnet_bord(
            spreadsheet_id="mock-id",
            values=[
                ["2026-03-10", "VSAV-PARIS15-01", "Jean Dupont", "Prise", "100", "3/4"],
                ["2026-03-10", "VL-PARIS15-02", "Marie Martin", "Retour", "150", "1/2"]
            ]
        )
        
        assert result["updates"]["updatedRows"] == 2
    
    def test_append_row_backward_compatibility(self):
        """Test that append_row alias still works."""
        service = get_sheets_service()
        result = service.append_row(
            spreadsheet_id="mock-id",
            range_name="Sheet1!A1",
            values=[["value1", "value2"]]
        )
        
        assert result["updates"]["updatedRows"] == 1


class TestGoogleSheetsServiceReal:
    """Test real Google Sheets service implementation."""

    @patch('app.services.sheets_real.service_account')
    @patch('app.services.sheets_real.build')
    def test_initialization(self, mock_build, mock_service_account):
        """Test service initialization with credentials."""
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/creds.json"
        os.environ["USE_MOCKS"] = "false"

        from app.services.sheets_real import GoogleSheetsService

        mock_creds = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds

        service = GoogleSheetsService()

        mock_service_account.Credentials.from_service_account_file.assert_called_once()
        mock_build.assert_called_once_with('sheets', 'v4', credentials=mock_creds)

    @patch('app.services.sheets_real.service_account')
    @patch('app.services.sheets_real.build')
    def test_get_vehicles(self, mock_build, mock_service_account):
        """Test getting vehicles from real API."""
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/creds.json"
        os.environ["VEHICULES_SPREADSHEET_ID"] = "test-sheet-id"
        os.environ["USE_MOCKS"] = "false"

        from app.services.sheets_real import GoogleSheetsService

        # Mock the API response
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            'values': [
                ['dt_ul', 'immat', 'indicatif'],  # Headers
                ['UL Paris 15', 'AB-123-CD', 'PARIS-15-01']  # Data
            ]
        }
        mock_service.spreadsheets().values().get().execute.return_value = mock_response

        service = GoogleSheetsService()
        vehicles = service.get_vehicles()

        assert len(vehicles) == 1
        assert vehicles[0]['dt_ul'] == 'UL Paris 15'
        assert vehicles[0]['immat'] == 'AB-123-CD'

    @patch('app.services.sheets_real.service_account')
    @patch('app.services.sheets_real.build')
    @patch('app.services.sheets_real.time.sleep')
    def test_retry_with_backoff_on_429(self, mock_sleep, mock_build, mock_service_account):
        """Test exponential backoff on 429 rate limit errors."""
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/creds.json"
        os.environ["USE_MOCKS"] = "false"

        from app.services.sheets_real import GoogleSheetsService

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Create a mock 429 error
        mock_response = Mock()
        mock_response.status = 429
        error_429 = HttpError(resp=mock_response, content=b'Rate limit exceeded')

        # Fail twice with 429, then succeed
        mock_execute = mock_service.spreadsheets().values().get().execute
        mock_execute.side_effect = [
            error_429,
            error_429,
            {'values': [['header'], ['data']]}
        ]

        service = GoogleSheetsService()
        service.get_vehicles(spreadsheet_id="test-id")

        # Should have slept twice (1s, 2s)
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1  # First retry: 2^0 = 1s
        assert mock_sleep.call_args_list[1][0][0] == 2  # Second retry: 2^1 = 2s

    @patch('app.services.sheets_real.service_account')
    @patch('app.services.sheets_real.build')
    def test_append_carnet_bord(self, mock_build, mock_service_account):
        """Test appending to carnet de bord."""
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/creds.json"
        os.environ["USE_MOCKS"] = "false"

        from app.services.sheets_real import GoogleSheetsService

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            'spreadsheetId': 'test-id',
            'updates': {
                'updatedRange': 'Sheet1!A1',
                'updatedRows': 1,
                'updatedColumns': 6
            }
        }
        mock_service.spreadsheets().values().append().execute.return_value = mock_response

        service = GoogleSheetsService()
        result = service.append_carnet_bord(
            spreadsheet_id="test-id",
            values=[["2026-03-10", "VSAV-PARIS15-01", "Jean Dupont", "Prise", "100", "3/4"]]
        )

        assert result['spreadsheetId'] == 'test-id'
        assert result['updates']['updatedRows'] == 1

