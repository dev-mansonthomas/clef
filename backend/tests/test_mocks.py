"""Tests for Google API mocks."""
import os
import pytest
from datetime import datetime, timedelta

# Set USE_MOCKS before importing services
os.environ["USE_MOCKS"] = "true"

from app.mocks.service_factory import (
    get_sheets_service,
    get_drive_service,
    get_calendar_service,
    get_gmail_service,
    use_mocks
)


class TestServiceFactory:
    """Test the service factory."""
    
    def test_use_mocks_enabled(self):
        """Test that USE_MOCKS environment variable is detected."""
        assert use_mocks() is True
    
    def test_get_sheets_service(self):
        """Test getting sheets service returns mock."""
        service = get_sheets_service()
        assert service is not None
        assert hasattr(service, "get_vehicules")
    
    def test_get_drive_service(self):
        """Test getting drive service returns mock."""
        service = get_drive_service()
        assert service is not None
        assert hasattr(service, "create_folder")
    
    def test_get_calendar_service(self):
        """Test getting calendar service returns mock."""
        service = get_calendar_service()
        assert service is not None
        assert hasattr(service, "create_calendar")
    
    def test_get_gmail_service(self):
        """Test getting gmail service returns mock."""
        service = get_gmail_service()
        assert service is not None
        assert hasattr(service, "send_email")


class TestGoogleSheetsMock:
    """Test Google Sheets mock service."""
    
    def test_get_vehicules(self):
        """Test getting vehicles from mock data."""
        service = get_sheets_service()
        vehicules = service.get_vehicules()
        
        assert len(vehicules) == 4
        assert vehicules[0]["immat"] == "AB-123-CD"
        assert vehicules[0]["nom_synthetique"] == "VSAV-PARIS15-01"
    
    def test_get_vehicule_by_nom_synthetique(self):
        """Test getting a specific vehicle by synthetic name."""
        service = get_sheets_service()
        vehicule = service.get_vehicule_by_nom_synthetique("VSAV-PARIS15-01")
        
        assert vehicule is not None
        assert vehicule["immat"] == "AB-123-CD"
        assert vehicule["indicatif"] == "PARIS-15-01"
    
    def test_get_vehicule_not_found(self):
        """Test getting a non-existent vehicle."""
        service = get_sheets_service()
        vehicule = service.get_vehicule_by_nom_synthetique("NON-EXISTENT")
        
        assert vehicule is None
    
    def test_get_benevoles(self):
        """Test getting volunteers from mock data."""
        service = get_sheets_service()
        benevoles = service.get_benevoles()
        
        assert len(benevoles) == 5
        assert benevoles[0]["email"] == "jean.dupont@croix-rouge.fr"
    
    def test_get_benevole_by_email(self):
        """Test getting a specific volunteer by email."""
        service = get_sheets_service()
        benevole = service.get_benevole_by_email("thomas.manson@croix-rouge.fr")
        
        assert benevole is not None
        assert benevole["nom"] == "Manson"
        assert benevole["role"] == "Gestionnaire DT"
    
    def test_get_responsables(self):
        """Test getting managers from mock data."""
        service = get_sheets_service()
        responsables = service.get_responsables()
        
        assert len(responsables) == 4
        assert responsables[0]["email"] == "thomas.manson@croix-rouge.fr"
    
    def test_append_row(self):
        """Test appending a row (mock operation)."""
        service = get_sheets_service()
        result = service.append_row(
            spreadsheet_id="mock-id",
            range_name="Sheet1!A1",
            values=[["value1", "value2", "value3"]]
        )
        
        assert result["updates"]["updatedRows"] == 1
        assert result["updates"]["updatedColumns"] == 3


class TestGoogleDriveMock:
    """Test Google Drive mock service."""
    
    def test_create_folder(self):
        """Test creating a folder."""
        service = get_drive_service()
        folder = service.create_folder("Test Folder")
        
        assert folder["name"] == "Test Folder"
        assert folder["mimeType"] == "application/vnd.google-apps.folder"
        assert "id" in folder
    
    def test_upload_file(self):
        """Test uploading a file."""
        service = get_drive_service()
        file_content = b"test content"
        file_metadata = service.upload_file(
            file_name="test.txt",
            file_content=file_content,
            mime_type="text/plain"
        )
        
        assert file_metadata["name"] == "test.txt"
        assert file_metadata["size"] == len(file_content)
        assert "id" in file_metadata
    
    def test_list_files(self):
        """Test listing files."""
        service = get_drive_service()
        files = service.list_files()
        
        assert len(files) >= 2  # At least the pre-populated mock folders


class TestGoogleCalendarMock:
    """Test Google Calendar mock service."""
    
    def test_create_calendar(self):
        """Test creating a calendar."""
        service = get_calendar_service()
        calendar = service.create_calendar(
            summary="Test Calendar",
            description="Test description"
        )
        
        assert calendar["summary"] == "Test Calendar"
        assert calendar["description"] == "Test description"
        assert "id" in calendar
    
    def test_create_event(self):
        """Test creating an event."""
        service = get_calendar_service()
        start = datetime.now()
        end = start + timedelta(hours=2)
        
        event = service.create_event(
            calendar_id="mock-calendar-dev",
            summary="Test Event",
            start=start,
            end=end,
            description="Test description"
        )
        
        assert event["summary"] == "Test Event"
        assert event["status"] == "confirmed"
        assert "id" in event


class TestGoogleGmailMock:
    """Test Gmail mock service."""
    
    def test_send_email(self):
        """Test sending an email."""
        service = get_gmail_service()
        service.clear_sent_messages()
        
        message = service.send_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        assert message["to"] == "test@example.com"
        assert message["subject"] == "Test Subject"
        assert message["body"] == "Test body"
        assert "id" in message
    
    def test_send_alert_email(self):
        """Test sending an alert email."""
        service = get_gmail_service()
        service.clear_sent_messages()
        
        message = service.send_alert_email(
            to="alert@example.com",
            vehicle_name="VSAV-PARIS15-01",
            alert_type="Contrôle Technique",
            expiry_date="2026-03-15"
        )
        
        assert message["to"] == "alert@example.com"
        assert "VSAV-PARIS15-01" in message["subject"]
        assert "Contrôle Technique" in message["body"]

