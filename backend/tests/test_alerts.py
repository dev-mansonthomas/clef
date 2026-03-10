"""Tests for alert service."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Set USE_MOCKS before importing services
os.environ["USE_MOCKS"] = "true"

from app.services.alert_service import AlertService
from app.services.config_service import ConfigService
from app.mocks.google_gmail_mock import GoogleGmailMock
from app.mocks.google_sheets_mock import GoogleSheetsMock


class TestAlertService:
    """Test alert service functionality."""
    
    @pytest.fixture
    def mock_config_service(self):
        """Create a mock config service."""
        config_service = MagicMock(spec=ConfigService)
        config_service.get_config = AsyncMock(return_value={
            "email_destinataire_alertes": "test@example.com",
            "email_gestionnaire_dt": "dt@croix-rouge.fr"
        })
        return config_service
    
    @pytest.fixture
    def alert_service(self, mock_config_service):
        """Create an alert service instance."""
        return AlertService(mock_config_service)
    
    def test_parse_date_valid_formats(self, alert_service):
        """Test parsing dates in various formats."""
        # DD/MM/YYYY format
        date1 = alert_service._parse_date("15/03/2026")
        assert date1 == datetime(2026, 3, 15)
        
        # YYYY-MM-DD format
        date2 = alert_service._parse_date("2026-03-15")
        assert date2 == datetime(2026, 3, 15)
        
        # DD-MM-YYYY format
        date3 = alert_service._parse_date("15-03-2026")
        assert date3 == datetime(2026, 3, 15)
    
    def test_parse_date_invalid(self, alert_service):
        """Test parsing invalid dates."""
        assert alert_service._parse_date("") is None
        assert alert_service._parse_date("invalid") is None
        assert alert_service._parse_date("32/13/2026") is None
    
    def test_check_expiry_within_delay(self, alert_service):
        """Test checking expiry within alert delay."""
        # Date in 30 days (should trigger alert)
        future_date = datetime.now() + timedelta(days=30)
        assert alert_service._check_expiry(future_date) is True
        
        # Date in 90 days (should not trigger alert with default 60 days)
        far_future_date = datetime.now() + timedelta(days=90)
        assert alert_service._check_expiry(far_future_date) is False
        
        # Date in the past (should trigger alert)
        past_date = datetime.now() - timedelta(days=10)
        assert alert_service._check_expiry(past_date) is True
    
    def test_check_expiry_none(self, alert_service):
        """Test checking expiry with None date."""
        assert alert_service._check_expiry(None) is False
    
    @pytest.mark.asyncio
    async def test_check_and_send_alerts_no_config(self, mock_config_service):
        """Test alert check with no recipient email configured."""
        # Mock config with no recipient email
        mock_config_service.get_config = AsyncMock(return_value={
            "email_destinataire_alertes": "",
            "email_gestionnaire_dt": "dt@croix-rouge.fr"
        })
        
        alert_service = AlertService(mock_config_service)
        result = await alert_service.check_and_send_alerts()
        
        assert result["success"] is False
        assert "No recipient email" in result["error"]
        assert result["alerts_sent"] == 0
    
    @pytest.mark.asyncio
    async def test_check_and_send_alerts_with_expiring_vehicles(self, alert_service):
        """Test alert check with vehicles expiring soon."""
        # Mock sheets service to return vehicles with expiring dates
        with patch.object(alert_service.sheets_service, 'get_vehicles') as mock_get_vehicles:
            # Create test vehicles with expiring dates
            future_date = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
            
            mock_get_vehicles.return_value = [
                {
                    "Nom Synthétique": "VSAV-TEST-01",
                    "Immat": "AB-123-CD",
                    "Prochain Controle Technique": future_date,
                    "Prochain Controle Pollution": ""
                },
                {
                    "Nom Synthétique": "VSAV-TEST-02",
                    "Immat": "EF-456-GH",
                    "Prochain Controle Technique": "",
                    "Prochain Controle Pollution": future_date
                }
            ]
            
            # Clear sent messages
            alert_service.gmail_service.clear_sent_messages()
            
            # Run alert check
            result = await alert_service.check_and_send_alerts()
            
            # Verify results
            assert result["success"] is True
            assert result["alerts_sent"] == 1
            assert result["ct_alerts"] == 1
            assert result["pollution_alerts"] == 1
            assert result["total_vehicles_checked"] == 2
            
            # Verify email was sent
            sent_messages = alert_service.gmail_service.get_sent_messages()
            assert len(sent_messages) == 1
            assert "test@example.com" in sent_messages[0]["to"]
            assert "VSAV-TEST-01" in sent_messages[0]["body"]
            assert "VSAV-TEST-02" in sent_messages[0]["body"]
    
    @pytest.mark.asyncio
    async def test_check_and_send_alerts_no_expiring_vehicles(self, alert_service):
        """Test alert check with no expiring vehicles."""
        # Mock sheets service to return vehicles with valid dates
        with patch.object(alert_service.sheets_service, 'get_vehicles') as mock_get_vehicles:
            # Create test vehicles with dates far in the future
            future_date = (datetime.now() + timedelta(days=365)).strftime("%d/%m/%Y")
            
            mock_get_vehicles.return_value = [
                {
                    "Nom Synthétique": "VSAV-TEST-01",
                    "Immat": "AB-123-CD",
                    "Prochain Controle Technique": future_date,
                    "Prochain Controle Pollution": future_date
                }
            ]
            
            # Clear sent messages
            alert_service.gmail_service.clear_sent_messages()
            
            # Run alert check
            result = await alert_service.check_and_send_alerts()
            
            # Verify results
            assert result["success"] is True
            assert result["alerts_sent"] == 0
            assert result["ct_alerts"] == 0
            assert result["pollution_alerts"] == 0
            
            # Verify no email was sent
            sent_messages = alert_service.gmail_service.get_sent_messages()
            assert len(sent_messages) == 0

